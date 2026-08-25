try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest

import database
import resellers
from app import app


class NubeAdminEdicionEliminacionTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.original_db = database.DB; database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,imagen TEXT,plan TEXT,
            precio TEXT,estado TEXT DEFAULT 'disponible',visible INTEGER DEFAULT 1)""")
        conn.commit(); conn.close()
        database.inicializar_db(); resellers.inicializar_revendedores()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["admin"] = True; session["csrf_admin"] = "csrf-nube"

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def cuenta(self, modalidad="cuenta_completa", duracion=30, cantidad=0, **extras):
        return database.crear_cuenta_nube(
            plataforma=extras.pop("plataforma", "YouTube Premium"),
            correo=extras.pop("correo", f"cuenta-{os.urandom(3).hex()}@test.com"),
            contrasena="clave-segura", tipo_cuenta="perfil" if modalidad == "perfiles" else "cuenta_completa",
            modalidad=modalidad, cantidad_perfiles=cantidad,
            duracion_unidad_dias=duracion, **extras)

    def payload(self, **cambios):
        datos = {"plataforma":"YouTube Premium", "correo":"editada@test.com",
                 "contrasena":"nueva-clave", "pin":"1234", "modalidad":"cuenta_completa",
                 "duracion_unidad_dias":30, "cantidad_perfiles":0}
        datos.update(cambios); return datos

    def test_editar_cuenta_completa_y_duraciones_30_90(self):
        cuenta = self.cuenta()
        resultado = database.actualizar_cuenta_nube_admin(cuenta, self.payload(duracion_unidad_dias=90))
        self.assertTrue(resultado["ok"])
        conn = database.conectar(); fila = conn.execute(
            "SELECT correo,contrasena,pin,duracion_unidad_dias FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone(); conn.close()
        self.assertEqual(tuple(fila), ("editada@test.com", "nueva-clave", "1234", 90))

    def test_corregir_perfiles_a_cuenta_completa(self):
        cuenta = self.cuenta("perfiles", 90, 5)
        previo = database.actualizar_cuenta_nube_admin(cuenta, self.payload(duracion_unidad_dias=90))
        self.assertEqual(previo["codigo"], "confirmacion_requerida")
        resultado = database.actualizar_cuenta_nube_admin(cuenta, self.payload(duracion_unidad_dias=90), True)
        self.assertTrue(resultado["ok"])
        conn = database.conectar()
        self.assertEqual(tuple(conn.execute("SELECT modalidad,cantidad_perfiles FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone()), ("cuenta_completa", 0))
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 0); conn.close()

    def test_corregir_cuenta_completa_a_perfiles(self):
        cuenta = self.cuenta()
        datos = self.payload(modalidad="perfiles", cantidad_perfiles=3, duracion_unidad_dias=90)
        resultado = database.actualizar_cuenta_nube_admin(cuenta, datos, True)
        self.assertTrue(resultado["ok"])
        conn = database.conectar()
        self.assertEqual(tuple(conn.execute("SELECT modalidad,cantidad_perfiles,duracion_unidad_dias FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone()), ("perfiles", 3, 90))
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 3); conn.close()

    def test_cambiar_cantidad_perfiles_requiere_confirmacion(self):
        cuenta = self.cuenta("perfiles", 90, 2)
        datos = self.payload(modalidad="perfiles", cantidad_perfiles=4, duracion_unidad_dias=90)
        self.assertEqual(database.actualizar_cuenta_nube_admin(cuenta, datos)["codigo"], "confirmacion_requerida")
        self.assertTrue(database.actualizar_cuenta_nube_admin(cuenta, datos, True)["ok"])
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 4); conn.close()

    def test_historial_comercial_bloquea_estructura_pero_no_credenciales(self):
        cuenta = self.cuenta()
        conn = database.conectar(); conn.execute(
            "INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion) VALUES (?,'venta','Venta real')", (cuenta,)); conn.commit(); conn.close()
        bloqueada = database.actualizar_cuenta_nube_admin(cuenta, self.payload(duracion_unidad_dias=90))
        self.assertEqual(bloqueada["codigo"], "historial_comercial")
        credenciales = database.actualizar_cuenta_nube_admin(cuenta, self.payload())
        self.assertTrue(credenciales["ok"])

    def test_eliminar_cuenta_nueva_sin_relaciones_y_sin_huerfanos(self):
        cuenta = self.cuenta("perfiles", 90, 2)
        self.assertEqual(database.eliminar_cuenta_nube_descartable(cuenta)["codigo"], "confirmacion_requerida")
        self.assertTrue(database.eliminar_cuenta_nube_descartable(cuenta, True)["ok"])
        conn = database.conectar()
        self.assertIsNone(conn.execute("SELECT 1 FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone())
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_movimientos WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 0)
        self.assertIsNone(conn.execute("PRAGMA foreign_key_check").fetchone()); conn.close()

    def test_rechazar_eliminacion_asignada(self):
        cuenta = self.cuenta(nombre_cliente="Cliente", fecha_entrega="2026-08-24", dias_cuenta=30)
        resultado = database.eliminar_cuenta_nube_descartable(cuenta, True)
        self.assertEqual(resultado["codigo"], "eliminacion_bloqueada")

    def test_rechazar_eliminacion_con_compra_reseller(self):
        cuenta = self.cuenta()
        revendedor = resellers.crear_revendedor("Prueba", "reseller@test.com", "", "Negocio", "clave123456")
        conn = database.conectar()
        plan = conn.execute("INSERT INTO productos(nombre,imagen,plan,precio) VALUES ('YouTube','x','1 mes','1')").lastrowid
        conn.execute("""INSERT INTO reseller_purchases
            (revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,fecha_compra,
             dias_contratados,precio_pagado,estado_persistido)
            VALUES (?,?,?,NULL,'cuenta','purchase','2026-08-24',30,1,'active')""", (revendedor, plan, cuenta))
        conn.commit(); conn.close()
        resultado = database.eliminar_cuenta_nube_descartable(cuenta, True)
        self.assertEqual(resultado["codigo"], "eliminacion_bloqueada")
        self.assertIn("compras reseller", resultado["razones"])

    def test_eliminacion_fail_closed_ante_referencia_no_reconocida(self):
        cuenta = self.cuenta()
        conn = database.conectar()
        conn.execute("CREATE TABLE integracion_desconocida(id INTEGER PRIMARY KEY, cuenta_id INTEGER)")
        conn.execute("INSERT INTO integracion_desconocida(cuenta_id) VALUES (?)", (cuenta,)); conn.commit(); conn.close()
        resultado = database.eliminar_cuenta_nube_descartable(cuenta, True)
        self.assertEqual(resultado["codigo"], "eliminacion_bloqueada")
        self.assertIn("referencias no reconocidas", resultado["razones"])

    def test_rollback_total_ante_fallo(self):
        cuenta = self.cuenta("perfiles", 90, 2)
        with self.assertRaisesRegex(RuntimeError, "Fallo de prueba"):
            database.actualizar_cuenta_nube_admin(cuenta, self.payload(duracion_unidad_dias=90), True, "despues_perfiles")
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT modalidad FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone()[0], "perfiles")
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 2); conn.close()

    def test_rollback_total_eliminacion_ante_fallo(self):
        cuenta = self.cuenta("perfiles", 90, 2)
        with self.assertRaisesRegex(RuntimeError, "Fallo de prueba"):
            database.eliminar_cuenta_nube_descartable(cuenta, True, "antes_cuenta")
        conn = database.conectar()
        self.assertIsNotNone(conn.execute("SELECT 1 FROM nube_cuentas WHERE id=?", (cuenta,)).fetchone())
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_perfiles WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT count(*) FROM nube_movimientos WHERE cuenta_id=?", (cuenta,)).fetchone()[0], 1); conn.close()

    def test_rutas_exigen_admin_y_csrf(self):
        cuenta = self.cuenta()
        url = f"/admin/nube-cuentas/{cuenta}/edicion"
        self.assertEqual(self.client.post(url, json=self.payload()).status_code, 403)
        respuesta = self.client.post(url, json=self.payload(), headers={"X-CSRF-Token":"csrf-nube"})
        self.assertEqual(respuesta.status_code, 200)
        with self.client.session_transaction() as session: session.clear()
        self.assertEqual(self.client.get(url).status_code, 401)


if __name__ == "__main__":
    unittest.main()
