"""Resolución interna de unidad autorizada a mailbox; nunca usa el email buscado."""

from dataclasses import dataclass

import database

ALLOWED_PROVIDERS = frozenset({"private_email"})
ALLOWED_FOLDERS = frozenset({"INBOX"})


@dataclass(frozen=True)
class MailboxBinding:
    binding_id: int
    provider: str
    provider_config_id: str
    folder_key: str
    binding_version: int
    enabled: bool
    inventory_type: str
    account_id: int
    profile_id: int | None


class MailboxBindingDenied(Exception):
    def __init__(self, safe_code="mailbox_binding_denied"):
        super().__init__(safe_code)
        self.safe_code = safe_code


def initialize_schema(connection=None):
    own = connection is None
    conn = connection or database.conectar()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reseller_mailbox_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_type TEXT NOT NULL CHECK (inventory_type IN ('cuenta','perfil')),
            inventory_account_id INTEGER NOT NULL,
            inventory_profile_id INTEGER,
            provider TEXT NOT NULL CHECK (provider IN ('private_email')),
            provider_config_id TEXT NOT NULL CHECK (length(trim(provider_config_id)) BETWEEN 1 AND 80),
            folder_key TEXT NOT NULL DEFAULT 'INBOX' CHECK (folder_key IN ('INBOX')),
            binding_version INTEGER NOT NULL DEFAULT 1 CHECK (binding_version > 0),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((inventory_type='cuenta' AND inventory_profile_id IS NULL)
                OR (inventory_type='perfil' AND inventory_profile_id IS NOT NULL)),
            FOREIGN KEY (inventory_account_id) REFERENCES nube_cuentas(id),
            FOREIGN KEY (inventory_profile_id) REFERENCES nube_perfiles(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mailbox_binding_enabled_unit
            ON reseller_mailbox_bindings(
                inventory_type,inventory_account_id,coalesce(inventory_profile_id,-1))
            WHERE enabled=1;
        CREATE INDEX IF NOT EXISTS idx_mailbox_binding_config
            ON reseller_mailbox_bindings(provider,provider_config_id,enabled);
        """)
        conn.commit()
    finally:
        if own: conn.close()


class MailboxBindingResolver:
    def resolve(self, inventory_unit, reseller_purchase_id, assignment_version):
        if not isinstance(inventory_unit, dict) or not assignment_version:
            raise MailboxBindingDenied()
        unit_type = inventory_unit.get("type")
        account_id = inventory_unit.get("account_id")
        profile_id = inventory_unit.get("profile_id")
        if unit_type not in {"cuenta", "perfil"} or not isinstance(account_id, int):
            raise MailboxBindingDenied()
        if (unit_type == "cuenta") != (profile_id is None):
            raise MailboxBindingDenied()
        conn = database.conectar()
        try:
            rows = conn.execute("""SELECT * FROM reseller_mailbox_bindings
                WHERE inventory_type=? AND inventory_account_id=?
                AND coalesce(inventory_profile_id,-1)=coalesce(?,-1) AND enabled=1""",
                (unit_type, account_id, profile_id)).fetchall()
        finally: conn.close()
        if len(rows) != 1:
            raise MailboxBindingDenied("mailbox_binding_ambiguous" if rows else "mailbox_binding_missing")
        row = rows[0]
        if row["provider"] not in ALLOWED_PROVIDERS or row["folder_key"] not in ALLOWED_FOLDERS:
            raise MailboxBindingDenied()
        config_id = str(row["provider_config_id"] or "").strip()
        if not config_id or int(row["binding_version"] or 0) <= 0:
            raise MailboxBindingDenied()
        return MailboxBinding(int(row["id"]), row["provider"], config_id,
            row["folder_key"], int(row["binding_version"]), True, unit_type,
            account_id, profile_id)
