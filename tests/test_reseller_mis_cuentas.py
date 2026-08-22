import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app as app_module
import database
import reseller_accounts
import resellers


class ResellerMisCuentasTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
          CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible');
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          INSERT INTO productos VALUES(1,'Netflix','', 'Premium','10000','disponible');
          INSERT INTO productos VALUES(2,'Max','', 'Perfil','8000','disponible');
        """)
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        self.owner = resellers.crear_revendedor("Andrea", "andrea@example.com", "3001234567", "Tienda", "ClaveSegura123")
        self.other = resellers.crear_revendedor("Luis", "luis@example.com", "3007654321", "Tienda", "ClaveSegura123")
        app_module.app.config.update(TESTING=True, SECRET_KEY="mis-cuentas-test")
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def login(self, reseller_id=None):
        reseller = resellers.obtener_revendedor(reseller_id or self.owner)
        with self.client.session_transaction() as session:
            session["reseller_id"] = reseller["id"]
            session["reseller_auth_version"] = reseller["auth_version"]

    def purchase(self, owner=None, tipo="cuenta", offset=10, no_renovar=0):
        owner = owner or self.owner
        nombre = resellers.obtener_revendedor(owner)["nombre"]
        conn = database.conectar()
        cuenta_id = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM nube_cuentas").fetchone()[0]
        modalidad = "cuenta_completa" if tipo == "cuenta" else "perfiles"
        etiqueta = f"Reseller #{owner} - {nombre}"
        conn.execute("INSERT INTO nube_cuentas(id,plataforma,correo,contrasena,pin,nombre_cliente,estado,modalidad) VALUES(?,?,?,?,?,?,?,?)",
                     (cuenta_id, "Netflix" if tipo == "cuenta" else "Max", "actual@test", "actual-secret", "mother-pin", etiqueta if tipo == "cuenta" else "", "activa", modalidad))
        perfil_id = None
        if tipo == "perfil":
            perfil_id = cuenta_id
            conn.execute("INSERT INTO nube_perfiles(id,cuenta_id,nombre_perfil,pin,nombre_cliente,estado) VALUES(?,?,?,?,?,'activa')",
                         (perfil_id, cuenta_id, "Perfil 2", "only-this-pin", etiqueta))
            conn.execute("INSERT INTO nube_perfiles(id,cuenta_id,nombre_perfil,pin,nombre_cliente,estado) VALUES(?,?,?,?,?,'activa')",
                         (perfil_id + 1000, cuenta_id, "Perfil ajeno", "never-return", "Otro"))
        expiry = (date.today() + timedelta(days=offset)).isoformat()
        cur = conn.execute("""INSERT INTO reseller_purchases(revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,precio_pagado,cantidad_periodos,duracion_base_dias,estado_persistido,no_renovar)
          VALUES(?,?,?,?,?,'purchase',?,?,?,?,10000,1,30,'active',?)""",
          (owner, 1 if tipo == "cuenta" else 2, cuenta_id, perfil_id, tipo, date.today().isoformat(), date.today().isoformat(), expiry, 30, no_renovar))
        purchase_id = cur.lastrowid; conn.commit(); conn.close(); return purchase_id

    def test_ruta_requiere_sesion_y_empty_state(self):
        self.assertEqual(self.client.get("/revendedores/mis-cuentas").status_code, 302)
        self.login()
        html = self.client.get("/revendedores/mis-cuentas").get_data(as_text=True)
        self.assertIn("Aún no tienes servicios adquiridos", html)

    def test_ownership_listado_y_detalle_fail_closed(self):
        propio, ajeno = self.purchase(), self.purchase(self.other)
        self.login(); html = self.client.get("/revendedores/mis-cuentas").get_data(as_text=True)
        self.assertIn(f'data-account-id="{propio}"', html)
        self.assertNotIn(f'data-account-id="{ajeno}"', html)
        self.assertEqual(self.client.get(f"/revendedores/mis-cuentas/{propio}").status_code, 200)
        self.assertEqual(self.client.get(f"/revendedores/mis-cuentas/{ajeno}").status_code, 404)

    def test_estados_orden_filtros_busqueda_metricas_e_historial(self):
        ids = [self.purchase(offset=value, no_renovar=no) for value, no in ((10,0), (2,0), (0,0), (-2,0), (20,1))]
        items = reseller_accounts.listar_mis_cuentas(self.owner)
        self.assertEqual([item["estado_visual"] for item in items], ["VENCE_HOY","PROXIMA_A_VENCER","ACTIVA","VENCIDA","NO_RENOVADA"])
        self.assertEqual(len(reseller_accounts.listar_mis_cuentas(self.owner, estado="VENCIDA")), 1)
        self.assertEqual(len(reseller_accounts.listar_mis_cuentas(self.owner, tipo="cuenta", busqueda="netflix premium")), 5)
        self.assertEqual(reseller_accounts.resumen_mis_cuentas(self.owner), {"total":5,"activas":1,"proximas":1,"vencen_hoy":1,"vencidas":1,"no_renovadas":1})
        self.assertIn(ids[3], [item["id"] for item in items])

    def test_listado_no_contiene_credenciales_y_comprar_sigue_inactivo(self):
        self.purchase(); self.login()
        html = self.client.get("/revendedores/mis-cuentas").get_data(as_text=True)
        self.assertNotIn("actual-secret", html); self.assertNotIn("mother-pin", html)
        productos = Path("templates/index.html").read_text(encoding="utf-8")
        self.assertIn("reseller-buy-disabled", productos)
        self.assertIn("disabled", productos)

    def test_credenciales_actuales_y_reasignacion_fail_closed(self):
        purchase_id = self.purchase(); self.login()
        data = self.client.get(f"/revendedores/mis-cuentas/{purchase_id}/credenciales").get_json()
        self.assertTrue(data["autorizadas"]); self.assertIn("actual-secret", [x["valor"] for x in data["campos"]])
        conn = database.conectar(); conn.execute("UPDATE nube_cuentas SET contrasena='new-secret' WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE id=?)", (purchase_id,)); conn.commit(); conn.close()
        data = self.client.get(f"/revendedores/mis-cuentas/{purchase_id}/credenciales").get_json()
        self.assertIn("new-secret", [x["valor"] for x in data["campos"]])
        conn = database.conectar(); conn.execute("UPDATE nube_cuentas SET nombre_cliente='Reasignada' WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE id=?)", (purchase_id,)); conn.commit(); conn.close()
        self.assertFalse(self.client.get(f"/revendedores/mis-cuentas/{purchase_id}/credenciales").get_json()["autorizadas"])

    def test_cortada_y_ajena_no_entregan_credenciales(self):
        propio, ajeno = self.purchase(), self.purchase(self.other)
        conn = database.conectar(); conn.execute("UPDATE reseller_purchases SET cortada_at=CURRENT_TIMESTAMP WHERE id=?", (propio,)); conn.commit(); conn.close()
        self.login()
        self.assertFalse(self.client.get(f"/revendedores/mis-cuentas/{propio}/credenciales").get_json()["autorizadas"])
        self.assertEqual(self.client.get(f"/revendedores/mis-cuentas/{ajeno}/credenciales").status_code, 404)

    def test_perfil_entrega_solo_su_pin(self):
        purchase_id = self.purchase(tipo="perfil"); self.login()
        raw = self.client.get(f"/revendedores/mis-cuentas/{purchase_id}/credenciales").get_data(as_text=True)
        self.assertIn("only-this-pin", raw); self.assertNotIn("never-return", raw); self.assertNotIn("mother-pin", raw)

    def test_corte_atomico_idempotente_y_disponibilidad_en_vivo(self):
        purchase_id = self.purchase(no_renovar=1)
        conn = database.conectar(); conn.execute("BEGIN IMMEDIATE"); cursor = conn.cursor()
        cuenta_id = cursor.execute("SELECT cuenta_id FROM reseller_purchases WHERE id=?", (purchase_id,)).fetchone()[0]
        cursor.execute("UPDATE nube_cuentas SET cliente_id=NULL,nombre_cliente='',telefono='',fecha_entrega='',dias_cuenta=0,fecha_vencimiento='',estado='disponible' WHERE id=?", (cuenta_id,))
        self.assertEqual(reseller_accounts.registrar_corte_purchase_reseller(cursor=cursor, cuenta_id=cuenta_id, motivo="fin", actor_id=7), purchase_id)
        self.assertIsNone(reseller_accounts.registrar_corte_purchase_reseller(cursor=cursor, cuenta_id=cuenta_id, actor_id=7))
        conn.commit()
        compra = conn.execute("SELECT * FROM reseller_purchases WHERE id=?", (purchase_id,)).fetchone()
        self.assertTrue(compra["cortada_at"].endswith("-05:00")); self.assertEqual(compra["estado_persistido"], "cut")
        self.assertEqual(compra["no_renovar"], 1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM reseller_purchase_events WHERE purchase_id=? AND tipo='cut'", (purchase_id,)).fetchone()[0], 1)
        conn.close()
        disponible = reseller_accounts.consultar_disponibilidad_recuperacion(self.owner, purchase_id)
        self.assertEqual((disponible["code"], disponible["recoverable"]), ("AVAILABLE", True))
        self.assertNotIn("secret", str(disponible).lower())
        conn = database.conectar(); conn.execute("UPDATE nube_cuentas SET nombre_cliente='Otro cliente',contrasena='never-expose',estado='activa' WHERE id=?", (cuenta_id,)); conn.commit(); conn.close()
        vendido = reseller_accounts.consultar_disponibilidad_recuperacion(self.owner, purchase_id)
        self.assertEqual(vendido["code"], "SOLD"); self.assertNotIn("never-expose", str(vendido))

    def test_disponibilidad_ownership_not_cut_y_perfil_original(self):
        perfil_id = self.purchase(tipo="perfil"); ajeno = self.purchase(self.other)
        self.assertEqual(reseller_accounts.consultar_disponibilidad_recuperacion(self.owner, perfil_id)["code"], "NOT_CUT")
        self.assertIsNone(reseller_accounts.consultar_disponibilidad_recuperacion(self.owner, ajeno))
        conn = database.conectar(); compra = conn.execute("SELECT cuenta_id,perfil_id FROM reseller_purchases WHERE id=?", (perfil_id,)).fetchone()
        conn.execute("UPDATE reseller_purchases SET cortada_at=CURRENT_TIMESTAMP,estado_persistido='cut' WHERE id=?", (perfil_id,))
        conn.execute("UPDATE nube_perfiles SET cliente_id=NULL,nombre_cliente='',telefono='',fecha_entrega='',dias_cuenta=0,fecha_vencimiento='',estado='disponible' WHERE id=?", (compra["perfil_id"],))
        conn.commit(); conn.close()
        self.assertEqual(reseller_accounts.consultar_disponibilidad_recuperacion(self.owner, perfil_id)["code"], "AVAILABLE")

    def test_ruta_disponibilidad_y_csrf_admin_fail_closed(self):
        purchase_id = self.purchase(); self.login()
        self.assertEqual(self.client.get(f"/revendedores/mis-cuentas/{purchase_id}/disponibilidad").status_code, 409)
        with self.client.session_transaction() as session:
            session.clear(); session["admin"] = True; session["csrf_admin"] = "csrf-corte"
        self.assertEqual(self.client.post("/admin/nube-cortes/cortar", json={"servicios": []}).status_code, 403)
        self.assertNotEqual(self.client.post("/admin/nube-cortes/cortar", json={"servicios": []}, headers={"X-CSRF-Token": "csrf-corte"}).status_code, 403)


if __name__ == "__main__": unittest.main()
