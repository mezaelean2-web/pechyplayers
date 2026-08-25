try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import threading
import unittest

import bold_recharges
import database
import resellers
import wallets


class BoldReconciliationTest(unittest.TestCase):
    PAYMENT = "PAY-RECONCILE"
    ORDER = "RCH-reconcile"

    def setUp(self):
        descriptor, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self.original_db = database.DB
        database.DB = self.db_path
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
            "Reconcile Test", "reconcile@example.com", "", "", "ClaveSegura123"
        )
        self.intent_id = self.add_intent(self.reseller_id, self.ORDER)
        self.add_event("SALE_APPROVED")

    def tearDown(self):
        database.DB = self.original_db
        os.remove(self.db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_intent(self, reseller_id, order, *, state="pending", payment=None):
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO reseller_recharge_intents
               (revendedor_id, order_id, monto, moneda, provider, estado,
                external_transaction_id, environment)
               VALUES (?, ?, 10000, 'COP', 'bold', ?, ?, 'production')""",
            (reseller_id, order, state, payment),
        )
        intent_id = cursor.lastrowid
        conn.commit(); conn.close()
        return intent_id

    def add_event(self, event_type, *, payment=None, order=None, intent_id=None):
        payment = self.PAYMENT if payment is None else payment
        order = self.ORDER if order is None else order
        intent_id = self.intent_id if intent_id is None else intent_id
        conn = self.connect()
        cursor = conn.execute(
            """INSERT INTO bold_webhook_events
               (event_id, intent_id, payment_id, order_id, event_type, environment,
                processing_status, result_reason, processed_at)
               VALUES (?, ?, ?, ?, ?, 'production', 'ignored', 'amount_mismatch', CURRENT_TIMESTAMP)""",
            (f"evt-{event_type}-{conn.execute('SELECT COUNT(*) FROM bold_webhook_events').fetchone()[0]}",
             intent_id, payment, order, event_type),
        )
        event_id = cursor.lastrowid
        conn.commit(); conn.close()
        return event_id

    def voucher(self, **changes):
        value = {"transaction_id": self.PAYMENT, "reference_id": self.ORDER,
                 "total": 10000, "payment_status": "APPROVED"}
        value.update(changes)
        return value

    def reconcile(self, voucher=None, **kwargs):
        return bold_recharges.reconcile_approved_payment(
            self.intent_id, voucher or self.voucher(),
            expected_transaction_id=kwargs.get("transaction", self.PAYMENT),
            expected_reference_id=kwargs.get("reference", self.ORDER),
            actor="admin:test",
        )

    def snapshot(self):
        conn = self.connect()
        result = (
            conn.execute("SELECT estado, external_transaction_id FROM reseller_recharge_intents WHERE id=?",
                         (self.intent_id,)).fetchone(),
            conn.execute("SELECT saldo FROM reseller_wallets WHERE revendedor_id=?",
                         (self.reseller_id,)).fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM reseller_wallet_transactions").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM bold_reconciliation_audit").fetchone()[0],
        )
        conn.close()
        return (tuple(result[0]),) + result[1:]

    def assert_abort(self, reason, call):
        before = self.snapshot()
        with self.assertRaises(bold_recharges.ReconciliationError) as captured:
            call()
        self.assertEqual(captured.exception.reason, reason)
        self.assertEqual(self.snapshot(), before)

    def test_valid_reconciliation_and_repeated_execution_are_idempotent(self):
        first = self.reconcile()
        second = self.reconcile()
        self.assertEqual((first["status"], second["reason"]),
                         ("processed", "already_reconciled"))
        self.assertFalse(first["currency_confirmed_by_voucher"])
        self.assertEqual(self.snapshot(), (("approved", self.PAYMENT), 10000, 1, 1))

    def test_concurrent_execution_credits_once(self):
        barrier = threading.Barrier(8)
        results = []
        lock = threading.Lock()
        def worker():
            barrier.wait()
            value = self.reconcile()["status"]
            with lock: results.append(value)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(results.count("processed"), 1)
        self.assertEqual(results.count("duplicate"), 7)
        self.assertEqual(self.snapshot(), (("approved", self.PAYMENT), 10000, 1, 1))

    def test_amount_reference_transaction_and_status_mismatches_abort(self):
        cases = (
            ("amount_mismatch", lambda: self.reconcile(self.voucher(total=9999))),
            ("reference_id_mismatch", lambda: self.reconcile(self.voucher(reference_id="RCH-other"))),
            ("transaction_id_mismatch", lambda: self.reconcile(self.voucher(transaction_id="PAY-other"))),
            ("official_status_not_approved", lambda: self.reconcile(self.voucher(payment_status="PENDING"))),
        )
        for reason, call in cases:
            with self.subTest(reason=reason): self.assert_abort(reason, call)

    def test_non_pending_intent_aborts(self):
        conn = self.connect()
        conn.execute("UPDATE reseller_recharge_intents SET estado='rejected' WHERE id=?", (self.intent_id,))
        conn.commit(); conn.close()
        self.assert_abort("intent_not_pending", self.reconcile)

    def test_existing_bold_ledger_aborts(self):
        wallets.apply_wallet_transaction(
            self.reseller_id, "recharge", 10000, "Existing", provider="bold",
            external_reference=self.PAYMENT,
            idempotency_key=f"bold:payment:{self.PAYMENT}",
        )
        self.assert_abort("bold_ledger_already_exists", self.reconcile)

    def test_payment_owned_by_other_intent_aborts(self):
        other = resellers.crear_revendedor("Other", "other-reconcile@example.com", "", "", "ClaveSegura123")
        self.add_intent(other, "RCH-other", state="approved", payment=self.PAYMENT)
        self.assert_abort("payment_owned_by_other_intent", self.reconcile)

    def test_missing_local_event_aborts(self):
        conn = self.connect(); conn.execute("DELETE FROM bold_webhook_events")
        conn.commit(); conn.close()
        self.assert_abort("local_sale_event_not_found", self.reconcile)

    def test_incorrect_local_event_aborts(self):
        conn = self.connect(); conn.execute("UPDATE bold_webhook_events SET event_type='SALE_REJECTED'")
        conn.commit(); conn.close()
        self.assert_abort("local_event_incorrect", self.reconcile)

    def test_later_void_aborts(self):
        self.add_event("VOID_APPROVED")
        self.assert_abort("later_void_approved", self.reconcile)

    def test_failure_during_intent_update_rolls_back_everything(self):
        conn = self.connect()
        conn.execute("""CREATE TRIGGER fail_reconciliation BEFORE UPDATE ON reseller_recharge_intents
                        WHEN NEW.estado='approved' BEGIN SELECT RAISE(ABORT, 'fail'); END""")
        conn.commit(); conn.close()
        before = self.snapshot()
        with self.assertRaises(sqlite3.IntegrityError): self.reconcile()
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
