"""Notificación transaccional segura de pedidos pagados mediante Resend."""

import html
import hashlib
import json
import os
import re
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
SAFE_MESSAGE_VALIDATION_CATEGORIES = frozenset({
    "validation_from", "validation_to", "validation_subject",
    "validation_html", "validation_text", "validation_domain",
    "validation_api_key", "validation_required",
    "validation_idempotency", "validation_unknown",
})
MAX_DIAGNOSTIC_MESSAGE_CHARS = 4096
MAX_ERROR_BODY_BYTES = 4096
SAFE_CONTENT_TYPES = frozenset({"application/json", "text/html", "text/plain"})
_MEDIA_TYPE_RE = re.compile(r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$")


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
        "Gracias por confiar en PECHY PLAYERS.\n\n"
        "Muy pronto podrás disfrutar de nuevos beneficios y ofertas de PECHY PLAYERS.\n\n"
        "Este es un correo automático relacionado con tu compra. "
        "No compartas los datos de tu pedido con terceros."
    )
    body = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"></head>
<body style="margin:0;padding:0;background-color:#f5f6fa;color:#171a35;font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:100%;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#f5f6fa" style="width:100%;background-color:#f5f6fa;">
<tr><td align="center" style="padding:0 12px 34px 12px;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#ffffff" style="width:100%;max-width:620px;background-color:#ffffff;">
<tr><td bgcolor="#ffffff" style="padding:25px 30px;background-color:#ffffff;border-bottom:1px solid #e4e5ed;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
<td style="color:#151967;font-size:20px;line-height:26px;font-weight:800;letter-spacing:2px;">PECHY <span style="color:#a62b82;">PLAYERS</span></td>
<td align="right" style="color:#747990;font-size:10px;line-height:16px;font-weight:700;letter-spacing:1.2px;">CONFIRMACIÓN DE PAGO</td>
</tr></table></td></tr>
<tr><td bgcolor="#171821" style="padding:34px 30px 32px 30px;background-color:#171821 !important;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr>
<td width="48" height="48" align="center" valign="middle" bgcolor="#d52f58" style="width:48px;height:48px;background-color:#d52f58;background-image:linear-gradient(145deg,#6422ad,#e73250);border-radius:24px;color:#ffffff;font-size:25px;line-height:48px;font-weight:800;">&#10003;</td>
<td style="padding-left:15px;color:#ffdce8 !important;-webkit-text-fill-color:#ffdce8 !important;font-size:12px;line-height:18px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;">Pago confirmado</td>
</tr></table>
<h1 style="margin:20px 0 15px 0;color:#ffffff !important;-webkit-text-fill-color:#ffffff !important;font-size:29px;line-height:36px;font-weight:800;">¡Tu pago fue confirmado!</h1>
<p style="margin:0 0 9px 0;color:#f5f5f7 !important;-webkit-text-fill-color:#f5f5f7 !important;font-size:16px;line-height:25px;">Hola <strong style="color:#f5f5f7 !important;-webkit-text-fill-color:#f5f5f7 !important;">{safe_name}</strong>,</p>
<p style="margin:0;color:#d9dbe5 !important;-webkit-text-fill-color:#d9dbe5 !important;font-size:15px;line-height:24px;">Recibimos correctamente el pago de tu pedido.</p>
</td></tr>
<tr><td style="padding:0 30px 24px 30px;background-color:#ffffff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#ffffff" style="width:100%;background-color:#ffffff;border:1px solid #dcddea;border-radius:12px;">
<tr><td align="center" style="padding:22px 20px 8px 20px;color:#6e7289;font-size:11px;line-height:17px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;">Número de pedido</td></tr>
<tr><td align="center" style="padding:0 20px 22px 20px;color:#71249a;font-size:25px;line-height:33px;font-weight:800;letter-spacing:.5px;word-break:break-word;">{safe_id}</td></tr>
<tr><td style="padding:22px 24px;border-top:1px solid #e4e5ed;">
<p style="margin:0;color:#3e435a;font-size:14px;line-height:23px;"><strong style="color:#252941;">Guarda este número.</strong> Puedes utilizarlo en la opción “Consultar mi pedido” dentro de PECHY PLAYERS para revisar el estado de tu compra y recuperar tu entrega cuando esté disponible.</p>
<p style="margin:18px 0 0 0;color:#30354d;font-size:14px;line-height:23px;">Gracias por confiar en <strong style="color:#151967;">PECHY PLAYERS</strong>.</p>
</td></tr></table></td></tr>
<tr><td style="padding:0 30px 24px 30px;background-color:#ffffff;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#25177d" style="width:100%;background-color:#25177d;background-image:linear-gradient(110deg,#151f79 0%,#792383 55%,#df3154 100%);border-radius:12px;">
<tr><td bgcolor="#25177d" style="padding:23px 25px;background-color:#25177d;color:#ffffff !important;-webkit-text-fill-color:#ffffff;">
<p style="margin:0 0 5px 0;color:#ffffff !important;-webkit-text-fill-color:#ffffff;font-size:16px;line-height:22px;font-weight:800;">Muy pronto, más beneficios y ofertas</p>
<p style="margin:0;color:#ffffff !important;-webkit-text-fill-color:#ffffff;font-size:13px;line-height:20px;">Nuevas experiencias de PECHY PLAYERS están por llegar.</p>
</td><td width="86" align="center" valign="middle" style="padding:18px 20px 18px 0;">
<span style="display:inline-block;padding:8px 13px;background-color:#ffffff !important;border-radius:18px;color:#9c164e !important;-webkit-text-fill-color:#9c164e;font-size:11px;line-height:16px;font-weight:800;white-space:nowrap;">MUY PRONTO</span>
</td></tr></table></td></tr>
<tr><td bgcolor="#ffffff" style="padding:20px 30px 26px 30px;background-color:#ffffff;border-top:1px solid #e4e5ed;">
<p style="margin:0;color:#555b72;font-size:12px;line-height:19px;"><strong style="color:#252941;">SEGURIDAD:</strong> Este es un correo automático relacionado con tu compra.<br>No compartas los datos de tu pedido con terceros.</p>
</td></tr>
</table></td></tr></table>
</body></html>"""
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


def classify_resend_message_without_name(message):
    """Clasifica semántica cerrada; nunca devuelve texto derivado del proveedor."""
    if not isinstance(message, str) or not message.strip():
        return "validation_unknown"
    if len(message) > MAX_DIAGNOSTIC_MESSAGE_CHARS:
        return "validation_unknown"
    normalized = message.casefold()
    matches = set()
    for field in SAFE_RESEND_VALIDATION_FIELDS:
        if f"`{field}`" in normalized:
            matches.add(f"validation_{field}")
    if (
        "domain is not verified" in normalized
        or "domain has not been verified" in normalized
        or "verify your domain" in normalized
        or "verified domain" in normalized
    ):
        matches.add("validation_domain")
    if any(token in normalized for token in (
        "missing api key", "invalid api key", "restricted api key",
        "api key is invalid", "api key in the authorization header",
    )):
        matches.add("validation_api_key")
    if "missing required field" in normalized or "required field" in normalized:
        matches.add("validation_required")
    if any(token in normalized for token in (
        "idempotency key", "idempotent request", "idempotency-key",
    )):
        matches.add("validation_idempotency")
    return next(iter(matches)) if len(matches) == 1 else "validation_unknown"


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


def _safe_header(error, name):
    headers = getattr(error, "headers", None)
    if headers is None:
        return None
    try:
        return headers.get(name)
    except Exception:
        return None


def _content_metadata(error):
    raw_type = _safe_header(error, "Content-Type")
    content_type_present = isinstance(raw_type, str) and bool(raw_type.strip())
    media_type = None
    charset = None
    if content_type_present:
        candidate = raw_type.split(";", 1)[0].strip().casefold()
        media_type = candidate if _MEDIA_TYPE_RE.fullmatch(candidate) else "invalid"
        match = re.search(r"(?:^|;)\s*charset\s*=\s*[\"']?([^;\s\"']+)", raw_type, re.I)
        if match:
            normalized = match.group(1).casefold().replace("_", "-")
            charset = "utf-8" if normalized in {"utf-8", "utf8"} else "unknown"

    raw_length = _safe_header(error, "Content-Length")
    length_present = isinstance(raw_length, str) and bool(raw_length.strip())
    content_length = None
    if length_present and raw_length.strip().isdigit():
        content_length = int(raw_length.strip())

    raw_encoding = _safe_header(error, "Content-Encoding")
    encoding_present = isinstance(raw_encoding, str) and bool(raw_encoding.strip())
    encoding = None
    if encoding_present:
        normalized = raw_encoding.strip().casefold()
        encoding = normalized if normalized in {"identity", "gzip", "deflate", "br"} else "unknown"
    return {
        "content_type_present": content_type_present,
        "content_type": (
            media_type if media_type in SAFE_CONTENT_TYPES
            else "unexpected" if media_type is not None else None
        ),
        "charset": charset,
        "content_length_present": length_present,
        "content_length": content_length,
        "content_length_valid": not length_present or content_length is not None,
        "content_encoding_present": encoding_present,
        "content_encoding": encoding,
    }


def inspect_resend_http_error(error):
    """Lee una vez el error y devuelve sólo metadata estructural allowlisted."""
    try:
        status = int(getattr(error, "code", None))
        status = status if 100 <= status <= 599 else None
    except (TypeError, ValueError):
        status = None
    metadata = {
        "http_status": status,
        **_content_metadata(error),
        "body_present": False,
        "response_body_bytes_read": 0,
        "response_body_bytes_analyzed": 0,
        "body_truncated": None,
        "response_body_sha256": None,
        "body_read_error": False,
        "json_parse": "not_attempted",
        "json_top_level_type": "unknown",
        "name_present": False,
        "name_type": "absent",
        "name_allowlisted": False,
        "message_present": False,
        "message_type": "absent",
        "message_safe_category": "validation_unknown",
        "statusCode_present": False,
        "statusCode_type": "absent",
        "unknown_keys_present": False,
    }
    try:
        probe = error.read(MAX_ERROR_BODY_BYTES + 1)
        if not isinstance(probe, bytes):
            raise TypeError("HTTPError.read() did not return bytes")
    except Exception:
        metadata["body_read_error"] = True
        return metadata, b""

    body = probe[:MAX_ERROR_BODY_BYTES]
    metadata.update({
        "body_present": bool(probe),
        "response_body_bytes_read": len(probe),
        "response_body_bytes_analyzed": len(body),
        "body_truncated": len(probe) > MAX_ERROR_BODY_BYTES,
        "response_body_sha256": hashlib.sha256(body).hexdigest(),
    })
    if not body or metadata["charset"] == "unknown":
        return metadata, body
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        metadata["json_parse"] = "failed"
        return metadata, body

    metadata["json_parse"] = "ok"
    if parsed is None:
        metadata["json_top_level_type"] = "null"
    elif isinstance(parsed, dict):
        metadata["json_top_level_type"] = "object"
    elif isinstance(parsed, list):
        metadata["json_top_level_type"] = "array"
    elif isinstance(parsed, str):
        metadata["json_top_level_type"] = "string"
    elif isinstance(parsed, (int, float)) and not isinstance(parsed, bool):
        metadata["json_top_level_type"] = "number"
    else:
        metadata["json_top_level_type"] = "unknown"
    if not isinstance(parsed, dict):
        return metadata, body

    known = {"name", "message", "statusCode"}
    metadata["unknown_keys_present"] = any(key not in known for key in parsed)
    for key in known:
        present_key = f"{key}_present"
        type_key = f"{key}_type"
        metadata[present_key] = key in parsed
        if key in parsed:
            metadata[type_key] = "string" if isinstance(parsed[key], str) else "non_string"
    metadata["name_allowlisted"] = (
        isinstance(parsed.get("name"), str) and parsed["name"] in SAFE_RESEND_ERROR_NAMES
    )
    if "name" not in parsed and "message" in parsed:
        metadata["message_safe_category"] = classify_resend_message_without_name(
            parsed["message"]
        )
    return metadata, body


def _safe_http_error_details(error):
    safe_code = _safe_http_code(error.code)
    metadata, body = inspect_resend_http_error(error)
    if metadata["body_read_error"]:
        return safe_code, metadata
    diagnostic_code = diagnostic_resend_error_code(body)
    return (f"{safe_code}_{diagnostic_code}" if diagnostic_code else safe_code), metadata


def _safe_http_error_code(error):
    return _safe_http_error_details(error)[0]


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


def send_resend_email(*, to, subject, text, html_body, idempotency_key,
                      transport=None, config=None):
    """Envía un email sin tocar pedidos ni abrir la base de datos."""
    config_error = None
    if config is None:
        config, config_error = _configuration()
    if config_error:
        return {"success": False, "safe_code": config_error,
                "http_status": None, "provider_message_id": None}
    if transport is None and os.environ.get("PECHY_TESTING", "").strip() == "1":
        return {"success": False, "safe_code": "test_network_blocked",
                "http_status": None, "provider_message_id": None}

    payload = {
        "from": f"{config['from_name']} <{config['from_email']}>",
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html_body,
    }
    try:
        status, response_body = (transport or _post_resend)(
            payload, config["api_key"], HTTP_TIMEOUT_SECONDS, idempotency_key
        )
        message_id, error_code = _safe_provider_result(status, response_body)
    except urllib.error.HTTPError as error:
        status = error.code
        error_code, http_diagnostic = _safe_http_error_details(error)
        message_id = None
    except TimeoutError:
        status, message_id, error_code = None, None, "provider_timeout"
    except (urllib.error.URLError, OSError):
        status, message_id, error_code = None, None, "provider_network_error"
    except Exception:
        status, message_id, error_code = None, None, "provider_unexpected_error"
    return {
        "success": error_code is None,
        "safe_code": error_code,
        "http_status": status,
        "provider_message_id": message_id,
        "http_diagnostic": locals().get("http_diagnostic"),
    }


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
    result = send_resend_email(
        to=order["customer_email"], subject=subject, text=text, html_body=body,
        idempotency_key=f"customer-order-{order['id']}-{NOTIFICATION_TYPE}",
        transport=transport, config=config,
    )
    message_id, error_code = result["provider_message_id"], result["safe_code"]
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
