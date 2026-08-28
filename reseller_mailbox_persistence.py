"""Persistencia SQLite mínima y no sensible para el Buzón reseller."""

import json
from datetime import datetime, timezone

import database
import mailbox_bindings


REQUEST_STATUSES = frozenset({"waiting", "found", "expired", "denied"})
MESSAGE_TYPES = frozenset({
    "numeric_code", "alphanumeric_code", "action_link", "approval_action",
    "device_notice", "instructions",
})
AUDIT_RESULTS = frozenset({"waiting", "delivered", "denied", "expired"})
AUDIT_SAFE_CODES = frozenset({
    "authorized", "invalid_or_limited", "purchase_not_found",
    "ambiguous_assignment", "authorization_changed", "request_expired",
    "message_delivered", "provider_state_unavailable", "invalid_request",
})


def _connect():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_schema(connection=None):
    own = connection is None
    conn = connection or _connect()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reseller_mailbox_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            reseller_id INTEGER NOT NULL,
            reseller_purchase_id INTEGER NOT NULL,
            inventory_type TEXT NOT NULL CHECK (inventory_type IN ('cuenta','perfil')),
            inventory_account_id INTEGER NOT NULL,
            inventory_profile_id INTEGER,
            requested_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('waiting','found','expired','denied')),
            assignment_version TEXT NOT NULL,
            delivery_id TEXT,
            last_polled_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reseller_id) REFERENCES revendedores(id),
            FOREIGN KEY (reseller_purchase_id) REFERENCES reseller_purchases(id),
            CHECK ((inventory_type='cuenta' AND inventory_profile_id IS NULL)
                OR (inventory_type='perfil' AND inventory_profile_id IS NOT NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mailbox_active_request
            ON reseller_mailbox_requests(reseller_id, reseller_purchase_id)
            WHERE status='waiting';
        CREATE INDEX IF NOT EXISTS idx_mailbox_requests_owner
            ON reseller_mailbox_requests(reseller_id, request_id);
        CREATE INDEX IF NOT EXISTS idx_mailbox_requests_expiry
            ON reseller_mailbox_requests(status, expires_at);

        CREATE TABLE IF NOT EXISTS reseller_authorized_message_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            delivery_id TEXT NOT NULL UNIQUE,
            request_id TEXT NOT NULL,
            reseller_id INTEGER NOT NULL,
            reseller_purchase_id INTEGER NOT NULL,
            inventory_type TEXT NOT NULL CHECK (inventory_type IN ('cuenta','perfil')),
            inventory_account_id INTEGER NOT NULL,
            inventory_profile_id INTEGER,
            message_type TEXT NOT NULL CHECK (message_type IN (
                'numeric_code','alphanumeric_code','action_link','approval_action',
                'device_notice','instructions')),
            service TEXT NOT NULL,
            provider_reference_opaca TEXT NOT NULL,
            received_at TEXT NOT NULL,
            delivered_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES reseller_mailbox_requests(request_id),
            FOREIGN KEY (reseller_id) REFERENCES revendedores(id),
            FOREIGN KEY (reseller_purchase_id) REFERENCES reseller_purchases(id),
            UNIQUE (reseller_purchase_id, provider_reference_opaca),
            CHECK ((inventory_type='cuenta' AND inventory_profile_id IS NULL)
                OR (inventory_type='perfil' AND inventory_profile_id IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS idx_mailbox_deliveries_history
            ON reseller_authorized_message_deliveries(
                reseller_id, reseller_purchase_id, received_at DESC, id DESC);

        CREATE TABLE IF NOT EXISTS reseller_message_audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL CHECK (event_type IN (
                'request_created','request_denied','request_expired',
                'authorization_denied','message_delivered')),
            actor_type TEXT NOT NULL DEFAULT 'reseller' CHECK (actor_type='reseller'),
            reseller_id INTEGER NOT NULL,
            reseller_purchase_id INTEGER,
            inventory_type TEXT,
            inventory_account_id INTEGER,
            inventory_profile_id INTEGER,
            request_id TEXT,
            result TEXT NOT NULL CHECK (result IN ('waiting','delivered','denied','expired')),
            safe_code TEXT NOT NULL CHECK (safe_code IN (
                'authorized','invalid_or_limited','purchase_not_found',
                'ambiguous_assignment','authorization_changed','request_expired',
                'message_delivered','provider_state_unavailable','invalid_request')),
            provider_reference_hash TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (reseller_id) REFERENCES revendedores(id)
        );
        CREATE INDEX IF NOT EXISTS idx_mailbox_audit_actor
            ON reseller_message_audit_events(reseller_id, created_at DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_mailbox_audit_request
            ON reseller_message_audit_events(request_id, id DESC);
        CREATE TRIGGER IF NOT EXISTS trg_mailbox_audit_immutable_update
            BEFORE UPDATE ON reseller_message_audit_events
            BEGIN SELECT RAISE(ABORT, 'mailbox audit is append-only'); END;
        CREATE TRIGGER IF NOT EXISTS trg_mailbox_audit_immutable_delete
            BEFORE DELETE ON reseller_message_audit_events
            BEGIN SELECT RAISE(ABORT, 'mailbox audit is append-only'); END;
        """)
        mailbox_bindings.initialize_schema(conn)
        request_columns = {row[1] for row in conn.execute("PRAGMA table_info(reseller_mailbox_requests)")}
        for name, definition in (
            ("mailbox_binding_id", "INTEGER"), ("binding_version", "INTEGER"),
            ("folder_key", "TEXT"), ("uidvalidity_at_t0", "INTEGER"),
            ("uidnext_at_t0", "INTEGER"), ("provider_cursor_captured_at", "TEXT"),
            ("initialization_state", "TEXT NOT NULL DEFAULT 'legacy'"),
            ("lease_owner", "TEXT"), ("lease_expires_at", "TEXT")):
            if name not in request_columns:
                conn.execute(f"ALTER TABLE reseller_mailbox_requests ADD COLUMN {name} {definition}")
        delivery_columns = {row[1] for row in conn.execute("PRAGMA table_info(reseller_authorized_message_deliveries)")}
        for name, definition in (
            ("mailbox_binding_id", "INTEGER"), ("folder_key", "TEXT"),
            ("imap_uidvalidity", "INTEGER"), ("imap_uid", "INTEGER"),
            ("provider_locator_version", "INTEGER NOT NULL DEFAULT 1")):
            if name not in delivery_columns:
                conn.execute(f"ALTER TABLE reseller_authorized_message_deliveries ADD COLUMN {name} {definition}")
        conn.executescript("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mailbox_delivery_imap_locator
          ON reseller_authorized_message_deliveries(
            mailbox_binding_id,folder_key,imap_uidvalidity,imap_uid)
          WHERE mailbox_binding_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_mailbox_request_lease
          ON reseller_mailbox_requests(status,lease_expires_at);
        """)
        conn.commit()
    finally:
        if own:
            conn.close()


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _moment(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class SQLiteMailboxRepository:
    def reset(self):
        """Solo para tests: respeta el trigger y elimina auditoría por recreación."""
        conn = _connect()
        try:
            conn.execute("DELETE FROM reseller_authorized_message_deliveries")
            conn.execute("DELETE FROM reseller_mailbox_requests")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _request(row):
        if not row:
            return None
        unit = {"type": row["inventory_type"], "account_id": row["inventory_account_id"],
                "profile_id": row["inventory_profile_id"]}
        return {"id": row["request_id"], "reseller_id": row["reseller_id"],
                "purchase_id": row["reseller_purchase_id"], "unit": unit,
                "assignment_version": row["assignment_version"],
                "requested_at": _moment(row["requested_at"]),
                "expires_at": _moment(row["expires_at"]),
                "last_polled_at": _moment(row["last_polled_at"]) if row["last_polled_at"] else None,
                "status": row["status"], "delivery_id": row["delivery_id"]}

    def get_request(self, request_id, reseller_id=None):
        conn = _connect()
        try:
            sql = "SELECT * FROM reseller_mailbox_requests WHERE request_id=?"
            args = [str(request_id)]
            if reseller_id is not None:
                sql += " AND reseller_id=?"; args.append(int(reseller_id))
            return self._request(conn.execute(sql, args).fetchone())
        finally: conn.close()

    def active_request(self, reseller_id, purchase_id, now):
        conn = _connect()
        try:
            row = conn.execute("""SELECT * FROM reseller_mailbox_requests
                WHERE reseller_id=? AND reseller_purchase_id=? AND status='waiting'
                AND expires_at>? ORDER BY id DESC LIMIT 1""",
                (int(reseller_id), int(purchase_id), _iso(now))).fetchone()
            return self._request(row)
        finally: conn.close()

    def create_request(self, record):
        unit = record["unit"]
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""UPDATE reseller_mailbox_requests SET status='expired',updated_at=?
                WHERE reseller_id=? AND reseller_purchase_id=? AND status='waiting' AND expires_at<=?""",
                (_iso(record["requested_at"]), record["reseller_id"], record["purchase_id"], _iso(record["requested_at"])))
            conn.execute("""INSERT INTO reseller_mailbox_requests
                (request_id,reseller_id,reseller_purchase_id,inventory_type,inventory_account_id,
                 inventory_profile_id,requested_at,expires_at,status,assignment_version,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
                record["id"], record["reseller_id"], record["purchase_id"], unit["type"],
                unit["account_id"], unit.get("profile_id"), _iso(record["requested_at"]),
                _iso(record["expires_at"]), "waiting", record["assignment_version"], _iso(record["requested_at"])))
            conn.commit()
        finally: conn.close()

    def update_request(self, record):
        conn = _connect()
        try:
            conn.execute("""UPDATE reseller_mailbox_requests SET status=?,delivery_id=?,
                last_polled_at=?,updated_at=? WHERE request_id=? AND reseller_id=?""",
                (record["status"], record.get("delivery_id"),
                 _iso(record["last_polled_at"]) if record.get("last_polled_at") else None,
                 _iso(datetime.now(timezone.utc)), record["id"], record["reseller_id"]))
            conn.commit()
        finally: conn.close()

    def create_delivery(self, record, delivery, delivered_at):
        unit = record["unit"]
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            locator=delivery.get("provider_locator")
            conn.execute("""INSERT OR IGNORE INTO reseller_authorized_message_deliveries
                (delivery_id,request_id,reseller_id,reseller_purchase_id,inventory_type,
                 inventory_account_id,inventory_profile_id,message_type,service,
                 provider_reference_opaca,received_at,delivered_at,mailbox_binding_id,
                 folder_key,imap_uidvalidity,imap_uid,provider_locator_version)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""", (
                delivery["id"], record["id"], record["reseller_id"], record["purchase_id"],
                unit["type"], unit["account_id"], unit.get("profile_id"), delivery["kind"],
                delivery["service"], delivery["provider_reference"], _iso(delivery["received_at"]),
                _iso(delivered_at), getattr(locator,"binding_id",None),getattr(locator,"folder_key",None),
                getattr(locator,"uidvalidity",None),getattr(locator,"uid",None)))
            row = conn.execute("""SELECT delivery_id FROM reseller_authorized_message_deliveries
                WHERE reseller_purchase_id=? AND provider_reference_opaca=?""",
                (record["purchase_id"], delivery["provider_reference"])).fetchone()
            record["delivery_id"] = row[0]
            record["status"] = "found"
            conn.execute("""UPDATE reseller_mailbox_requests SET status='found',delivery_id=?,updated_at=?
                WHERE request_id=? AND status='waiting'""", (row[0], _iso(delivered_at), record["id"]))
            conn.commit()
            return row[0]
        finally: conn.close()

    @staticmethod
    def _delivery(row):
        if not row: return None
        return {"id": row["delivery_id"], "reseller_id": row["reseller_id"],
                "purchase_id": row["reseller_purchase_id"],
                "unit": {"type": row["inventory_type"], "account_id": row["inventory_account_id"],
                         "profile_id": row["inventory_profile_id"]},
                "service": row["service"], "kind": row["message_type"], "value": None,
                "received_at": _moment(row["received_at"]),
                "provider_reference": row["provider_reference_opaca"]}

    def history_for(self, reseller_id, purchase_id, limit=20):
        conn = _connect()
        try:
            rows = conn.execute("""SELECT * FROM reseller_authorized_message_deliveries
                WHERE reseller_id=? AND reseller_purchase_id=?
                ORDER BY received_at DESC,id DESC LIMIT ?""",
                (int(reseller_id), int(purchase_id), int(limit))).fetchall()
            return [self._delivery(row) for row in rows]
        finally: conn.close()

    def get_delivery(self, delivery_id, reseller_id):
        conn = _connect()
        try:
            return self._delivery(conn.execute("""SELECT * FROM reseller_authorized_message_deliveries
                WHERE delivery_id=? AND reseller_id=?""", (str(delivery_id), int(reseller_id))).fetchone())
        finally: conn.close()

    def append_audit(self, event):
        if event["result"] not in AUDIT_RESULTS:
            raise ValueError("invalid mailbox audit classification")
        safe_code = (event["safe_code"] if event["safe_code"] in AUDIT_SAFE_CODES
                     else "invalid_request")
        unit = event.get("inventory_unit") or {}
        event_type = {"waiting":"request_created", "delivered":"message_delivered",
                      "expired":"request_expired"}.get(event["result"], "request_denied")
        conn = _connect()
        try:
            conn.execute("""INSERT INTO reseller_message_audit_events
                (event_id,event_type,actor_type,reseller_id,reseller_purchase_id,inventory_type,
                 inventory_account_id,inventory_profile_id,request_id,result,safe_code,
                 provider_reference_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                event["event_id"], event_type, "reseller", event["reseller_id"], event["purchase_id"],
                unit.get("type"), unit.get("account_id"), unit.get("profile_id"), event["request_id"],
                event["result"], safe_code, event.get("provider_reference"), event["timestamp"]))
            conn.commit()
        finally: conn.close()

    def claim_poll(self, request_id, reseller_id, owner, now, lease_seconds=15):
        expires = datetime.fromtimestamp(now.timestamp()+lease_seconds, timezone.utc)
        conn=_connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            changed=conn.execute("""UPDATE reseller_mailbox_requests
              SET lease_owner=?,lease_expires_at=?,updated_at=?
              WHERE request_id=? AND reseller_id=? AND status='waiting'
              AND (lease_owner IS NULL OR lease_expires_at<=? OR lease_owner=?)""",
              (owner,_iso(expires),_iso(now),str(request_id),int(reseller_id),_iso(now),owner)).rowcount
            conn.commit(); return changed==1
        finally: conn.close()

    def release_poll(self, request_id, owner):
        conn=_connect()
        try:
            conn.execute("""UPDATE reseller_mailbox_requests SET lease_owner=NULL,lease_expires_at=NULL
              WHERE request_id=? AND lease_owner=?""",(str(request_id),str(owner)))
            conn.commit()
        finally: conn.close()
