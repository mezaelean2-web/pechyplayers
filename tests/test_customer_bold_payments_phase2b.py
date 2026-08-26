try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import bold_recharges
import customer_bold_payments as payments
import customer_cart
import customer_orders
import database
from app import app


class CustomerBoldPaymentsPhase2BTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.previous_db = database.DB
        self.previous_env = {key: os.environ.get(key) for key in ("BOLD_ENV","BOLD_IDENTITY_KEY","BOLD_SECRET_KEY")}
        database.DB = self.path
        os.environ.update(BOLD_ENV="test", BOLD_IDENTITY_KEY="identity-test", BOLD_SECRET_KEY="secret-test")
        conn=sqlite3.connect(self.path)
        conn.execute("""CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT,plan TEXT,precio TEXT,
            oferta_precio TEXT DEFAULT '',oferta_activa INTEGER DEFAULT 0,visible INTEGER DEFAULT 1,
            estado TEXT DEFAULT 'disponible',participa_descuento_carrito INTEGER DEFAULT 0)""")
        conn.execute("INSERT INTO productos VALUES(1,'Netflix','Perfil','10000','',0,1,'disponible',1)")
        # Tablas reseller mínimas: prueban colisión global sin usar wallet.
        conn.execute("""CREATE TABLE reseller_recharge_intents(id INTEGER PRIMARY KEY,order_id TEXT,
            estado TEXT,external_transaction_id TEXT)""")
        conn.execute("""CREATE TABLE reseller_wallet_transactions(id INTEGER PRIMARY KEY,provider TEXT,
            external_reference TEXT)""")
        conn.commit();conn.close()
        customer_cart.initialize_schema(); customer_orders.initialize_schema(); payments.initialize_schema()
        self.guest="a"*64; self.other="b"*64
        payload={"customer":{"first_name":"Ana","last_name":"Pérez","whatsapp":"3001234567","country_code":"+57"},
                 "items":[{"plan_id":1,"quantity":1}],"idempotency_key":"k"*32}
        self.order,_=customer_orders.create_order(payload,guest_session_hash=self.guest)
        app.config.update(TESTING=True,SECRET_KEY="customer-bold-tests")
        self.client=app.test_client()
        with self.client.session_transaction() as session:
            session["csrf_customer_checkout"]="csrf"
            session["customer_checkout_guest_token"]="guest-token"
        self.session_hash=hashlib.sha256(b"guest-token").hexdigest()
        conn=sqlite3.connect(self.path)
        conn.execute("UPDATE customer_orders SET guest_session_hash=?",(self.session_hash,));conn.commit();conn.close()

    def tearDown(self):
        database.DB=self.previous_db
        for key,value in self.previous_env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        for suffix in ("","-wal","-shm"):
            try: os.remove(self.path+suffix)
            except FileNotFoundError: pass

    def checkout(self):
        return self.client.post(f"/compras/pedidos/{self.order['id']}/pago/bold",json={},headers={"X-CSRF-Token":"csrf"})

    def payload(self, reference, *, transaction="TX-CUSTOMER-1", total=10000, currency="COP", event="SALE_APPROVED", event_id="evt-customer-1"):
        return {"id":event_id,"type":event,"data":{"payment_id":transaction,
            "amount":{"total":total,"currency":currency},"metadata":{"reference":reference}}}

    def post_webhook(self,payload):
        raw=json.dumps(payload,separators=(",",":")).encode()
        signature=hmac.new(b"",base64.b64encode(raw),hashlib.sha256).hexdigest()
        return self.client.post("/webhooks/bold",data=raw,headers={"Content-Type":"application/json","X-Bold-Signature":signature})

    def rows(self,sql,args=()):
        conn=sqlite3.connect(self.path);conn.row_factory=sqlite3.Row
        try:return [dict(x) for x in conn.execute(sql,args)]
        finally:conn.close()

    def test_checkout_uses_snapshot_signature_and_is_idempotent(self):
        first=self.checkout();second=self.checkout()
        self.assertEqual(first.status_code,200);self.assertEqual(second.status_code,200)
        one,two=first.get_json(),second.get_json()
        self.assertEqual(one["intent_id"],two["intent_id"]);self.assertEqual(one["checkout"]["orderId"],two["checkout"]["orderId"])
        self.assertEqual(one["checkout"]["amount"],"10000");self.assertEqual(one["checkout"]["currency"],"COP")
        expected=hashlib.sha256(f"{one['checkout']['orderId']}10000COPsecret-test".encode()).hexdigest()
        self.assertEqual(one["checkout"]["integritySignature"],expected)
        self.assertEqual(len(self.rows("SELECT * FROM customer_bold_payment_intents")),1)

    def test_checkout_bold_usa_total_con_descuento_acumulado_congelado(self):
        conn=sqlite3.connect(self.path);conn.execute("UPDATE productos SET descuento_carrito_bps=200 WHERE id=1");conn.commit();conn.close()
        payload={"customer":{"first_name":"Ana","last_name":"Perez","whatsapp":"3001234567","country_code":"+57"},
                 "items":[{"plan_id":1,"quantity":1}],"idempotency_key":"bold-plan-discount-snapshot-0001"}
        order,_=customer_orders.create_order(payload,guest_session_hash=self.session_hash)
        response=self.client.post(f"/compras/pedidos/{order['id']}/pago/bold",json={},headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(response.status_code,200);checkout=response.get_json()["checkout"]
        self.assertEqual(checkout["amount"],"9800")
        expected=hashlib.sha256(f"{checkout['orderId']}9800COPsecret-test".encode()).hexdigest()
        self.assertEqual(checkout["integritySignature"],expected)

    def test_frontend_cannot_supply_financial_fields_and_other_guest_is_blocked(self):
        bad=self.client.post(f"/compras/pedidos/{self.order['id']}/pago/bold",json={"amount":1},headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(bad.status_code,400)
        with self.client.session_transaction() as session:session["customer_checkout_guest_token"]="other"
        self.assertEqual(self.checkout().status_code,404)

    def test_cancelled_and_expired_cannot_start(self):
        conn=sqlite3.connect(self.path);conn.execute("UPDATE customer_orders SET status='cancelled'");conn.commit();conn.close()
        self.assertEqual(self.checkout().status_code,409)
        conn=sqlite3.connect(self.path);conn.execute("UPDATE customer_orders SET status='pending_payment',expires_at='2020-01-01T00:00:00Z'");conn.commit();conn.close()
        self.assertEqual(self.checkout().status_code,409)

    def test_valid_webhook_marks_paid_once_even_twenty_times(self):
        checkout=self.checkout().get_json()["checkout"]
        payload=self.payload(checkout["orderId"])
        results=[]
        with mock.patch("customer_fulfillment.fulfill_customer_order") as fulfill:
            for _ in range(20):results.append(self.post_webhook(payload).get_json()["status"])
        fulfill.assert_called_once()
        self.assertEqual(results[0],"processed");self.assertTrue(all(x=="duplicate" for x in results[1:]))
        intent=self.rows("SELECT * FROM customer_bold_payment_intents")[0]
        self.assertEqual(intent["status"],"approved");self.assertEqual(intent["external_transaction_id"],"TX-CUSTOMER-1")
        self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"paid")
        self.assertEqual(len(self.rows("SELECT * FROM bold_payment_claims")),1)
        self.assertEqual(len(self.rows("SELECT * FROM customer_bold_payment_audit WHERE result='processed'")),1)
        self.assertEqual(len(self.rows("SELECT * FROM reseller_wallet_transactions")),0)

    def test_invalid_official_evidence_never_marks_paid(self):
        for index,change in enumerate(({"total":9999},{"currency":"USD"},{"transaction":""}),1):
            if index>1:
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_bold_webhook_events");conn.commit();conn.close()
            checkout=self.checkout().get_json()["checkout"]
            args={"event_id":f"bad-{index}",**change}
            self.post_webhook(self.payload(checkout["orderId"],**args))
            self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"pending_payment")

    def test_reconcile_official_voucher_and_repeat(self):
        checkout=self.checkout().get_json();reference=checkout["checkout"]["orderId"]
        voucher={"reference_id":reference,"transaction_id":"TX-REC-1","payment_status":"APPROVED","total":10000}
        with mock.patch.object(bold_recharges,"fetch_official_voucher",return_value=(voucher,200,"a"*64)):
            first=payments.reconcile_customer_pending_from_bold(checkout["intent_id"])
            second=payments.reconcile_customer_pending_from_bold(checkout["intent_id"])
        self.assertEqual(first["status"],"processed");self.assertEqual(second["reason"],"already_reconciled")
        self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"paid")

    def test_reseller_transaction_collision_is_fail_closed(self):
        checkout=self.checkout().get_json()["checkout"]
        conn=sqlite3.connect(self.path);conn.execute("INSERT INTO reseller_wallet_transactions VALUES(1,'bold','COLLISION')");conn.commit();conn.close()
        response=self.post_webhook(self.payload(checkout["orderId"],transaction="COLLISION"))
        self.assertEqual(response.get_json()["status"],"ignored")
        self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"pending_payment")

    def test_redirect_and_query_string_never_mark_paid_status_hides_pii(self):
        self.checkout()
        response=self.client.get(f"/compras/pago/resultado?order={self.order['id']}&bold-tx-status=approved&transaction_id=fake")
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"pending_payment")
        status=self.client.get(f"/compras/pedidos/{self.order['id']}/estado",headers={"X-CSRF-Token":"csrf"})
        self.assertNotIn("whatsapp",status.get_json());self.assertNotIn("customer",status.get_json())

    def test_late_approved_goes_to_review_not_paid(self):
        checkout=self.checkout().get_json()["checkout"]
        conn=sqlite3.connect(self.path);conn.execute("UPDATE customer_orders SET status='expired'");conn.commit();conn.close()
        self.post_webhook(self.payload(checkout["orderId"],transaction="TX-LATE"))
        self.assertEqual(self.rows("SELECT status FROM customer_orders")[0]["status"],"expired")
        self.assertEqual(self.rows("SELECT status FROM customer_bold_payment_intents")[0]["status"],"payment_review")


if __name__ == "__main__": unittest.main()
