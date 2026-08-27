try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock
from datetime import datetime
from pathlib import Path

import customer_cart
import customer_fulfillment
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
        customer_fulfillment.initialize_schema()
        conn=sqlite3.connect(path);conn.execute("UPDATE productos SET descuento_carrito_bps=250 WHERE id IN (1,2)");conn.commit();conn.close()
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.guest_hash = "1" * 64

    def tearDown(self):
        database.DB = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def payload(self, items=None, key="a" * 32, **customer):
        data = {"first_name":"José", "last_name":"O'Connor", "whatsapp":"300 123 4567", "country_code":"+57", "email":"Cliente@Example.COM"}
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
        self.assertEqual(order["customer"],{"first_name":"José","last_name":"O'Connor","whatsapp":"+573001234567","email":"Cliente@example.com"})
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
        conn.execute("UPDATE productos SET descuento_carrito_bps=5000 WHERE id=1")
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

    def test_email_obligatorio_valido_normalizado_y_congelado(self):
        order,_=self.create(self.payload(email="  Compras+uno@EXAMPLE.COM  ",key="1"*32))
        self.assertEqual(order["customer"]["email"],"Compras+uno@example.com")
        conn=sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT customer_email FROM customer_orders WHERE public_order_id=?",(order["id"],)).fetchone()[0],"Compras+uno@example.com")
        conn.close()

    def test_email_invalido_vacio_largo_y_tipo_inesperado(self):
        cases=(None,"","   ","sin-arroba","a@@example.com","a b@example.com",".a@example.com","a..b@example.com","a@example","a@-example.com","a"*65+"@example.com","a@"+"b"*250+".com")
        for index,email in enumerate(cases):
            with self.subTest(email=email),self.assertRaises(customer_orders.OrderValidationError) as caught:
                self.create(self.payload(email=email,key=(str(index%10)+"e")*16))
            self.assertEqual(caught.exception.code,"invalid_email")

    def test_retry_email_distinto_falla_cerrado_sin_mutar_snapshot_ni_fingerprint_con_pii(self):
        key="2"*32
        original,_=self.create(self.payload(email="original@example.com",key=key))
        conn=sqlite3.connect(self.path)
        before=conn.execute("SELECT customer_email,request_fingerprint FROM customer_orders WHERE public_order_id=?",(original["id"],)).fetchone()
        conn.close()
        self.assertNotIn("original",before[1]);self.assertNotIn("example.com",before[1])
        with self.assertRaises(customer_orders.OrderValidationError) as caught:
            self.create(self.payload(email="otro@example.com",key=key))
        self.assertEqual(caught.exception.code,"idempotency_conflict")
        conn=sqlite3.connect(self.path)
        after=conn.execute("SELECT customer_email,request_fingerprint FROM customer_orders WHERE public_order_id=?",(original["id"],)).fetchone()
        self.assertEqual(before,after);self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_orders").fetchone()[0],1)
        conn.close()

    def test_historico_email_null_sigue_leyendose_y_migracion_es_idempotente(self):
        order,_=self.create(self.payload(key="3"*32))
        conn=sqlite3.connect(self.path);conn.execute("UPDATE customer_orders SET customer_email=NULL WHERE public_order_id=?",(order["id"],));conn.commit();conn.close()
        customer_orders.initialize_schema();customer_orders.initialize_schema()
        saved=customer_orders.get_order_admin(order["id"])
        self.assertIsNone(saved["customer"]["email"])
        with self.client.session_transaction() as session:session["admin"]=True
        self.assertIn("Sin correo (pedido histórico)".encode(),self.client.get(f"/admin/pedidos-clientes/{order['id']}").data)

    def test_cambio_material_cancela_a_crea_b_y_preserva_snapshots(self):
        order_a,_=self.create(self.payload(key="j"*32))
        order_b,_=self.create(self.payload([{"plan_id":1,"quantity":1},{"plan_id":2,"quantity":1}],"k"*32))
        self.assertNotEqual(order_a["id"],order_b["id"])
        saved_a=customer_orders.get_order_admin(order_a["id"])
        self.assertEqual(saved_a["status"],"cancelled")
        self.assertEqual((saved_a["subtotal"],len(saved_a["items"])),(12000,1))
        self.assertEqual(order_b["status"],"pending_payment")
        self.assertEqual((order_b["subtotal"],len(order_b["items"])),(22001,2))

    def _set_order_and_fulfillment_status(self, public_id, order_status, fulfillment_status=None):
        conn=sqlite3.connect(self.path)
        order_id=conn.execute("SELECT id FROM customer_orders WHERE public_order_id=?",(public_id,)).fetchone()[0]
        conn.execute("UPDATE customer_orders SET status=? WHERE id=?",(order_status,order_id))
        if fulfillment_status is not None:
            conn.execute("INSERT INTO customer_order_fulfillments(order_id,status) VALUES(?,?)",(order_id,fulfillment_status))
        conn.commit();conn.close()
        return order_id

    def test_paid_fulfilled_es_terminal_y_nuevo_pedido_reemplaza_solo_el_puntero(self):
        old,_=self.create(self.payload(key="q"*32))
        old_id=self._set_order_and_fulfillment_status(old["id"],"paid","fulfilled")
        conn=sqlite3.connect(self.path)
        before_order=conn.execute("SELECT status,updated_at,guest_session_hash FROM customer_orders WHERE id=?",(old_id,)).fetchone()
        before_fulfillment=conn.execute("SELECT * FROM customer_order_fulfillments WHERE order_id=?",(old_id,)).fetchone()
        before_lines=conn.execute("SELECT * FROM customer_order_fulfillment_lines WHERE fulfillment_id=?",(before_fulfillment[0],)).fetchall()
        conn.close()

        new,created=self.create(self.payload([{"plan_id":2,"quantity":1}],key="r"*32))
        retry,created_again=self.create(self.payload([{"plan_id":2,"quantity":1}],key="r"*32))

        self.assertTrue(created);self.assertFalse(created_again);self.assertEqual(retry,new);self.assertEqual(new["status"],"pending_payment")
        conn=sqlite3.connect(self.path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_orders").fetchone()[0],2)
        self.assertEqual(conn.execute("SELECT current_order_id FROM customer_checkout_sessions WHERE session_hash=?",(self.guest_hash,)).fetchone()[0],conn.execute("SELECT id FROM customer_orders WHERE public_order_id=?",(new["id"],)).fetchone()[0])
        self.assertEqual(conn.execute("SELECT status,updated_at,guest_session_hash FROM customer_orders WHERE id=?",(old_id,)).fetchone(),before_order)
        self.assertEqual(conn.execute("SELECT * FROM customer_order_fulfillments WHERE order_id=?",(old_id,)).fetchone(),before_fulfillment)
        self.assertEqual(conn.execute("SELECT * FROM customer_order_fulfillment_lines WHERE fulfillment_id=?",(before_fulfillment[0],)).fetchall(),before_lines)
        conn.close()

    def test_paid_no_terminal_permanece_fail_closed(self):
        for index,fulfillment_status in enumerate((None,"pending","processing","review")):
            with self.subTest(fulfillment_status=fulfillment_status):
                old,_=self.create(self.payload(key=(str(index)+"s")*16))
                self._set_order_and_fulfillment_status(old["id"],"paid",fulfillment_status)
                with self.assertRaises(customer_orders.OrderValidationError) as caught:
                    self.create(self.payload([{"plan_id":2,"quantity":1}],key=(str(index)+"t")*16))
                self.assertEqual(caught.exception.code,"current_order_not_cancellable")
                conn=sqlite3.connect(self.path)
                conn.execute("UPDATE customer_orders SET status='cancelled' WHERE public_order_id=?",(old["id"],));conn.commit();conn.close()

    def test_concurrencia_desde_terminal_deja_un_solo_nuevo_pedido_activo(self):
        old,_=self.create(self.payload(key="u"*32))
        old_id=self._set_order_and_fulfillment_status(old["id"],"paid","fulfilled")
        barrier=threading.Barrier(2);results=[];errors=[]
        def create_new(key,plan_id):
            try:
                barrier.wait()
                results.append(self.create(self.payload([{"plan_id":plan_id,"quantity":1}],key=key))[0])
            except Exception as error:
                errors.append(error)
        threads=[threading.Thread(target=create_new,args=("v"*32,1)),threading.Thread(target=create_new,args=("w"*32,2))]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertFalse(errors);self.assertEqual(len(results),2)
        conn=sqlite3.connect(self.path)
        active=conn.execute("SELECT id,public_order_id FROM customer_orders WHERE status='pending_payment'").fetchall()
        current=conn.execute("SELECT current_order_id FROM customer_checkout_sessions WHERE session_hash=?",(self.guest_hash,)).fetchone()[0]
        self.assertEqual(len(active),1);self.assertEqual(active[0][0],current)
        self.assertIn(active[0][1],{result["id"] for result in results})
        self.assertEqual(conn.execute("SELECT status FROM customer_orders WHERE id=?",(old_id,)).fetchone()[0],"paid")
        self.assertEqual(conn.execute("SELECT status FROM customer_order_fulfillments WHERE order_id=?",(old_id,)).fetchone()[0],"fulfilled")
        conn.close()

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
        payload=self.payload(key="g"*32);payload["customer"]["address"]="inesperado"
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
        self.assertEqual(response.get_json()["order"]["total"],11700)
        retry=self.client.post("/compras/pedidos",json=payload,headers={"X-CSRF-Token":"token"})
        self.assertEqual(retry.status_code,200)

    def test_contrato_real_navegador_acepta_checkout_colombiano_con_gmail(self):
        payload={"customer":{"first_name":"Carlos","last_name":"Prueba","country_code":"+57",
                 "whatsapp":"3001234567","email":"pechy.checkout.test@GMAIL.COM"},
                 "items":[{"plan_id":1,"quantity":1}],"idempotency_key":"browser-contract-email-0000000001"}
        with self.client.session_transaction() as session:session["csrf_customer_checkout"]="token"
        with mock.patch("customer_bold_payments.create_or_reuse_checkout") as bold, mock.patch("customer_order_email.send_payment_confirmation") as email, mock.patch("customer_fulfillment.fulfill_customer_order") as fulfillment:
            response=self.client.post("/compras/pedidos",json=payload,headers={"X-CSRF-Token":"token"})
        self.assertEqual(response.status_code,201);bold.assert_not_called();email.assert_not_called();fulfillment.assert_not_called()
        saved=customer_orders.get_order_admin(response.get_json()["order"]["id"])
        self.assertEqual(saved["customer"]["email"],"pechy.checkout.test@gmail.com")

    def test_payload_js_cacheado_sin_email_reproduce_error_de_formato(self):
        payload=self.payload(key="stale-browser-payload-0000000001");del payload["customer"]["email"]
        with self.assertRaises(customer_orders.OrderValidationError) as caught:self.create(payload)
        self.assertEqual(caught.exception.code,"invalid_customer")
        self.assertEqual(str(caught.exception),"Los datos del cliente no tienen el formato esperado.")

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
        self.assertNotIn(b"Cliente@example.com",listing.data);self.assertIn(b"Cliente@example.com",detail.data)
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
        self.assertIn("customer_email TEXT",order_sql)
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
        self.assertFalse(any("email" in line.lower() for line in storage_calls))

    def test_email_checkout_requerido_y_sin_cambios_de_paleta(self):
        self.assertIn('name="email"',self.html);self.assertIn('type="email"',self.html)
        self.assertIn('maxlength="254"',self.html);self.assertIn('autocomplete="email"',self.html)
        self.assertIn('fields.get("email")',self.js)

    def test_loading_retry_no_borra_carrito_y_cache_busting(self):
        self.assertIn('submit.disabled=true',self.js)
        self.assertIn('checkoutFingerprint!==fingerprint',self.js)
        self.assertNotIn('localStorage.removeItem(STORAGE_KEY)',self.js)
        self.assertIn("customer-cart.js') }}?v=8",self.index)
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
