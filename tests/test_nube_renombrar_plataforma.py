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

    def test_renombra_cuentas_modalidades_y_reglas_sin_tocar_historial(self):
        cuenta = self._cuenta("completa@test.com", "cuenta_completa", 30)
        madre = self._cuenta("perfiles@test.com", "perfiles", 90, perfiles=2)
        planes = [self._plan("YouTube 30", 30), self._plan("YouTube 90", 90, "perfil")]
        conn = database.conectar()
        conn.execute(
            "INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion) VALUES (?,'alta','YouTube Premium original')",
            (cuenta,),
        )
        perfiles_antes = [fila[0] for fila in conn.execute(
            "SELECT id FROM nube_perfiles WHERE cuenta_id=? ORDER BY id", (madre,)
        )]
        conn.commit()
        conn.close()

        resultado = database.renombrar_plataforma_nube(
            " YouTube   Premium ", "YouTube Familiar"
        )

        self.assertEqual(resultado["cuentas_actualizadas"], 2)
        self.assertEqual(resultado["reglas_actualizadas"], 2)
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
