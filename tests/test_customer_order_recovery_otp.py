try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib
import hashlib
import io
import logging
import os
import re
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import customer_delivery_access
import customer_fulfillment
import customer_order_recovery as recovery
import database
from app import app


class CustomerOrderRecoveryOtpTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.previous_db = database.DB
        database.DB = self.path
        connection = sqlite3.connect(self.path)
        connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE customer_orders(
                id INTEGER PRIMARY KEY,public_order_id TEXT UNIQUE,status TEXT,
                customer_email TEXT,customer_whatsapp TEXT,guest_session_hash TEXT,
                item_count INTEGER,expires_at TEXT);
            CREATE TABLE customer_order_lines(
                id INTEGER PRIMARY KEY,order_id INTEGER,line_number INTEGER,
                source_plan_id INTEGER,product_name TEXT,plan_name TEXT);
            CREATE TABLE nube_cuentas(
                id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT,contrasena TEXT,pin TEXT,
                modalidad TEXT,estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,
                fecha_vencimiento TEXT,dias_cuenta INTEGER);
            CREATE TABLE nube_perfiles(
                id INTEGER PRIMARY KEY,cuenta_id INTEGER,nombre_perfil TEXT,pin TEXT,
                estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,fecha_vencimiento TEXT,
                dias_cuenta INTEGER);
            CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,cuenta_id INTEGER,tipo TEXT);
            INSERT INTO nube_cuentas VALUES(
                1,'NETFLIX','delivery@example.test','PRODUCT-SECRET','',
                'perfiles','disponible','','','',0);
            INSERT INTO nube_perfiles VALUES(
                2,1,'PERFIL PRIVADO','4321','activa','Cliente',
                '2026-08-27','2026-09-27',30);
            INSERT INTO nube_movimientos VALUES(1,1,'asignacion_customer_order_perfil');
        """)
        self.owner_token = "original-owner-token"
        self.owner_hash = hashlib.sha256(self.owner_token.encode()).hexdigest()
        connection.execute("INSERT INTO customer_orders VALUES(1,'ORD-RECOVERY-A','paid',?,?,?,1,?)",
                           ("maria@example.com", "+573001234567", self.owner_hash, "2030-01-01T00:00:00Z"))
        connection.execute("INSERT INTO customer_orders VALUES(2,'ORD-RECOVERY-B','paid',?,?,?,1,?)",
                           ("other@example.com", "+573009876543", "b"*64, "2030-01-01T00:00:00Z"))
        connection.execute("INSERT INTO customer_order_lines VALUES(1,1,1,10,'Netflix','Perfil')")
        connection.execute("INSERT INTO customer_order_lines VALUES(2,2,1,10,'Netflix','Perfil')")
        connection.commit(); connection.close()
        customer_fulfillment.initialize_schema()
        connection = sqlite3.connect(self.path)
        cursor = connection.execute("""INSERT INTO customer_order_fulfillments
            (order_id,status,attempt_count,fulfilled_at) VALUES(1,'fulfilled',1,'2026-08-27T00:00:00Z')""")
        connection.execute("""INSERT INTO customer_order_fulfillment_lines
            (fulfillment_id,order_line_id,nube_account_id,nube_profile_id,tipo_unidad,assigned_at,expires_at)
            VALUES(?,1,1,2,'perfil','2026-08-27T00:00:00Z','2026-09-27')""", (cursor.lastrowid,))
        connection.commit(); connection.close()
        customer_delivery_access.initialize_schema()
        recovery.initialize_schema()
        app.config.update(TESTING=True, SECRET_KEY="otp-recovery-test", SESSION_COOKIE_SECURE=False)
        self.client = app.test_client()
        self.now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
        self.requester = "a" * 24
        self.secret = "otp-secret-test"
        self.codes = []

    def tearDown(self):
        database.DB = self.previous_db
        for suffix in ("", "-wal", "-shm"):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def conn(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def email_transport(self, destination, subject, text, html):
        code = re.search(r"\b([0-9]{6})\b", text).group(1)
        self.codes.append(code)
        self.assertNotIn("PRODUCT-SECRET", text + html)
        self.assertNotIn("4321", text + html)
        return True

    def request_email(self, *, now=None, transport=None):
        return recovery.request_order_otp(
            "ORD-RECOVERY-A", "email", self.requester, self.secret,
            email_transport=transport or self.email_transport, now=now or self.now)

    def session_headers(self, client=None, token="new-browser-token"):
        client = client or self.client
        with client.session_transaction() as flask_session:
            flask_session["csrf_customer_checkout"] = "csrf"
            flask_session["customer_checkout_guest_token"] = token
        return {"X-CSRF-Token": "csrf"}

    def start_http_recovery(self, client=None, public_id="ORD-RECOVERY-A"):
        client = client or self.client
        response = client.post("/compras/pedidos/consultar",
            json={"public_order_id": public_id}, headers=self.session_headers(client))
        return response, response.get_json()

    def test_original_session_does_not_request_otp(self):
        response = self.client.post("/compras/pedidos/consultar",
            json={"public_order_id": "ORD-RECOVERY-A"},
            headers=self.session_headers(token=self.owner_token))
        self.assertEqual(response.status_code, 200)
        self.assertIn("order", response.get_json())
        self.assertNotIn("recovery_required", response.get_json())

    def test_new_browser_valid_missing_and_malformed_are_publicly_neutral(self):
        valid, valid_data = self.start_http_recovery(public_id="ORD-RECOVERY-A")
        missing, missing_data = self.start_http_recovery(public_id="ORD-NOT-FOUND")
        malformed, malformed_data = self.start_http_recovery(public_id="bad")
        self.assertEqual((valid.status_code, missing.status_code, malformed.status_code), (200, 200, 200))
        for data in (valid_data, missing_data, malformed_data):
            self.assertTrue(data["recovery_required"])
            self.assertEqual(set(data), {"ok","recovery_required","recovery_id","channels","message"})
        self.assertEqual(len(valid_data["channels"]), len(missing_data["channels"]))
        serialized = repr(valid_data) + repr(missing_data) + repr(malformed_data)
        self.assertNotIn("maria@example.com", serialized)
        self.assertNotIn("+573001234567", serialized)

    def test_email_request_success_hashes_code_and_contains_no_delivery_secrets(self):
        stdout, stderr, logs = io.StringIO(), io.StringIO(), io.StringIO()
        handler = logging.StreamHandler(logs); logging.getLogger().addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = self.request_email()
        finally: logging.getLogger().removeHandler(handler)
        self.assertTrue(result["sent"]); self.assertEqual(len(self.codes), 1)
        connection = self.conn(); row = dict(connection.execute("SELECT * FROM customer_order_otp_challenges").fetchone()); connection.close()
        self.assertNotIn(self.codes[0], repr(row))
        self.assertEqual(len(row["code_hash"]), 64)
        self.assertNotIn(self.codes[0], stdout.getvalue()+stderr.getvalue()+logs.getvalue())

    def test_correct_incorrect_expired_reused_and_attempt_limit(self):
        self.request_email()
        self.assertEqual(recovery.verify_order_otp("ORD-RECOVERY-A","000000",self.requester,self.secret,now=self.now)["reason"], "invalid_code")
        correct = recovery.verify_order_otp("ORD-RECOVERY-A",self.codes[0],self.requester,self.secret,now=self.now)
        self.assertTrue(correct["verified"])
        self.assertFalse(recovery.verify_order_otp("ORD-RECOVERY-A",self.codes[0],self.requester,self.secret,now=self.now)["verified"])
        self.request_email(now=self.now+timedelta(seconds=61))
        expired = recovery.verify_order_otp("ORD-RECOVERY-A",self.codes[-1],self.requester,self.secret,now=self.now+timedelta(seconds=362))
        self.assertEqual(expired["reason"], "expired")
        self.request_email(now=self.now+timedelta(seconds=423))
        for index in range(recovery.OTP_MAX_VERIFY_ATTEMPTS):
            result = recovery.verify_order_otp("ORD-RECOVERY-A","999999",self.requester,self.secret,now=self.now+timedelta(seconds=423))
        self.assertEqual(result["reason"], "too_many_attempts")
        self.assertFalse(recovery.verify_order_otp("ORD-RECOVERY-A",self.codes[-1],self.requester,self.secret,now=self.now+timedelta(seconds=423))["verified"])

    def test_cooldown_and_new_code_invalidates_previous(self):
        self.request_email(); first = self.codes[-1]
        cooldown = self.request_email(now=self.now+timedelta(seconds=10))
        self.assertEqual(cooldown["reason"], "cooldown"); self.assertEqual(len(self.codes), 1)
        self.request_email(now=self.now+timedelta(seconds=61)); second = self.codes[-1]
        self.assertNotEqual(first, second)
        self.assertFalse(recovery.verify_order_otp("ORD-RECOVERY-A",first,self.requester,self.secret,now=self.now+timedelta(seconds=61))["verified"])
        self.assertTrue(recovery.verify_order_otp("ORD-RECOVERY-A",second,self.requester,self.secret,now=self.now+timedelta(seconds=61))["verified"])

    def test_rate_limits_apply_per_order_and_requester(self):
        for index in range(recovery.OTP_ORDER_WINDOW_LIMIT):
            result = self.request_email(now=self.now+timedelta(seconds=61*index))
            self.assertTrue(result["sent"])
        limited = self.request_email(now=self.now+timedelta(seconds=61*recovery.OTP_ORDER_WINDOW_LIMIT))
        self.assertEqual(limited["reason"], "rate_limited")

        connection = self.conn()
        for order_id in range(10, 22):
            connection.execute("INSERT INTO customer_orders VALUES(?,?,?,?,?,?,1,?)", (
                order_id, f"ORD-RATE-{order_id}", "paid", f"rate{order_id}@example.com",
                "+573001234567", "d"*64, "2030-01-01T00:00:00Z"))
        connection.commit(); connection.close()
        other_requester = "e"*24
        sent = 0
        for order_id in range(10, 22):
            result = recovery.request_order_otp(
                f"ORD-RATE-{order_id}", "email", other_requester, self.secret,
                email_transport=self.email_transport, now=self.now)
            sent += int(result["sent"])
            if order_id == 20:
                self.assertEqual(result["reason"], "rate_limited")
                break
        self.assertEqual(sent, recovery.OTP_REQUESTER_WINDOW_LIMIT)

    def test_concurrent_requests_and_verifications_have_one_effective_result(self):
        results=[]; barrier=threading.Barrier(2)
        def ask():
            barrier.wait(); results.append(self.request_email())
        threads=[threading.Thread(target=ask) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(bool(item["sent"]) for item in results), 1)
        verified=[]; barrier=threading.Barrier(2); code=self.codes[0]
        def check():
            barrier.wait(); verified.append(recovery.verify_order_otp("ORD-RECOVERY-A",code,self.requester,self.secret,now=self.now))
        threads=[threading.Thread(target=check) for _ in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(sum(bool(item["verified"]) for item in verified), 1)

    def test_channel_availability_and_whatsapp_injected_transport(self):
        prepared = recovery.prepare_recovery("ORD-RECOVERY-A")
        self.assertEqual([item["channel"] for item in prepared["channels"]], ["email"])
        messages=[]
        result = recovery.request_order_otp("ORD-RECOVERY-A","whatsapp",self.requester,self.secret,
            whatsapp_transport=lambda destination,message: messages.append((destination,message)) or True,now=self.now)
        self.assertTrue(result["sent"]); self.assertEqual(len(messages),1)
        self.assertTrue(messages[0][0].startswith("+57")); self.assertNotIn("PRODUCT-SECRET",messages[0][1])
        unavailable = recovery.request_order_otp("ORD-RECOVERY-B","whatsapp","c"*24,self.secret,now=self.now)
        self.assertEqual(unavailable["reason"],"channel_unavailable")

    def test_transport_failures_are_safe(self):
        result = self.request_email(transport=lambda *_: False)
        self.assertEqual(result["reason"], "transport_error")
        connection=self.conn();row=connection.execute("SELECT status,last_error_code FROM customer_order_otp_challenges").fetchone();connection.close()
        self.assertEqual(tuple(row),("failed","transport_error"))

    def test_http_verification_authorizes_only_one_order_and_delivery(self):
        response, data = self.start_http_recovery()
        self.assertEqual(response.status_code,200)
        capture={}
        def fake_send(destination,code,*_args,**_kwargs): capture["code"]=code; return True
        with mock.patch("customer_order_recovery._send_email",side_effect=fake_send):
            requested=self.client.post("/compras/pedidos/recuperacion/otp/solicitar",
                json={"recovery_id":data["recovery_id"],"channel":"email"},headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(requested.status_code,202)
        before=self.client.get("/compras/pedidos/ORD-RECOVERY-A/entrega",headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(before.status_code,404)
        verified=self.client.post("/compras/pedidos/recuperacion/otp/verificar",
            json={"recovery_id":data["recovery_id"],"code":capture["code"]},headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(verified.status_code,200)
        delivery=self.client.get("/compras/pedidos/ORD-RECOVERY-A/entrega",headers={"X-CSRF-Token":"csrf"})
        other=self.client.get("/compras/pedidos/ORD-RECOVERY-B/entrega",headers={"X-CSRF-Token":"csrf"})
        self.assertEqual((delivery.status_code,other.status_code),(200,404))
        self.assertIn("PRODUCT-SECRET",delivery.get_data(as_text=True));self.assertNotIn("PRODUCT-SECRET",verified.get_data(as_text=True))

    def test_authorization_expires_and_is_order_scoped(self):
        session_data={}
        recovery.authorize_order_access(session_data,"ORD-RECOVERY-A",1,now=self.now)
        self.assertEqual(recovery.authorized_order_id(session_data,"ORD-RECOVERY-A",now=self.now),1)
        self.assertIsNone(recovery.authorized_order_id(session_data,"ORD-RECOVERY-B",now=self.now))
        self.assertIsNone(recovery.authorized_order_id(session_data,"ORD-RECOVERY-A",now=self.now+timedelta(seconds=1801)))

    def test_cookie_security_configuration_and_no_real_whatsapp_provider(self):
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"],"Lax")
        self.assertIn(app.config["SESSION_COOKIE_SECURE"],{True,False})
        self.assertFalse(recovery.whatsapp_configuration()["configured"])


if __name__ == "__main__": unittest.main()
