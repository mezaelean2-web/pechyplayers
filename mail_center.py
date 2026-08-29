"""Centro de Correo: configuración administrativa no sensible y acciones allowlist."""

import json
import re
import sqlite3
from email.header import decode_header
from email.utils import getaddresses

import database
import managed_secret_store
from mail_message_parsers import ServiceAdapterRegistry
from netflix_link_adapter import LinkHostRule, NetflixLinkAdapter
from private_email_provider import ProviderError


MAILBOX_PROVIDERS = frozenset({"private_email"})
EXTRACTOR_TYPES = frozenset({"password_reset_link"})
_KEY_RE = re.compile(r"[a-z][a-z0-9_]{2,63}")
_HOST_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+")
_CONFIG_RE = re.compile(r"[a-z][a-z0-9_-]{2,63}")


class MailCenterError(Exception):
    safe_code = "mail_center_invalid"


def _connection(connection=None):
    return connection or database.conectar()


def initialize_schema(connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS mail_center_mailboxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            provider TEXT NOT NULL CHECK(provider='private_email'),
            host TEXT NOT NULL,
            port INTEGER NOT NULL CHECK(port BETWEEN 1 AND 65535),
            tls_mode TEXT NOT NULL CHECK(tls_mode='required'),
            secret_ref TEXT NOT NULL UNIQUE,
            folder_key TEXT NOT NULL CHECK(folder_key='INBOX'),
            enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS mail_center_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL COLLATE NOCASE,
            internal_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            subject_policy TEXT NOT NULL,
            extractor_type TEXT NOT NULL CHECK(extractor_type='password_reset_link'),
            extractor_config TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(platform,internal_key)
        );
        CREATE INDEX IF NOT EXISTS idx_mail_center_actions_enabled
            ON mail_center_actions(enabled,platform,display_name);
        CREATE TABLE IF NOT EXISTS mail_center_admin_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL CHECK(entity_type IN ('mailbox','action')),
            entity_id INTEGER NOT NULL,
            actor TEXT NOT NULL,
            result_code TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TRIGGER IF NOT EXISTS trg_mail_center_audit_no_update
            BEFORE UPDATE ON mail_center_admin_audit BEGIN
              SELECT RAISE(ABORT,'mail center audit is append-only');
            END;
        CREATE TRIGGER IF NOT EXISTS trg_mail_center_audit_no_delete
            BEFORE DELETE ON mail_center_admin_audit BEGIN
              SELECT RAISE(ABORT,'mail center audit is append-only');
            END;
        CREATE TABLE IF NOT EXISTS mail_center_action_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL CHECK(event_type IN (
                'reseller_mail_action_requested','reseller_mail_action_delivered')),
            reseller_id INTEGER NOT NULL,
            reseller_purchase_id INTEGER NOT NULL,
            action_id INTEGER NOT NULL,
            result_code TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TRIGGER IF NOT EXISTS trg_mail_center_action_events_no_update
            BEFORE UPDATE ON mail_center_action_events BEGIN
              SELECT RAISE(ABORT,'mail action audit is append-only');
            END;
        CREATE TRIGGER IF NOT EXISTS trg_mail_center_action_events_no_delete
            BEFORE DELETE ON mail_center_action_events BEGIN
              SELECT RAISE(ABORT,'mail action audit is append-only');
            END;
        """)
        managed_secret_store.initialize_schema(conn)
        mailbox_columns={row[1] for row in conn.execute("PRAGMA table_info(mail_center_mailboxes)")}
        if "credential_hint" not in mailbox_columns:
            conn.execute("ALTER TABLE mail_center_mailboxes ADD COLUMN credential_hint TEXT")
        conn.commit()
    finally:
        if own:
            conn.close()


def _clean_text(value, maximum=120):
    value = " ".join(str(value or "").strip().split())
    if not value or len(value) > maximum or any(char in value for char in "\r\n\x00"):
        raise MailCenterError()
    return value


def _audit(conn, event, entity, entity_id, actor, code="ok"):
    allowed = {"mailbox_config_created", "mailbox_config_updated", "mailbox_connection_tested",
               "mail_action_created", "mail_action_updated", "mail_action_enabled",
               "mail_action_disabled"}
    if event not in allowed:
        raise MailCenterError()
    conn.execute("""INSERT INTO mail_center_admin_audit
        (event_type,entity_type,entity_id,actor,result_code) VALUES(?,?,?,?,?)""",
        (event, entity, int(entity_id), _clean_text(actor, 80), _clean_text(code, 64)))


def _mailbox_values(payload):
    provider = str(payload.get("provider") or "").strip().lower()
    host = str(payload.get("host") or "").strip().lower().rstrip(".")
    secret_ref = str(payload.get("secret_ref") or "").strip()
    folder = str(payload.get("folder_key") or "").strip().upper()
    try:
        port = int(payload.get("port"))
    except (TypeError, ValueError) as exc:
        raise MailCenterError() from exc
    if (provider not in MAILBOX_PROVIDERS or host != "mail.privateemail.com" or port != 993
            or str(payload.get("tls_mode") or "") != "required" or folder != "INBOX"
            or not (_CONFIG_RE.fullmatch(secret_ref)
                    or (secret_ref.startswith(managed_secret_store.REFERENCE_PREFIX)
                        and re.fullmatch(r"ms1_[A-Za-z0-9_-]{30,76}",secret_ref)))):
        raise MailCenterError()
    return (_clean_text(payload.get("display_name")), provider, host, port, "required",
            secret_ref, folder, int(bool(payload.get("enabled"))))


def save_mailbox(payload, *, mailbox_id=None, actor="admin", connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        values = _mailbox_values(payload)
        conn.execute("BEGIN IMMEDIATE")
        if mailbox_id is None:
            cursor = conn.execute("""INSERT INTO mail_center_mailboxes
                (display_name,provider,host,port,tls_mode,secret_ref,folder_key,enabled)
                VALUES(?,?,?,?,?,?,?,?)""", values)
            entity_id = cursor.lastrowid
            event = "mailbox_config_created"
        else:
            entity_id = int(mailbox_id)
            changed = conn.execute("""UPDATE mail_center_mailboxes SET display_name=?,provider=?,host=?,
                port=?,tls_mode=?,secret_ref=?,folder_key=?,enabled=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=?""", (*values, entity_id)).rowcount
            if changed != 1:
                raise MailCenterError()
            event = "mailbox_config_updated"
        _audit(conn, event, "mailbox", entity_id, actor)
        conn.commit()
        return entity_id
    except (sqlite3.Error, ValueError, MailCenterError):
        conn.rollback()
        raise MailCenterError() from None
    finally:
        if own:
            conn.close()


def list_mailboxes(connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        return [dict(row) for row in conn.execute("""SELECT id,display_name,provider,host,port,
            tls_mode,folder_key,enabled,credential_hint,created_at,updated_at,
            CASE WHEN secret_ref LIKE 'ms1_%' THEN 1 ELSE 0 END AS credential_configured
            FROM mail_center_mailboxes ORDER BY id""").fetchall()]
    finally:
        if own:
            conn.close()


def test_mailbox_connection(mailbox_id, resolver, transport_factory, *, actor="admin", connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        row = conn.execute("SELECT * FROM mail_center_mailboxes WHERE id=?", (int(mailbox_id),)).fetchone()
        if not row or not row["enabled"]:
            raise MailCenterError()
        resolver.resolve(row["secret_ref"])
        transport = transport_factory(resolver)
        try:
            state = transport.examine(row["secret_ref"], row["folder_key"])
            if int(state["uidvalidity"]) <= 0 or int(state["uidnext"]) <= 0:
                raise MailCenterError()
            result = {"ok": True, "status": "connected"}
            code = "connected"
        except ProviderError as exc:
            safe=getattr(exc,"safe_code","")
            status={"provider_auth_failed":"authentication_failed",
                    "provider_unavailable":"connection_failed",
                    "provider_timeout":"connection_failed",
                    "provider_tls_failed":"tls_failed",
                    "provider_config_invalid":"configuration_failed",
                    "provider_protocol_error":"folder_unavailable"}.get(safe,"connection_failed")
            result = {"ok": False, "status": status}
            code = result["status"]
        conn.execute("BEGIN IMMEDIATE")
        _audit(conn, "mailbox_connection_tested", "mailbox", row["id"], actor, code)
        conn.commit()
        return result
    except (sqlite3.Error, ValueError, MailCenterError):
        conn.rollback()
        return {"ok": False, "status": "configuration_failed"}
    finally:
        if own:
            conn.close()


def _masked_username(value):
    username=str(value or "").strip()
    if "@" not in username:return "Configurada"
    local,domain=username.rsplit("@",1)
    return ((local[:1]+"***" if local else "***")+"@"+domain)


def _managed_config_values(payload):
    safe=dict(payload or {}); safe["secret_ref"]="managed_placeholder"
    values=_mailbox_values(safe)
    username=str(payload.get("username") or "").strip()
    password=str(payload.get("password") or "")
    if not username or "@" not in username or len(username)>254 or not password or len(password)>1024:
        raise MailCenterError()
    return values,username,password


def save_managed_mailbox(payload, secret_store, *, actor="admin", connection=None):
    own=connection is None; conn=_connection(connection); password=None
    try:
        initialize_schema(conn); values,username,password=_managed_config_values(payload)
        conn.execute("BEGIN IMMEDIATE")
        secret_ref=secret_store.put({"username":username,"password":password},connection=conn)
        configured=(*values[:5],secret_ref,*values[6:])
        cursor=conn.execute("""INSERT INTO mail_center_mailboxes
            (display_name,provider,host,port,tls_mode,secret_ref,folder_key,enabled,credential_hint)
            VALUES(?,?,?,?,?,?,?,?,?)""",(*configured,_masked_username(username)))
        _audit(conn,"mailbox_config_created","mailbox",cursor.lastrowid,actor)
        conn.commit(); return cursor.lastrowid
    except (managed_secret_store.SecretStoreError,sqlite3.Error,MailCenterError,ValueError,TypeError):
        conn.rollback(); raise MailCenterError() from None
    finally:
        password=None
        if own:conn.close()


def update_mailbox_configuration(mailbox_id,payload,*,actor="admin",connection=None):
    own=connection is None; conn=_connection(connection)
    try:
        initialize_schema(conn); row=conn.execute("SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",
                                                  (int(mailbox_id),)).fetchone()
        if not row:raise MailCenterError()
        safe=dict(payload or {}); safe["secret_ref"]=row[0]; values=_mailbox_values(safe)
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("""UPDATE mail_center_mailboxes SET display_name=?,provider=?,host=?,port=?,
            tls_mode=?,folder_key=?,enabled=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (*values[:5],values[6],values[7],int(mailbox_id))).rowcount!=1:raise MailCenterError()
        _audit(conn,"mailbox_config_updated","mailbox",mailbox_id,actor);conn.commit()
    except (sqlite3.Error,MailCenterError,ValueError,TypeError):
        conn.rollback();raise MailCenterError() from None
    finally:
        if own:conn.close()


def rotate_mailbox_credential(mailbox_id,username,password,secret_store,*,actor="admin",connection=None):
    own=connection is None;conn=_connection(connection);password=str(password or "")
    try:
        initialize_schema(conn);row=conn.execute("SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",
                                                 (int(mailbox_id),)).fetchone()
        if not row or not str(row[0]).startswith(managed_secret_store.REFERENCE_PREFIX):raise MailCenterError()
        username=str(username or "").strip()
        conn.execute("BEGIN IMMEDIATE")
        secret_store.replace(row[0],{"username":username,"password":password},connection=conn)
        conn.execute("UPDATE mail_center_mailboxes SET credential_hint=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                     (_masked_username(username),int(mailbox_id)))
        _audit(conn,"mailbox_config_updated","mailbox",mailbox_id,actor,"credential_rotated");conn.commit()
    except (managed_secret_store.SecretStoreError,sqlite3.Error,MailCenterError,ValueError,TypeError):
        conn.rollback();raise MailCenterError() from None
    finally:
        password=None
        if own:conn.close()


def test_unsaved_credentials(payload,transport_factory):
    password=None
    try:
        values,username,password=_managed_config_values(payload)
        from private_email_credentials import ProviderCredentialResolver
        reference="transient"
        resolver=ProviderCredentialResolver(bundle={reference:{"username":username,"password":password}})
        transport=transport_factory(resolver)
        state=transport.examine(reference,values[6])
        if int(state["uidvalidity"])<=0 or int(state["uidnext"])<=0:raise MailCenterError()
        return {"ok":True,"status":"connected"}
    except ProviderError as exc:
        safe=getattr(exc,"safe_code","")
        status={"provider_auth_failed":"authentication_failed","provider_unavailable":"connection_failed",
                "provider_timeout":"connection_failed","provider_config_invalid":"configuration_failed",
                "provider_tls_failed":"tls_failed",
                "provider_protocol_error":"folder_unavailable"}.get(safe,"connection_failed")
        return {"ok":False,"status":status}
    except Exception:
        return {"ok":False,"status":"configuration_failed"}
    finally:
        password=None


def delete_managed_mailbox(mailbox_id,secret_store,*,actor="admin",connection=None):
    own=connection is None;conn=_connection(connection)
    try:
        initialize_schema(conn);conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(int(mailbox_id),)).fetchone()
        if not row or not str(row[0]).startswith(managed_secret_store.REFERENCE_PREFIX):raise MailCenterError()
        if conn.execute("SELECT COUNT(*) FROM mail_center_mailboxes WHERE secret_ref=?",(row[0],)).fetchone()[0]!=1:
            raise MailCenterError()
        if conn.execute("SELECT 1 FROM reseller_mailbox_bindings WHERE provider_config_id=? LIMIT 1",(row[0],)).fetchone():
            raise MailCenterError()
        conn.execute("DELETE FROM mail_center_mailboxes WHERE id=?",(int(mailbox_id),))
        secret_store.delete(row[0],connection=conn);conn.commit()
    except (managed_secret_store.SecretStoreError,sqlite3.Error,MailCenterError,ValueError,TypeError):
        conn.rollback();raise MailCenterError() from None
    finally:
        if own:conn.close()


def _canonical_platform(conn, value):
    value = _clean_text(value, 80)
    row = conn.execute("""SELECT MIN(trim(plataforma)) FROM nube_cuentas
        WHERE lower(trim(plataforma))=lower(trim(?))""", (value,)).fetchone()
    if not row or not row[0]:
        raise MailCenterError()
    return row[0]


def _validated_extractor_config(extractor_type, config):
    if extractor_type != "password_reset_link" or not isinstance(config, dict):
        raise MailCenterError()
    hosts = config.get("allowed_link_hosts")
    senders = config.get("sender_domains")
    if not isinstance(hosts, list) or not hosts or len(hosts) > 20:
        raise MailCenterError()
    if not isinstance(senders, list) or not senders or len(senders) > 20:
        raise MailCenterError()
    normalized_hosts = []
    for item in hosts:
        if not isinstance(item, dict) or set(item) - {"hostname", "allow_subdomains"}:
            raise MailCenterError()
        host = str(item.get("hostname") or "").strip().lower().rstrip(".")
        if not _HOST_RE.fullmatch(host) or host.startswith("xn--") or ".xn--" in host:
            raise MailCenterError()
        normalized_hosts.append({"hostname": host, "allow_subdomains": bool(item.get("allow_subdomains"))})
    normalized_senders = []
    for item in senders:
        domain = str(item or "").strip().lower().rstrip(".")
        if not _HOST_RE.fullmatch(domain):
            raise MailCenterError()
        normalized_senders.append(domain)
    return {"allowed_link_hosts": normalized_hosts, "sender_domains": sorted(set(normalized_senders)),
            "require_dkim_spf": bool(config.get("require_dkim_spf", False))}


def save_action(payload, *, action_id=None, actor="admin", connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        platform = _canonical_platform(conn, payload.get("platform"))
        key = str(payload.get("internal_key") or "").strip().lower()
        extractor = str(payload.get("extractor_type") or "").strip()
        if not _KEY_RE.fullmatch(key) or extractor not in EXTRACTOR_TYPES:
            raise MailCenterError()
        config = _validated_extractor_config(extractor, payload.get("extractor_config"))
        values = (platform, key, _clean_text(payload.get("display_name")),
                  _clean_text(payload.get("subject_policy"), 255), extractor,
                  json.dumps(config, sort_keys=True, separators=(",", ":")),
                  int(bool(payload.get("enabled"))))
        conn.execute("BEGIN IMMEDIATE")
        if action_id is None:
            cursor = conn.execute("""INSERT INTO mail_center_actions(platform,internal_key,
                display_name,subject_policy,extractor_type,extractor_config,enabled)
                VALUES(?,?,?,?,?,?,?)""", values)
            entity_id, event = cursor.lastrowid, "mail_action_created"
        else:
            entity_id = int(action_id)
            old = conn.execute("SELECT enabled FROM mail_center_actions WHERE id=?", (entity_id,)).fetchone()
            if not old:
                raise MailCenterError()
            conn.execute("""UPDATE mail_center_actions SET platform=?,internal_key=?,display_name=?,
                subject_policy=?,extractor_type=?,extractor_config=?,enabled=?,updated_at=CURRENT_TIMESTAMP
                WHERE id=?""", (*values, entity_id))
            event = ("mail_action_enabled" if values[-1] and not old[0] else
                     "mail_action_disabled" if not values[-1] and old[0] else "mail_action_updated")
        _audit(conn, event, "action", entity_id, actor)
        conn.commit()
        return entity_id
    except (sqlite3.Error, ValueError, MailCenterError, TypeError):
        conn.rollback()
        raise MailCenterError() from None
    finally:
        if own:
            conn.close()


def _action(row):
    if not row:
        return None
    result = dict(row)
    try:
        result["extractor_config"] = _validated_extractor_config(
            result["extractor_type"], json.loads(result["extractor_config"]))
    except Exception:
        return None
    result["enabled"] = bool(result["enabled"])
    return result


def list_actions(*, enabled_only=False, platform=None, connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        clauses, args = [], []
        if enabled_only:
            clauses.append("enabled=1")
        if platform:
            clauses.append("lower(platform)=lower(?)")
            args.append(str(platform).strip())
        sql = "SELECT * FROM mail_center_actions" + (" WHERE " + " AND ".join(clauses) if clauses else "")
        return [item for item in (_action(row) for row in conn.execute(
            sql + " ORDER BY platform,display_name,id", args).fetchall()) if item]
    finally:
        if own:
            conn.close()


def get_action(action_id, *, enabled_only=True, connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        initialize_schema(conn)
        sql = "SELECT * FROM mail_center_actions WHERE id=?" + (" AND enabled=1" if enabled_only else "")
        return _action(conn.execute(sql, (int(action_id),)).fetchone())
    except (TypeError, ValueError):
        return None
    finally:
        if own:
            conn.close()


def platform_for_unit(unit, connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        row = conn.execute("SELECT plataforma FROM nube_cuentas WHERE id=?",
                           (int(unit["account_id"]),)).fetchone()
        return str(row[0]).strip() if row and row[0] else None
    except (KeyError, TypeError, ValueError):
        return None
    finally:
        if own:
            conn.close()


def recipient_for_unit(unit, connection=None):
    own = connection is None
    conn = _connection(connection)
    try:
        row = conn.execute("SELECT correo FROM nube_cuentas WHERE id=?",
                           (int(unit["account_id"]),)).fetchone()
        return str(row[0]).strip().lower() if row and row[0] and "@" in str(row[0]) else None
    except (KeyError, TypeError, ValueError):
        return None
    finally:
        if own:
            conn.close()


def action_runtime(action, unit):
    if not action or not action.get("enabled"):
        return None
    platform = platform_for_unit(unit)
    recipient = recipient_for_unit(unit)
    if not platform or platform.casefold() != str(action["platform"]).casefold() or not recipient:
        return None
    return {**action, "expected_recipient": recipient}


def available_actions_for_reseller(reseller_id, *, now=None):
    import inventory_assignment_access
    conn = database.conectar()
    try:
        purchase_ids = [row[0] for row in conn.execute(
            "SELECT id FROM reseller_purchases WHERE revendedor_id=? ORDER BY id", (int(reseller_id),))]
    finally:
        conn.close()
    platforms = set()
    for purchase_id in purchase_ids:
        result = inventory_assignment_access.authorize_reseller_message_access(
            reseller_id, purchase_id, now=now)
        if result.get("authorized") is True:
            platform = platform_for_unit(result["inventory_unit"])
            if platform:
                platforms.add(platform.casefold())
    return [action for action in list_actions(enabled_only=True)
            if action["platform"].casefold() in platforms]


def append_reseller_event(event_type, reseller_id, purchase_id, action_id, result_code):
    if event_type not in {"reseller_mail_action_requested", "reseller_mail_action_delivered"}:
        raise MailCenterError()
    code = str(result_code or "invalid_request").strip()
    if not re.fullmatch(r"[a-z_]{2,64}", code):
        code = "invalid_request"
    conn = database.conectar()
    try:
        initialize_schema(conn)
        conn.execute("""INSERT INTO mail_center_action_events(event_type,reseller_id,
            reseller_purchase_id,action_id,result_code) VALUES(?,?,?,?,?)""",
            (event_type,int(reseller_id),int(purchase_id),int(action_id),code))
        conn.commit()
    finally:
        conn.close()


def _decoded_subject(value):
    pieces = []
    for part, charset in decode_header(str(value or "")):
        pieces.append(part.decode(charset or "ascii", "strict") if isinstance(part, bytes) else str(part))
    return "".join(pieces)


def action_metadata_matches(action, metadata):
    try:
        if _decoded_subject(metadata.get("subject")) != action["subject_policy"]:
            return False
        addresses = [address.strip().lower() for _, address in getaddresses([str(metadata.get("to") or "")])]
        if addresses != [action["expected_recipient"]]:
            return False
        senders = [address.strip().lower() for _, address in getaddresses([str(metadata.get("from") or "")])]
        if len(senders) != 1 or senders[0].rsplit("@", 1)[-1] not in action["extractor_config"]["sender_domains"]:
            return False
        if action["extractor_config"].get("require_dkim_spf"):
            auth = str(metadata.get("authentication_results") or "").lower()
            if "dkim=pass" not in auth or "spf=pass" not in auth:
                return False
        return True
    except (LookupError, UnicodeError, ValueError, KeyError, TypeError):
        return False


def build_action_registry(action):
    if action.get("extractor_type") != "password_reset_link":
        raise MailCenterError()
    rules = [LinkHostRule(item["hostname"], item["allow_subdomains"])
             for item in action["extractor_config"]["allowed_link_hosts"]]
    return ServiceAdapterRegistry([NetflixLinkAdapter(subjects={action["subject_policy"]},
                                                       allowed_link_hosts=rules)])
