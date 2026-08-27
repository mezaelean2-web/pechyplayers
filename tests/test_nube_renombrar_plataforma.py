try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database
import customer_fulfillment
import customer_orders
import reseller_accounts
import resellers
from app import app


class NubeRenombrarPlataformaTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.original_db = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, imagen TEXT,
            plan TEXT, precio TEXT, estado TEXT DEFAULT 'disponible',
            visible INTEGER DEFAULT 1)""")
        conn.commit()
        conn.close()
        database.inicializar_db()
        resellers.inicializar_revendedores()
        reseller_accounts.inicializar_esquema()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["admin"] = True
            session["csrf_admin"] = "csrf-renombre"

    def tearDown(self):
        database.DB = self.original_db
        try:
            os.remove(self.path)
        except PermissionError:
            pass

    def _plan(self, nombre, dias, tipo="cuenta", plataforma="YouTube Premium"):
        conn = database.conectar()
        plan_id = conn.execute(
            "INSERT INTO productos(nombre,imagen,plan,precio) VALUES (?,?,?,?)",
            (nombre, "x.png", f"{dias} dias", "10000"),
        ).lastrowid
        conn.execute(
            """INSERT INTO reseller_plan_inventory_rules
               (plan_id,plataforma,tipo_unidad,duracion_dias,activo)
               VALUES (?,?,?,?,1)""",
            (plan_id, plataforma, tipo, dias),
        )
        conn.commit()
        conn.close()
        return plan_id

    def _cuenta(self, correo, modalidad, dias, plataforma="YouTube Premium", perfiles=0):
        cuenta_id = database.crear_cuenta_nube(
            plataforma=plataforma,
            correo=correo,
            contrasena="clave",
            modalidad=modalidad,
            tipo_cuenta="perfil" if modalidad == "perfiles" else "cuenta_completa",
            cantidad_perfiles=perfiles,
            duracion_unidad_dias=dias,
        )
        return cuenta_id

    def _regla_cliente(self, plan_id, plataforma="YouTube Premium", tipo="cuenta", dias=30, activo=1):
        conn=database.conectar()
        cursor=conn.execute("""INSERT INTO customer_plan_fulfillment_rules
            (plan_id,plataforma,tipo_unidad,duracion_dias,activo) VALUES(?,?,?,?,?)""",
            (plan_id,plataforma,tipo,dias,activo))
        conn.commit();conn.close();return cursor.lastrowid

    def test_renombra_cuentas_modalidades_y_reglas_sin_tocar_historial(self):
        cuenta = self._cuenta("completa@test.com", "cuenta_completa", 30)
        madre = self._cuenta("perfiles@test.com", "perfiles", 90, perfiles=2)
        planes = [self._plan("YouTube 30", 30), self._plan("YouTube 90", 90, "perfil")]
        regla_cliente_id=self._regla_cliente(planes[0],activo=0)
        conn = database.conectar()
        conn.execute(
            "INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion) VALUES (?,'alta','YouTube Premium original')",
            (cuenta,),
        )
        perfiles_antes = [fila[0] for fila in conn.execute(
            "SELECT id FROM nube_perfiles WHERE cuenta_id=? ORDER BY id", (madre,)
        )]
        regla_cliente_antes=conn.execute("""SELECT plan_id,tipo_unidad,duracion_dias,activo,created_at
            FROM customer_plan_fulfillment_rules WHERE id=?""",(regla_cliente_id,)).fetchone()
        conn.commit()
        conn.close()

        resultado = database.renombrar_plataforma_nube(
            " YouTube   Premium ", "YouTube Familiar"
        )

        self.assertEqual(resultado["cuentas_actualizadas"], 2)
        self.assertEqual(resultado["reglas_actualizadas"], 2)
        self.assertEqual(resultado["reglas_cliente_actualizadas"], 1)
        conn = database.conectar()
        self.assertEqual(
            [fila[0] for fila in conn.execute("SELECT DISTINCT plataforma FROM nube_cuentas")],
            ["YouTube Familiar"],
        )
        self.assertEqual(
            [tuple(fila) for fila in conn.execute(
                "SELECT plataforma,duracion_dias FROM reseller_plan_inventory_rules ORDER BY duracion_dias"
            )],
            [("YouTube Familiar", 30), ("YouTube Familiar", 90)],
        )
        self.assertEqual(
            [fila[0] for fila in conn.execute(
                "SELECT id FROM nube_perfiles WHERE cuenta_id=? ORDER BY id", (madre,)
            )],
            perfiles_antes,
        )
        regla_cliente_despues=conn.execute("""SELECT plan_id,tipo_unidad,duracion_dias,activo,created_at,plataforma
            FROM customer_plan_fulfillment_rules WHERE id=?""",(regla_cliente_id,)).fetchone()
        self.assertEqual(tuple(regla_cliente_despues[:5]),tuple(regla_cliente_antes))
        self.assertEqual(regla_cliente_despues[5],"YouTube Familiar")
        self.assertEqual(
            conn.execute(
                "SELECT descripcion FROM nube_movimientos WHERE cuenta_id=? AND tipo='alta' ORDER BY id DESC LIMIT 1",
                (cuenta,),
            ).fetchone()[0],
            "YouTube Premium original",
        )
        self.assertIsNone(conn.execute("PRAGMA foreign_key_check").fetchone())
        conn.close()

    def test_elegibilidad_reseller_se_conserva_despues_del_renombre(self):
        self._cuenta("unidad30@test.com", "cuenta_completa", 30)
        self._cuenta("unidad90@test.com", "cuenta_completa", 90)
        plan_30 = self._plan("YouTube 30", 30)
        plan_90 = self._plan("YouTube 90", 90)
        database.renombrar_plataforma_nube("YouTube Premium", "YouTube Plus")
        conn = database.conectar()
        cursor = conn.cursor()
        regla_30 = dict(cursor.execute(
            "SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?", (plan_30,)
        ).fetchone())
        regla_90 = dict(cursor.execute(
            "SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?", (plan_90,)
        ).fetchone())
        unidades_30 = reseller_accounts._unidades_elegibles_en_cursor(cursor, regla_30)
        unidades_90 = reseller_accounts._unidades_elegibles_en_cursor(cursor, regla_90)
        conn.close()
        self.assertEqual(len(unidades_30), 1)
        self.assertEqual(len(unidades_90), 1)

    def test_rechaza_vacio_inexistente_equivalente_y_colision_normalizada(self):
        self._cuenta("origen@test.com", "cuenta_completa", 30)
        self._cuenta("destino@test.com", "cuenta_completa", 30, "Spotífy Premium")
        casos = [
            (("YouTube Premium", "   "), "nombre_invalido"),
            (("No existe", "Nuevo"), "plataforma_no_encontrada"),
            (("youtube premium", " YOUTUBE   PRÉMIUM "), "nombre_equivalente"),
            (("YouTube Premium", " spotify premium "), "plataforma_existente"),
        ]
        for argumentos, codigo in casos:
            with self.subTest(codigo=codigo), self.assertRaises(database.RenombrarPlataformaNubeError) as contexto:
                database.renombrar_plataforma_nube(*argumentos)
            self.assertEqual(contexto.exception.codigo, codigo)

    def test_rollback_total_si_falla_actualizacion_de_reglas(self):
        self._cuenta("rollback@test.com", "cuenta_completa", 30)
        self._plan("YouTube 30", 30)
        conn = database.conectar()
        conn.execute("""CREATE TRIGGER bloquear_renombre_regla
            BEFORE UPDATE OF plataforma ON reseller_plan_inventory_rules
            BEGIN SELECT RAISE(ABORT, 'fallo controlado'); END""")
        conn.commit()
        conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            database.renombrar_plataforma_nube("YouTube Premium", "YouTube Nuevo")
        conn = database.conectar()
        self.assertEqual(conn.execute("SELECT plataforma FROM nube_cuentas").fetchone()[0], "YouTube Premium")
        self.assertEqual(conn.execute("SELECT plataforma FROM reseller_plan_inventory_rules").fetchone()[0], "YouTube Premium")
        conn.close()

    def test_rollback_total_si_falla_regla_cliente(self):
        self._cuenta("rollback-cliente@test.com","cuenta_completa",30)
        plan=self._plan("YouTube 30",30);self._regla_cliente(plan)
        conn=database.conectar()
        conn.execute("""CREATE TRIGGER bloquear_renombre_regla_cliente
            BEFORE UPDATE OF plataforma ON customer_plan_fulfillment_rules
            BEGIN SELECT RAISE(ABORT,'fallo cliente controlado'); END""")
        conn.commit();conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            database.renombrar_plataforma_nube("YouTube Premium","YouTube Nuevo")
        conn=database.conectar()
        self.assertEqual(conn.execute("SELECT plataforma FROM nube_cuentas").fetchone()[0],"YouTube Premium")
        self.assertEqual(conn.execute("SELECT plataforma FROM reseller_plan_inventory_rules").fetchone()[0],"YouTube Premium")
        self.assertEqual(conn.execute("SELECT plataforma FROM customer_plan_fulfillment_rules").fetchone()[0],"YouTube Premium")
        conn.close()

    def test_fulfillment_cliente_funciona_despues_del_rename(self):
        self._cuenta("fulfillment@test.com","cuenta_completa",30)
        plan=self._plan("YouTube Cliente",30);self._regla_cliente(plan,activo=1)
        resultado=database.renombrar_plataforma_nube("YouTube Premium","YouTube Plus")
        self.assertEqual(resultado["reglas_cliente_actualizadas"],1)
        payload={"customer":{"first_name":"Ana","last_name":"Pérez","whatsapp":"3001234567","country_code":"+57","email":"ana@example.com"},
            "items":[{"plan_id":plan,"quantity":1}],"idempotency_key":"rename-fulfillment-customer-0001"}
        order,_=customer_orders.create_order(payload,guest_session_hash="8"*64)
        conn=database.conectar();order_id=conn.execute("SELECT id FROM customer_orders WHERE public_order_id=?",(order["id"],)).fetchone()[0]
        conn.execute("UPDATE customer_orders SET status='paid' WHERE id=?",(order_id,));conn.commit();conn.close()
        fulfilled=customer_fulfillment.fulfill_customer_order(order_id)
        self.assertEqual(fulfilled["status"],"fulfilled")
        conn=database.conectar()
        self.assertEqual(conn.execute("SELECT plataforma FROM customer_plan_fulfillment_rules WHERE plan_id=?",(plan,)).fetchone()[0],"YouTube Plus")
        self.assertEqual(conn.execute("""SELECT c.plataforma FROM customer_order_fulfillment_lines fl
            JOIN customer_order_fulfillments f ON f.id=fl.fulfillment_id
            JOIN nube_cuentas c ON c.id=fl.nube_account_id WHERE f.order_id=?""",(order_id,)).fetchone()[0],"YouTube Plus")
        conn.close()

    def test_fail_closed_ante_referencia_de_plataforma_no_reconocida(self):
        self._cuenta("cerrada@test.com", "cuenta_completa", 30)
        conn = database.conectar()
        conn.execute("CREATE TABLE integracion_futura(id INTEGER PRIMARY KEY, platform_code TEXT)")
        conn.commit()
        conn.close()
        with self.assertRaises(database.RenombrarPlataformaNubeError) as contexto:
            database.renombrar_plataforma_nube("YouTube Premium", "YouTube Nuevo")
        self.assertEqual(contexto.exception.codigo, "referencia_desconocida")

    def test_ruta_exige_admin_csrf_payload_estricto_y_reporta_conflicto(self):
        self._cuenta("ruta@test.com", "cuenta_completa", 30)
        url = "/admin/nube-cuentas/plataformas/renombrar"
        payload = {"nombre_actual":"YouTube Premium", "nombre_nuevo":"YouTube Nuevo"}
        self.assertEqual(self.client.post(url, json=payload).status_code, 403)
        respuesta = self.client.post(
            url, json={**payload, "extra":True}, headers={"X-CSRF-Token":"csrf-renombre"}
        )
        self.assertEqual(respuesta.status_code, 400)
        respuesta = self.client.post(
            url, json=payload, headers={"X-CSRF-Token":"csrf-renombre"}
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.get_json()["ok"])
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.post(url, json=payload).status_code, 401)

    def test_frontend_conserva_filtro_y_expone_ambos_gestos_sin_dependencias(self):
        raiz = Path(__file__).resolve().parents[1]
        javascript = (raiz / "static/js/admin/nube_cuentas.js").read_text(encoding="utf-8")
        template = (raiz / "templates/admin/nube_cuentas.html").read_text(encoding="utf-8")
        self.assertIn('addEventListener("click", evento =>', javascript)
        self.assertIn('addEventListener("dblclick", evento =>', javascript)
        self.assertIn('addEventListener("contextmenu", evento =>', javascript)
        self.assertIn("sincronizarPlataformaInventario(boton.dataset.plataforma)", javascript)
        self.assertIn("abrirRenombrePlataforma(boton.dataset.plataforma)", javascript)
        self.assertIn('fetch("/admin/nube-cuentas/plataformas/renombrar"', javascript)
        self.assertIn('id="modalRenombrarPlataforma"', template)
        self.assertNotIn("jquery", javascript.lower())


if __name__ == "__main__":
    unittest.main()
