"""Consulta historica de pedidos y telemetria segura de entrega."""

import hashlib
import hmac
import re

import database


PUBLIC_ORDER_RE = re.compile(r"^ORD-[A-Za-z0-9_-]{1,72}$")
EVENT_TYPES = {
    "delivery_status_checked",
    "delivery_fulfilled_observed",
    "delivery_request_started",
    "delivery_request_success",
    "delivery_request_denied",
    "delivery_request_failed",
    "client_result_loaded",
    "client_polling_started",
    "client_paid_observed",
    "client_fulfilled_observed",
    "client_delivery_requested",
    "client_delivery_received",
    "client_delivery_rendered",
    "client_error",
}
CLIENT_EVENTS = {event for event in EVENT_TYPES if event.startswith("client_")}
CLIENT_SAFE_CODES = {
    "", "ok", "network_error", "status_http_error", "delivery_http_error",
    "response_parse_error", "render_error", "invalid_context", "unknown",
}


class CustomerOrderLookupNotFound(Exception):
    """Pedido inexistente o ajeno; ambos son indistinguibles externamente."""


def _connect():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_schema(connection=None):
    owns = connection is None
    conn = _connect() if owns else connection
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customer_delivery_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('server','client')),
                http_status INTEGER CHECK(http_status IS NULL OR http_status BETWEEN 100 AND 599),
                safe_code TEXT NOT NULL DEFAULT '' CHECK(length(safe_code) <= 40),
                session_fingerprint TEXT NOT NULL CHECK(length(session_fingerprint) = 24),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_customer_delivery_events_order
                ON customer_delivery_events(order_id,created_at,id);
            CREATE INDEX IF NOT EXISTS idx_customer_delivery_events_type
                ON customer_delivery_events(event_type,created_at,id);
            CREATE INDEX IF NOT EXISTS idx_customer_delivery_events_session
                ON customer_delivery_events(session_fingerprint,created_at,id);
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


def session_fingerprint(guest_session_hash, secret_key):
    key = str(secret_key or "").encode("utf-8")
    value = str(guest_session_hash or "").encode("ascii", "ignore")
    return hmac.new(key, value, hashlib.sha256).hexdigest()[:24]


def normalize_public_order_id(value):
    public_order_id = str(value or "").strip()
    if not PUBLIC_ORDER_RE.fullmatch(public_order_id):
        raise CustomerOrderLookupNotFound()
    return public_order_id


def lookup_owned_order(public_order_id, guest_session_hash):
    public_order_id = normalize_public_order_id(public_order_id)
    conn = _connect()
    try:
        has_fulfillment = conn.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='customer_order_fulfillments'""").fetchone()
        if has_fulfillment:
            row = conn.execute("""SELECT o.id,o.public_order_id,o.status,
                    f.status AS fulfillment_status
                FROM customer_orders o
                LEFT JOIN customer_order_fulfillments f ON f.order_id=o.id
                WHERE o.public_order_id=? AND o.guest_session_hash=?""",
                (public_order_id, str(guest_session_hash or ""))).fetchone()
        else:
            row = conn.execute("""SELECT id,public_order_id,status,NULL AS fulfillment_status
                FROM customer_orders WHERE public_order_id=? AND guest_session_hash=?""",
                (public_order_id, str(guest_session_hash or ""))).fetchone()
        if not row:
            raise CustomerOrderLookupNotFound()
        status = row["status"]
        fulfillment = row["fulfillment_status"]
        if status == "pending_payment":
            state, message = "pending_payment", "Este pedido todavía no registra un pago confirmado."
        elif status == "paid" and fulfillment == "fulfilled":
            state, message = "fulfilled", "Tu pago y tu entrega están confirmados."
        elif status == "paid" and fulfillment in {None, "pending", "processing"}:
            state, message = "preparing", "Tu pago está confirmado y estamos preparando tu pedido."
        elif status == "paid" and fulfillment == "review":
            state, message = "review", "Tu pago está confirmado, pero necesitamos revisar la entrega. Comunícate con soporte."
        else:
            state, message = "unavailable", "Este pedido no tiene una entrega disponible."
        return {
            "internal_id": row["id"],
            "public_order_id": row["public_order_id"],
            "state": state,
            "payment_status": "paid" if status == "paid" else status,
            "delivery_available": state == "fulfilled",
            "message": message,
        }
    finally:
        conn.close()


def record_event(*, order_id, event_type, source, http_status, safe_code, session_fingerprint_value):
    if event_type not in EVENT_TYPES or source not in {"server", "client"}:
        raise ValueError("Evento de entrega no permitido.")
    safe_code = str(safe_code or "")
    if len(safe_code) > 40 or not re.fullmatch(r"[a-z0-9_]*", safe_code):
        raise ValueError("Codigo seguro no permitido.")
    if not re.fullmatch(r"[0-9a-f]{24}", str(session_fingerprint_value or "")):
        raise ValueError("Fingerprint de sesion no valido.")
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("""INSERT INTO customer_delivery_events
            (order_id,event_type,source,http_status,safe_code,session_fingerprint)
            VALUES(?,?,?,?,?,?)""",
            (order_id, event_type, source, http_status, safe_code, session_fingerprint_value))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def validate_client_event(event_type, safe_code):
    if event_type not in CLIENT_EVENTS or safe_code not in CLIENT_SAFE_CODES:
        raise ValueError("Telemetria cliente no permitida.")
    return event_type, safe_code
