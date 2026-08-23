try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import tempfile
import unittest
from pathlib import Path

import app as app_module
import database
import reseller_accounts
import resellers
import wallets


class ResellerOrderDeliveryTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.path
        conn = database.conectar()
        conn.executescript("""
          CREATE TABLE productos(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,imagen TEXT DEFAULT '',plan TEXT NOT NULL,precio TEXT NOT NULL,estado TEXT DEFAULT 'disponible',visible INTEGER DEFAULT 1);
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,telefono_normalizado TEXT UNIQUE,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT NOT NULL,correo TEXT,contrasena TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',modalidad TEXT DEFAULT 'cuenta_completa',fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,nombre_perfil TEXT DEFAULT '',pin TEXT DEFAULT '',cliente_id INTEGER,nombre_cliente TEXT DEFAULT '',telefono TEXT DEFAULT '',fecha_entrega TEXT DEFAULT '',dias_cuenta INTEGER DEFAULT 0,fecha_vencimiento TEXT DEFAULT '',estado TEXT DEFAULT 'disponible',fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER NOT NULL,tipo TEXT NOT NULL,descripcion TEXT,estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        self.cuenta_plan = conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Disney','Premium','999999')").lastrowid
        self.perfil_plan = conn.execute("INSERT INTO productos(nombre,plan,precio) VALUES('Max','Premium','999999')").lastrowid
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); reseller_accounts.inicializar_esquema()
        self.owner = resellers.crear_revendedor("Andrea", "andrea-delivery@example.com", "3001234567", "Tienda", "ClaveSegura123")
        self.other = resellers.crear_revendedor("Luis", "luis-delivery@example.com", "3007654321", "Tienda", "ClaveSegura123")
        for reseller_id in (self.owner, self.other):
            wallets.apply_wallet_transaction(reseller_id, "manual_credit", 500000, "Saldo")
        conn = database.conectar()
        conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,estado) VALUES('Disney','cuenta_completa','caida')")
        mother = conn.execute("INSERT INTO nube_cuentas(plataforma,modalidad,estado) VALUES('Max','perfiles','caida')").lastrowid
        conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,estado) VALUES(?,'Esquema','caida')", (mother,))
        conn.commit(); conn.close()
        reseller_accounts.guardar_regla_inventario_plan(self.cuenta_plan, "Disney", "cuenta", 30)
        reseller_accounts.guardar_regla_inventario_plan(self.perfil_plan, "Max", "perfil", 30)
        resellers.guardar_precio_general(self.cuenta_plan, 12000)
        resellers.guardar_precio_general(self.perfil_plan, 8000)
        app_module.app.config.update(TESTING=True, SECRET_KEY="delivery-test", RESELLER_PURCHASES_ENABLED=True)
        self.client = app_module.app.test_client()

    def tearDown(self):
        database.DB = self.original_db
        try: os.remove(self.path)
        except PermissionError: pass

    def login(self, reseller_id=None):
        reseller = resellers.obtener_revendedor(reseller_id or self.owner)
        with self.client.session_transaction() as session:
            session.clear(); session["reseller_id"] = reseller["id"]
            session["reseller_auth_version"] = reseller["auth_version"]

    def account(self, index=1, pin="1234"):
        conn = database.conectar()
        result = conn.execute("INSERT INTO nube_cuentas(plataforma,correo,contrasena,pin,modalidad,duracion_unidad_dias) VALUES(?,?,?,?,?,30)",
                              ("Disney", f"cuenta{index}@pechy.test", f"clave-{index}", pin, "cuenta_completa")).lastrowid
        conn.commit(); conn.close(); return result

    def profile(self, index=1, pin="5678"):
        conn = database.conectar()
        account_id = conn.execute("INSERT INTO nube_cuentas(plataforma,correo,contrasena,modalidad,duracion_unidad_dias) VALUES(?,?,?,'perfiles',30)",
                                  ("Max", f"perfil{index}@pechy.test", f"perfil-clave-{index}")).lastrowid
        conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,pin) VALUES(?,?,?)",
                     (account_id, f"Perfil {index}", pin))
        conn.commit(); conn.close(); return account_id

    def buy(self, reseller_id=None, accounts=1, profiles=0, intent="delivery"):
        reseller_id = reseller_id or self.owner
        for index in range(accounts): self.account(index + 1)
        for index in range(profiles): self.profile(index + 1)
        lines = []
        if accounts: lines.append({"plan_id": self.cuenta_plan, "cantidad_unidades": accounts, "cantidad_periodos": 1})
        if profiles: lines.append({"plan_id": self.perfil_plan, "cantidad_unidades": profiles, "cantidad_periodos": 1})
        return reseller_accounts.comprar_carrito_reseller(reseller_id, intent, lines)

    def state(self):
        conn = database.conectar()
        result = (
            conn.execute("SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (self.owner,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM reseller_orders").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM reseller_purchases").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions").fetchone()[0],
            tuple(tuple(row) for row in conn.execute("SELECT id,estado,nombre_cliente FROM nube_cuentas ORDER BY id")),
            tuple(tuple(row) for row in conn.execute("SELECT id,estado,nombre_cliente FROM nube_perfiles ORDER BY id")),
        )
        conn.close(); return result

    def test_sesion_owner_otro_reseller_y_order_inexistente(self):
        order = self.buy()
        url = f"/revendedores/pedidos/{order['order_id']}/entrega"
        self.assertEqual(self.client.get(url).status_code, 401)
        self.login(self.other)
        foreign = self.client.get(url)
        self.assertEqual(foreign.status_code, 404)
        self.assertNotIn("clave-1", foreign.get_data(as_text=True))
        self.login()
        self.assertEqual(self.client.get("/revendedores/pedidos/999999/entrega").status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_cuenta_completa_campos_reales_y_vacios_omitidos(self):
        order = self.buy()
        self.login(); data = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega").get_json()
        unit = data["unidades"][0]
        self.assertEqual((unit["modalidad"], unit["modalidad_etiqueta"]), ("cuenta", "Cuenta completa"))
        fields = {field["clave"]: field["valor"] for field in unit["campos"]}
        self.assertEqual(fields, {"correo": "cuenta1@pechy.test", "contrasena": "clave-1", "pin": "1234"})
        order = self.buy(accounts=1, intent="without-pin")
        conn = database.conectar(); conn.execute("UPDATE nube_cuentas SET pin='' WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE order_id=?)", (order["order_id"],)); conn.commit(); conn.close()
        data = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega").get_json()
        self.assertNotIn("pin", [field["clave"] for field in data["unidades"][0]["campos"]])

    def test_perfil_devuelve_solo_perfil_y_pin_asignados(self):
        order = self.buy(accounts=0, profiles=1)
        conn = database.conectar()
        account_id = conn.execute("SELECT cuenta_id FROM reseller_purchases WHERE order_id=?", (order["order_id"],)).fetchone()[0]
        conn.execute("INSERT INTO nube_perfiles(cuenta_id,nombre_perfil,pin,nombre_cliente,estado) VALUES(?, 'Perfil ajeno','never-return','Otro','activa')", (account_id,))
        conn.commit(); conn.close()
        self.login(); raw = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega").get_data(as_text=True)
        self.assertIn("Perfil 1", raw); self.assertIn("5678", raw)
        self.assertNotIn("never-return", raw)

    def test_entrega_multiple_mixta_y_numerada(self):
        order = self.buy(accounts=2, profiles=2)
        self.login(); data = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega").get_json()
        self.assertTrue(data["entrega_completa"])
        self.assertEqual([unit["numero"] for unit in data["unidades"]], [1, 2, 3, 4])
        self.assertEqual([unit["modalidad"] for unit in data["unidades"]], ["cuenta", "cuenta", "perfil", "perfil"])
        self.assertEqual([unit["producto"] for unit in data["unidades"]], ["Disney", "Disney", "Max", "Max"])

    def test_solo_order_purchase_y_asignacion_coherentes_se_entregan(self):
        order = self.buy(accounts=2)
        conn = database.conectar()
        purchase_ids = [row[0] for row in conn.execute("SELECT id FROM reseller_purchases WHERE order_id=? ORDER BY id", (order["order_id"],))]
        conn.execute("UPDATE nube_cuentas SET nombre_cliente='Manipulada' WHERE id=(SELECT cuenta_id FROM reseller_purchases WHERE id=?)", (purchase_ids[1],))
        conn.commit(); conn.close()
        foreign = self.buy(self.other, accounts=1, intent="foreign")
        conn = database.conectar()
        conn.execute("UPDATE reseller_purchases SET order_id=? WHERE order_id=?", (order["order_id"], foreign["order_id"]))
        conn.commit(); conn.close()
        self.login(); data = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega").get_json()
        self.assertEqual(len(data["unidades"]), 1)
        self.assertFalse(data["entrega_completa"])
        self.assertNotIn("clave-2", str(data))

    def test_endpoint_repetido_es_estrictamente_read_only(self):
        order = self.buy(accounts=1, profiles=1)
        self.login(); before = self.state()
        first = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega")
        second = self.client.get(f"/revendedores/pedidos/{order['order_id']}/entrega")
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.headers["Cache-Control"], "no-store, private")
        self.assertEqual(self.state(), before)

    def test_preview_y_post_compra_siguen_sin_credenciales(self):
        self.account(); self.login()
        with self.client.session_transaction() as session: session["csrf_reseller"] = "csrf"
        line = [{"plan_id": self.cuenta_plan, "cantidad_unidades": 1, "cantidad_periodos": 1}]
        preview = self.client.post("/revendedores/productos/carrito/preview", json={"lineas": line, "cart_intent_id": "safe"}, headers={"X-CSRF-Token": "csrf"})
        purchase = self.client.post("/revendedores/productos/carrito/comprar", json={"items": line, "cart_intent_id": "safe", "preview_token": preview.get_json()["preview"]["preview_token"]}, headers={"X-CSRF-Token": "csrf"})
        for raw in (preview.get_data(as_text=True), purchase.get_data(as_text=True)):
            self.assertNotIn("cuenta1@pechy.test", raw); self.assertNotIn("clave-1", raw); self.assertNotIn("1234", raw)

    def test_frontend_seguridad_copias_ocultacion_advertencia_y_overflow(self):
        script = Path("static/js/reseller-cart.js").read_text(encoding="utf-8")
        css = Path("static/css/reseller-cart.css").read_text(encoding="utf-8")
        self.assertIn("data-delivery-copy-field", script); self.assertIn("data-delivery-copy-unit", script)
        self.assertIn("data-delivery-copy-all", script); self.assertIn('field.sensible ? "••••••••"', script)
        self.assertIn('unit.modalidad === "perfil"', script); self.assertIn("1 DISPOSITIVO", script)
        self.assertNotIn("WhatsApp", script); self.assertNotIn("wa.me", script)
        self.assertNotIn("localStorage.setItem(CART_KEY, JSON.stringify({ cart_intent_id: intentId, lineas: cart, delivery", script)
        self.assertIn("overflow-x:hidden", css); self.assertIn("overflow-y:auto", css)
        self.assertIn("reseller-delivery-device-warning", css)


if __name__ == "__main__":
    unittest.main()
