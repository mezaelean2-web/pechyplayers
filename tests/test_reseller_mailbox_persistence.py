try:
    from tests.test_reseller_mailbox import ResellerMailboxTest, Clock
except ModuleNotFoundError:
    from test_reseller_mailbox import ResellerMailboxTest, Clock

import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import database
import inventory_assignment_access
from mail_providers import FakeMailProvider
import reseller_mailbox
import reseller_mailbox_persistence
import app as app_module


class ResellerMailboxPersistenceTest(ResellerMailboxTest):
    """Reutiliza únicamente el fixture comercial aislado de Fase 3."""

    def setUp(self):
        super().setUp()
        self.repository = reseller_mailbox_persistence.SQLiteMailboxRepository()
        self.service = reseller_mailbox.ResellerMailboxService(
            self.provider, self.repository, self.clock)
        app_module.reseller_mailbox_service = self.service

    def unit(self, request_id):
        return self.repository.get_request(request_id, self.owner)["unit"]

    def add(self, request_id, *, seconds, reference="provider-1",
            kind="numeric_code", value="482193", unit=None):
        record = self.repository.get_request(request_id, self.owner)
        self.provider.add_message(
            reference=reference, unit=unit or record["unit"], service="Netflix",
            kind=kind, value=value,
            received_at=record["requested_at"] + timedelta(seconds=seconds))

    # Los tests heredados que inspeccionan deliberadamente el repositorio efímero
    # pertenecen a Fase 3 y no aplican al contrato SQLite.
    test_history_isolated_by_reseller_purchase_and_idor = None
    test_audit_contains_no_email_code_or_provider_reference = None

    def test_schema_is_idempotent_and_has_expected_objects(self):
        reseller_mailbox_persistence.initialize_schema()
        reseller_mailbox_persistence.initialize_schema()
        conn = database.conectar()
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index','trigger')")}
        conn.close()
        for name in ("reseller_mailbox_requests", "reseller_authorized_message_deliveries",
                     "reseller_message_audit_events", "uq_mailbox_active_request",
                     "idx_mailbox_deliveries_history", "trg_mailbox_audit_immutable_update",
                     "trg_mailbox_audit_immutable_delete"):
            self.assertIn(name, names)

    def test_request_and_delivery_survive_repository_reload_without_plaintext(self):
        purchase = self.purchase(); result = self.request(); request_id = result["request_id"]
        self.add(request_id, seconds=2, value="FAKE_SECRET_DO_NOT_LEAK")
        self.clock.advance(2); found = self.service.poll_request(self.owner, request_id)
        self.assertEqual(found["status"], "found")
        reloaded = reseller_mailbox.ResellerMailboxService(
            self.provider, reseller_mailbox_persistence.SQLiteMailboxRepository(), self.clock)
        history = reloaded.request_message(self.owner, "account@pechy.org")["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["value"], "FAKE_SECRET_DO_NOT_LEAK")
        raw = Path(self.path).read_bytes()
        self.assertNotIn(b"FAKE_SECRET_DO_NOT_LEAK", raw)
        self.assertEqual(self.scalar("SELECT reseller_purchase_id FROM reseller_authorized_message_deliveries"), purchase)

    def test_restart_without_fake_state_expires_old_waiting_request(self):
        self.purchase(); old = self.request()["request_id"]
        fresh_provider = FakeMailProvider(auto_message=False)
        service = reseller_mailbox.ResellerMailboxService(
            fresh_provider, reseller_mailbox_persistence.SQLiteMailboxRepository(), self.clock)
        new = service.request_message(self.owner, "account@pechy.org")
        self.assertNotEqual(new["request_id"], old)
        self.assertEqual(self.scalar("SELECT status FROM reseller_mailbox_requests WHERE request_id=?", (old,)), "expired")

    def test_delivery_idor_and_provider_reference_do_not_authorize(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=2); self.clock.advance(2)
        delivery = self.service.poll_request(self.owner, request_id)["message"]
        opaque = self.scalar("SELECT provider_reference_opaca FROM reseller_authorized_message_deliveries")
        self.assertEqual(self.service.read_delivery(self.other, delivery["id"])["status"], "unavailable")
        self.assertEqual(self.service.poll_request(self.other, request_id)["status"], "unavailable")
        self.assertEqual(self.service.read_delivery(self.other, opaque)["status"], "unavailable")

    def test_historical_content_requires_current_authorization(self):
        purchase = self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=2); self.clock.advance(2)
        delivery = self.service.poll_request(self.owner, request_id)["message"]
        conn = database.conectar(); conn.execute(
            "UPDATE reseller_purchases SET estado_persistido='cut' WHERE id=?", (purchase,)); conn.commit(); conn.close()
        self.assertEqual(self.service.read_delivery(self.owner, delivery["id"])["status"], "unavailable")

    def test_provider_reference_is_deduplicated_per_purchase(self):
        self.purchase(); first = self.request(); self.add(first["request_id"], seconds=2)
        self.clock.advance(2); self.service.poll_request(self.owner, first["request_id"])
        self.clock.advance(100); second = self.request(); self.add(second["request_id"], seconds=2)
        self.clock.advance(2); self.service.poll_request(self.owner, second["request_id"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM reseller_authorized_message_deliveries"), 1)

    def test_audit_is_append_only_and_contains_no_sensitive_material(self):
        self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=2, value="482193", reference="fake-person@example.invalid")
        self.clock.advance(2); self.service.poll_request(self.owner, request_id)
        conn = database.conectar()
        serialized = json.dumps([dict(row) for row in conn.execute(
            "SELECT * FROM reseller_message_audit_events")])
        self.assertNotIn("482193", serialized); self.assertNotIn("fake-person@example.invalid", serialized)
        event_id = conn.execute("SELECT id FROM reseller_message_audit_events LIMIT 1").fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE reseller_message_audit_events SET safe_code='authorized' WHERE id=?", (event_id,))
        conn.rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM reseller_message_audit_events WHERE id=?", (event_id,))
        conn.close()

    def test_constraints_reject_invalid_states_and_message_types(self):
        self.purchase(); request_id = self.request()["request_id"]
        conn = database.conectar()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("UPDATE reseller_mailbox_requests SET status='evil' WHERE request_id=?", (request_id,))
        conn.close()

    def test_toctou_change_produces_no_delivery(self):
        purchase = self.purchase(); request_id = self.request()["request_id"]
        self.add(request_id, seconds=2); self.clock.advance(2)
        conn = database.conectar(); conn.execute(
            "UPDATE reseller_purchases SET updated_at='assignment-v2' WHERE id=?", (purchase,)); conn.commit(); conn.close()
        self.assertEqual(self.service.poll_request(self.owner, request_id)["status"], "unavailable")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM reseller_authorized_message_deliveries"), 0)


# Evita que unittest redescubra en este módulo la clase importada de Fase 3.
del ResellerMailboxTest
