"""Pedidos guest pendientes de pago, sin pagos, reservas ni inventario."""

import hashlib
import json
import re
import secrets
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

import customer_cart
import database

ORDER_TTL_MINUTES = 15
CHECKOUT_PROFILE_TTL_HOURS = 24
ORDER_STATUSES = ("pending_payment", "paid", "processing", "delivered", "failed", "cancelled", "expired")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{32,100}$")
_COUNTRY_CODE_RE = re.compile(r"^\+[1-9][0-9]{0,2}$")
_SESSION_HASH_RE = re.compile(r"^[a-f0-9]{64}$")


class OrderValidationError(ValueError):
    def __init__(self, message, code="invalid_order", status=400):
        super().__init__(message)
        self.code = code
        self.status = status


def _utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def normalize_name(value, label):
    if not isinstance(value, str):
        raise OrderValidationError(f"{label} es obligatorio.", "invalid_customer")
    value = " ".join(unicodedata.normalize("NFC", value).strip().split())
    if not 2 <= len(value) <= 80:
        raise OrderValidationError(f"{label} debe tener entre 2 y 80 caracteres.", "invalid_customer")
    punctuation = {"'", "’", "-", " "}
    if any(not (unicodedata.category(char).startswith(("L", "M")) or char in punctuation) for char in value):
        raise OrderValidationError(f"{label} contiene caracteres no permitidos.", "invalid_customer")
    return value


def normalize_whatsapp(value, country_code):
    if not isinstance(value, str) or not isinstance(country_code, str):
        raise OrderValidationError("WhatsApp y código de país son obligatorios.", "invalid_whatsapp")
    raw = value.strip()
    if not raw:
        raise OrderValidationError("WhatsApp es obligatorio.", "invalid_whatsapp")
    if re.search(r"[^0-9+\s().-]", raw) or raw.count("+") > 1 or ("+" in raw and not raw.startswith("+")):
        raise OrderValidationError("El WhatsApp contiene caracteres no válidos.", "invalid_whatsapp")
    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("+"):
        canonical = compact
    else:
        code = country_code.strip().replace(" ", "")
        if not _COUNTRY_CODE_RE.fullmatch(code):
            raise OrderValidationError("El código de país no es válido.", "invalid_whatsapp")
        if not compact.isdigit() or not 6 <= len(compact) <= 12:
            raise OrderValidationError("El WhatsApp no tiene una longitud válida.", "invalid_whatsapp")
        if code == "+57" and (len(compact) != 10 or not compact.startswith("3")):
            raise OrderValidationError("Para Colombia ingresa un celular de 10 dígitos que comience por 3.", "invalid_whatsapp")
        canonical = code + compact
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", canonical):
        raise OrderValidationError("El WhatsApp debe ser un número internacional válido.", "invalid_whatsapp")
    return canonical


def _validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != {"customer", "items", "idempotency_key"}:
        raise OrderValidationError("El payload solo admite customer, items e idempotency_key.")
    customer = payload["customer"]
    if not isinstance(customer, dict) or set(customer) != {"first_name", "last_name", "whatsapp", "country_code"}:
        raise OrderValidationError("Los datos del cliente no tienen el formato esperado.", "invalid_customer")
    key = payload["idempotency_key"]
    if not isinstance(key, str) or not _IDEMPOTENCY_RE.fullmatch(key):
        raise OrderValidationError("La clave de idempotencia no es válida.", "invalid_idempotency_key")
    first_name = normalize_name(customer["first_name"], "Nombre")
    last_name = normalize_name(customer["last_name"], "Apellido")
    whatsapp = normalize_whatsapp(customer["whatsapp"], customer["country_code"])
    items = customer_cart._validated_items({"items": payload["items"]})
    if not items:
        raise OrderValidationError("El carrito está vacío.", "empty_cart")
    normalized_items = [{"plan_id": plan_id, "quantity": quantity} for plan_id, quantity in items]
    normalized = {"customer": {"first_name": first_name, "last_name": last_name, "whatsapp": whatsapp}, "items": normalized_items}
    fingerprint = hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return normalized, key, fingerprint


def initialize_schema(connection=None):
    owns = connection is None
    conn = connection or database.conectar()
    statuses = ",".join(f"'{status}'" for status in ORDER_STATUSES)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f"""CREATE TABLE IF NOT EXISTS customer_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            public_order_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending_payment' CHECK (status IN ({statuses})),
            customer_first_name TEXT NOT NULL,
            customer_last_name TEXT NOT NULL,
            customer_whatsapp TEXT NOT NULL,
            subtotal INTEGER NOT NULL CHECK (subtotal >= 0),
            discount_total INTEGER NOT NULL CHECK (discount_total >= 0),
            total INTEGER NOT NULL CHECK (total >= 0 AND total = subtotal - discount_total),
            currency TEXT NOT NULL DEFAULT 'COP' CHECK (currency = 'COP'),
            item_count INTEGER NOT NULL CHECK (item_count BETWEEN 1 AND {customer_cart.MAX_CART_SERVICES}),
            eligible_item_count INTEGER NOT NULL CHECK (eligible_item_count BETWEEN 0 AND item_count),
            discount_rule_id INTEGER,
            discount_min_items INTEGER,
            discount_bps INTEGER NOT NULL CHECK (discount_bps BETWEEN 0 AND 10000),
            idempotency_key TEXT NOT NULL UNIQUE,
            request_fingerprint TEXT NOT NULL,
            guest_session_hash TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(customer_orders)")}
        if "guest_session_hash" not in columns:
            conn.execute("ALTER TABLE customer_orders ADD COLUMN guest_session_hash TEXT")
        conn.execute("""CREATE TABLE IF NOT EXISTS customer_order_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            line_number INTEGER NOT NULL CHECK (line_number > 0),
            source_plan_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            list_price INTEGER NOT NULL CHECK (list_price >= 0),
            effective_price INTEGER NOT NULL CHECK (effective_price >= 0),
            offer_applied INTEGER NOT NULL CHECK (offer_applied IN (0,1)),
            discount_eligible INTEGER NOT NULL CHECK (discount_eligible IN (0,1)),
            discount_bps INTEGER NOT NULL CHECK (discount_bps BETWEEN 0 AND 10000),
            discount_amount INTEGER NOT NULL CHECK (discount_amount >= 0),
            final_total INTEGER NOT NULL CHECK (final_total >= 0 AND final_total = effective_price - discount_amount),
            currency TEXT NOT NULL DEFAULT 'COP' CHECK (currency = 'COP'),
            created_at TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT,
            UNIQUE (order_id, line_number)
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_orders_status_expires ON customer_orders(status, expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_orders_guest_status ON customer_orders(guest_session_hash, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_order_lines_order ON customer_order_lines(order_id, line_number)")
        conn.execute("""CREATE TABLE IF NOT EXISTS customer_checkout_sessions (
            session_hash TEXT PRIMARY KEY,
            customer_first_name TEXT,
            customer_last_name TEXT,
            customer_whatsapp TEXT,
            current_order_id INTEGER,
            updated_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (current_order_id) REFERENCES customer_orders(id) ON DELETE SET NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_checkout_sessions_expiry ON customer_checkout_sessions(expires_at)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def _new_public_id():
    return "ORD-" + secrets.token_urlsafe(18)


def _serialize(order, lines):
    return {
        "id": order["public_order_id"], "status": order["status"],
        "customer": {"first_name": order["customer_first_name"], "last_name": order["customer_last_name"], "whatsapp": order["customer_whatsapp"]},
        "subtotal": order["subtotal"], "discount_total": order["discount_total"], "total": order["total"],
        "currency": order["currency"], "item_count": order["item_count"], "eligible_item_count": order["eligible_item_count"],
        "discount_min_items": order["discount_min_items"], "discount_bps": order["discount_bps"],
        "created_at": order["created_at"], "expires_at": order["expires_at"],
        "items": [{"line_number": line["line_number"], "plan_id": line["source_plan_id"],
                   "producto": line["product_name"], "plan": line["plan_name"],
                   "precio_lista": line["list_price"], "precio_efectivo": line["effective_price"],
                   "oferta_aplicada": bool(line["offer_applied"]), "discount_eligible": bool(line["discount_eligible"]),
                   "discount_bps": line["discount_bps"], "discount_amount": line["discount_amount"],
                   "line_total_final": line["final_total"], "currency": line["currency"]} for line in lines],
    }


def _read_order(conn, column, value):
    if column not in {"id", "public_order_id", "idempotency_key"}:
        raise ValueError("Columna de búsqueda no permitida.")
    order = conn.execute(f"SELECT * FROM customer_orders WHERE {column}=?", (value,)).fetchone()
    if not order:
        return None
    lines = conn.execute("SELECT * FROM customer_order_lines WHERE order_id=? ORDER BY line_number", (order["id"],)).fetchall()
    return _serialize(order, lines)


def _validate_session_hash(value):
    if not isinstance(value, str) or not _SESSION_HASH_RE.fullmatch(value):
        raise OrderValidationError("La sesión guest no es válida.", "invalid_guest_session", 403)
    return value


def _cancel_current_in_cursor(conn, session_hash, now):
    checkout = conn.execute("SELECT current_order_id FROM customer_checkout_sessions WHERE session_hash=?", (session_hash,)).fetchone()
    if not checkout or checkout["current_order_id"] is None:
        return "none", None
    order = conn.execute("SELECT id,public_order_id,status,guest_session_hash FROM customer_orders WHERE id=?", (checkout["current_order_id"],)).fetchone()
    if not order or order["guest_session_hash"] != session_hash:
        return "ownership_mismatch", None
    if order["status"] == "pending_payment":
        conn.execute("UPDATE customer_orders SET status='cancelled',updated_at=? WHERE id=? AND status='pending_payment'", (now, order["id"]))
        return "cancelled", order["public_order_id"]
    if order["status"] == "cancelled":
        return "already_cancelled", order["public_order_id"]
    return "not_cancellable", order["public_order_id"]


def _remember_checkout_in_cursor(conn, session_hash, customer, order_id, now):
    expires = _timestamp(datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(hours=CHECKOUT_PROFILE_TTL_HOURS))
    conn.execute("DELETE FROM customer_checkout_sessions WHERE expires_at<=?", (now,))
    conn.execute("""INSERT INTO customer_checkout_sessions (
        session_hash,customer_first_name,customer_last_name,customer_whatsapp,current_order_id,updated_at,expires_at
    ) VALUES (?,?,?,?,?,?,?) ON CONFLICT(session_hash) DO UPDATE SET
        customer_first_name=excluded.customer_first_name,customer_last_name=excluded.customer_last_name,
        customer_whatsapp=excluded.customer_whatsapp,current_order_id=excluded.current_order_id,
        updated_at=excluded.updated_at,expires_at=excluded.expires_at""",
        (session_hash, customer["first_name"], customer["last_name"], customer["whatsapp"], order_id, now, expires))


def create_order(payload, *, guest_session_hash, before_line_insert=None):
    normalized, key, fingerprint = _validate_request(payload)
    guest_session_hash = _validate_session_hash(guest_session_hash)
    conn = database.conectar()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT id,request_fingerprint,guest_session_hash,status FROM customer_orders WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            if existing["guest_session_hash"] != guest_session_hash:
                raise OrderValidationError("La clave de idempotencia no pertenece a esta sesión.", "idempotency_conflict", 409)
            if existing["request_fingerprint"] != fingerprint:
                raise OrderValidationError("La clave de idempotencia ya pertenece a otra compra.", "idempotency_conflict", 409)
            result = _read_order(conn, "idempotency_key", key)
            if existing["status"] == "pending_payment":
                _remember_checkout_in_cursor(conn, guest_session_hash, normalized["customer"], existing["id"], _timestamp(_utc_now()))
            conn.commit()
            return result, False
        cancel_result, _ = _cancel_current_in_cursor(conn, guest_session_hash, _timestamp(_utc_now()))
        if cancel_result in {"ownership_mismatch", "not_cancellable"}:
            raise OrderValidationError("El pedido actual no puede reemplazarse automáticamente.", "current_order_not_cancellable", 409)
        preview = customer_cart.calculate_cart({"items": normalized["items"]}, connection=conn)
        now = _utc_now()
        created_at = _timestamp(now)
        expires_at = _timestamp(now + timedelta(minutes=ORDER_TTL_MINUTES))
        order_id = None
        for _ in range(5):
            try:
                cursor = conn.execute("""INSERT INTO customer_orders (
                    public_order_id,status,customer_first_name,customer_last_name,customer_whatsapp,
                    subtotal,discount_total,total,currency,item_count,eligible_item_count,discount_rule_id,
                    discount_min_items,discount_bps,idempotency_key,request_fingerprint,guest_session_hash,created_at,updated_at,expires_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (_new_public_id(), "pending_payment", normalized["customer"]["first_name"], normalized["customer"]["last_name"],
                 normalized["customer"]["whatsapp"], preview["subtotal_bruto"], preview["discount_total"], preview["total_final"],
                 preview["currency"], preview["item_count"], preview["eligible_item_count"], preview["discount_rule_id"],
                 preview["discount_min_items"], preview["discount_bps"], key, fingerprint, guest_session_hash, created_at, created_at, expires_at))
                order_id = cursor.lastrowid
                break
            except sqlite3.IntegrityError as error:
                if "public_order_id" not in str(error):
                    raise
        if order_id is None:
            raise RuntimeError("No se pudo generar un identificador público único.")
        for line in preview["items"]:
            if before_line_insert:
                before_line_insert(line)
            conn.execute("""INSERT INTO customer_order_lines (
                order_id,line_number,source_plan_id,product_name,plan_name,list_price,effective_price,
                offer_applied,discount_eligible,discount_bps,discount_amount,final_total,currency,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_id, line["line_number"], line["plan_id"], line["producto"], line["plan"], line["precio_lista"],
             line["precio_efectivo"], int(line["oferta_aplicada"]), int(line["discount_eligible"]), line["discount_bps"],
             line["discount_amount"], line["line_total_final"], preview["currency"], created_at))
        sums = conn.execute("SELECT COUNT(*),SUM(effective_price),SUM(discount_amount),SUM(final_total) FROM customer_order_lines WHERE order_id=?", (order_id,)).fetchone()
        if (sums[0] != preview["item_count"] or sums[1] != preview["subtotal_bruto"] or sums[2] != preview["discount_total"]
                or sums[3] != preview["total_final"] or preview["subtotal_bruto"] - preview["discount_total"] != preview["total_final"]):
            raise RuntimeError("Las invariantes financieras del pedido no coinciden.")
        _remember_checkout_in_cursor(conn, guest_session_hash, normalized["customer"], order_id, created_at)
        result = _read_order(conn, "id", order_id)
        conn.commit()
        return result, True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_current_order(guest_session_hash):
    guest_session_hash = _validate_session_hash(guest_session_hash)
    conn = database.conectar()
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        result, public_order_id = _cancel_current_in_cursor(conn, guest_session_hash, _timestamp(_utc_now()))
        conn.commit()
        return {"result": result, "order_id": public_order_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_checkout_customer(guest_session_hash):
    guest_session_hash = _validate_session_hash(guest_session_hash)
    conn = database.conectar()
    try:
        row = conn.execute("SELECT customer_first_name,customer_last_name,customer_whatsapp FROM customer_checkout_sessions WHERE session_hash=? AND expires_at>?", (guest_session_hash, _timestamp(_utc_now()))).fetchone()
        if not row or not all(row):
            return None
        return {"first_name": row[0], "last_name": row[1], "whatsapp": row[2]}
    finally:
        conn.close()


def list_orders_admin(filter_name="pending"):
    filters = {"pending": ("pending_payment",), "paid": ("paid",), "cancelled": ("cancelled",),
               "expired": ("expired",), "all": None}
    if filter_name not in filters:
        filter_name = "pending"
    conn = database.conectar()
    try:
        base = "SELECT public_order_id,status,customer_first_name,customer_last_name,customer_whatsapp,subtotal,discount_total,total,currency,item_count,eligible_item_count,created_at,expires_at FROM customer_orders"
        values = filters[filter_name]
        if values:
            base += " WHERE status=?"
        base += " ORDER BY id DESC"
        return [dict(row) for row in conn.execute(base, values or ())]
    finally:
        conn.close()


def get_order_admin(public_order_id):
    conn = database.conectar()
    try:
        result = _read_order(conn, "public_order_id", public_order_id)
        if result:
            row = conn.execute("SELECT id FROM customer_orders WHERE public_order_id=?", (public_order_id,)).fetchone()
            result["internal_id"] = row["id"]
        return result
    finally:
        conn.close()
