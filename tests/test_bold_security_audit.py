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

import app as app_module
import bold_recharges
import database
import resellers


class BoldSecurityAuditTest(unittest.TestCase):
    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        self.original_env = {key: os.environ.get(key) for key in (
            "BOLD_ENV", "BOLD_IDENTITY_KEY", "BOLD_SECRET_KEY", "BOLD_REDIRECTION_URL"
        )}
        database.DB = self.db_path
        os.environ.update(
            BOLD_ENV="production", BOLD_IDENTITY_KEY="audit_identity_ficticia",
            BOLD_SECRET_KEY="audit_secret_ficticio", BOLD_REDIRECTION_URL="",
        )
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (
            id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, imagen TEXT NOT NULL DEFAULT '',
            plan TEXT NOT NULL, precio TEXT NOT NULL, oferta_precio TEXT,
            oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999,
            categoria TEXT DEFAULT 'Streaming', orden_categoria INTEGER DEFAULT 999,
            estado TEXT DEFAULT 'disponible')""")
        conn.commit(); conn.close()
        resellers.inicializar_revendedores(); bold_recharges.initialize()
        self.reseller_a = resellers.crear_revendedor(
            "Audit A", "audit-a@example.com", "", "", "ClaveSegura123"
        )
        self.reseller_b = resellers.crear_revendedor(
            "Audit B", "audit-b@example.com", "", "", "ClaveSegura123"
        )
        app_module.app.config.update(TESTING=True, SECRET_KEY="bold-audit-tests")
        self.client = app_module.app.test_client()
        self.login(self.reseller_a)

    def tearDown(self):
        database.DB = self.original_db
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        os.remove(self.db_path)

    def login(self, reseller_id):
        with self.client.session_transaction() as session:
            session["reseller_id"] = reseller_id
            session["reseller_auth_version"] = 1
            session["csrf_reseller"] = "csrf-audit"

    def create(self, reseller_id=None, amount=10000):
        if reseller_id is not None:
            self.login(reseller_id)
        response = self.client.post(
            "/revendedores/recargas", json={"monto": amount},
            headers={"X-CSRF-Token": "csrf-audit"},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["checkout"]

    @staticmethod
    def payload(order_id, *, total=10000, currency="COP", event="SALE_APPROVED",
                payment="PAY-AUDIT", event_id="EVT-AUDIT"):
        return {
            "id": event_id, "type": event,
            "data": {"payment_id": payment, "amount": {"total": total, "currency": currency},
                     "metadata": {"reference": order_id}},
        }

    @staticmethod
    def signed_headers(raw, key=b"audit_secret_ficticio", content_type="application/json"):
        signature = hmac.new(key, base64.b64encode(raw), hashlib.sha256).hexdigest()
        return {"Content-Type": content_type, "X-Bold-Signature": signature}

    def post(self, payload):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return self.client.post("/webhooks/bold", data=raw, headers=self.signed_headers(raw))

    def snapshot(self):
        conn = sqlite3.connect(self.db_path)
        result = {
            "wallets": conn.execute(
                "SELECT revendedor_id, saldo FROM reseller_wallets ORDER BY revendedor_id"
            ).fetchall(),
            "ledger": conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions").fetchone()[0],
            "intents": conn.execute(
                "SELECT order_id, estado, external_transaction_id FROM reseller_recharge_intents ORDER BY id"
            ).fetchall(),
        }
        conn.close()
        return result

    def test_redirect_parameters_are_read_only_and_owner_scoped(self):
        checkout = self.create(self.reseller_a)
        order = checkout["orderId"]
        before = self.snapshot()
        queries = (
            "", "?bold-tx-status=approved", f"?bold-order-id={order}&bold-tx-status=approved",
            "?bold-order-id=RCH-inventado", f"?bold-order-id={order}&bold-order-id=RCH-otro",
            "?bold-tx-status[]=approved", "?bold-tx-status=unexpected&other=1",
        )
        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/revendedores/recargas/resultado" + query).status_code, 200)
                self.assertEqual(self.snapshot(), before)
        self.login(self.reseller_b)
        response = self.client.get(f"/revendedores/recargas/resultado?bold-order-id={order}&bold-tx-status=approved")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Recarga aprobada", response.get_data(as_text=True))
        self.assertEqual(self.client.get(f"/revendedores/recargas/{order}/estado").status_code, 404)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_webhook_auth_and_bodies_never_credit(self):
        order = self.create()["orderId"]
        payload = self.payload(order)
        raw = json.dumps(payload, separators=(",", ":")).encode()
        valid = self.signed_headers(raw)
        cases = (
            (raw, {"Content-Type": "application/json"}),
            (raw, {"Content-Type": "application/json", "X-Bold-Signature": ""}),
            (raw, {"Content-Type": "application/json", "X-Bold-Signature": "wrong"}),
            (raw, self.signed_headers(raw, b"otra_clave_ficticia")),
            (raw + b" ", valid),
            (b"", self.signed_headers(b"")),
            (b"{invalid", self.signed_headers(b"{invalid")),
            (raw, self.signed_headers(raw, content_type="text/plain")),
        )
        before = self.snapshot()
        for body, headers in cases:
            with self.subTest(body=body, headers=list(headers)):
                self.assertIn(self.client.post("/webhooks/bold", data=body, headers=headers).status_code,
                              {400, 415})
                self.assertEqual(self.snapshot(), before)

    def test_amount_and_currency_matrix_is_exact(self):
        order = self.create(amount=10000)["orderId"]
        invalid_totals = (10001, 9999, 0, -1, True, "10000", 10000.5,
                          float("nan"), float("inf"), [], {}, None)
        for index, total in enumerate(invalid_totals):
            with self.subTest(total=total):
                response = self.post(self.payload(
                    order, total=total, event_id=f"EVT-AMOUNT-{index}", payment=f"PAY-AMOUNT-{index}"
                ))
                self.assertEqual(response.get_json()["reason"], "amount_mismatch")
        for index, currency in enumerate(("USD", "EUR", "cop", "COP ", "", None)):
            with self.subTest(currency=currency):
                response = self.post(self.payload(
                    order, currency=currency, event_id=f"EVT-CURRENCY-{index}",
                    payment=f"PAY-CURRENCY-{index}",
                ))
                self.assertEqual(response.get_json()["reason"], "currency_mismatch")
        missing_total = self.payload(order, event_id="EVT-NO-TOTAL", payment="PAY-NO-TOTAL")
        del missing_total["data"]["amount"]["total"]
        self.assertEqual(self.post(missing_total).get_json()["reason"], "amount_mismatch")
        missing_currency = self.payload(order, event_id="EVT-NO-CURRENCY", payment="PAY-NO-CURRENCY")
        del missing_currency["data"]["amount"]["currency"]
        self.assertEqual(self.post(missing_currency).get_json()["reason"], "currency_mismatch")
        self.assertEqual(self.snapshot()["ledger"], 0)
        valid = self.post(self.payload(
            order, total=10000.0, event_id="EVT-VALID-FLOAT", payment="PAY-VALID-FLOAT"
        ))
        self.assertEqual(valid.get_json()["reason"], "sale_approved")
        self.assertEqual(self.snapshot()["ledger"], 1)

    def test_reference_payment_event_and_state_matrices_do_not_cross_credit(self):
        order_a = self.create(self.reseller_a)["orderId"]
        order_b = self.create(self.reseller_b)["orderId"]
        invalid_refs = ("RCH-not-found", "bad/reference", "X" * 61, "", None)
        for index, reference in enumerate(invalid_refs):
            payload = self.payload(order_a, event_id=f"EVT-REF-{index}", payment=f"PAY-REF-{index}")
            payload["data"]["metadata"]["reference"] = reference
            self.assertIn(self.post(payload).get_json()["reason"], {"invalid_reference", "unknown_order"})
        for index, payment in enumerate(("", None, 7, [], {}, "X" * 181)):
            payload = self.payload(order_a, event_id=f"EVT-PAY-{index}", payment=payment)
            self.assertEqual(self.post(payload).get_json()["reason"], "invalid_payment_id")
        events = ("SALE_REJECTED", "VOID_APPROVED", "VOID_REJECTED",
                  "inventado", "sale_approved", "", None, 7, [], {})
        for index, event in enumerate(events):
            payload = self.payload(order_a, event=event, event_id=f"EVT-TYPE-{index}",
                                   payment=f"PAY-TYPE-{index}")
            response = self.post(payload)
            self.assertEqual(response.status_code, 200)
            expected_status = "processed" if index < 3 else "ignored"
            self.assertEqual(response.get_json()["status"], expected_status)
            self.assertNotEqual((response.get_json() or {}).get("reason"), "sale_approved")
        self.assertEqual(self.snapshot()["ledger"], 0)

        order_a = self.create(self.reseller_a)["orderId"]
        order_b = self.create(self.reseller_b)["orderId"]
        approved = self.post(self.payload(order_a, event_id="EVT-OWNER-A", payment="PAY-SHARED"))
        self.assertEqual(approved.get_json()["reason"], "sale_approved")
        crossed = self.post(self.payload(order_b, event_id="EVT-OWNER-B", payment="PAY-SHARED"))
        self.assertEqual(crossed.get_json()["reason"], "duplicate_payment")
        conn = sqlite3.connect(self.db_path)
        balances = dict(conn.execute("SELECT revendedor_id, saldo FROM reseller_wallets"))
        states = dict(conn.execute("SELECT order_id, estado FROM reseller_recharge_intents"))
        conn.close()
        self.assertEqual(balances, {self.reseller_a: 10000, self.reseller_b: 0})
        self.assertEqual((states[order_a], states[order_b]), ("approved", "pending"))

    def test_non_pending_states_and_replay_never_add_a_second_credit(self):
        for index, state in enumerate(("approved", "rejected", "cancelled", "expired")):
            order = self.create(self.reseller_a)["orderId"]
            conn = sqlite3.connect(self.db_path)
            conn.execute("UPDATE reseller_recharge_intents SET estado=? WHERE order_id=?", (state, order))
            conn.commit(); conn.close()
            response = self.post(self.payload(
                order, event_id=f"EVT-STATE-{index}", payment=f"PAY-STATE-{index}"
            ))
            self.assertIn(response.get_json()["reason"], {"order_already_approved", "not_creditable"})
        self.assertEqual(self.snapshot()["ledger"], 0)

        order = self.create(self.reseller_a)["orderId"]
        payload = self.payload(order, event_id="EVT-REPLAY", payment="PAY-REPLAY")
        self.assertEqual(self.post(payload).get_json()["reason"], "sale_approved")
        for _ in range(5):
            self.assertEqual(self.post(payload).get_json()["reason"], "duplicate_event")
        self.assertEqual(self.snapshot()["ledger"], 1)

    def test_webhook_failure_before_ledger_rolls_back_event_and_finances(self):
        order = self.create()["orderId"]
        before = self.snapshot()
        with mock.patch("bold_recharges.wallets.apply_wallet_transaction",
                        side_effect=RuntimeError("fallo auditado")):
            with self.assertRaises(RuntimeError):
                bold_recharges.process_webhook(self.payload(order))
        self.assertEqual(self.snapshot(), before)
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bold_webhook_events").fetchone()[0], 0)
        conn.close()

    def test_sqlite_unique_constraints_backstop_bold_idempotency(self):
        conn = sqlite3.connect(self.db_path)
        indexes = {
            row[1] for table in ("reseller_recharge_intents", "reseller_wallet_transactions")
            for row in conn.execute(f"PRAGMA index_list({table})") if row[2]
        }
        conn.close()
        self.assertIn("uq_recharge_bold_transaction", indexes)
        self.assertIn("uq_wallet_transactions_idempotency", indexes)
        self.assertIn("uq_wallet_transactions_provider_reference", indexes)

    def test_reconciliation_is_not_exposed_as_http_route_and_audit_failure_rolls_back(self):
        rules = {rule.endpoint for rule in app_module.app.url_map.iter_rules()}
        self.assertNotIn("reconcile_approved_payment", rules)
        order = "RCH-reconciliation-audit"
        payment = "PAY-RECON-AUDIT"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            """INSERT INTO reseller_recharge_intents
               (revendedor_id, order_id, monto, moneda, provider, estado, environment)
               VALUES (?, ?, 10000, 'COP', 'bold', 'pending', 'production')""",
            (self.reseller_a, order),
        )
        intent_id = cursor.lastrowid
        conn.execute(
            """INSERT INTO bold_webhook_events
               (event_id, intent_id, payment_id, order_id, event_type, environment,
                processing_status, result_reason, processed_at)
               VALUES ('EVT-LOCAL-SALE', ?, ?, ?, 'SALE_APPROVED', 'production',
                       'ignored', 'amount_mismatch', CURRENT_TIMESTAMP)""",
            (intent_id, payment, order),
        )
        conn.execute("""CREATE TRIGGER fail_reconciliation_audit
                        BEFORE INSERT ON bold_reconciliation_audit
                        BEGIN SELECT RAISE(ABORT, 'audit failure'); END""")
        conn.commit(); conn.close()
        before = self.snapshot()
        voucher = {"transaction_id": payment, "reference_id": order,
                   "total": 10000, "payment_status": "APPROVED"}
        with self.assertRaises(sqlite3.IntegrityError):
            bold_recharges.reconcile_approved_payment(
                intent_id, voucher, expected_transaction_id=payment,
                expected_reference_id=order, actor="admin:audit",
            )
        self.assertEqual(self.snapshot(), before)
        conn = sqlite3.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM bold_reconciliation_audit").fetchone()[0], 0)
        conn.close()

    def test_secret_key_fails_closed_in_production_without_real_configuration(self):
        with mock.patch.dict(os.environ, {
            "APP_ENV": "production", "FLASK_ENV": "", "BOLD_ENV": "test",
            "SECRET_KEY": "", "PECHY_TESTING": "",
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY debe configurarse"):
                app_module._configured_secret_key()
        with mock.patch.dict(os.environ, {
            "APP_ENV": "", "FLASK_ENV": "", "BOLD_ENV": "production",
            "SECRET_KEY": "", "PECHY_TESTING": "",
        }, clear=False):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY debe configurarse"):
                app_module._configured_secret_key()
        with mock.patch.dict(os.environ, {
            "APP_ENV": "production", "SECRET_KEY": "clave-ficticia-de-test",
            "PECHY_TESTING": "",
        }, clear=False):
            self.assertEqual(app_module._configured_secret_key(), "clave-ficticia-de-test")


if __name__ == "__main__":
    unittest.main()
