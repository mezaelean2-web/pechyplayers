try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

import database


class NoRenovoNubeTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.ruta_db = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.db_original = database.DB
        database.DB = self.ruta_db
        conn = sqlite3.connect(self.ruta_db)
        conn.executescript("""
            CREATE TABLE nube_cuentas(
                id INTEGER PRIMARY KEY, plataforma TEXT, correo TEXT,
                contrasena TEXT DEFAULT '', estado TEXT, modalidad TEXT
            );
            CREATE TABLE nube_perfiles(
                id INTEGER PRIMARY KEY, cuenta_id INTEGER, nombre_perfil TEXT,
                pin TEXT, cliente_id INTEGER, nombre_cliente TEXT, telefono TEXT,
                fecha_entrega TEXT, dias_cuenta INTEGER, fecha_vencimiento TEXT,
                estado TEXT, notas TEXT, garantia_usada INTEGER DEFAULT 0,
                cantidad_garantias INTEGER DEFAULT 0, orden INTEGER,
                fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE nube_transferencias_servicios(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operacion_uuid TEXT NOT NULL UNIQUE, tipo_operacion TEXT,
                perfil_origen_id INTEGER, cuenta_origen_id INTEGER,
                cliente_id INTEGER, dias_disponibles INTEGER,
                dias_trasladados INTEGER, destino_tipo TEXT,
                perfil_destino_id INTEGER, cuenta_destino_id INTEGER,
                motivo TEXT, venta_origen_snapshot TEXT NOT NULL,
                destino_antes_snapshot TEXT, destino_despues_snapshot TEXT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE nube_movimientos(
                id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER,
                tipo TEXT, descripcion TEXT, estado_anterior TEXT,
                estado_nuevo TEXT, cliente_nombre TEXT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE nube_reemplazos_perfiles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                perfil_anterior_id INTEGER, perfil_nuevo_id INTEGER,
                cuenta_anterior_id INTEGER, cuenta_nueva_id INTEGER,
                cliente_id INTEGER, nombre_cliente TEXT, telefono TEXT,
                motivo TEXT, dias_restantes INTEGER,
                fecha_vencimiento_anterior TEXT,
                fecha TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            INSERT INTO nube_cuentas(id, plataforma, correo, estado, modalidad)
            VALUES (1, 'Netflix', 'madre@test.com', 'disponible', 'perfiles')
        """)
        hoy = date.today()
        conn.execute("""
            INSERT INTO nube_perfiles(
                id, cuenta_id, nombre_perfil, pin, cliente_id, nombre_cliente,
                telefono, fecha_entrega, dias_cuenta, fecha_vencimiento,
                estado, notas, orden
            ) VALUES (1, 1, 'Perfil 1', '4321', NULL, 'Cliente anterior',
                      '3001234567', ?, 30, ?, 'activa', 'Nota del slot', 1)
        """, ((hoy - timedelta(days=30)).isoformat(), hoy.isoformat()))
        conn.execute("""
            INSERT INTO nube_perfiles(
                id, cuenta_id, nombre_perfil, pin, cliente_id, nombre_cliente,
                telefono, fecha_entrega, dias_cuenta, fecha_vencimiento,
                estado, notas, orden
            ) VALUES (2, 1, 'Perfil 2', '9876', NULL, 'Otro cliente',
                      '3110000000', ?, 30, ?, 'activa', 'Otra nota', 2)
        """, ((hoy - timedelta(days=10)).isoformat(),
              (hoy + timedelta(days=20)).isoformat()))
        conn.commit()
        conn.close()

    def tearDown(self):
        database.DB = self.db_original
        os.remove(self.ruta_db)

    def fila(self, consulta, parametros=()):
        conn = sqlite3.connect(self.ruta_db)
        conn.row_factory = sqlite3.Row
        resultado = conn.execute(consulta, parametros).fetchone()
        conn.close()
        return resultado

    def test_no_renovo_limpia_solo_estado_vivo_y_conserva_historial(self):
        resultado = database.registrar_no_renovacion_perfil_nube(1, "op-no-renovo-1")
        self.assertTrue(resultado["ok"])
        perfil = self.fila("SELECT * FROM nube_perfiles WHERE id=1")
        self.assertEqual(perfil["estado"], "disponible")
        self.assertIsNone(perfil["cliente_id"])
        for campo in ("nombre_cliente", "telefono", "fecha_entrega", "fecha_vencimiento"):
            self.assertEqual(perfil[campo], "")
        self.assertEqual(perfil["dias_cuenta"], 0)
        self.assertEqual(perfil["nombre_perfil"], "Perfil 1")
        self.assertEqual(perfil["pin"], "4321")
        self.assertEqual(perfil["notas"], "Nota del slot")
        self.assertEqual(self.fila("SELECT estado FROM nube_cuentas WHERE id=1")[0], "disponible")
        self.assertEqual(self.fila("SELECT nombre_cliente FROM nube_perfiles WHERE id=2")[0], "Otro cliente")
        transferencia = self.fila("SELECT * FROM nube_transferencias_servicios WHERE tipo_operacion='no_renovo'")
        snapshot = json.loads(transferencia["venta_origen_snapshot"])
        self.assertEqual(snapshot["nombre_cliente"], "Cliente anterior")
        self.assertEqual(snapshot["fecha_vencimiento"], date.today().isoformat())
        self.assertEqual(self.fila("SELECT cliente_nombre FROM nube_movimientos WHERE tipo='servicio_no_renovado'")[0], "Cliente anterior")
        historial = database.obtener_historial_completo_perfil_nube(1)
        self.assertTrue(any(e["tipo"] == "no_renovo" and e["titulo"] == "Servicio no renovado" for e in historial["eventos"]))

    def test_segunda_solicitud_es_idempotente(self):
        self.assertTrue(database.registrar_no_renovacion_perfil_nube(1, "op-1")["ok"])
        repetida = database.registrar_no_renovacion_perfil_nube(1, "op-2")
        self.assertTrue(repetida["ok"])
        self.assertTrue(repetida["duplicado"])
        self.assertEqual(self.fila("SELECT COUNT(*) FROM nube_transferencias_servicios WHERE tipo_operacion='no_renovo'")[0], 1)

    def test_disponible_y_reemplazado_no_crean_historial(self):
        conn = sqlite3.connect(self.ruta_db)
        conn.execute("UPDATE nube_perfiles SET estado='disponible', nombre_cliente='', fecha_entrega='', dias_cuenta=0, fecha_vencimiento='' WHERE id=1")
        conn.execute("UPDATE nube_perfiles SET estado='reemplazada' WHERE id=2")
        conn.commit(); conn.close()
        self.assertTrue(database.registrar_no_renovacion_perfil_nube(1, "disp")["duplicado"])
        self.assertFalse(database.registrar_no_renovacion_perfil_nube(2, "reemp")["ok"])
        self.assertEqual(self.fila("SELECT COUNT(*) FROM nube_transferencias_servicios")[0], 0)

    def test_error_de_auditoria_revierte_todo(self):
        conn = sqlite3.connect(self.ruta_db)
        conn.execute("""
            CREATE TRIGGER fallo_no_renovo BEFORE INSERT ON nube_movimientos
            WHEN NEW.tipo='servicio_no_renovado'
            BEGIN SELECT RAISE(ABORT, 'fallo'); END
        """)
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            database.registrar_no_renovacion_perfil_nube(1, "rollback")
        perfil = self.fila("SELECT estado, nombre_cliente FROM nube_perfiles WHERE id=1")
        self.assertEqual(tuple(perfil), ("activa", "Cliente anterior"))
        self.assertEqual(self.fila("SELECT COUNT(*) FROM nube_transferencias_servicios")[0], 0)


if __name__ == "__main__":
    unittest.main()
