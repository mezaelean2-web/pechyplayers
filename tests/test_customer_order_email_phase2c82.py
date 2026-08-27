try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock

import customer_order_email
import database


class CustomerOrderEmailPhase2C82Test(unittest.TestCase):
    def setUp(self):
        descriptor,self.path=tempfile.mkstemp(suffix=".db");os.close(descriptor)
        self.previous_db=database.DB;database.DB=self.path
        self.previous_env={key:os.environ.get(key) for key in ("ORDER_EMAIL_PROVIDER","ORDER_EMAIL_API_KEY","ORDER_EMAIL_FROM","ORDER_EMAIL_FROM_NAME")}
        os.environ.update(ORDER_EMAIL_PROVIDER="resend",ORDER_EMAIL_API_KEY="test-secret-never-send",ORDER_EMAIL_FROM="pedidos@pechy.org",ORDER_EMAIL_FROM_NAME="PECHY PLAYERS")
        conn=sqlite3.connect(self.path)
        conn.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE customer_orders(id INTEGER PRIMARY KEY,public_order_id TEXT,status TEXT,
          customer_first_name TEXT,customer_email TEXT);
        CREATE TABLE customer_order_fulfillments(id INTEGER PRIMARY KEY,order_id INTEGER,status TEXT);
        CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,estado TEXT);
        CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,tipo TEXT);
        INSERT INTO customer_orders VALUES(1,'ORD-EMAIL-ONE','paid','Ana','Compras@Example.com');
        INSERT INTO customer_orders VALUES(2,'ORD-HISTORIC','paid','Luis',NULL);
        INSERT INTO customer_order_fulfillments VALUES(1,1,'fulfilled');
        INSERT INTO nube_cuentas VALUES(10,'asignada');
        INSERT INTO nube_movimientos VALUES(20,'venta_cliente_final');
        """);conn.commit();conn.close()
        customer_order_email.initialize_schema()

    def tearDown(self):
        database.DB=self.previous_db
        for key,value in self.previous_env.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        for suffix in ("","-wal","-shm"):
            try:os.remove(self.path+suffix)
            except FileNotFoundError:pass

    def rows(self,sql,args=()):
        conn=sqlite3.connect(self.path);conn.row_factory=sqlite3.Row
        try:return [dict(row) for row in conn.execute(sql,args)]
        finally:conn.close()

    @staticmethod
    def success(captured=None):
        def transport(payload,api_key,timeout,idempotency_key):
            if captured is not None:captured.update(payload=payload,api_key=api_key,timeout=timeout,idempotency_key=idempotency_key)
            return 200,json.dumps({"id":"resend-message-1"}).encode()
        return transport

    def test_exito_usa_snapshot_configuracion_y_guarda_id_proveedor(self):
        captured={};result=customer_order_email.send_payment_confirmation(1,transport=self.success(captured))
        self.assertEqual(result["status"],"sent")
        self.assertEqual(captured["payload"]["to"],["Compras@Example.com"])
        self.assertEqual(captured["payload"]["from"],"PECHY PLAYERS <pedidos@pechy.org>")
        self.assertEqual(captured["timeout"],8)
        self.assertEqual(captured["idempotency_key"],"customer-order-1-payment_confirmed")
        row=self.rows("SELECT * FROM customer_order_notifications")[0]
        self.assertEqual((row["status"],row["attempt_count"],row["provider_message_id"]),("sent",1,"resend-message-1"));self.assertIsNotNone(row["sent_at"])

    def test_contenido_html_texto_nombre_y_ord_sin_credenciales(self):
        captured={};customer_order_email.send_payment_confirmation(1,transport=self.success(captured));payload=captured["payload"]
        for field in ("subject","text","html"):self.assertIn("ORD-EMAIL-ONE",payload[field])
        self.assertIn("Ana",payload["text"]);self.assertIn("Ana",payload["html"]);self.assertIn("Consultar mi pedido",payload["text"])
        serialized=json.dumps(payload).lower()
        for forbidden in ("contrasena","contraseña","password","pin","account_id","profile_id","fulfillment_line_id","guest_session_hash","guest_token"):
            self.assertNotIn(forbidden,serialized)
        self.assertNotIn("href=",payload["html"].lower())

    def test_sent_y_segundo_intento_explicito_no_reenvian(self):
        calls=[];transport=lambda *args:(calls.append(1) or (200,b'{"id":"one"}'))
        self.assertEqual(customer_order_email.send_payment_confirmation(1,transport=transport)["status"],"sent")
        self.assertEqual(customer_order_email.send_payment_confirmation(1,retry_failed=True,transport=transport)["reason"],"already_sent")
        self.assertEqual(len(calls),1);self.assertEqual(len(self.rows("SELECT * FROM customer_order_notifications")),1)

    def test_historico_sin_email_no_envia(self):
        transport=mock.Mock();result=customer_order_email.send_payment_confirmation(2,transport=transport)
        self.assertEqual(result,{"status":"failed","reason":"missing_customer_email"});transport.assert_not_called()

    def test_configuracion_incompleta_o_proveedor_incorrecto_no_envia(self):
        for index,(key,value,reason) in enumerate((("ORDER_EMAIL_PROVIDER","smtp","provider_not_configured"),("ORDER_EMAIL_API_KEY","","email_configuration_missing"))):
            with self.subTest(key=key):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                os.environ[key]=value;transport=mock.Mock()
                result=customer_order_email.send_payment_confirmation(1,transport=transport)
                self.assertEqual(result["reason"],reason);transport.assert_not_called()
                os.environ.update(ORDER_EMAIL_PROVIDER="resend",ORDER_EMAIL_API_KEY="test-secret-never-send")

    def test_http_y_respuestas_invalidas_fallan_sin_mutar_negocio(self):
        cases=tuple((status,b"{}",f"provider_http_{status}") for status in (400,401,403,404,409,422,429,500,502,503))+((200,b"no-json","provider_invalid_response"),(200,b"{}","provider_invalid_response"))
        for status,body,reason in cases:
            with self.subTest(status=status,body=body):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");before={t:conn.execute("SELECT * FROM "+t).fetchall() for t in ("customer_orders","customer_order_fulfillments","nube_cuentas","nube_movimientos")};conn.commit();conn.close()
                result=customer_order_email.send_payment_confirmation(1,transport=lambda *_:(status,body))
                self.assertEqual(result["reason"],reason)
                conn=sqlite3.connect(self.path);after={t:conn.execute("SELECT * FROM "+t).fetchall() for t in before};conn.close();self.assertEqual(before,after)

    def test_timeout_red_y_excepcion_son_codigos_seguros(self):
        def timeout(*_):raise TimeoutError()
        def network(*_):raise OSError("network secret should not persist")
        def unexpected(*_):raise RuntimeError("unexpected secret should not persist")
        for transport,reason in ((timeout,"provider_timeout"),(network,"provider_network_error"),(unexpected,"provider_unexpected_error")):
            conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
            self.assertEqual(customer_order_email.send_payment_confirmation(1,transport=transport)["reason"],reason)
            self.assertEqual(self.rows("SELECT last_error_code FROM customer_order_notifications")[0]["last_error_code"],reason)

    def test_urllib_httperror_con_body_ilegible_conserva_status(self):
        class BodyThatMustNotBeRead:
            def read(self,*_):raise AssertionError("El body de error no debe leerse")
            def close(self):pass
        for status in (400,401,403,404,409,422,429,500,502,503):
            with self.subTest(status=status):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                def fail(*_,code=status):raise urllib.error.HTTPError("https://api.resend.com/emails",code,"redacted",{},BodyThatMustNotBeRead())
                self.assertEqual(customer_order_email.send_payment_confirmation(1,transport=fail)["reason"],f"provider_http_{status}")

    def test_httperror_combina_status_y_nombre_allowlisted(self):
        cases=((400,"validation_error"),(400,"invalid_idempotency_key"),(403,"invalid_api_key"),(422,"invalid_from_address"))
        for status,name in cases:
            with self.subTest(status=status,name=name):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                body=json.dumps({"statusCode":status,"name":name,"message":"FAKE_SECRET_DO_NOT_LEAK fake-person@example.invalid FAKE_PASSWORD_DO_NOT_LEAK"}).encode()
                def fail(*_,code=status,data=body):raise urllib.error.HTTPError("https://api.resend.com/emails",code,"redacted",{},__import__("io").BytesIO(data))
                result=customer_order_email.send_payment_confirmation(1,transport=fail)
                suffix = "validation_error_unknown" if name == "validation_error" else name
                expected=f"provider_http_{status}_{suffix}"
                self.assertEqual(result["reason"],expected);self.assertEqual(self.rows("SELECT last_error_code FROM customer_order_notifications")[0]["last_error_code"],expected)

    def test_clasificador_validation_error_es_cerrado_y_ambiguo_falla_unknown(self):
        cases = (
            ("The `from` field is invalid.", "from"),
            ("The `to` field contains an invalid address.", "to"),
            ("The `subject` field is required.", "subject"),
            ("The `html` field must be a string.", "html"),
            ("The `text` field must be a string.", "text"),
            (None, "unknown"), (123, "unknown"), ("", "unknown"),
            ("unrecognized provider detail", "unknown"),
            ("FAKE_SECRET_DO_NOT_LEAK fake-person@example.invalid", "unknown"),
            ("The `from` and `to` fields are invalid.", "unknown"),
            ("x" * 20000, "unknown"),
        )
        for message, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(
                    customer_order_email.classify_resend_validation_message(message),
                    expected,
                )

    def test_httperror_validation_error_clasifica_campos_sin_filtrar_message(self):
        secrets = (
            "FAKE_SECRET_DO_NOT_LEAK", "fake-person@example.invalid",
            "FAKE_PASSWORD_DO_NOT_LEAK", "FAKE_API_KEY_DO_NOT_LEAK",
        )
        for field in customer_order_email.SAFE_RESEND_VALIDATION_FIELDS:
            with self.subTest(field=field):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                message=f"The `{field}` field contains {' '.join(secrets)}"
                body=json.dumps({"statusCode":400,"name":"validation_error","message":message}).encode()
                def fail(*_,data=body):
                    raise urllib.error.HTTPError("https://api.resend.com/emails",400,"redacted",{},io.BytesIO(data))
                stdout=io.StringIO();stderr=io.StringIO()
                with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                    result=customer_order_email.send_payment_confirmation(1,transport=fail)
                expected=f"provider_http_400_validation_error_{field}"
                self.assertEqual(result,{"status":"failed","reason":expected})
                persisted=repr(self.rows("SELECT * FROM customer_order_notifications"))
                exposed=repr(result)+persisted+stdout.getvalue()+stderr.getvalue()
                for secret in secrets:
                    self.assertNotIn(secret,exposed)

    def test_httperror_validation_error_unknown_cubre_message_inseguro(self):
        messages=(None,123,"","unexpected FAKE_SECRET_DO_NOT_LEAK fake-person@example.invalid",
                  "The `from` and `to` fields contain FAKE_PASSWORD_DO_NOT_LEAK")
        for message in messages:
            with self.subTest(message_type=type(message).__name__):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                body=json.dumps({"statusCode":400,"name":"validation_error","message":message}).encode()
                def fail(*_,data=body):
                    raise urllib.error.HTTPError("https://api.resend.com/emails",400,"redacted",{},io.BytesIO(data))
                result=customer_order_email.send_payment_confirmation(1,transport=fail)
                self.assertEqual(result["reason"],"provider_http_400_validation_error_unknown")
                persisted=repr(self.rows("SELECT * FROM customer_order_notifications"))
                for forbidden in ("FAKE_SECRET_DO_NOT_LEAK","fake-person@example.invalid","FAKE_PASSWORD_DO_NOT_LEAK"):
                    self.assertNotIn(forbidden,persisted)

    def test_httperror_body_no_confiable_usa_fallback_y_no_filtra(self):
        bodies=(b"",b"not-json",b"[]",b'"string"',b'{"statusCode":400}',b'{"name":123}',b'{"name":"unknown_name"}',
                b'{"name":"unknown_name","message":"FAKE_SECRET_DO_NOT_LEAK fake-person@example.invalid FAKE_PASSWORD_DO_NOT_LEAK"}')
        for index,body in enumerate(bodies):
            with self.subTest(index=index):
                conn=sqlite3.connect(self.path);conn.execute("DELETE FROM customer_order_notifications");conn.commit();conn.close()
                def fail(*_,data=body):raise urllib.error.HTTPError("https://api.resend.com/emails",400,"redacted",{},__import__("io").BytesIO(data))
                result=customer_order_email.send_payment_confirmation(1,transport=fail)
                self.assertEqual(result["reason"],"provider_http_400")
                serialized=repr(self.rows("SELECT * FROM customer_order_notifications"))
                for forbidden in ("FAKE_SECRET_DO_NOT_LEAK","fake-person@example.invalid","FAKE_PASSWORD_DO_NOT_LEAK","unknown_name"):
                    self.assertNotIn(forbidden,serialized)

    def test_parser_diagnostico_allowlist_no_expone_message_ni_body(self):
        documented=("invalid_idempotency_key","validation_error","missing_required_field","invalid_from_address","restricted_api_key","invalid_api_key")
        for name in documented:
            body=json.dumps({"statusCode":400,"name":name,"message":"email@example.com secret-api-key arbitrary detail"}).encode()
            self.assertEqual(customer_order_email.diagnostic_resend_error_name(body),name)
        for body in (b"",b"not-json",b"[]",b'{"name":"invented_error","message":"secret"}',b'{"message":"secret"}'):
            self.assertIsNone(customer_order_email.diagnostic_resend_error_name(body))

    def test_concurrencia_no_duplica_registro_ni_http(self):
        entered=threading.Event();release=threading.Event();calls=[];results=[]
        def slow(*_):calls.append(1);entered.set();release.wait(5);return 200,b'{"id":"concurrent-one"}'
        first=threading.Thread(target=lambda:results.append(customer_order_email.send_payment_confirmation(1,transport=slow)));first.start();self.assertTrue(entered.wait(3))
        second=threading.Thread(target=lambda:results.append(customer_order_email.send_payment_confirmation(1,transport=slow)));second.start();second.join(3);release.set();first.join(3)
        self.assertEqual(len(calls),1);self.assertEqual(len(self.rows("SELECT * FROM customer_order_notifications")),1)
        self.assertEqual(self.rows("SELECT status FROM customer_order_notifications")[0]["status"],"sent")

    def test_failed_solo_reintenta_de_forma_explicita(self):
        customer_order_email.send_payment_confirmation(1,transport=lambda *_:(500,b"{}"));transport=mock.Mock(side_effect=self.success())
        self.assertEqual(customer_order_email.send_payment_confirmation(1,transport=transport)["reason"],"already_failed");transport.assert_not_called()
        self.assertEqual(customer_order_email.send_payment_confirmation(1,retry_failed=True,transport=self.success())["status"],"sent")
        self.assertEqual(self.rows("SELECT attempt_count FROM customer_order_notifications")[0]["attempt_count"],2)

    def test_tests_bloquean_red_real_y_no_persisten_secretos(self):
        with mock.patch("customer_order_email._post_resend") as real_transport:
            result=customer_order_email.send_payment_confirmation(1)
        real_transport.assert_not_called();self.assertEqual(result["reason"],"test_network_blocked")
        raw=" ".join(str(value) for row in self.rows("SELECT * FROM customer_order_notifications") for value in row.values())
        self.assertNotIn("test-secret-never-send",raw);self.assertNotIn("Compras@Example.com",raw)

    def test_schema_idempotente_y_reinicio_no_envia(self):
        with mock.patch("customer_order_email._post_resend") as transport:
            customer_order_email.initialize_schema();customer_order_email.initialize_schema()
        transport.assert_not_called();self.assertEqual(self.rows("SELECT COUNT(*) AS n FROM customer_order_notifications")[0]["n"],0)
        sql=self.rows("SELECT sql FROM sqlite_master WHERE name='customer_order_notifications'")[0]["sql"]
        self.assertIn("UNIQUE(order_id, notification_type)",sql)

    def test_admin_expone_solo_estado_seguro(self):
        customer_order_email.send_payment_confirmation(1,transport=self.success())
        admin=customer_order_email.get_admin(1)
        self.assertEqual((admin["status"],admin["provider"],admin["attempt_count"]),("sent","resend",1))
        serialized=json.dumps(admin)
        self.assertNotIn("Compras@Example.com",serialized);self.assertNotIn("test-secret-never-send",serialized)

    def test_request_real_construye_headers_oficiales_sin_exponer_secretos(self):
        captured={}
        class Response:
            status=200
            def read(self):return b'{"id":"request-one"}'
            def __enter__(self):return self
            def __exit__(self,*_):return False
        def fake_urlopen(request,timeout):captured.update(request=request,timeout=timeout);return Response()
        with mock.patch("urllib.request.urlopen",side_effect=fake_urlopen):
            status,body=customer_order_email._post_resend({"from":"PECHY PLAYERS <pedidos@pechy.org>","to":["fake@example.com"],"subject":"test","html":"<p>test</p>","text":"test"},"fake-api-key",8,"customer-order-1-payment_confirmed")
        headers={key.lower():value for key,value in captured["request"].header_items()}
        self.assertEqual(captured["request"].method,"POST");self.assertEqual(captured["request"].full_url,"https://api.resend.com/emails")
        self.assertEqual(headers["content-type"],"application/json");self.assertEqual(headers["user-agent"],"PECHY-PLAYERS/1.0")
        self.assertEqual(headers["idempotency-key"],"customer-order-1-payment_confirmed");self.assertEqual(status,200);self.assertIn(b"request-one",body)


if __name__ == "__main__":unittest.main()
