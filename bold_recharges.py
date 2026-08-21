import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3

import database
import wallets


PROVIDER = "bold"
CURRENCY = "COP"
MIN_AMOUNT = 10000
MAX_AMOUNT = 2000000
FINAL_STATES = {"approved", "rejected", "cancelled", "expired"}
KNOWN_EVENTS = {"SALE_APPROVED", "SALE_REJECTED", "VOID_APPROVED", "VOID_REJECTED"}
EVENT_STATES = {"processing", "processed", "ignored", "duplicate"}


def _connect():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def initialize():
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS reseller_recharge_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revendedor_id INTEGER NOT NULL,
                order_id TEXT NOT NULL UNIQUE,
                monto INTEGER NOT NULL CHECK (monto > 0),
                moneda TEXT NOT NULL DEFAULT 'COP' CHECK (moneda = 'COP'),
                provider TEXT NOT NULL DEFAULT 'bold' CHECK (provider = 'bold'),
                estado TEXT NOT NULL DEFAULT 'pending'
                    CHECK (estado IN ('pending','approved','rejected','cancelled','expired')),
                external_transaction_id TEXT,
                last_event_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                paid_at TEXT,
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id)
            );
            CREATE INDEX IF NOT EXISTS idx_recharge_intents_reseller_recent
                ON reseller_recharge_intents(revendedor_id, id DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_recharge_bold_transaction
                ON reseller_recharge_intents(provider, external_transaction_id)
                WHERE external_transaction_id IS NOT NULL;
        """)
        intent_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(reseller_recharge_intents)")
        }
        if "environment" not in intent_columns:
            conn.execute(
                """ALTER TABLE reseller_recharge_intents ADD COLUMN environment TEXT
                   NOT NULL DEFAULT 'test' CHECK (environment IN ('test','production'))"""
            )
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bold_webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                intent_id INTEGER,
                payment_id TEXT,
                order_id TEXT,
                event_type TEXT,
                environment TEXT NOT NULL
                    CHECK (environment IN ('test','production')),
                processing_status TEXT NOT NULL DEFAULT 'processing'
                    CHECK (processing_status IN ('processing','processed','ignored','duplicate')),
                result_reason TEXT NOT NULL DEFAULT '',
                received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                processed_at TEXT,
                FOREIGN KEY (intent_id) REFERENCES reseller_recharge_intents(id)
            );
            CREATE INDEX IF NOT EXISTS idx_bold_events_payment
                ON bold_webhook_events(payment_id);
            CREATE INDEX IF NOT EXISTS idx_bold_events_order
                ON bold_webhook_events(order_id);
            CREATE INDEX IF NOT EXISTS idx_bold_events_intent
                ON bold_webhook_events(intent_id, id DESC);
        """)
        conn.commit()
    finally:
        conn.close()


def _amount(value):
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value or "").strip()):
        raise ValueError("El monto debe ser un número entero en pesos.")
    amount = int(str(value).strip())
    if amount < MIN_AMOUNT:
        raise ValueError(f"La recarga mínima es de {wallets.formato_cop(MIN_AMOUNT)}.")
    if amount > MAX_AMOUNT:
        raise ValueError(f"La recarga máxima es de {wallets.formato_cop(MAX_AMOUNT)}.")
    return amount


def _bold_config():
    environment = os.environ.get("BOLD_ENV", "test").strip().lower()
    if environment != "test":
        raise RuntimeError("Esta fase solo permite BOLD_ENV=test.")
    identity = os.environ.get("BOLD_IDENTITY_KEY", "").strip()
    secret = os.environ.get("BOLD_SECRET_KEY", "").strip()
    if not identity or not secret:
        raise RuntimeError("La integración Bold TEST no está configurada.")
    return {"environment": environment, "identity": identity, "secret": secret}


def _test_config():
    config = _bold_config()
    return config["identity"], config["secret"]


def safe_checkout_diagnostics(checkout):
    """Metadatos de diagnóstico sin valores de llaves ni datos personales."""
    identity = os.environ.get("BOLD_IDENTITY_KEY", "").strip()
    secret = os.environ.get("BOLD_SECRET_KEY", "").strip()
    fields = {}
    for name in ("apiKey", "orderId", "amount", "currency", "integritySignature", "customerData"):
        value = checkout.get(name)
        fields[name] = {
            "present": value is not None and value != "",
            "type": type(value).__name__,
            "length": len(value) if isinstance(value, (str, list, dict)) else None,
        }
    customer = checkout.get("customerData")
    try:
        fields["customerData"]["validJsonObject"] = isinstance(json.loads(customer), dict)
    except (TypeError, ValueError):
        fields["customerData"]["validJsonObject"] = False
    return {
        "environment": os.environ.get("BOLD_ENV", "test").strip().lower(),
        "identityConfigured": bool(identity),
        "identityType": type(identity).__name__,
        "identityLength": len(identity),
        "secretConfigured": bool(secret),
        "secretType": type(secret).__name__,
        "secretLength": len(secret),
        "fields": fields,
    }


def create_intent(reseller_id, amount, redirection_url):
    amount = _amount(amount)
    config = _bold_config()
    identity, secret = config["identity"], config["secret"]
    initialize()
    order_id = f"RCH-{secrets.token_hex(16)}"
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        reseller = conn.execute(
            "SELECT id, nombre, correo, telefono, estado FROM revendedores WHERE id=?",
            (reseller_id,),
        ).fetchone()
        if not reseller or reseller["estado"] != "activo":
            raise LookupError("Revendedor activo no encontrado.")
        conn.execute(
            """INSERT INTO reseller_recharge_intents
               (revendedor_id, order_id, monto, moneda, provider, estado, environment)
               VALUES (?, ?, ?, 'COP', 'bold', 'pending', ?)""",
            (reseller_id, order_id, amount, config["environment"]),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    integrity = hashlib.sha256(f"{order_id}{amount}{CURRENCY}{secret}".encode()).hexdigest()
    customer = {"email": reseller["correo"], "fullName": reseller["nombre"]}
    phone = re.sub(r"\D", "", reseller["telefono"] or "")
    if phone:
        customer["phone"] = phone[-10:]
        if str(reseller["telefono"]).strip().startswith("+57"):
            customer["dialCode"] = "+57"
    checkout = {
        "orderId": order_id, "amount": str(amount), "currency": CURRENCY,
        "apiKey": identity, "integritySignature": integrity,
        "description": "Recarga saldo Pechy Players",
        "customerData": json.dumps(customer),
    }
    if redirection_url:
        checkout["redirectionUrl"] = redirection_url
    return checkout


def get_intent(order_id, reseller_id):
    initialize()
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT i.*, COALESCE(w.saldo, 0) AS saldo
               FROM reseller_recharge_intents i
               JOIN revendedores r ON r.id=i.revendedor_id
               LEFT JOIN reseller_wallets w ON w.revendedor_id=i.revendedor_id
               WHERE i.order_id=? AND i.revendedor_id=?""",
            (order_id, reseller_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def recent_movements(reseller_id, limit=10):
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT tipo, monto, descripcion, provider, created_at
               FROM reseller_wallet_transactions WHERE revendedor_id=?
               ORDER BY id DESC LIMIT ?""", (reseller_id, min(max(int(limit), 1), 20))
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def webhook_key():
    environment = os.environ.get("BOLD_ENV", "test").strip().lower()
    if environment == "test":
        # Bold documenta expresamente una clave vacía para firmas de webhook TEST.
        return b""
    if environment == "production":
        secret = os.environ.get("BOLD_SECRET_KEY", "").strip()
        if not secret:
            raise RuntimeError("La llave de webhook Bold no está configurada.")
        return secret.encode()
    raise RuntimeError("BOLD_ENV no es válido.")


def valid_signature(raw_body, received):
    if not received:
        return False
    encoded = base64.b64encode(raw_body)
    expected = hmac.new(webhook_key(), encoded, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(received).strip())


def _event_result(cursor, event_id, status, reason, *, intent_id=None,
                  payment_id=None, order_id=None, event_type=None):
    if status not in EVENT_STATES:
        raise ValueError("Estado interno de evento inválido.")
    cursor.execute(
        """UPDATE bold_webhook_events
           SET intent_id=COALESCE(?, intent_id),
               payment_id=COALESCE(?, payment_id),
               order_id=COALESCE(?, order_id),
               event_type=COALESCE(?, event_type),
               processing_status=?, result_reason=?,
               processed_at=CURRENT_TIMESTAMP
           WHERE event_id=?""",
        (intent_id, payment_id, order_id, event_type, status, reason, event_id),
    )
    return {"status": status, "reason": reason}


def _safe_identifier(value, maximum=180):
    return value if isinstance(value, str) and 0 < len(value) <= maximum else None


def process_webhook(payload):
    if not isinstance(payload, dict):
        raise ValueError("Payload inválido.")
    event_id = payload.get("id")
    event_type = payload.get("type")
    data = payload.get("data")
    if not _safe_identifier(event_id) or not isinstance(data, dict):
        raise ValueError("Payload inválido.")
    environment = os.environ.get("BOLD_ENV", "test").strip().lower()
    if environment not in {"test", "production"}:
        raise RuntimeError("BOLD_ENV no es válido.")
    transaction_id = _safe_identifier(data.get("payment_id"))
    amount_data = data.get("amount")
    metadata = data.get("metadata")
    order_id = _safe_identifier(metadata.get("reference"), 60) if isinstance(metadata, dict) else None
    initialize()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        previous = cursor.execute(
            "SELECT processing_status, result_reason FROM bold_webhook_events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if previous:
            conn.commit()
            return {"status": "duplicate", "reason": "duplicate_event"}
        cursor.execute(
            """INSERT INTO bold_webhook_events
               (event_id, payment_id, order_id, event_type, environment)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, transaction_id, order_id,
             event_type if isinstance(event_type, str) else None, environment),
        )
        if event_type not in KNOWN_EVENTS:
            result = _event_result(
                cursor, event_id, "ignored", "unknown_event", event_type=event_type
            )
            conn.commit()
            return result
        if not transaction_id:
            result = _event_result(cursor, event_id, "ignored", "invalid_payment_id")
            conn.commit()
            return result
        if not order_id:
            result = _event_result(cursor, event_id, "ignored", "invalid_reference")
            conn.commit()
            return result
        intent = conn.execute(
            "SELECT * FROM reseller_recharge_intents WHERE order_id=?", (order_id,)
        ).fetchone()
        if not intent:
            result = _event_result(cursor, event_id, "ignored", "unknown_order")
            conn.commit()
            return result
        event_fields = {
            "intent_id": intent["id"], "payment_id": transaction_id,
            "order_id": order_id, "event_type": event_type,
        }
        reseller = cursor.execute(
            "SELECT id FROM revendedores WHERE id=?", (intent["revendedor_id"],)
        ).fetchone()
        if not reseller:
            result = _event_result(
                cursor, event_id, "ignored", "unknown_reseller", **event_fields
            )
            conn.commit()
            return result
        if intent["environment"] != environment:
            result = _event_result(
                cursor, event_id, "ignored", "environment_mismatch", **event_fields
            )
            conn.commit()
            return result
        if not isinstance(amount_data, dict):
            result = _event_result(
                cursor, event_id, "ignored", "invalid_amount", **event_fields
            )
            conn.commit()
            return result
        total, currency = amount_data.get("total"), amount_data.get("currency")
        if isinstance(total, bool) or not isinstance(total, int) or total != intent["monto"]:
            result = _event_result(
                cursor, event_id, "ignored", "amount_mismatch", **event_fields
            )
            conn.commit()
            return result
        if currency != intent["moneda"]:
            result = _event_result(
                cursor, event_id, "ignored", "currency_mismatch", **event_fields
            )
            conn.commit()
            return result
        if event_type in {"SALE_APPROVED", "SALE_REJECTED"}:
            payment_owner = cursor.execute(
                """SELECT id, order_id FROM reseller_recharge_intents
                   WHERE provider=? AND external_transaction_id=? AND id<>?""",
                (PROVIDER, transaction_id, intent["id"]),
            ).fetchone()
            ledger_owner = cursor.execute(
                """SELECT revendedor_id, referencia FROM reseller_wallet_transactions
                   WHERE provider=? AND external_reference=?""",
                (PROVIDER, transaction_id),
            ).fetchone()
            if payment_owner or ledger_owner:
                result = _event_result(
                    cursor, event_id, "duplicate", "duplicate_payment", **event_fields
                )
                conn.commit()
                return result
        if event_type == "SALE_APPROVED":
            if intent["estado"] == "approved":
                result = _event_result(
                    cursor, event_id, "duplicate", "order_already_approved", **event_fields
                )
                conn.commit()
                return result
            if intent["estado"] != "pending":
                result = _event_result(
                    cursor, event_id, "ignored", "not_creditable", **event_fields
                )
                conn.commit()
                return result
            movement = wallets.apply_wallet_transaction(
                intent["revendedor_id"], "recharge", intent["monto"],
                "Recarga automática Bold", origen="bold_webhook", actor="system:bold",
                referencia=order_id, provider=PROVIDER,
                external_reference=transaction_id,
                idempotency_key=f"bold:payment:{transaction_id}", cursor=cursor,
            )
            if movement.get("duplicado"):
                result = _event_result(
                    cursor, event_id, "duplicate", "duplicate_payment", **event_fields
                )
                conn.commit()
                return result
            cursor.execute(
                """UPDATE reseller_recharge_intents SET estado='approved',
                   external_transaction_id=?, last_event_id=?, paid_at=CURRENT_TIMESTAMP,
                   updated_at=CURRENT_TIMESTAMP WHERE id=? AND estado='pending'""",
                (transaction_id, event_id, intent["id"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("No se pudo cerrar la intención de forma atómica.")
            result = _event_result(
                cursor, event_id, "processed", "sale_approved", **event_fields
            )
            conn.commit()
            return result
        if event_type == "SALE_REJECTED":
            if intent["estado"] == "pending":
                cursor.execute(
                """UPDATE reseller_recharge_intents SET estado='rejected',
                   external_transaction_id=?, last_event_id=?, updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND estado='pending'""", (transaction_id, event_id, intent["id"]),
                )
            result = _event_result(
                cursor, event_id, "processed", "sale_rejected", **event_fields
            )
            conn.commit()
            return result
        # Las anulaciones quedan auditadas, pero nunca alteran el ledger automáticamente.
        result = _event_result(
            cursor, event_id, "processed", "void_recorded_no_financial_action", **event_fields
        )
        conn.commit()
        return result
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
