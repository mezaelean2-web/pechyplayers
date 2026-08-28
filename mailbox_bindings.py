"""Resolución interna de unidad autorizada a mailbox; nunca usa el email buscado."""

from dataclasses import dataclass
import sqlite3
from threading import RLock

import database
import inventory_assignment_access
from private_email_provider import ProviderConfigurationError

ALLOWED_PROVIDERS = frozenset({"private_email"})
ALLOWED_FOLDERS = frozenset({"INBOX"})
PILOT_PROVIDER_CONFIGS = frozenset({"pechy_pilot"})
_ADMIN_BINDING_LOCK = RLock()


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


class MailboxBindingAdminError(Exception):
    def __init__(self, safe_code="mailbox_binding_admin_denied"):
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


class AdministrativeMailboxBindingService:
    """Alta y reemplazo internos; no acepta email ni abre transporte de red."""

    def __init__(self, credential_resolver, *, approved_provider_configs=None):
        if credential_resolver is None:
            raise MailboxBindingAdminError("provider_config_invalid")
        self.credential_resolver = credential_resolver
        approved = (PILOT_PROVIDER_CONFIGS if approved_provider_configs is None
                    else approved_provider_configs)
        self.approved_provider_configs = frozenset(approved)

    @staticmethod
    def _binding(row):
        return MailboxBinding(int(row["id"]), row["provider"],
            str(row["provider_config_id"]).strip(), row["folder_key"],
            int(row["binding_version"]), bool(row["enabled"]),
            row["inventory_type"], int(row["inventory_account_id"]),
            int(row["inventory_profile_id"]) if row["inventory_profile_id"] is not None else None)

    def create_or_replace(self, *, reseller_id, reseller_purchase_id,
                          provider, provider_config_id, folder_key, now=None):
        if provider != "private_email":
            raise MailboxBindingAdminError("provider_invalid")
        if folder_key != "INBOX":
            raise MailboxBindingAdminError("folder_invalid")
        config_id = str(provider_config_id or "").strip()
        if config_id not in self.approved_provider_configs:
            raise MailboxBindingAdminError("provider_config_not_approved")
        try:
            self.credential_resolver.resolve(config_id)
        except Exception:
            raise MailboxBindingAdminError("provider_config_invalid") from None

        _ADMIN_BINDING_LOCK.acquire()
        try:
            conn = database.conectar()
        except Exception:
            _ADMIN_BINDING_LOCK.release()
            raise MailboxBindingAdminError("binding_write_failed") from None
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            authorization = inventory_assignment_access.authorize_reseller_message_access(
                reseller_id, reseller_purchase_id, now=now, connection=conn)
            if authorization.get("authorized") is not True:
                raise MailboxBindingAdminError("assignment_not_authorized")
            unit = authorization["inventory_unit"]
            account = conn.execute("SELECT id FROM nube_cuentas WHERE id=?",
                (unit["account_id"],)).fetchone()
            if account is None:
                raise MailboxBindingAdminError("inventory_invalid")
            if unit["type"] == "perfil":
                profile = conn.execute(
                    "SELECT cuenta_id FROM nube_perfiles WHERE id=?", (unit["profile_id"],)).fetchone()
                if profile is None or int(profile["cuenta_id"]) != int(account["id"]):
                    raise MailboxBindingAdminError("inventory_invalid")
            elif unit["type"] != "cuenta" or unit.get("profile_id") is not None:
                raise MailboxBindingAdminError("inventory_invalid")

            rows = conn.execute("""SELECT * FROM reseller_mailbox_bindings
                WHERE inventory_type=? AND inventory_account_id=?
                AND coalesce(inventory_profile_id,-1)=coalesce(?,-1)
                ORDER BY binding_version,id""", (unit["type"], unit["account_id"],
                unit.get("profile_id"))).fetchall()
            active = [row for row in rows if int(row["enabled"]) == 1]
            if len(active) > 1:
                raise MailboxBindingAdminError("binding_state_ambiguous")
            if active and active[0]["provider"] == provider \
                    and str(active[0]["provider_config_id"]).strip() == config_id \
                    and active[0]["folder_key"] == folder_key:
                conn.commit()
                return self._binding(active[0])

            next_version = max((int(row["binding_version"]) for row in rows), default=0) + 1
            if active:
                conn.execute("""UPDATE reseller_mailbox_bindings
                    SET enabled=0,updated_at=CURRENT_TIMESTAMP WHERE id=? AND enabled=1""",
                    (active[0]["id"],))
            cursor = conn.execute("""INSERT INTO reseller_mailbox_bindings
                (inventory_type,inventory_account_id,inventory_profile_id,provider,
                 provider_config_id,folder_key,binding_version,enabled)
                VALUES (?,?,?,?,?,?,?,1)""", (unit["type"], unit["account_id"],
                unit.get("profile_id"), provider, config_id, folder_key, next_version))
            row = conn.execute("SELECT * FROM reseller_mailbox_bindings WHERE id=?",
                (cursor.lastrowid,)).fetchone()
            conn.commit()
            return self._binding(row)
        except MailboxBindingAdminError:
            conn.rollback()
            raise
        except (sqlite3.Error, ProviderConfigurationError):
            conn.rollback()
            raise MailboxBindingAdminError("binding_write_failed") from None
        except Exception:
            conn.rollback()
            raise MailboxBindingAdminError("binding_write_failed") from None
        finally:
            conn.close()
            _ADMIN_BINDING_LOCK.release()
