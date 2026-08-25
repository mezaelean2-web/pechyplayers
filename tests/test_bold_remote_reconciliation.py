try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from unittest import mock

import bold_recharges
import database
import resellers


class BoldRemoteReconciliationTest(unittest.TestCase):
    ORDER = "RCH-remote-recovery"
    PAYMENT = "PAY-REMOTE-RECOVERY"

    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        self.original_env = {key: os.environ.get(key) for key in (
            "BOLD_ENV", "BOLD_IDENTITY_KEY", "BOLD_SECRET_KEY"
        )}
        database.DB = self.db_path
        os.environ.update(BOLD_ENV="production", BOLD_IDENTITY_KEY="test-identity",
                          BOLD_SECRET_KEY="test-secret")
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
            imagen TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL, precio TEXT NOT NULL,
            oferta_precio TEXT, oferta_activa INTEGER DEFAULT 0, destacado INTEGER DEFAULT 0,
            visible INTEGER DEFAULT 1, orden INTEGER DEFAULT 999, categoria TEXT DEFAULT 'Streaming',
            orden_categoria INTEGER DEFAULT 999, estado TEXT DEFAULT 'disponible')""")
        conn.commit(); conn.close()
        resellers.inicializar_revendedores()
        bold_recharges.initialize()
        self.reseller_id = resellers.crear_revendedor(
            "Remote Test", "remote@example.com", "", "", "ClaveSegura123"
        )
        self.intent_id = self.add_intent(self.reseller_id, self.ORDER)

    def tearDown(self):
        database.DB = self.original_db
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        os.remove(self.db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def add_intent(self, reseller_id, order, *, state="pending", payment=None,
                   amount=10000, currency="COP", environment="production"):
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO reseller_recharge_intents
               (revendedor_id, order_id, monto, moneda, provider, estado,
                external_transaction_id, environment)
               VALUES (?, ?, ?, ?, 'bold', ?, ?, ?)""",
            (reseller_id, order, amount, currency, state, payment, environment),
        )
        value = cursor.lastrowid
        conn.commit(); conn.close()
        return value

    def voucher(self, **changes):
        value = {"transaction_id": self.PAYMENT, "reference_id": self.ORDER,
                 "total": 10000, "payment_status": "APPROVED"}
        value.update(changes)
        return value

    def fetcher(self, voucher=None, *, status=200):
        voucher = self.voucher() if voucher is None else voucher
        raw = json.dumps(voucher, sort_keys=True).encode()
        return lambda order: (voucher, status, hashlib.sha256(raw).hexdigest())

    def reconcile(self, fetcher=None, intent_id=None):
        with mock.patch.object(
            bold_recharges, "fetch_official_voucher",
            side_effect=fetcher or self.fetcher(),
        ):
            return bold_recharges.reconcile_pending_from_bold(
                self.intent_id if intent_id is None else intent_id
            )

    def snapshot(self):
        conn = self.connect()
        result = {
            "intent": tuple(conn.execute(
                "SELECT estado, external_transaction_id FROM reseller_recharge_intents WHERE id=?",
                (self.intent_id,),
            ).fetchone()),
            "balance": conn.execute(
                "SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (self.reseller_id,)
            ).fetchone()[0],
            "ledger": conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions").fetchone()[0],
            "success_audit": conn.execute(
                "SELECT COUNT(*) FROM bold_remote_reconciliation_audit WHERE result='processed'"
            ).fetchone()[0],
        }
        conn.close()
        return result

    def assert_rejected(self, reason, fetcher):
        before = self.snapshot()
        with self.assertRaises(bold_recharges.RemoteReconciliationError) as captured:
            self.reconcile(fetcher)
        self.assertEqual(captured.exception.reason, reason)
        self.assertEqual(self.snapshot(), before)

    def test_success_and_replay_credit_exactly_once(self):
        first = self.reconcile()
        second = self.reconcile()
        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["reason"], "already_reconciled")
        self.assertFalse(first["currency_confirmed_by_voucher"])
        self.assertEqual(self.snapshot(), {
            "intent": ("approved", self.PAYMENT), "balance": 10000,
            "ledger": 1, "success_audit": 1,
        })
        conn = self.connect()
        audit = conn.execute("SELECT * FROM bold_remote_reconciliation_audit").fetchone()
        movement = conn.execute("SELECT * FROM reseller_wallet_transactions").fetchone()
        conn.close()
        self.assertEqual((audit["reseller_id"], audit["wallet_id"], audit["local_currency"]),
                         (self.reseller_id, movement["wallet_id"], "COP"))
        self.assertEqual((movement["provider"], movement["external_reference"],
                          movement["idempotency_key"]),
                         ("bold", self.PAYMENT, f"bold:payment:{self.PAYMENT}"))

    def test_response_validation_matrix_has_zero_credit_and_audit(self):
        cases = (
            ("official_status_not_approved", self.voucher(payment_status="PENDING")),
            ("official_status_not_approved", self.voucher(payment_status="REJECTED")),
            ("reference_id_mismatch", self.voucher(reference_id="RCH-other")),
            ("amount_mismatch", self.voucher(total=9999)),
            ("invalid_transaction_id", self.voucher(transaction_id="")),
            ("invalid_transaction_id", self.voucher(transaction_id="bad/payment")),
            ("official_incomplete_response", []),
        )
        for index, (reason, voucher) in enumerate(cases):
            with self.subTest(reason=reason, index=index):
                self.assert_rejected(reason, self.fetcher(voucher))
        conn = self.connect()
        rejected = conn.execute(
            "SELECT COUNT(*) FROM bold_remote_reconciliation_audit WHERE result='rejected'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(rejected, len(cases))

    def test_transport_http_json_and_timeout_fail_closed(self):
        errors = (
            ("official_http_error", 503),
            ("official_invalid_json", 200),
            ("official_timeout", None),
            ("official_network_error", None),
        )
        for reason, status in errors:
            def failing(_order, reason=reason, status=status):
                raise bold_recharges.RemoteReconciliationError(reason, http_status=status)
            with self.subTest(reason=reason):
                self.assert_rejected(reason, failing)

    def test_missing_intent_non_pending_and_invalid_local_entities(self):
        with self.assertRaises(bold_recharges.RemoteReconciliationError) as captured:
            self.reconcile(intent_id=999999)
        self.assertEqual(captured.exception.reason, "intent_not_found")

        conn = self.connect()
        conn.execute("UPDATE reseller_recharge_intents SET estado='rejected' WHERE id=?",
                     (self.intent_id,))
        conn.commit(); conn.close()
        self.assert_rejected("intent_not_pending", self.fetcher())

    def test_inactive_reseller_and_missing_wallet_fail_closed(self):
        conn = self.connect()
        conn.execute("UPDATE revendedores SET estado='bloqueado' WHERE id=?", (self.reseller_id,))
        conn.commit(); conn.close()
        self.assert_rejected("reseller_not_active", self.fetcher())

        conn = self.connect()
        conn.execute("UPDATE revendedores SET estado='activo' WHERE id=?", (self.reseller_id,))
        conn.execute("DELETE FROM reseller_wallets WHERE revendedor_id=?", (self.reseller_id,))
        conn.commit(); conn.close()
        with self.assertRaises(bold_recharges.RemoteReconciliationError) as captured:
            self.reconcile()
        self.assertEqual(captured.exception.reason, "wallet_not_found")

    def test_transaction_owned_by_other_intent_is_rejected(self):
        other = resellers.crear_revendedor("Other", "other-remote@example.com", "", "", "ClaveSegura123")
        self.add_intent(other, "RCH-other", state="approved", payment=self.PAYMENT)
        self.assert_rejected("payment_owned_by_other_intent", self.fetcher())

    def test_intent_changed_while_bold_is_queried_is_rejected(self):
        def mutate_then_respond(order):
            conn = self.connect()
            conn.execute(
                "UPDATE reseller_recharge_intents SET monto=11000 WHERE id=?",
                (self.intent_id,),
            )
            conn.commit(); conn.close()
            return self.fetcher()(order)

        before_balance = self.snapshot()["balance"]
        with self.assertRaises(bold_recharges.RemoteReconciliationError) as captured:
            self.reconcile(mutate_then_respond)
        self.assertEqual(captured.exception.reason, "intent_changed")
        current = self.snapshot()
        self.assertEqual((current["balance"], current["ledger"]), (before_balance, 0))

    def test_induced_failure_rolls_back_credit_and_records_rejection(self):
        conn = self.connect()
        conn.execute("""CREATE TRIGGER fail_remote BEFORE UPDATE ON reseller_recharge_intents
                        WHEN NEW.estado='approved' BEGIN SELECT RAISE(ABORT, 'fail'); END""")
        conn.commit(); conn.close()
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError):
            self.reconcile()
        self.assertEqual(self.snapshot(), before)
        conn = self.connect()
        detail = conn.execute(
            "SELECT detail FROM bold_remote_reconciliation_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(detail, "transaction_failed")

    def test_webhook_arriving_during_remote_query_wins_without_double_credit(self):
        def webhook_then_voucher(_order):
            result = bold_recharges.process_webhook({
                "id": "EVT-RACE-WEBHOOK", "type": "SALE_APPROVED",
                "data": {"payment_id": self.PAYMENT,
                         "amount": {"total": 10000, "currency": "COP"},
                         "metadata": {"reference": self.ORDER}},
            })
            self.assertEqual(result["reason"], "sale_approved")
            return self.fetcher()(_order)

        result = self.reconcile(webhook_then_voucher)
        self.assertEqual(result["reason"], "already_reconciled")
        self.assertEqual(self.snapshot()["ledger"], 1)
        self.assertEqual(self.snapshot()["balance"], 10000)
        conn = self.connect()
        audited = conn.execute(
            "SELECT COUNT(*) FROM bold_remote_reconciliation_audit "
            "WHERE result='already_reconciled'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(audited, 1)

    def test_concurrent_remote_reconciliation_credits_once(self):
        barrier = threading.Barrier(6)
        results = []
        failures = []
        lock = threading.Lock()

        def concurrent_fetch(order):
            barrier.wait()
            return self.fetcher()(order)

        def worker():
            try:
                value = bold_recharges.reconcile_pending_from_bold(self.intent_id)
                with lock:
                    results.append(value["status"])
            except Exception as error:
                with lock:
                    failures.append(error)

        with mock.patch.object(
            bold_recharges, "fetch_official_voucher", side_effect=concurrent_fetch
        ):
            threads = [threading.Thread(target=worker) for _ in range(6)]
            for thread in threads: thread.start()
            for thread in threads: thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(results.count("processed"), 1)
        self.assertEqual(results.count("duplicate"), 5)
        self.assertEqual((self.snapshot()["ledger"], self.snapshot()["balance"]), (1, 10000))

    def test_foreign_keys_remain_valid(self):
        self.reconcile()
        conn = self.connect()
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
