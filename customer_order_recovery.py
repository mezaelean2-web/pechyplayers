"""Recuperacion segura de pedidos mediante OTP multicanal."""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

import customer_delivery_access
import customer_order_email
import database


OTP_TTL_SECONDS = 300
OTP_AUTHORIZATION_TTL_SECONDS = 1800
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_VERIFY_ATTEMPTS = 5
OTP_ORDER_WINDOW_LIMIT = 5
OTP_REQUESTER_WINDOW_LIMIT = 10
OTP_RATE_WINDOW_SECONDS = 3600
OTP_CODE_RE = re.compile(r"^[0-9]{6}$")
PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
CHANNELS = frozenset({"email", "whatsapp"})
RECOVERY_SESSION_KEY = "customer_order_recovery_context"
ACCESS_SESSION_KEY = "customer_order_recovery_access"


class RecoveryError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _connect():
    connection = database.conectar()
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _now(value=None):
    return (value or datetime.now(timezone.utc)).replace(microsecond=0)


def _timestamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def initialize_schema(connection=None):
    owns = connection is None
    conn = connection or _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customer_order_otp_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                channel TEXT NOT NULL CHECK(channel IN ('email','whatsapp')),
                code_hash TEXT NOT NULL CHECK(length(code_hash)=64),
                code_salt TEXT NOT NULL CHECK(length(code_salt)=32),
                requester_fingerprint TEXT NOT NULL CHECK(length(requester_fingerprint)=24),
                destination_fingerprint TEXT NOT NULL CHECK(length(destination_fingerprint)=64),
                status TEXT NOT NULL CHECK(status IN
                    ('active','consumed','expired','invalidated','locked','failed')),
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
                last_error_code TEXT CHECK(last_error_code IS NULL OR length(last_error_code)<=40),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                FOREIGN KEY(order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_customer_order_otp_active
                ON customer_order_otp_challenges(order_id,status,id DESC);
            CREATE INDEX IF NOT EXISTS idx_customer_order_otp_requester
                ON customer_order_otp_challenges(requester_fingerprint,created_at,id DESC);
        """)
        if owns:
            conn.commit()
    except Exception:
        if owns:
            conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def mask_email(value):
    if not isinstance(value, str) or value.count("@") != 1:
        return "***@***"
    local, domain = value.rsplit("@", 1)
    return f"{local[:1] or '*'}***@{domain}" if domain else "***@***"


def mask_phone(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return "******" + digits[-4:] if len(digits) >= 4 else "**********"


def _destination_fingerprint(destination, secret_key):
    return hmac.new(str(secret_key).encode(), str(destination).encode(), hashlib.sha256).hexdigest()


def requester_fingerprint(session_fingerprint, remote_address, secret_key):
    material = f"{session_fingerprint}|{remote_address or ''}".encode()
    return hmac.new(str(secret_key).encode(), material, hashlib.sha256).hexdigest()[:24]


def _find_order(public_order_id):
    try:
        normalized = customer_delivery_access.normalize_public_order_id(public_order_id)
    except customer_delivery_access.CustomerOrderLookupNotFound:
        return None
    conn = _connect()
    try:
        columns = {item[1] for item in conn.execute("PRAGMA table_info(customer_orders)")}
        email = "customer_email" if "customer_email" in columns else "NULL AS customer_email"
        phone = "customer_whatsapp" if "customer_whatsapp" in columns else "NULL AS customer_whatsapp"
        row = conn.execute(f"""SELECT id,public_order_id,status,{email},{phone}
            FROM customer_orders WHERE public_order_id=?""", (normalized,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def whatsapp_configuration():
    """No declara disponibilidad hasta existir un adaptador oficial soportado."""
    provider = os.environ.get("ORDER_OTP_WHATSAPP_PROVIDER", "").strip().lower()
    return {"configured": False, "provider": provider or None}


def available_channels(order, *, whatsapp_transport=None):
    channels = []
    if order and isinstance(order.get("customer_email"), str) and order["customer_email"]:
        channels.append({"channel": "email", "destination": mask_email(order["customer_email"])})
    whatsapp_ready = whatsapp_transport is not None or whatsapp_configuration()["configured"]
    if (order and whatsapp_ready and isinstance(order.get("customer_whatsapp"), str)
            and PHONE_RE.fullmatch(order["customer_whatsapp"])):
        channels.append({"channel": "whatsapp", "destination": mask_phone(order["customer_whatsapp"])})
    return channels


def prepare_recovery(public_order_id):
    order = _find_order(public_order_id)
    channels = available_channels(order)
    if not channels:
        channels = [{"channel": "email", "destination": "m***@correo.com", "available": True}]
    else:
        channels = [dict(item, available=True) for item in channels]
    return {"order": order, "channels": channels}


def _hash_code(code, salt, order_id, secret_key):
    value = f"{order_id}:{salt}:{code}".encode()
    return hmac.new(str(secret_key).encode(), value, hashlib.sha256).hexdigest()


def _email_message(code):
    subject = "PECHY PLAYERS — Código de verificación"
    text = ("PECHY PLAYERS\n\nTu código de verificación es:\n\n"
            f"{code}\n\nExpira en 5 minutos.\n\n"
            "Si no solicitaste este código, puedes ignorar este mensaje.")
    body = f"""<!doctype html><html lang="es"><body style="margin:0;background:#11151b;font-family:Arial,Helvetica,sans-serif;color:#ffffff">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#11151b"><tr><td align="center" style="padding:24px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#171821" style="max-width:600px;background-color:#171821;border:1px solid #343846;border-radius:14px">
<tr><td style="padding:28px"><div style="color:#ff4562;font-weight:800;letter-spacing:1.5px">PECHY PLAYERS</div>
<h1 style="color:#ffffff;margin:22px 0 12px;font-size:25px">Código de verificación</h1>
<p style="color:#d9dbe5;line-height:1.6">Tu código de verificación es:</p>
<p style="margin:18px 0;padding:16px;background-color:#0d0f16;border:1px solid #a62b82;border-radius:10px;color:#ffffff;font-size:30px;font-weight:800;letter-spacing:8px;text-align:center">{code}</p>
<p style="color:#d9dbe5;line-height:1.6">Expira en 5 minutos.</p>
<p style="color:#aeb3bd;line-height:1.6">Si no solicitaste este código, puedes ignorar este mensaje.</p>
</td></tr></table></td></tr></table></body></html>"""
    return subject, text, body


def _send_email(destination, code, challenge_id, transport=None):
    subject, text, body = _email_message(code)
    if transport is not None:
        return transport(destination, subject, text, body)
    return customer_order_email.send_resend_email(
        to=destination, subject=subject, text=text, html_body=body,
        idempotency_key=f"customer-order-otp-{challenge_id}")


def _send_whatsapp(destination, code, transport=None):
    if transport is None:
        raise RecoveryError("whatsapp_transport_unavailable")
    message = ("PECHY PLAYERS\n\nTu código de verificación es: " + code
               + "\n\nExpira en 5 minutos.\n\n"
               "Si no solicitaste este código, ignora este mensaje.")
    return transport(destination, message)


def request_order_otp(public_order_id, channel, requester, secret_key, *,
                      email_transport=None, whatsapp_transport=None, now=None):
    moment = _now(now)
    if channel not in CHANNELS:
        return {"accepted": True, "sent": False, "reason": "channel_unavailable"}
    order = _find_order(public_order_id)
    if not order:
        return {"accepted": True, "sent": False, "reason": "not_found"}
    channels = {item["channel"] for item in available_channels(
        order, whatsapp_transport=whatsapp_transport)}
    if channel not in channels:
        return {"accepted": True, "sent": False, "reason": "channel_unavailable"}
    destination = order["customer_email"] if channel == "email" else order["customer_whatsapp"]
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        window = _timestamp(moment - timedelta(seconds=OTP_RATE_WINDOW_SECONDS))
        order_count = conn.execute("""SELECT COUNT(*) FROM customer_order_otp_challenges
            WHERE order_id=? AND created_at>=?""", (order["id"], window)).fetchone()[0]
        requester_count = conn.execute("""SELECT COUNT(*) FROM customer_order_otp_challenges
            WHERE requester_fingerprint=? AND created_at>=?""", (requester, window)).fetchone()[0]
        latest = conn.execute("""SELECT created_at FROM customer_order_otp_challenges
            WHERE order_id=? AND channel=? ORDER BY id DESC LIMIT 1""",
            (order["id"], channel)).fetchone()
        if order_count >= OTP_ORDER_WINDOW_LIMIT or requester_count >= OTP_REQUESTER_WINDOW_LIMIT:
            conn.commit()
            return {"accepted": True, "sent": False, "reason": "rate_limited"}
        if latest:
            created = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
            remaining = OTP_RESEND_COOLDOWN_SECONDS - int((moment-created).total_seconds())
            if remaining > 0:
                conn.commit()
                return {"accepted": True, "sent": False, "reason": "cooldown",
                        "retry_after": remaining}
        conn.execute("""UPDATE customer_order_otp_challenges
            SET status='invalidated' WHERE order_id=? AND status='active'""", (order["id"],))
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(16)
        created_at = _timestamp(moment)
        expires_at = _timestamp(moment + timedelta(seconds=OTP_TTL_SECONDS))
        cursor = conn.execute("""INSERT INTO customer_order_otp_challenges
            (order_id,channel,code_hash,code_salt,requester_fingerprint,
             destination_fingerprint,status,created_at,expires_at)
            VALUES(?,?,?,?,?,?,'active',?,?)""",
            (order["id"], channel, _hash_code(code, salt, order["id"], secret_key), salt,
             requester, _destination_fingerprint(destination, secret_key), created_at, expires_at))
        challenge_id = cursor.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    try:
        result = (_send_email(destination, code, challenge_id, email_transport)
                  if channel == "email" else
                  _send_whatsapp(destination, code, whatsapp_transport))
        success = result is True or (isinstance(result, dict) and result.get("success") is True)
    except Exception:
        success = False
    if not success:
        conn = _connect()
        try:
            conn.execute("""UPDATE customer_order_otp_challenges SET status='failed',
                last_error_code='transport_error' WHERE id=? AND status='active'""", (challenge_id,))
            conn.commit()
        finally:
            conn.close()
        return {"accepted": True, "sent": False, "reason": "transport_error"}
    return {"accepted": True, "sent": True, "reason": "sent",
            "retry_after": OTP_RESEND_COOLDOWN_SECONDS}


def verify_order_otp(public_order_id, code, requester, secret_key, *, now=None):
    moment = _now(now)
    order = _find_order(public_order_id)
    if not order or not isinstance(code, str) or not OTP_CODE_RE.fullmatch(code):
        return {"verified": False, "reason": "invalid_code"}
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        challenge = conn.execute("""SELECT * FROM customer_order_otp_challenges
            WHERE order_id=? AND requester_fingerprint=? AND status='active'
            ORDER BY id DESC LIMIT 1""", (order["id"], requester)).fetchone()
        if not challenge:
            conn.commit()
            return {"verified": False, "reason": "invalid_code"}
        expires = datetime.fromisoformat(challenge["expires_at"].replace("Z", "+00:00"))
        if moment >= expires:
            conn.execute("UPDATE customer_order_otp_challenges SET status='expired' WHERE id=?", (challenge["id"],))
            conn.commit()
            return {"verified": False, "reason": "expired"}
        candidate = _hash_code(code, challenge["code_salt"], order["id"], secret_key)
        if not hmac.compare_digest(candidate, challenge["code_hash"]):
            attempts = challenge["attempt_count"] + 1
            status = "locked" if attempts >= OTP_MAX_VERIFY_ATTEMPTS else "active"
            conn.execute("UPDATE customer_order_otp_challenges SET attempt_count=?,status=? WHERE id=?",
                         (attempts, status, challenge["id"]))
            conn.commit()
            return {"verified": False, "reason": "too_many_attempts" if status == "locked" else "invalid_code"}
        updated = conn.execute("""UPDATE customer_order_otp_challenges
            SET status='consumed',consumed_at=? WHERE id=? AND status='active'""",
            (_timestamp(moment), challenge["id"])).rowcount
        conn.commit()
        if updated != 1:
            return {"verified": False, "reason": "invalid_code"}
        return {"verified": True, "reason": "verified", "order_id": order["id"],
                "public_order_id": order["public_order_id"]}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def authorize_order_access(session_data, public_order_id, order_id, *, now=None):
    moment = _now(now)
    grants = dict(session_data.get(ACCESS_SESSION_KEY) or {})
    grants = {key: value for key, value in grants.items()
              if isinstance(value, dict) and float(value.get("expires", 0)) > moment.timestamp()}
    grants[str(public_order_id)] = {
        "order_id": int(order_id),
        "expires": (moment + timedelta(seconds=OTP_AUTHORIZATION_TTL_SECONDS)).timestamp(),
    }
    session_data[ACCESS_SESSION_KEY] = dict(list(grants.items())[-5:])


def authorized_order_id(session_data, public_order_id, *, now=None):
    moment = _now(now)
    grant = (session_data.get(ACCESS_SESSION_KEY) or {}).get(str(public_order_id))
    if not isinstance(grant, dict) or float(grant.get("expires", 0)) <= moment.timestamp():
        return None
    try:
        return int(grant["order_id"])
    except (KeyError, TypeError, ValueError):
        return None
