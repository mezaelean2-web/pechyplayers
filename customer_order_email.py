"""Notificación transaccional segura de pedidos pagados mediante Resend."""

import html
import json
import os
import urllib.error
import urllib.request

import database

NOTIFICATION_TYPE = "payment_confirmed"
PROVIDER = "resend"
RESEND_URL = "https://api.resend.com/emails"
HTTP_TIMEOUT_SECONDS = 8
USER_AGENT = "PECHY-PLAYERS/1.0"
SAFE_RESEND_ERROR_NAMES = frozenset({
    "invalid_idempotency_key", "validation_error", "missing_api_key",
    "restricted_api_key", "invalid_api_key", "not_found",
    "method_not_allowed", "invalid_idempotent_request",
    "concurrent_idempotent_requests", "invalid_attachment",
    "invalid_from_address", "invalid_access", "invalid_parameter",
    "invalid_region", "missing_required_field", "monthly_quota_exceeded",
    "daily_quota_exceeded", "rate_limit_exceeded", "security_error",
    "application_error", "internal_server_error",
})
SAFE_RESEND_VALIDATION_FIELDS = ("from", "to", "subject", "html", "text")


def _connect():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def initialize_schema(connection=None):
    owns = connection is None
    conn = connection or _connect()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS customer_order_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL CHECK(notification_type IN ('payment_confirmed')),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','failed')),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            provider TEXT NOT NULL DEFAULT 'resend' CHECK(provider='resend'),
            provider_message_id TEXT,
            last_error_code TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT,
            FOREIGN KEY(order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT,
            UNIQUE(order_id, notification_type)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_order_notifications_status ON customer_order_notifications(status, id)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def _configuration():
    provider = os.environ.get("ORDER_EMAIL_PROVIDER", "").strip().lower()
    api_key = os.environ.get("ORDER_EMAIL_API_KEY", "").strip()
    from_email = os.environ.get("ORDER_EMAIL_FROM", "").strip()
    from_name = os.environ.get("ORDER_EMAIL_FROM_NAME", "").strip()
    if provider != PROVIDER:
        return None, "provider_not_configured"
    if not api_key or not from_email or not from_name:
        return None, "email_configuration_missing"
    return {"api_key": api_key, "from_email": from_email, "from_name": from_name}, None


def _message(order):
    public_id = str(order["public_order_id"])
    name = str(order["customer_first_name"])
    safe_id = html.escape(public_id)
    safe_name = html.escape(name)
    subject = f"PECHY PLAYERS — Pago confirmado | {public_id}"
    text = (
        "PECHY PLAYERS\n\n¡Tu pago fue confirmado!\n\n"
        f"Hola {name},\n\nRecibimos correctamente el pago de tu pedido.\n\n"
        f"Número de pedido:\n{public_id}\n\nGuarda este número.\n\n"
        "Puedes utilizarlo en la opción “Consultar mi pedido” dentro de PECHY PLAYERS "
        "para revisar el estado de tu compra y recuperar tu entrega cuando esté disponible.\n\n"
        "Gracias por confiar en PECHY PLAYERS."
    )
    body = f"""<!doctype html><html><body style="margin:0;background:#111318;color:#f4f4f5;font-family:Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#111318;padding:24px"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#1a1d24;border:1px solid #343841;border-radius:12px">
<tr><td style="padding:28px"><div style="color:#e5252a;font-weight:800;letter-spacing:.08em">PECHY PLAYERS</div>
<h1 style="margin:20px 0 12px;color:#ffffff;font-size:25px">¡Tu pago fue confirmado!</h1>
<p style="color:#d5d7dc;line-height:1.6">Hola {safe_name},</p><p style="color:#d5d7dc;line-height:1.6">Recibimos correctamente el pago de tu pedido.</p>
<p style="margin:24px 0 8px;color:#aeb3bd">Número de pedido</p><p style="margin:0;padding:14px;background:#101217;border-left:4px solid #e5252a;color:#ffffff;font-size:20px;font-weight:800">{safe_id}</p>
<p style="color:#d5d7dc;line-height:1.6"><strong>Guarda este número.</strong> Puedes utilizarlo en la opción “Consultar mi pedido” dentro de PECHY PLAYERS para revisar el estado de tu compra y recuperar tu entrega cuando esté disponible.</p>
<p style="margin:24px 0 0;color:#aeb3bd">Gracias por confiar en PECHY PLAYERS.</p></td></tr></table></td></tr></table></body></html>"""
    return subject, text, body


def _post_resend(payload, api_key, timeout, idempotency_key):
    request = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "User-Agent": USER_AGENT, "Idempotency-Key": idempotency_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def _safe_http_code(status):
    try:
        status = int(status)
    except (TypeError, ValueError):
        return "provider_http_error"
    return f"provider_http_{status}" if 400 <= status <= 599 else "provider_http_error"


def _parse_resend_error(body):
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def diagnostic_resend_error_name(body):
    """Extrae sólo un nombre oficial allowlisted; ignora mensaje y body libre."""
    parsed = _parse_resend_error(body)
    name = parsed.get("name") if parsed else None
    return name if name in SAFE_RESEND_ERROR_NAMES else None


def classify_resend_validation_message(message):
    """Clasifica tokens de campos oficiales sin devolver texto del proveedor."""
    if not isinstance(message, str) or not message.strip():
        return "unknown"
    normalized = message.casefold()
    matches = [
        field for field in SAFE_RESEND_VALIDATION_FIELDS
        if f"`{field}`" in normalized
    ]
    return matches[0] if len(matches) == 1 else "unknown"


def diagnostic_resend_error_code(body):
    """Devuelve exclusivamente una categoría cerrada apta para persistencia."""
    parsed = _parse_resend_error(body)
    name = parsed.get("name") if parsed else None
    if name not in SAFE_RESEND_ERROR_NAMES:
        return None
    if name == "validation_error":
        category = classify_resend_validation_message(parsed.get("message"))
        return f"validation_error_{category}"
    return name


def _safe_http_error_code(error):
    safe_code = _safe_http_code(error.code)
    try:
        body = error.read(4096)
    except Exception:
        return safe_code
    diagnostic_code = diagnostic_resend_error_code(body)
    return f"{safe_code}_{diagnostic_code}" if diagnostic_code else safe_code


def _safe_provider_result(status, body):
    if status not in (200, 201):
        return None, _safe_http_code(status)
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return None, "provider_invalid_response"
    message_id = parsed.get("id") if isinstance(parsed, dict) else None
    if not isinstance(message_id, str) or not message_id or len(message_id) > 255:
        return None, "provider_invalid_response"
    return message_id, None


def _mark(notification_id, status, *, provider_message_id=None, error_code=None):
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""UPDATE customer_order_notifications
            SET status=?,provider_message_id=?,last_error_code=?,updated_at=CURRENT_TIMESTAMP,
                sent_at=CASE WHEN ?='sent' THEN CURRENT_TIMESTAMP ELSE sent_at END
            WHERE id=? AND status='sending'""",
            (status, provider_message_id, error_code, status, notification_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def send_payment_confirmation(order_id, *, retry_failed=False, transport=None):
    """Intenta una notificación; nunca modifica pago, fulfillment ni inventario."""
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = conn.execute("""SELECT id,public_order_id,status,customer_first_name,customer_email
            FROM customer_orders WHERE id=?""", (order_id,)).fetchone()
        if not order or order["status"] != "paid":
            conn.commit()
            return {"status": "skipped", "reason": "order_not_paid"}
        conn.execute("""INSERT OR IGNORE INTO customer_order_notifications
            (order_id,notification_type,status,attempt_count,provider)
            VALUES(?,?,'pending',0,?)""", (order_id, NOTIFICATION_TYPE, PROVIDER))
        notification = conn.execute("""SELECT * FROM customer_order_notifications
            WHERE order_id=? AND notification_type=?""", (order_id, NOTIFICATION_TYPE)).fetchone()
        allowed = notification["status"] == "pending" or (retry_failed and notification["status"] == "failed")
        if not allowed:
            conn.commit()
            return {"status": "skipped", "reason": f"already_{notification['status']}"}
        updated = conn.execute("""UPDATE customer_order_notifications
            SET status='sending',attempt_count=attempt_count+1,last_error_code=NULL,updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND status=?""", (notification["id"], notification["status"])).rowcount
        if updated != 1:
            conn.commit()
            return {"status": "skipped", "reason": "claim_lost"}
        notification_id = notification["id"]
        order = dict(order)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if not order["customer_email"]:
        _mark(notification_id, "failed", error_code="missing_customer_email")
        return {"status": "failed", "reason": "missing_customer_email"}
    config, config_error = _configuration()
    if config_error:
        _mark(notification_id, "failed", error_code=config_error)
        return {"status": "failed", "reason": config_error}
    if transport is None and os.environ.get("PECHY_TESTING", "").strip() == "1":
        _mark(notification_id, "failed", error_code="test_network_blocked")
        return {"status": "failed", "reason": "test_network_blocked"}
    subject, text, body = _message(order)
    payload = {
        "from": f"{config['from_name']} <{config['from_email']}>",
        "to": [order["customer_email"]],
        "subject": subject,
        "text": text,
        "html": body,
    }
    try:
        idempotency_key = f"customer-order-{order['id']}-{NOTIFICATION_TYPE}"
        status, response_body = (transport or _post_resend)(payload, config["api_key"], HTTP_TIMEOUT_SECONDS, idempotency_key)
        message_id, error_code = _safe_provider_result(status, response_body)
    except urllib.error.HTTPError as error:
        message_id, error_code = None, _safe_http_error_code(error)
    except TimeoutError:
        message_id, error_code = None, "provider_timeout"
    except (urllib.error.URLError, OSError):
        message_id, error_code = None, "provider_network_error"
    except Exception:
        message_id, error_code = None, "provider_unexpected_error"
    if error_code:
        _mark(notification_id, "failed", error_code=error_code)
        return {"status": "failed", "reason": error_code}
    _mark(notification_id, "sent", provider_message_id=message_id)
    return {"status": "sent", "reason": "provider_accepted"}


def get_admin(order_id):
    initialize_schema()
    conn = _connect()
    try:
        row = conn.execute("""SELECT status,attempt_count,provider,provider_message_id,last_error_code,
            created_at,updated_at,sent_at FROM customer_order_notifications
            WHERE order_id=? AND notification_type=?""", (order_id, NOTIFICATION_TYPE)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
