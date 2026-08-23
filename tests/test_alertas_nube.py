try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

import database
from app import app


class AlertasNubeTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.ruta_db = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.db_original = database.DB
        database.DB = self.ruta_db
        self._crear_esquema()

    def tearDown(self):
        database.DB = self.db_original
        os.remove(self.ruta_db)

    def _crear_esquema(self):
        conn = sqlite3.connect(self.ruta_db)
        conn.executescript("""
            CREATE TABLE nube_cuentas (
                id INTEGER PRIMARY KEY, plataforma TEXT, nombre_cliente TEXT,
                fecha_entrega TEXT, dias_cuenta INTEGER, fecha_vencimiento TEXT,
                estado TEXT, modalidad TEXT, tipo_pago TEXT,
                fecha_proximo_pago TEXT
            );
            CREATE TABLE nube_perfiles (
                id INTEGER PRIMARY KEY, cuenta_id INTEGER, nombre_perfil TEXT,
                cliente_id INTEGER, nombre_cliente TEXT, fecha_entrega TEXT,
                dias_cuenta INTEGER, fecha_vencimiento TEXT, estado TEXT
            );
        """)
        conn.close()

    @staticmethod
    def _fecha(dias):
        return (datetime.now().date() + timedelta(days=dias)).isoformat()

    def _cuenta(self, cuenta_id, estado="disponible", modalidad="perfiles",
                dias_vencimiento=None, tipo_pago="", dias_pago=None,
                cliente=""):
        fecha = self._fecha(dias_vencimiento) if dias_vencimiento is not None else ""
        entrega = self._fecha(-30) if cliente else ""
        conn = sqlite3.connect(self.ruta_db)
        conn.execute(
            "INSERT INTO nube_cuentas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cuenta_id, "Netflix", cliente, entrega, 30 if cliente else 0,
             fecha, estado, modalidad, tipo_pago,
             self._fecha(dias_pago) if dias_pago is not None else "")
        )
        conn.commit()
        conn.close()

    def _perfil(self, perfil_id, cuenta_id, dias, estado="activa", cliente="Cliente"):
        conn = sqlite3.connect(self.ruta_db)
        conn.execute(
            "INSERT INTO nube_perfiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (perfil_id, cuenta_id, f"Perfil {perfil_id}", perfil_id, cliente,
             self._fecha(-30), 30, self._fecha(dias), estado)
        )
        conn.commit()
        conn.close()

    def test_franjas_perfiles_y_disponible_sin_alerta(self):
        self._cuenta(1)
        for perfil_id, dias in enumerate((3, 1, 0, -1), 1):
            self._perfil(perfil_id, 1, dias)
        self._perfil(5, 1, -20, estado="disponible", cliente="")

        tipos = [a["tipo"] for a in database.obtener_alertas_operativas_nube()["alertas"]]
        self.assertEqual(tipos.count("perfil_por_vencer"), 2)
        self.assertEqual(tipos.count("perfil_vence_hoy"), 1)
        self.assertEqual(tipos.count("perfil_vencido"), 1)
        self.assertEqual(len(tipos), 4)

    def test_cuenta_caida_suprime_spam_de_perfiles(self):
        self._cuenta(1, estado="caida")
        self._perfil(1, 1, 0, estado="caida")
        self._perfil(2, 1, -1, estado="caida")

        alertas = database.obtener_alertas_operativas_nube()["alertas"]
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["tipo"], "cuenta_caida")
        self.assertEqual(alertas[0]["perfiles_afectados"], 2)

    def test_cuenta_completa_pin_fechas_vacias_e_historicos(self):
        self._cuenta(1, modalidad="cuenta_completa", dias_vencimiento=0,
                     tipo_pago="pin", dias_pago=1, cliente="Cliente cuenta")
        self._cuenta(2, modalidad="cuenta_completa")
        self._cuenta(3, estado="papelera", modalidad="cuenta_completa",
                     dias_vencimiento=-1, tipo_pago="pin", dias_pago=-1,
                     cliente="Histórico")
        self._cuenta(4)
        self._perfil(4, 4, -1, estado="reemplazada")

        tipos = {a["tipo"] for a in database.obtener_alertas_operativas_nube()["alertas"]}
        self.assertEqual(tipos, {"cuenta_vence_hoy", "pago_pin_proximo"})

    def test_pin_hoy_y_pendiente(self):
        self._cuenta(1, tipo_pago="pin", dias_pago=0)
        self._cuenta(2, tipo_pago="pin", dias_pago=-1)
        self._cuenta(3, tipo_pago="pin", dias_pago=3)
        resultado = database.obtener_alertas_operativas_nube()
        tipos = {a["tipo"] for a in resultado["alertas"]}
        self.assertEqual(tipos, {
            "pago_pin_vence_hoy", "pago_pin_pendiente", "pago_pin_proximo"
        })
        self.assertEqual(resultado["resumen"]["hoy"], 1)
        self.assertEqual(resultado["resumen"]["criticas"], 1)
        self.assertEqual(resultado["resumen"]["proximas"], 1)

    def test_endpoint_requiere_admin(self):
        cliente = app.test_client()
        self.assertEqual(cliente.get("/admin/nube-cuentas/alertas").status_code, 401)
        with cliente.session_transaction() as sesion:
            sesion["admin"] = True
        respuesta = cliente.get("/admin/nube-cuentas/alertas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.get_json()["ok"])
        pagina = cliente.get("/admin/nube-alertas")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn(b"alertasCentro", pagina.data)

    def _preparar_historial_pin(self):
        conn = sqlite3.connect(self.ruta_db)
        for definicion in (
            "valor_pin INTEGER DEFAULT 0", "plan_pago TEXT DEFAULT ''",
            "precio_plan_referencia INTEGER DEFAULT 0",
            "fecha_aplicacion_pin TEXT DEFAULT ''",
            "dias_estimados_pin INTEGER DEFAULT 0"
        ):
            conn.execute(f"ALTER TABLE nube_cuentas ADD COLUMN {definicion}")
        conn.execute("""
            CREATE TABLE nube_pagos_pin (
                id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER NOT NULL,
                valor_pin INTEGER NOT NULL DEFAULT 0, plan TEXT DEFAULT '',
                precio_plan_referencia INTEGER DEFAULT 0,
                fecha_aplicacion TEXT NOT NULL, dias_estimados INTEGER DEFAULT 0,
                fecha_estimada_fin TEXT DEFAULT '', notas TEXT DEFAULT '',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def test_pago_pin_preserva_historial_calcula_y_resuelve_alerta(self):
        self._cuenta(1, tipo_pago="pin", dias_pago=-1)
        self._preparar_historial_pin()
        conn = sqlite3.connect(self.ruta_db)
        conn.execute("""
            INSERT INTO nube_pagos_pin
            (cuenta_id, valor_pin, plan, precio_plan_referencia,
             fecha_aplicacion, dias_estimados, fecha_estimada_fin)
            VALUES (1, 50000, 'Anterior', 50000, ?, 30, ?)
        """, (self._fecha(-31), self._fecha(-1)))
        conn.commit()
        conn.close()

        pago = database.registrar_pago_pin_nube(
            1, 100000, "Plan nuevo", 50000, self._fecha(0)
        )
        self.assertEqual(pago["dias_estimados"], 60)
        self.assertEqual(pago["proximo_pago"], self._fecha(60))
        conn = sqlite3.connect(self.ruta_db)
        cantidad = conn.execute(
            "SELECT COUNT(*) FROM nube_pagos_pin WHERE cuenta_id = 1"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(cantidad, 2)
        self.assertFalse(any(
            alerta["tipo"].startswith("pago_pin_")
            for alerta in database.obtener_alertas_operativas_nube()["alertas"]
        ))

        repetido = database.registrar_pago_pin_nube(
            1, 100000, "Plan nuevo", 50000, self._fecha(0)
        )
        self.assertTrue(repetido["duplicado"])
        conn = sqlite3.connect(self.ruta_db)
        cantidad = conn.execute("SELECT COUNT(*) FROM nube_pagos_pin").fetchone()[0]
        conn.close()
        self.assertEqual(cantidad, 2)

    def test_pago_pin_invalido_no_modifica_cuenta(self):
        self._cuenta(1, tipo_pago="autopagable", dias_pago=-1)
        self._preparar_historial_pin()
        with self.assertRaises(ValueError):
            database.registrar_pago_pin_nube(1, 50000, "Plan", 50000, self._fecha(0))
        conn = sqlite3.connect(self.ruta_db)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM nube_pagos_pin").fetchone()[0], 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
