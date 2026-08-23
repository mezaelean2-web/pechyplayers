try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import json
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import date, timedelta

import database
from app import app


class PapeleraNubeTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original = database.DB; database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
        CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY, plataforma TEXT, correo TEXT,
          cliente_id INTEGER, nombre_cliente TEXT DEFAULT '', telefono TEXT DEFAULT '', fecha_entrega TEXT DEFAULT '', dias_cuenta INTEGER DEFAULT 0,
          fecha_vencimiento TEXT DEFAULT '', estado TEXT, modalidad TEXT, tipo_pago TEXT DEFAULT '',
          valor_pin INTEGER DEFAULT 0, plan_pago TEXT DEFAULT '', precio_plan_referencia INTEGER DEFAULT 0,
          fecha_aplicacion_pin TEXT DEFAULT '', dias_estimados_pin INTEGER DEFAULT 0,
          fecha_proximo_pago TEXT DEFAULT '', fecha_archivada TEXT DEFAULT '', motivo_archivo TEXT DEFAULT '',
          fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY, cuenta_id INTEGER, nombre_perfil TEXT, pin TEXT,
          cliente_id INTEGER, nombre_cliente TEXT DEFAULT '', telefono TEXT DEFAULT '', fecha_entrega TEXT DEFAULT '',
          dias_cuenta INTEGER DEFAULT 0, fecha_vencimiento TEXT DEFAULT '', estado TEXT, garantia_usada INTEGER DEFAULT 0,
          cantidad_garantias INTEGER DEFAULT 0, notas TEXT DEFAULT '', orden INTEGER DEFAULT 1,
          fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER, tipo TEXT,
          descripcion TEXT, estado_anterior TEXT, estado_nuevo TEXT, cliente_nombre TEXT DEFAULT '',
          fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE nube_pagos_pin(id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER, valor_pin INTEGER,
          plan TEXT, precio_plan_referencia INTEGER, fecha_aplicacion TEXT, dias_estimados INTEGER,
          fecha_estimada_fin TEXT, notas TEXT, fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        conn.execute("INSERT INTO nube_cuentas(id,plataforma,correo,estado,modalidad,tipo_pago) VALUES(1,'Netflix','madre@test','caida','perfiles','pin')")
        for i in range(1, 6):
            entrega = (date.today() - timedelta(days=5)).isoformat()
            vence = (date.today() + timedelta(days=12)).isoformat()
            conn.execute("INSERT INTO nube_perfiles(id,cuenta_id,nombre_perfil,pin,cliente_id,nombre_cliente,telefono,fecha_entrega,dias_cuenta,fecha_vencimiento,estado,orden) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                         (i, 1, f"Perfil {i}", f"PIN-{i}", i if i <= 2 else None, f"Cliente {i}" if i <= 2 else "", "", entrega if i <= 2 else "", 30 if i <= 2 else 0, vence if i <= 2 else "", "caida" if i <= 2 else "disponible", i))
        conn.commit(); conn.close()

    def tearDown(self):
        database.DB = self.original; os.remove(self.path)

    def scalar(self, sql):
        conn = sqlite3.connect(self.path); value = conn.execute(sql).fetchone()[0]; conn.close(); return value

    def resolver(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_perfiles SET estado='reemplazada' WHERE cliente_id IS NOT NULL")
        conn.execute("INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion) VALUES(1,'reemplazo_perfil','historial previo')")
        conn.commit(); conn.close()

    def test_pendientes_rechazan_y_resueltos_habilitan_archivo(self):
        rechazado = database.mover_cuenta_papelera_nube(1)
        self.assertFalse(rechazado["ok"]); self.assertIn("2", rechazado["mensaje"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "caida")
        self.resolver()
        archivado = database.mover_cuenta_papelera_nube(1, "Garantías completas")
        self.assertTrue(archivado["ok"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "papelera")
        self.assertEqual(len(database.obtener_cuentas_papelera_nube()), 1)
        self.assertFalse(any(a["cuenta_id"] == 1 for a in database.obtener_alertas_operativas_nube()["alertas"]))
        self.assertTrue(database.mover_cuenta_papelera_nube(1)["duplicado"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='reemplazo_perfil'"), 1)

    def test_pin_desde_papelera_restaura_sin_revive_clientes(self):
        self.resolver(); database.mover_cuenta_papelera_nube(1)
        hoy = date.today().isoformat()
        pago = database.registrar_pago_pin_nube(1, 100000, "Plan 50", 50000, hoy)
        self.assertEqual(pago["proximo_pago"], (date.today() + timedelta(days=60)).isoformat())
        self.assertTrue(pago["cuenta_restaurada"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE cliente_id IS NOT NULL OR nombre_cliente != ''"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='disponible'"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='cuenta_restaurada_por_pago_pin'"), 1)

    def test_endpoint_pin_papelera_restaura_y_expone_contrato(self):
        self.resolver(); database.mover_cuenta_papelera_nube(1, "Ciclo cerrado")
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO nube_pagos_pin(cuenta_id,valor_pin,plan,precio_plan_referencia,fecha_aplicacion,dias_estimados,fecha_estimada_fin,notas) VALUES(1,50000,'Anterior',50000,'2026-06-01',30,'2026-07-01','historial')")
        conn.commit(); conn.close()
        cliente = app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["admin"] = True
        hoy = date.today().isoformat()
        respuesta = cliente.post("/admin/nube-cuentas/pagos-pin", json={
            "cuenta_id": 1, "valor_pin": 100000, "plan": "Plan nuevo",
            "precio_plan_referencia": 50000, "fecha_aplicacion": hoy
        })
        datos = respuesta.get_json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(datos["pago_registrado"])
        self.assertTrue(datos["cuenta_restaurada"])
        self.assertEqual(datos["estado"], "disponible")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 2)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(len(database.obtener_cuentas_papelera_nube()), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='disponible' AND cliente_id IS NULL AND nombre_cliente='' AND telefono='' AND fecha_entrega='' AND dias_cuenta=0 AND fecha_vencimiento=''"), 5)

    def test_reenvio_pago_existente_completa_restauracion_sin_duplicar(self):
        self.resolver(); database.mover_cuenta_papelera_nube(1)
        hoy = date.today().isoformat()
        proximo = (date.today() + timedelta(days=60)).isoformat()
        conn = sqlite3.connect(self.path)
        conn.execute("INSERT INTO nube_pagos_pin(cuenta_id,valor_pin,plan,precio_plan_referencia,fecha_aplicacion,dias_estimados,fecha_estimada_fin,notas) VALUES(1,100000,'Plan recuperado',50000,?,60,?,'intento previo')", (hoy, proximo))
        conn.commit(); conn.close()
        pago = database.registrar_pago_pin_nube(1, 100000, "Plan recuperado", 50000, hoy)
        self.assertTrue(pago["duplicado"])
        self.assertTrue(pago["cuenta_restaurada"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 1)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='cuenta_restaurada_por_pago_pin'"), 1)

    def test_pin_papelera_hace_rollback_completo_si_falla_restauracion(self):
        self.resolver(); database.mover_cuenta_papelera_nube(1)
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TRIGGER fallo_restauracion BEFORE INSERT ON nube_movimientos WHEN NEW.tipo='cuenta_restaurada_por_pago_pin' BEGIN SELECT RAISE(ABORT,'fallo'); END")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            database.registrar_pago_pin_nube(1, 100000, "Plan rollback", 50000, date.today().isoformat())
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 0)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "papelera")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='papelera'"), 5)

    def test_vencido_no_bloquea_snapshot_y_limpieza(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_perfiles SET estado='reemplazada' WHERE id=1")
        conn.execute("UPDATE nube_perfiles SET fecha_vencimiento=?, telefono='3001234567' WHERE id=2", ((date.today() - timedelta(days=1)).isoformat(),))
        conn.commit(); conn.close()
        archivado = database.mover_cuenta_papelera_nube(1)
        self.assertTrue(archivado["ok"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_archivos_asignaciones"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE cliente_id IS NOT NULL OR nombre_cliente!='' OR telefono!='' OR fecha_entrega!='' OR dias_cuenta!=0 OR fecha_vencimiento!=''"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='papelera'"), 5)

    def test_unico_vigente_bloquea_aunque_otros_resueltos_o_vencidos(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_perfiles SET estado='reemplazada' WHERE id=1")
        conn.execute("UPDATE nube_perfiles SET fecha_vencimiento=? WHERE id=2", ((date.today() + timedelta(days=12)).isoformat(),))
        conn.commit(); conn.close()
        resultado = database.mover_cuenta_papelera_nube(1)
        self.assertFalse(resultado["ok"])
        self.assertEqual(resultado["mensaje"], "Falta 1 servicio vigente por resolver.")

    def test_restauracion_manual_sin_pin_deja_slots_reutilizables(self):
        self.resolver()
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_cuentas SET tipo_pago='' WHERE id=1")
        conn.commit(); conn.close()
        self.assertTrue(database.mover_cuenta_papelera_nube(1)["ok"])
        restaurada = database.restaurar_cuenta_papelera_nube(1)
        self.assertTrue(restaurada["ok"])
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='disponible'"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_archivos_asignaciones"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='cuenta_restaurada'"), 1)

    def test_archivo_visible_en_db_funcion_endpoint_y_busqueda(self):
        self.resolver()
        correo = "madre@test"
        self.assertTrue(database.mover_cuenta_papelera_nube(1)["ok"])
        conn = sqlite3.connect(self.path)
        fila = conn.execute("SELECT id,correo,estado,fecha_archivada FROM nube_cuentas WHERE id=?", (1,)).fetchone()
        conn.close()
        self.assertEqual(fila[:3], (1, correo, "papelera"))
        self.assertTrue(fila[3])
        conn = sqlite3.connect(self.path)
        visible_nube = conn.execute("SELECT COUNT(*) FROM nube_cuentas WHERE id=? AND COALESCE(estado,'')!='papelera'", (1,)).fetchone()[0]
        conn.close()
        self.assertEqual(visible_nube, 0)
        self.assertFalse(any(a["cuenta_id"] == 1 for a in database.obtener_alertas_operativas_nube()["alertas"]))
        self.assertIn(1, [c["id"] for c in database.obtener_cuentas_papelera_nube()])
        cliente = app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["admin"] = True
        respuesta = cliente.get("/admin/nube-papelera/cuentas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no-store", respuesta.headers.get("Cache-Control", ""))
        cuentas = respuesta.get_json()["cuentas"]
        self.assertTrue(any(c["id"] == 1 and correo.lower() in c["correo"].lower() for c in cuentas))
        with open(os.path.join(os.path.dirname(__file__), "..", "static", "js", "admin", "nube_papelera.js"), encoding="utf-8") as archivo_js:
            js = archivo_js.read()
        self.assertIn('papeleraBuscar").value = ""', js)
        self.assertIn('papeleraPinVencido").checked = false', js)
        self.assertIn('cache: "no-store"', js)

    def test_endpoint_archivado_y_fechas_opcionales_renderizan_sin_excepcion(self):
        self.resolver()
        self.assertTrue(database.mover_cuenta_papelera_nube(1)["ok"])
        conn = sqlite3.connect(self.path)
        conn.execute("""UPDATE nube_cuentas SET fecha_proximo_pago=NULL,
                     fecha_aplicacion_pin='', fecha_vencimiento=NULL WHERE id=1""")
        conn.execute("UPDATE nube_movimientos SET fecha=NULL WHERE cuenta_id=1 AND tipo='reemplazo_perfil'")
        conn.commit(); conn.close()

        cliente = app.test_client()
        with cliente.session_transaction() as sesion:
            sesion["admin"] = True
        listado = cliente.get("/admin/nube-papelera/cuentas").get_json()["cuentas"]
        cuenta = next(item for item in listado if item["id"] == 1)
        detalle = cliente.get("/admin/nube-papelera/1").get_json()

        self.assertRegex(cuenta["fecha_archivada"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertIsNone(cuenta["fecha_proximo_pago"])
        self.assertEqual(detalle["cuenta"]["fecha_aplicacion_pin"], "")
        self.assertTrue(any(movimiento["fecha"] is None for movimiento in detalle["movimientos"]))

        valores = [
            cuenta["fecha_archivada"], cuenta["fecha_proximo_pago"],
            detalle["cuenta"]["fecha_aplicacion_pin"],
            *[movimiento["fecha"] for movimiento in detalle["movimientos"]],
            "—", "fecha-invalida", "2026-08-10T15:30:00-05:00"
        ]
        js_path = os.path.join(os.path.dirname(__file__), "..", "static", "js", "admin", "nube_papelera.js")
        programa = """
const helpers = require(process.argv[1]);
const valores = JSON.parse(process.argv[2]);
const salida = valores.map(helpers.formatearFechaSegura);
const sinFecha = salida.filter(valor => valor === 'Sin fecha').length;
const cuenta = {tipo_pago: 'pin', fecha_proximo_pago: null};
process.stdout.write(JSON.stringify({salida, sinFecha, pinVencido: helpers.esPinVencido(cuenta)}));
"""
        proceso = subprocess.run(
            ["node", "-e", programa, js_path, json.dumps(valores)],
            check=True, capture_output=True, text=True
        )
        resultado = json.loads(proceso.stdout)
        self.assertNotEqual(resultado["salida"][0], "Sin fecha")
        self.assertGreaterEqual(resultado["sinFecha"], 4)
        self.assertFalse(resultado["pinVencido"])

    def test_pin_reactiva_caida_y_libera_slots_sin_borrar_historial(self):
        self.resolver()
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_perfiles SET telefono='3001234567', estado='reemplazada' WHERE id=1")
        conn.execute("UPDATE nube_perfiles SET estado='caida' WHERE id=2")
        conn.execute("INSERT INTO nube_pagos_pin(cuenta_id,valor_pin,plan,precio_plan_referencia,fecha_aplicacion,dias_estimados,fecha_estimada_fin,notas) VALUES(1,50000,'Anterior',50000,'2026-06-01',30,'2026-07-01','historial')")
        conn.commit(); conn.close()
        pago = database.registrar_pago_pin_nube(
            1, 100000, "Plan nuevo", 50000, date.today().isoformat()
        )
        self.assertTrue(pago["cuenta_reactivada"])
        self.assertEqual(pago["perfiles_liberados"], 5)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "disponible")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='disponible'"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE cliente_id IS NOT NULL OR nombre_cliente!='' OR telefono!='' OR fecha_entrega!='' OR dias_cuenta!=0 OR fecha_vencimiento!=''"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE nombre_perfil LIKE 'Perfil %'"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE pin LIKE 'PIN-%'"), 5)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='reemplazo_perfil'"), 1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos WHERE tipo='cuenta_reactivada_por_pago_pin'"), 1)
        self.assertFalse(any(a["cuenta_id"] == 1 for a in database.obtener_alertas_operativas_nube()["alertas"]))

    def test_pin_normal_no_libera_perfiles(self):
        conn = sqlite3.connect(self.path)
        conn.execute("UPDATE nube_cuentas SET estado='disponible' WHERE id=1")
        conn.commit(); conn.close()
        pago = database.registrar_pago_pin_nube(
            1, 100000, "Plan normal", 50000, date.today().isoformat()
        )
        self.assertFalse(pago["cuenta_reactivada"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE cliente_id IS NOT NULL"), 2)

    def test_pin_reactivacion_hace_rollback_completo(self):
        conn = sqlite3.connect(self.path)
        conn.execute("CREATE TRIGGER fallo_reactivacion BEFORE INSERT ON nube_movimientos WHEN NEW.tipo='cuenta_reactivada_por_pago_pin' BEGIN SELECT RAISE(ABORT,'fallo'); END")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            database.registrar_pago_pin_nube(
                1, 100000, "Plan rollback", 50000, date.today().isoformat()
            )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_pagos_pin"), 0)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "caida")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE cliente_id IS NOT NULL"), 2)

    def test_rollback_si_falla_auditoria(self):
        self.resolver(); conn = sqlite3.connect(self.path)
        conn.execute("CREATE TRIGGER fallo BEFORE INSERT ON nube_movimientos WHEN NEW.tipo='cuenta_movida_papelera' BEGIN SELECT RAISE(ABORT,'fallo'); END")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError): database.mover_cuenta_papelera_nube(1)
        self.assertEqual(self.scalar("SELECT estado FROM nube_cuentas WHERE id=1"), "caida")


if __name__ == "__main__": unittest.main()
