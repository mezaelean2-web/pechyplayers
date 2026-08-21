import base64
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import threading
import unittest

import app as app_module
import bold_recharges
import database
import resellers
import wallets


class BoldRechargesTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        self.original_env = {key: os.environ.get(key) for key in (
            "BOLD_ENV", "BOLD_IDENTITY_KEY", "BOLD_SECRET_KEY", "BOLD_REDIRECTION_URL"
        )}
        database.DB = self.db_path
        os.environ.update(BOLD_ENV="test", BOLD_IDENTITY_KEY="test_identity", BOLD_SECRET_KEY="test_secret")
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
            imagen TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL, precio TEXT NOT NULL,
            oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999, categoria TEXT DEFAULT 'Streaming',
            orden_categoria INTEGER DEFAULT 999, estado TEXT DEFAULT 'disponible')""")
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); bold_recharges.initialize()
        self.reseller_id = resellers.crear_revendedor("Ana Test", "ana@example.com", "+57 3001234567", "Ana TV", "ClaveSegura123")
        self.other_id = resellers.crear_revendedor("Otro Test", "otro@example.com", "", "", "ClaveSegura123")
        app_module.app.config.update(TESTING=True, SECRET_KEY="bold-tests")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["reseller_id"] = self.reseller_id
            session["reseller_auth_version"] = 1
            session["csrf_reseller"] = "csrf-bold"

    def tearDown(self):
        database.DB = self.original_db
        for key, value in self.original_env.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        os.remove(self.db_path)

    def create(self, amount=50000):
        response = self.client.post("/revendedores/recargas", json={"monto": amount}, headers={"X-CSRF-Token": "csrf-bold"})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["checkout"]

    @staticmethod
    def payload(order_id, amount=50000, currency="COP", event="SALE_APPROVED", transaction="PAY-123", event_id="evt-1"):
        return {"id": event_id, "type": event, "subject": transaction, "source": "/payments/links", "time": 1,
                "data": {"payment_id": transaction, "created_at": "2026-08-20T10:00:00-05:00",
                         "amount": {"currency": currency, "total": amount}, "metadata": {"reference": order_id}}}

    @staticmethod
    def signed(payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"", base64.b64encode(raw), hashlib.sha256).hexdigest()
        return raw, {"Content-Type": "application/json", "X-Bold-Signature": signature}

    @staticmethod
    def signed_raw(raw, key=b"", content_type="application/json"):
        signature = hmac.new(key, base64.b64encode(raw), hashlib.sha256).hexdigest()
        return {"Content-Type": content_type, "X-Bold-Signature": signature}

    def post_payload(self, payload):
        raw, headers = self.signed(payload)
        return self.client.post("/webhooks/bold", data=raw, headers=headers)

    def events(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM bold_webhook_events ORDER BY id"
            ).fetchall()]
        finally:
            conn.close()

    def counts(self):
        conn = sqlite3.connect(self.db_path)
        try:
            intent = conn.execute("SELECT estado FROM reseller_recharge_intents ORDER BY id DESC LIMIT 1").fetchone()
            return (conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions").fetchone()[0],
                    conn.execute("SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (self.reseller_id,)).fetchone()[0],
                    intent[0] if intent else None)
        finally:
            conn.close()

    def test_create_requires_session_csrf_active_and_valid_integer_limits(self):
        anon = app_module.app.test_client()
        self.assertEqual(anon.post("/revendedores/recargas", json={"monto": 50000}).status_code, 401)
        self.assertEqual(self.client.post("/revendedores/recargas", json={"monto": 50000}).status_code, 403)
        for value in ("50000.5", -1, 0, 9999, 2000001, True):
            with self.subTest(value=value):
                self.assertEqual(self.client.post("/revendedores/recargas", json={"monto": value}, headers={"X-CSRF-Token": "csrf-bold"}).status_code, 400)
        self.assertEqual(self.counts()[0:2], (0, 0))
        resellers.cambiar_estado_revendedor(self.reseller_id, "bloqueado")
        self.assertEqual(self.client.post("/revendedores/recargas", json={"monto": 50000}, headers={"X-CSRF-Token": "csrf-bold"}).status_code, 401)

    def test_checkout_data_signature_and_secret_never_returned(self):
        checkout = self.create()
        self.assertRegex(checkout["orderId"], r"^RCH-[a-f0-9]{32}$")
        expected = hashlib.sha256(f'{checkout["orderId"]}50000COPtest_secret'.encode()).hexdigest()
        self.assertEqual(checkout["integritySignature"], expected)
        self.assertEqual(checkout["apiKey"], "test_identity")
        self.assertNotIn("test_secret", json.dumps(checkout))
        self.assertEqual(self.counts(), (0, 0, "pending"))

    def test_configuracion_test_incompleta_o_produccion_fallan_controladamente(self):
        os.environ["BOLD_IDENTITY_KEY"] = ""
        response = self.client.post(
            "/revendedores/recargas", json={"monto": 10000},
            headers={"X-CSRF-Token": "csrf-bold"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("Bold TEST", response.get_json()["error"])

        os.environ.update(BOLD_ENV="production", BOLD_IDENTITY_KEY="test_identity")
        response = self.client.post(
            "/revendedores/recargas", json={"monto": 10000},
            headers={"X-CSRF-Token": "csrf-bold"}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("BOLD_ENV=test", response.get_json()["error"])

    def test_redirection_url_configurable_sin_dominio_hardcodeado(self):
        os.environ["BOLD_REDIRECTION_URL"] = "https://pruebas.example/retorno-bold"
        checkout = self.create(10000)
        self.assertEqual(checkout["redirectionUrl"], "https://pruebas.example/retorno-bold")

    def test_redirection_url_se_omite_si_no_esta_configurada(self):
        os.environ["BOLD_REDIRECTION_URL"] = ""
        checkout = self.create(10000)
        self.assertNotIn("redirectionUrl", checkout)

    def test_webhook_signature_payload_mismatch_and_unknown_do_not_credit(self):
        checkout = self.create(); payload = self.payload(checkout["orderId"])
        raw, headers = self.signed(payload)
        self.assertEqual(self.client.post("/webhooks/bold", data=raw).status_code, 400)
        self.assertEqual(self.client.post("/webhooks/bold", data=raw + b" ", headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/webhooks/bold", data=b"not-json", headers=self.signed({})[1]).status_code, 400)
        for changed in ({"amount": 49999}, {"currency": "USD"}, {"event": "SALE_REJECTED"}):
            current = self.payload(checkout["orderId"], **changed); body, signed_headers = self.signed(current)
            self.assertEqual(self.client.post("/webhooks/bold", data=body, headers=signed_headers).status_code, 200)
        self.assertEqual(self.counts()[0:2], (0, 0))

    def test_approved_ten_times_credits_exactly_once_and_owner_isolated(self):
        checkout = self.create(); payload = self.payload(checkout["orderId"]); raw, headers = self.signed(payload)
        results = [self.client.post("/webhooks/bold", data=raw, headers=headers).get_json()["status"] for _ in range(10)]
        self.assertEqual(results[0], "processed"); self.assertEqual(results[1:], ["duplicate"] * 9)
        self.assertEqual(self.counts(), (1, 50000, "approved"))
        with self.client.session_transaction() as session:
            session["reseller_id"] = self.other_id; session["reseller_auth_version"] = 1
        self.assertEqual(self.client.get(f'/revendedores/recargas/{checkout["orderId"]}/estado').status_code, 404)

    def test_ten_concurrent_approved_events_credit_once(self):
        checkout = self.create(); payload = self.payload(checkout["orderId"])
        barrier = threading.Barrier(10); results = []; lock = threading.Lock()
        def worker():
            barrier.wait()
            try: result = bold_recharges.process_webhook(payload)["status"]
            except Exception as error: result = type(error).__name__
            with lock: results.append(result)
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(results.count("processed"), 1)
        self.assertEqual(results.count("duplicate"), 9)
        self.assertEqual(self.counts(), (1, 50000, "approved"))

    def test_atomic_rollback_if_intent_cannot_be_approved(self):
        checkout = self.create()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TRIGGER fail_intent BEFORE UPDATE ON reseller_recharge_intents
                        WHEN NEW.estado='approved' BEGIN SELECT RAISE(ABORT, 'fail intent'); END""")
        conn.commit(); conn.close()
        with self.assertRaises(sqlite3.IntegrityError):
            bold_recharges.process_webhook(self.payload(checkout["orderId"]))
        self.assertEqual(self.counts(), (0, 0, "pending"))
        self.assertEqual(self.events(), [])

    def test_endpoint_rechaza_firma_header_content_type_utf8_y_json_invalidos(self):
        checkout = self.create()
        payload = self.payload(checkout["orderId"])
        raw = json.dumps(payload, separators=(",", ":")).encode()
        self.assertEqual(self.client.post("/webhooks/bold", data=raw).status_code, 400)
        self.assertEqual(self.client.post("/webhooks/bold", data=raw, headers={
            "Content-Type": "application/json", "X-Bold-Signature": "0" * 64
        }).status_code, 400)
        self.assertEqual(self.client.post("/webhooks/bold", data=raw, headers=self.signed_raw(
            raw, content_type="text/plain"
        )).status_code, 415)
        invalid_utf8 = b"\xff\xfe"
        self.assertEqual(self.client.post("/webhooks/bold", data=invalid_utf8,
            headers=self.signed_raw(invalid_utf8)).status_code, 400)
        invalid_json = b'{"id":'
        self.assertEqual(self.client.post("/webhooks/bold", data=invalid_json,
            headers=self.signed_raw(invalid_json)).status_code, 400)
        self.assertEqual(self.counts()[0:2], (0, 0))
        self.assertEqual(self.events(), [])

    def test_firma_test_vacia_y_produccion_ficticia_estan_aisladas(self):
        raw = b'{"test":true}'
        os.environ.update(BOLD_ENV="test", BOLD_SECRET_KEY="secret_test_no_usado")
        empty_signature = self.signed_raw(raw)["X-Bold-Signature"]
        secret_signature = self.signed_raw(raw, b"secret_test_no_usado")["X-Bold-Signature"]
        self.assertTrue(bold_recharges.valid_signature(raw, empty_signature))
        self.assertFalse(bold_recharges.valid_signature(raw, secret_signature))
        os.environ.update(BOLD_ENV="production", BOLD_SECRET_KEY="prod_secret_ficticio")
        prod_signature = self.signed_raw(raw, b"prod_secret_ficticio")["X-Bold-Signature"]
        self.assertTrue(bold_recharges.valid_signature(raw, prod_signature))
        self.assertFalse(bold_recharges.valid_signature(raw, empty_signature))

    def test_event_id_invalido_nunca_se_registra_ni_acredita(self):
        checkout = self.create()
        for event_id in (None, "", 123):
            with self.subTest(event_id=event_id):
                payload = self.payload(checkout["orderId"], event_id="temporal")
                payload["id"] = event_id
                self.assertEqual(self.post_payload(payload).status_code, 400)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.counts(), (0, 0, "pending"))

    def test_payment_id_y_metadata_invalidos_quedan_ignorados_sin_dinero(self):
        checkout = self.create()
        variants = [
            ("evt-pay-none", {"payment_id": None}, "invalid_payment_id"),
            ("evt-pay-int", {"payment_id": 99}, "invalid_payment_id"),
            ("evt-meta-none", {"metadata": None}, "invalid_reference"),
            ("evt-meta-list", {"metadata": []}, "invalid_reference"),
            ("evt-ref-int", {"metadata": {"reference": 8}}, "invalid_reference"),
        ]
        for event_id, changes, reason in variants:
            payload = self.payload(checkout["orderId"], event_id=event_id,
                                   transaction=f"PAY-{event_id}")
            payload["data"].update(changes)
            response = self.post_payload(payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["reason"], reason)
        self.assertTrue(all(row["processing_status"] == "ignored" for row in self.events()))
        self.assertEqual(self.counts(), (0, 0, "pending"))

    def test_orden_desconocida_y_ambiente_inconsistente_quedan_auditados(self):
        unknown = self.payload("RCH-no-existe", event_id="evt-unknown", transaction="PAY-U")
        self.assertEqual(self.post_payload(unknown).get_json()["reason"], "unknown_order")
        checkout = self.create()
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE reseller_recharge_intents SET environment='production' WHERE order_id=?",
                     (checkout["orderId"],))
        conn.commit(); conn.close()
        mismatch = self.payload(checkout["orderId"], event_id="evt-env", transaction="PAY-E")
        self.assertEqual(self.post_payload(mismatch).get_json()["reason"], "environment_mismatch")
        self.assertEqual([row["result_reason"] for row in self.events()],
                         ["unknown_order", "environment_mismatch"])
        self.assertEqual(self.counts()[0:2], (0, 0))

    def test_revendedor_inexistente_no_acredita_y_queda_auditado(self):
        checkout = self.create()
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM revendedores WHERE id=?", (self.reseller_id,))
        conn.commit(); conn.close()
        response = self.post_payload(self.payload(
            checkout["orderId"], event_id="evt-no-reseller", transaction="PAY-NR"
        ))
        self.assertEqual(response.get_json()["reason"], "unknown_reseller")
        self.assertEqual(self.events()[0]["processing_status"], "ignored")

    def test_rechazo_valido_se_audita_y_nunca_acredita(self):
        checkout = self.create()
        response = self.post_payload(self.payload(
            checkout["orderId"], event="SALE_REJECTED", event_id="evt-rejected",
            transaction="PAY-REJECTED"
        ))
        self.assertEqual(response.get_json()["reason"], "sale_rejected")
        self.assertEqual(self.counts(), (0, 0, "rejected"))
        self.assertEqual(self.events()[0]["processing_status"], "processed")

    def test_monto_y_moneda_incorrectos_quedan_auditados(self):
        checkout = self.create()
        amount = self.payload(checkout["orderId"], amount=49999,
                              event_id="evt-amount", transaction="PAY-A")
        currency = self.payload(checkout["orderId"], currency="USD",
                                event_id="evt-currency", transaction="PAY-C")
        self.assertEqual(self.post_payload(amount).get_json()["reason"], "amount_mismatch")
        self.assertEqual(self.post_payload(currency).get_json()["reason"], "currency_mismatch")
        self.assertEqual(self.counts(), (0, 0, "pending"))

    def test_evento_duplicado_y_eventos_distintos_mismo_pago_acreditan_una_vez(self):
        checkout = self.create()
        first = self.payload(checkout["orderId"], event_id="evt-first", transaction="PAY-ONE")
        self.assertEqual(self.post_payload(first).get_json()["reason"], "sale_approved")
        self.assertEqual(self.post_payload(first).get_json()["reason"], "duplicate_event")
        second = self.payload(checkout["orderId"], event_id="evt-second", transaction="PAY-ONE")
        self.assertEqual(self.post_payload(second).get_json()["reason"], "duplicate_payment")
        self.assertEqual(self.counts(), (1, 50000, "approved"))
        self.assertEqual(len(self.events()), 2)

    def test_mismo_payment_id_en_dos_ordenes_no_acredita_la_segunda(self):
        first = self.create(50000)
        second = self.create(50000)
        self.assertEqual(self.post_payload(self.payload(
            first["orderId"], event_id="evt-order-1", transaction="PAY-SHARED"
        )).get_json()["reason"], "sale_approved")
        response = self.post_payload(self.payload(
            second["orderId"], event_id="evt-order-2", transaction="PAY-SHARED"
        ))
        self.assertEqual(response.get_json()["reason"], "duplicate_payment")
        conn = sqlite3.connect(self.db_path)
        states = [row[0] for row in conn.execute(
            "SELECT estado FROM reseller_recharge_intents ORDER BY id"
        ).fetchall()]
        conn.close()
        self.assertEqual(states, ["approved", "pending"])
        self.assertEqual(self.counts()[0:2], (1, 50000))

    def test_voids_y_evento_desconocido_se_auditan_sin_movimiento(self):
        checkout = self.create()
        approved = self.payload(checkout["orderId"], event="SALE_APPROVED",
                                event_id="evt-approved-before-void", transaction="PAY-VOID")
        self.assertEqual(self.post_payload(approved).get_json()["reason"], "sale_approved")
        for event, event_id in (("VOID_APPROVED", "evt-va"),
                                ("VOID_REJECTED", "evt-vr"),
                                ("NEW_EVENT", "evt-new")):
            response = self.post_payload(self.payload(
                checkout["orderId"], event=event, event_id=event_id,
                transaction="PAY-VOID"
            ))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.counts(), (1, 50000, "approved"))
        self.assertEqual([row["result_reason"] for row in self.events()], [
            "sale_approved",
            "void_recorded_no_financial_action",
            "void_recorded_no_financial_action", "unknown_event"
        ])

    def test_respuestas_y_logs_webhook_no_exponen_secretos(self):
        checkout = self.create()
        secret = os.environ["BOLD_SECRET_KEY"]
        with self.assertLogs(app_module.app.logger, level="INFO") as captured:
            response = self.post_payload(self.payload(
                checkout["orderId"], event_id="evt-log", transaction="PAY-LOG"
            ))
        combined = response.get_data(as_text=True) + "\n".join(captured.output)
        self.assertNotIn(secret, combined)
        self.assertNotIn(os.environ["BOLD_IDENTITY_KEY"], combined)
        self.assertIn("duration_ms=", combined)

    def test_dos_eventos_concurrentes_distintos_para_mismo_pago_acreditan_una_vez(self):
        checkout = self.create()
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()
        def worker(number):
            barrier.wait()
            result = bold_recharges.process_webhook(self.payload(
                checkout["orderId"], event_id=f"evt-concurrent-{number}",
                transaction="PAY-CONCURRENT"
            ))
            with lock:
                results.append(result["reason"])
        threads = [threading.Thread(target=worker, args=(number,)) for number in (1, 2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertIn("sale_approved", results)
        self.assertIn("duplicate_payment", results)
        self.assertEqual(self.counts(), (1, 50000, "approved"))


if __name__ == "__main__":
    unittest.main()
