"""Prueba controlada de Resend, independiente de pedidos y sin persistencia."""

import json
import hashlib
import os
import re
import secrets
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

import customer_order_email


RECIPIENT_ENV = "ORDER_EMAIL_DIAGNOSTIC_RECIPIENT"
SUBJECT = "PECHY PLAYERS - prueba de correo"
TEXT = "Prueba controlada de correo de PECHY PLAYERS."
HTML = "<p>Prueba controlada de correo de PECHY PLAYERS.</p>"
MAX_REAL_RESEND_CALLS = 1
EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")
HTTP_ERROR_REPORT_FIELDS = (
    "message_safe_category", "content_type", "content_length", "body_present",
    "response_body_bytes_read", "body_truncated", "json_parse",
    "json_top_level_type", "name_present", "message_present",
    "statusCode_present",
)
PROTECTED_PUBLIC_ORDER_ID = "ORD-CF1-8YV_1zBuj379SCdkAOrf"
EXPECTED_PROTECTED_ORDER = (
    "paid", "fulfilled", 1, "failed", 3, "provider_http_400", None, None,
)
COUNT_TABLES = (
    "customer_orders", "customer_order_notifications",
    "customer_order_fulfillments", "customer_order_fulfillment_lines",
    "nube_cuentas", "nube_perfiles", "nube_movimientos",
    "customer_bold_payment_intents", "customer_bold_webhook_events",
)


def production_snapshot(path="pechy.db"):
    """Obtiene evidencia exclusivamente mediante una conexión SQLite read-only."""
    database_path = Path(path).resolve()
    stat = database_path.stat()
    digest = hashlib.sha256(database_path.read_bytes()).hexdigest()
    connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if table in tables else None
            for table in COUNT_TABLES
        }
        integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        protected = connection.execute("""
            SELECT o.status, f.status, f.attempt_count, n.status, n.attempt_count,
                   n.last_error_code, n.provider_message_id, n.sent_at
            FROM customer_orders o
            LEFT JOIN customer_order_fulfillments f ON f.order_id=o.id
            LEFT JOIN customer_order_notifications n
              ON n.order_id=o.id AND n.notification_type='payment_confirmed'
            WHERE o.public_order_id=?
        """, (PROTECTED_PUBLIC_ORDER_ID,)).fetchone()
    finally:
        connection.close()
    return {
        "sha256": digest, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "integrity_check": integrity, "foreign_key_check": foreign_keys,
        "counts": counts, "protected_order": tuple(protected) if protected else None,
    }


def preflight(recipient, config, idempotency_key):
    if not isinstance(config, dict):
        return False
    required = ("api_key", "from_email", "from_name")
    if not all(isinstance(config.get(key), str) and config[key]
               for key in required):
        return False
    if not isinstance(recipient, str):
        return False
    final_from = f"{config['from_name']} <{config['from_email']}>"
    payload = {"from": final_from, "to": [recipient], "subject": SUBJECT,
               "text": TEXT, "html": HTML}
    checks = (
        customer_order_email.RESEND_URL == "https://api.resend.com/emails",
        bool(config["api_key"]),
        config["from_email"] == "pedidos@pechy.org",
        config["from_name"] == "PECHY PLAYERS",
        final_from == "PECHY PLAYERS <pedidos@pechy.org>",
        all("\r" not in value and "\n" not in value
            for value in (final_from, recipient)),
        isinstance(payload["from"], str),
        isinstance(payload["to"], list) and len(payload["to"]) == 1
        and isinstance(payload["to"][0], str),
        all(isinstance(payload[key], str) and bool(payload[key])
            for key in ("subject", "text", "html")),
        all(value is not None for value in payload.values()),
        bool(EMAIL_RE.fullmatch(recipient)),
        isinstance(idempotency_key, str) and 1 <= len(idempotency_key) <= 256,
    )
    try:
        encoded = json.dumps(payload).encode("utf-8")
        checks += (len(encoded) < 100_000,)
    except (TypeError, UnicodeEncodeError):
        checks += (False,)
    return all(checks)


def execute(recipient, *, transport=None, config=None, idempotency_key=None):
    config_error = None
    if config is None:
        config, config_error = customer_order_email._configuration()
    if config_error:
        return {"result": "PRE_FLIGHT_FAILED", "safe_code": config_error,
                "calls": 0, "http_status": None, "provider_message_id": None}
    key = idempotency_key or f"pechy-diagnostic-email-{secrets.token_urlsafe(18)}"
    if not preflight(recipient, config, key):
        return {"result": "PRE_FLIGHT_FAILED", "safe_code": "invalid_request_shape",
                "calls": 0, "http_status": None, "provider_message_id": None}
    calls = 0

    def guarded(payload, api_key, timeout, request_key):
        nonlocal calls
        if calls >= MAX_REAL_RESEND_CALLS:
            raise RuntimeError("maximum_resend_calls_exceeded")
        calls += 1
        return (transport or customer_order_email._post_resend)(
            payload, api_key, timeout, request_key
        )

    result = customer_order_email.send_resend_email(
        to=recipient, subject=SUBJECT, text=TEXT, html_body=HTML,
        idempotency_key=key, transport=guarded, config=config,
    )
    return {
        "result": "DIAGNOSTIC_SUCCESS" if result["success"] else "DIAGNOSTIC_PROVIDER_ERROR",
        "safe_code": result["safe_code"], "calls": calls,
        "http_status": result["http_status"],
        "provider_message_id": result["provider_message_id"],
        "http_diagnostic": result["http_diagnostic"],
    }


def main():
    load_dotenv()
    before = production_snapshot()
    if before["protected_order"] != EXPECTED_PROTECTED_ORDER:
        print("PRE_FLIGHT_FAILED")
        print("safe_code=protected_order_mismatch")
        return 3
    recipient = os.environ.get(RECIPIENT_ENV, "").strip()
    if not recipient:
        after = production_snapshot()
        print("READY_FOR_DIAGNOSTIC_SEND")
        print("NEED_DIAGNOSTIC_RECIPIENT")
        print("snapshot_before=" + json.dumps(before, sort_keys=True))
        print("snapshot_after=" + json.dumps(after, sort_keys=True))
        return 2
    result = execute(recipient)
    after = production_snapshot()
    print(result["result"])
    print(f"real_calls={result['calls']}")
    print(f"http_status={result['http_status'] if result['http_status'] is not None else 'absent'}")
    print(f"safe_code={result['safe_code'] if result['safe_code'] else 'absent'}")
    if result["result"] == "DIAGNOSTIC_SUCCESS":
        print(f"provider_message_id={'present' if result['provider_message_id'] else 'absent'}")
    if result["http_diagnostic"] is not None:
        report = {
            ("body_bytes_read" if key == "response_body_bytes_read" else key):
                result["http_diagnostic"][key]
            for key in HTTP_ERROR_REPORT_FIELDS
            if key in result["http_diagnostic"]
            and (key != "content_length"
                 or result["http_diagnostic"][key] is not None)
        }
        print("http_diagnostic=" + json.dumps(report, sort_keys=True))
    print("snapshot_before=" + json.dumps(before, sort_keys=True))
    print("snapshot_after=" + json.dumps(after, sort_keys=True))
    return 0 if result["result"] == "DIAGNOSTIC_SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
