try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import customer_cart
import customer_orders
import database
from app import app


class CustomerOrdersPhase2ATest(unittest.TestCase):
    def setUp(self):
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.path = path
        self.previous_db = database.DB
        database.DB = path
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT NOT NULL,plan TEXT NOT NULL,
            precio TEXT NOT NULL,oferta_precio TEXT DEFAULT '',oferta_activa INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1,estado TEXT DEFAULT 'disponible',participa_descuento_carrito INTEGER DEFAULT 0)""")
        conn.executemany("INSERT INTO productos VALUES(?,?,?,?,?,?,?,?,?)", [
            (1,"Netflix","Perfil","15.000","12.000",1,1,"disponible",1),
            (2,"Disney","Cuenta completa","10.001","",0,1,"disponible",1),
            (3,"Crunchyroll","Perfil","8.000","",0,1,"disponible",0),
            (4,"Oculto","Perfil","9.000","",0,0,"disponible",1),
            (5,"Agotado","Perfil","9.000","",0,1,"agotado",1),
            (6,"Ambiguo","Perfil","10.0000","",0,1,"disponible",1),
        ])
        conn.execute("CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY, correo TEXT)")
        conn.execute("INSERT INTO nube_cuentas VALUES(1,'intacto')")
        conn.execute("CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO reseller_purchases VALUES(1)")
        conn.execute("CREATE TABLE bold_webhook_events(id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO bold_webhook_events VALUES(1)")
        conn.commit(); conn.close()
        customer_cart.initialize_schema()
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO customer_cart_discount_rules(minimum_eligible_services,discount_bps,active) VALUES(2,500,1)")
        conn.commit(); conn.close()
        customer_orders.initialize_schema()
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.guest_hash = "1" * 64

    def tearDown(self):
        database.DB = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def payload(self, items=None, key="a" * 32, **customer):
        data = {"first_name":"José", "last_name":"O'Connor", "whatsapp":"300 123 4567", "country_code":"+57"}
        data.update(customer)
        return {"customer":data, "items":items if items is not None else [{"plan_id":1,"quantity":1}], "idempotency_key":key}

    def counts(self):
        conn=sqlite3.connect(self.path)
        result=tuple(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("nube_cuentas","reseller_purchases","bold_webhook_events"))
        conn.close(); return result

    def create(self, payload, **kwargs):
        return customer_orders.create_order(payload, guest_session_hash=self.guest_hash, **kwargs)

    def test_pedido_valido_unicode_whatsapp_estado_y_expiracion(self):
        before=self.counts()
        order,created=self.create(self.payload())
        self.assertTrue(created)
        self.assertEqual(order["status"],"pending_payment")
        self.assertEqual(order["customer"],{"first_name":"José","last_name":"O'Connor","whatsapp":"+573001234567"})
        self.assertRegex(order["id"],r"^ORD-[A-Za-z0-9_-]{20,}$")
        delta=(datetime.fromisoformat(order["expires_at"].replace("Z","+00:00"))-datetime.fromisoformat(order["created_at"].replace("Z","+00:00"))).total_seconds()
        self.assertEqual(delta,900)
        self.assertEqual(before,self.counts())

    def test_oferta_descuento_exclusion_quantity_y_mayor_resto_igual_preview(self):
        items=[{"plan_id":1,"quantity":2},{"plan_id":2,"quantity":1},{"plan_id":3,"quantity":1}]
        preview=customer_cart.calculate_cart({"items":items})
        order,_=self.create(self.payload(items,key="b"*32))
        self.assertEqual(order["item_count"],4)
        self.assertEqual((order["subtotal"],order["discount_total"],order["total"]),(preview["subtotal_bruto"],preview["discount_total"],preview["total_final"]))
        self.assertEqual([x["discount_amount"] for x in order["items"]],[x["discount_amount"] for x in preview["items"]])
        self.assertTrue(order["items"][0]["oferta_aplicada"])
        self.assertFalse(order["items"][-1]["discount_eligible"])
        self.assertEqual(sum(x["precio_efectivo"] for x in order["items"]),order["subtotal"])
        self.assertEqual(sum(x["discount_amount"] for x in order["items"]),order["discount_total"])
        self.assertEqual(sum(x["line_total_final"] for x in order["items"]),order["total"])

    def test_snapshot_no_cambia_con_precio_o_regla_posterior(self):
        order,_=self.create(self.payload([{"plan_id":1,"quantity":2}],"c"*32))
        conn=sqlite3.connect(self.path)
        conn.execute("UPDATE productos SET precio='99.000',oferta_precio='88.000' WHERE id=1")
        conn.execute("UPDATE customer_cart_discount_rules SET discount_bps=4000")
        conn.commit();conn.close()
        saved=customer_orders.get_order_admin(order["id"])
        self.assertEqual(saved["subtotal"],order["subtotal"])
        self.assertEqual(saved["discount_total"],order["discount_total"])
        self.assertEqual(saved["items"],order["items"])

    def test_idempotencia_retry_y_conflicto(self):
        first,created=self.create(self.payload(key="d"*32))
        retry,created_again=self.create(self.payload(key="d"*32))
        self.assertTrue(created);self.assertFalse(created_again);self.assertEqual(first,retry)
        with self.assertRaises(customer_orders.OrderValidationError) as caught:
            self.create(self.payload([{"plan_id":2,"quantity":1}],"d"*32))
        self.assertEqual(caught.exception.code,"idempotency_conflict")
        conn=sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_orders").fetchone()[0],1)
        conn.close()

    def test_cambio_material_cancela_a_crea_b_y_preserva_snapshots(self):
        order_a,_=self.create(self.payload(key="j"*32))
        order_b,_=self.create(self.payload([{"plan_id":1,"quantity":1},{"plan_id":2,"quantity":1}],"k"*32))
        self.assertNotEqual(order_a["id"],order_b["id"])
        saved_a=customer_orders.get_order_admin(order_a["id"])
        self.assertEqual(saved_a["status"],"cancelled")
        self.assertEqual((saved_a["subtotal"],len(saved_a["items"])),(12000,1))
        self.assertEqual(order_b["status"],"pending_payment")
        self.assertEqual((order_b["subtotal"],len(order_b["items"])),(22001,2))

    def test_cancelar_actual_es_idempotente_y_aislado_por_sesion(self):
        order,_=self.create(self.payload(key="l"*32))
        other="2"*64
        self.assertEqual(customer_orders.cancel_current_order(other)["result"],"none")
        self.assertEqual(customer_orders.get_order_admin(order["id"])["status"],"pending_payment")
        self.assertEqual(customer_orders.cancel_current_order(self.guest_hash)["result"],"cancelled")
        self.assertEqual(customer_orders.cancel_current_order(self.guest_hash)["result"],"already_cancelled")

    def test_perfil_checkout_server_side_expone_solo_sesion_propietaria(self):
        self.create(self.payload(key="m"*32))
        self.assertEqual(customer_orders.get_checkout_customer(self.guest_hash),{"first_name":"José","last_name":"O'Connor","whatsapp":"+573001234567"})
        self.assertIsNone(customer_orders.get_checkout_customer("3"*64))

    def test_rollback_total_ante_fallo_de_linea_y_sin_huerfanas(self):
        def fail_second(line):
            if line["line_number"]==2: raise RuntimeError("fallo inducido")
        with self.assertRaises(RuntimeError):
            self.create(self.payload([{"plan_id":1,"quantity":2}],"e"*32),before_line_insert=fail_second)
        conn=sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_orders").fetchone()[0],0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_order_lines").fetchone()[0],0)
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(),[])
        conn.close()

    def test_validaciones_cliente_payload_y_whatsapp(self):
        valid=[{"first_name":"María José"},{"last_name":"Ana-María"},{"whatsapp":"+14155552671","country_code":"+57"}]
        for index,change in enumerate(valid):
            self.create(self.payload(key=(str(index)+"v")*16,**change))
        invalid=[{"first_name":" "},{"first_name":"<script>"},{"whatsapp":"abc"},{"whatsapp":"123","country_code":"+57"},{"country_code":"57"}]
        for index,change in enumerate(invalid):
            with self.subTest(change=change),self.assertRaises(customer_orders.OrderValidationError):
                self.create(self.payload(key=(str(index)+"x")*16,**change))
        payload=self.payload(key="f"*32);payload["total"]=1
        with self.assertRaises(customer_orders.OrderValidationError):self.create(payload)
        payload=self.payload(key="g"*32);payload["customer"]["email"]="x@y.co"
        with self.assertRaises(customer_orders.OrderValidationError):self.create(payload)

    def test_carrito_vacio_limite_y_planes_fail_closed(self):
        cases=[([],"empty_cart"),([{"plan_id":1,"quantity":6}],"cart_limit"),([{"plan_id":999,"quantity":1}],"plan_not_found"),([{"plan_id":4,"quantity":1}],"plan_unavailable"),([{"plan_id":5,"quantity":1}],"plan_unavailable"),([{"plan_id":6,"quantity":1}],"invalid_plan_price")]
        for index,(items,code) in enumerate(cases):
            with self.subTest(code=code),self.assertRaises((customer_orders.OrderValidationError,customer_cart.CartValidationError)) as caught:
                self.create(self.payload(items,key=(str(index)+"z")*16))
            self.assertEqual(caught.exception.code,code)

    def test_endpoint_csrf_schema_no_confia_en_dinero_y_no_devuelve_pii(self):
        payload=self.payload(key="h"*32)
        self.assertEqual(self.client.post("/compras/pedidos",json=payload).status_code,403)
        with self.client.session_transaction() as session:session["csrf_customer_checkout"]="token"
        bad=dict(payload,total=1)
        self.assertEqual(self.client.post("/compras/pedidos",json=bad,headers={"X-CSRF-Token":"token"}).status_code,400)
        response=self.client.post("/compras/pedidos",json=payload,headers={"X-CSRF-Token":"token"})
        self.assertEqual(response.status_code,201)
        self.assertNotIn("customer",response.get_json()["order"])
        self.assertEqual(response.get_json()["order"]["total"],12000)
        retry=self.client.post("/compras/pedidos",json=payload,headers={"X-CSRF-Token":"token"})
        self.assertEqual(retry.status_code,200)

    def test_endpoint_cancelacion_no_acepta_order_id_y_profile_no_cache(self):
        with self.client.session_transaction() as session:
            session["csrf_customer_checkout"]="token"
            session["customer_checkout_guest_token"]="guest-one"
        response=self.client.post("/compras/pedidos",json=self.payload(key="n"*32),headers={"X-CSRF-Token":"token"})
        public_id=response.get_json()["order"]["id"]
        manipulated=self.client.post("/compras/pedidos/cancelar-actual",json={"public_order_id":public_id},headers={"X-CSRF-Token":"token"})
        self.assertEqual(manipulated.status_code,400)
        profile=self.client.get("/compras/checkout-profile",headers={"X-CSRF-Token":"token"})
        self.assertEqual(profile.status_code,200);self.assertIn("no-store",profile.headers["Cache-Control"])
        cancelled=self.client.post("/compras/pedidos/cancelar-actual",json={},headers={"X-CSRF-Token":"token"})
        self.assertEqual(cancelled.get_json()["result"],"cancelled")
        again=self.client.post("/compras/pedidos/cancelar-actual",json={},headers={"X-CSRF-Token":"token"})
        self.assertEqual(again.get_json()["result"],"already_cancelled")

    def test_admin_lista_detalle_exige_sesion_y_es_solo_lectura(self):
        order,_=self.create(self.payload(key="i"*32))
        self.assertEqual(self.client.get("/admin/pedidos-clientes").status_code,302)
        self.assertEqual(self.client.get(f"/admin/pedidos-clientes/{order['id']}").status_code,302)
        with self.client.session_transaction() as session:session["admin"]=True
        listing=self.client.get("/admin/pedidos-clientes")
        detail=self.client.get(f"/admin/pedidos-clientes/{order['id']}")
        self.assertEqual(listing.status_code,200);self.assertEqual(detail.status_code,200)
        self.assertIn(order["id"].encode(),listing.data);self.assertIn("Pendiente de pago".encode(),detail.data)
        self.assertNotIn(b"Marcar pagado",detail.data);self.assertNotIn(b"Entregar",detail.data)

    def test_admin_pendientes_cancelados_todos_y_detalle(self):
        cancelled,_=self.create(self.payload(key="o"*32))
        customer_orders.cancel_current_order(self.guest_hash)
        pending,_=self.create(self.payload([{"plan_id":2,"quantity":1}],"p"*32))
        with self.client.session_transaction() as session:session["admin"]=True
        pending_page=self.client.get("/admin/pedidos-clientes")
        cancelled_page=self.client.get("/admin/pedidos-clientes?estado=cancelled")
        all_page=self.client.get("/admin/pedidos-clientes?estado=all")
        self.assertIn(pending["id"].encode(),pending_page.data);self.assertNotIn(cancelled["id"].encode(),pending_page.data)
        self.assertIn(cancelled["id"].encode(),cancelled_page.data);self.assertNotIn(pending["id"].encode(),cancelled_page.data)
        self.assertIn(cancelled["id"].encode(),all_page.data);self.assertIn(pending["id"].encode(),all_page.data)
        self.assertIn("Cancelado por cliente".encode(),self.client.get(f"/admin/pedidos-clientes/{cancelled['id']}").data)

    def test_constraints_public_id_estado_fk_y_tipos_monetarios(self):
        conn=sqlite3.connect(self.path)
        order_sql=conn.execute("SELECT sql FROM sqlite_master WHERE name='customer_orders'").fetchone()[0]
        line_sql=conn.execute("SELECT sql FROM sqlite_master WHERE name='customer_order_lines'").fetchone()[0]
        self.assertIn("public_order_id TEXT NOT NULL UNIQUE",order_sql)
        self.assertIn("idempotency_key TEXT NOT NULL UNIQUE",order_sql)
        self.assertNotIn(" REAL",order_sql.upper());self.assertNotIn(" REAL",line_sql.upper())
        self.assertIn("ON DELETE RESTRICT",line_sql)
        self.assertIn("pending_payment",order_sql)
        self.assertIn("guest_session_hash",order_sql)
        self.assertIsNotNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='customer_checkout_sessions'").fetchone())
        conn.close()


class CustomerOrdersFrontendStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(__file__).resolve().parents[1]
        cls.html=(root/"templates"/"_customer_cart.html").read_text(encoding="utf-8")
        cls.js=(root/"static"/"js"/"customer-cart.js").read_text(encoding="utf-8")
        cls.index=(root/"templates"/"index.html").read_text(encoding="utf-8")

    def test_tres_estados_y_cta_pago_bold_fase_2b(self):
        for marker in ('data-customer-cart-stage="cart"','data-customer-cart-stage="customer"','data-customer-cart-stage="ready"','Continuar compra','Pedido preparado','Pagar con Bold','data-customer-pay-bold'):
            self.assertIn(marker,self.html)
        self.assertIn('/pago/bold',self.js)

    def test_frontend_envia_solo_cliente_items_key_y_no_persiste_pii(self):
        self.assertIn('JSON.stringify({customer,items:cart,idempotency_key:checkoutKey})',self.js)
        self.assertIn('fetch("/compras/pedidos"',self.js)
        self.assertIn('"X-CSRF-Token"',self.js)
        storage_calls=[line for line in self.js.splitlines() if "localStorage.setItem" in line]
        self.assertEqual(len(storage_calls),2)
        self.assertTrue(any("FAB_POSITION_KEY" in line for line in storage_calls))
        self.assertTrue(any("STORAGE_KEY" in line and "JSON.stringify(cart)" in line for line in storage_calls))
        self.assertFalse(any("customer" in line.lower() for line in storage_calls))

    def test_loading_retry_no_borra_carrito_y_cache_busting(self):
        self.assertIn('submit.disabled=true',self.js)
        self.assertIn('checkoutFingerprint!==fingerprint',self.js)
        self.assertNotIn('localStorage.removeItem(STORAGE_KEY)',self.js)
        self.assertIn("customer-cart.js') }}?v=7",self.index)
        self.assertIn("css/style.css') }}?v=6",self.index)

    def test_precarga_cancelacion_feedback_empty_y_privacidad(self):
        self.assertIn('fetch("/compras/checkout-profile"',self.js)
        self.assertIn('fetch("/compras/pedidos/cancelar-actual"',self.js)
        self.assertNotIn("public_order_id",self.js)
        self.assertIn('button.textContent="✓ Agregado al carrito"',self.js)
        self.assertIn('button.dataset.feedbackActive==="true"',self.js)
        self.assertIn("},1100)",self.js)
        self.assertIn("announcer.textContent=",self.js)
        self.assertIn("const hasItems=preview.items.length>0",self.js)
        self.assertIn("empty.hidden=hasItems",self.js)
        self.assertIn(".customer-cart-empty[hidden]{display:none}",(Path(__file__).resolve().parents[1]/"static"/"css"/"style.css").read_text(encoding="utf-8"))
        self.assertNotIn("sessionStorage",self.js)


if __name__ == "__main__":
    unittest.main()
