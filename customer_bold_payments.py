"""Pagos Bold de pedidos cliente: sin wallet, inventario ni fulfillment."""

import hashlib
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone

import bold_recharges
import database
import customer_fulfillment
import customer_order_email

PROVIDER = "bold"
CURRENCY = "COP"
KNOWN_EVENTS = {"SALE_APPROVED", "SALE_REJECTED", "VOID_APPROVED", "VOID_REJECTED"}
REFERENCE_RE = re.compile(r"^CUST-[A-Za-z0-9_-]{1,55}$")
TRANSACTION_RE = re.compile(r"^[A-Za-z0-9_-]{1,180}$")
RECONCILE_COOLDOWN_SECONDS = 15


class CustomerPaymentError(ValueError):
    def __init__(self, reason, message=None, status=409):
        self.reason = reason
        self.status = status
        super().__init__(message or reason)


def _connect():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def initialize_schema(connection=None):
    owns = connection is None
    conn = connection or _connect()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS customer_bold_payment_intents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_order_id INTEGER NOT NULL UNIQUE,
            provider TEXT NOT NULL DEFAULT 'bold' CHECK(provider='bold'),
            reference_id TEXT NOT NULL UNIQUE,
            expected_amount INTEGER NOT NULL CHECK(expected_amount>0),
            expected_currency TEXT NOT NULL DEFAULT 'COP' CHECK(expected_currency='COP'),
            environment TEXT NOT NULL CHECK(environment IN ('test','production')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','approved','rejected','cancelled','expired','payment_review')),
            external_transaction_id TEXT,
            official_status TEXT,
            confirmation_source TEXT,
            last_event_id TEXT,
            last_checked_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            paid_at TEXT,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(customer_order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_bold_transaction
            ON customer_bold_payment_intents(external_transaction_id)
            WHERE external_transaction_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_customer_bold_status
            ON customer_bold_payment_intents(status, id DESC);
        CREATE TABLE IF NOT EXISTS customer_bold_webhook_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            intent_id INTEGER,
            reference_id TEXT,
            transaction_id TEXT,
            event_type TEXT,
            environment TEXT NOT NULL CHECK(environment IN ('test','production')),
            processing_status TEXT NOT NULL CHECK(processing_status IN ('processing','processed','ignored','duplicate')),
            result_reason TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT,
            FOREIGN KEY(intent_id) REFERENCES customer_bold_payment_intents(id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS customer_bold_payment_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_id INTEGER NOT NULL,
            customer_order_id INTEGER NOT NULL,
            reference_id TEXT NOT NULL,
            transaction_id TEXT,
            expected_amount INTEGER NOT NULL,
            official_amount INTEGER,
            local_currency TEXT NOT NULL,
            official_currency TEXT,
            official_status TEXT,
            source TEXT NOT NULL CHECK(source IN ('webhook','payment_voucher_reconciliation')),
            http_status INTEGER,
            result TEXT NOT NULL,
            evidence_sha256 TEXT,
            detail TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(intent_id) REFERENCES customer_bold_payment_intents(id) ON DELETE RESTRICT,
            FOREIGN KEY(customer_order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_customer_bold_audit_intent
            ON customer_bold_payment_audit(intent_id, id DESC);
        CREATE TABLE IF NOT EXISTS bold_payment_claims (
            transaction_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL CHECK(domain IN ('reseller_recharge','customer_order')),
            local_entity_id INTEGER NOT NULL,
            reference_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # El trigger cubre nuevos créditos reseller sin alterar su lógica financiera.
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reseller_recharge_intents'").fetchone():
            conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS claim_reseller_bold_transaction
            AFTER UPDATE OF external_transaction_id ON reseller_recharge_intents
            WHEN NEW.external_transaction_id IS NOT NULL AND NEW.estado='approved'
                 AND OLD.external_transaction_id IS NULL
            BEGIN
              INSERT INTO bold_payment_claims(transaction_id,domain,local_entity_id,reference_id)
              VALUES(NEW.external_transaction_id,'reseller_recharge',NEW.id,NEW.order_id);
            END;
            """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns:
            conn.close()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _parse_time(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _validate_order(conn, public_order_id, guest_session_hash):
    order = conn.execute("SELECT * FROM customer_orders WHERE public_order_id=?", (public_order_id,)).fetchone()
    if not order or order["guest_session_hash"] != guest_session_hash:
        raise CustomerPaymentError("order_not_found", "Pedido no encontrado.", 404)
    if order["status"] != "pending_payment":
        raise CustomerPaymentError("order_not_payable", "Este pedido ya no admite pagos.")
    if _parse_time(order["expires_at"]) <= _now():
        conn.execute("UPDATE customer_orders SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending_payment'", (order["id"],))
        raise CustomerPaymentError("order_expired", "El pedido expiró. Prepara uno nuevo para actualizar precios.")
    if order["currency"] != CURRENCY or order["total"] <= 0:
        raise CustomerPaymentError("invalid_financial_snapshot", "El snapshot financiero no es válido.")
    sums = conn.execute("SELECT COUNT(*),COALESCE(SUM(effective_price),0),COALESCE(SUM(discount_amount),0),COALESCE(SUM(final_total),0) FROM customer_order_lines WHERE order_id=?", (order["id"],)).fetchone()
    if sums[0] != order["item_count"] or sums[1] != order["subtotal"] or sums[2] != order["discount_total"] or sums[3] != order["total"]:
        raise CustomerPaymentError("invalid_financial_snapshot", "El snapshot financiero no es válido.")
    return order


def create_or_reuse_checkout(public_order_id, guest_session_hash, redirection_url):
    config = bold_recharges._bold_config()
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order = _validate_order(conn, public_order_id, guest_session_hash)
        intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE customer_order_id=?", (order["id"],)).fetchone()
        if intent:
            if (intent["status"] != "pending" or intent["expected_amount"] != order["total"] or
                    intent["expected_currency"] != order["currency"] or intent["environment"] != config["environment"]):
                raise CustomerPaymentError("incompatible_intent", "El intento existente no es compatible.")
        else:
            reference = "CUST-" + secrets.token_hex(16)
            cursor = conn.execute("""INSERT INTO customer_bold_payment_intents
                (customer_order_id,reference_id,expected_amount,expected_currency,environment,expires_at)
                VALUES(?,?,?,'COP',?,?)""", (order["id"], reference, order["total"], config["environment"], order["expires_at"]))
            intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE id=?", (cursor.lastrowid,)).fetchone()
        conn.commit()
    except Exception as error:
        if isinstance(error, CustomerPaymentError) and error.reason == "order_expired":
            conn.commit()
        else:
            conn.rollback()
        raise
    finally:
        conn.close()
    signature = hashlib.sha256(f"{intent['reference_id']}{intent['expected_amount']}{CURRENCY}{config['secret']}".encode()).hexdigest()
    checkout = {"orderId": intent["reference_id"], "amount": str(intent["expected_amount"]), "currency": CURRENCY,
                "apiKey": config["identity"], "integritySignature": signature,
                "description": f"Pedido Pechy Players {public_order_id}"}
    if redirection_url:
        checkout["redirectionUrl"] = redirection_url
    return {"intent_id": intent["id"], "checkout": checkout}


def _claim_transaction(cursor, transaction_id, intent):
    if cursor.execute("SELECT 1 FROM reseller_recharge_intents WHERE external_transaction_id=?", (transaction_id,)).fetchone():
        raise CustomerPaymentError("transaction_claimed_by_reseller")
    if cursor.execute("SELECT 1 FROM reseller_wallet_transactions WHERE provider='bold' AND external_reference=?", (transaction_id,)).fetchone():
        raise CustomerPaymentError("transaction_claimed_by_reseller")
    try:
        cursor.execute("INSERT INTO bold_payment_claims(transaction_id,domain,local_entity_id,reference_id) VALUES(?,'customer_order',?,?)",
                       (transaction_id, intent["id"], intent["reference_id"]))
    except sqlite3.IntegrityError as error:
        owner = cursor.execute("SELECT * FROM bold_payment_claims WHERE transaction_id=?", (transaction_id,)).fetchone()
        if not owner or owner["domain"] != "customer_order" or owner["local_entity_id"] != intent["id"]:
            raise CustomerPaymentError("transaction_already_claimed") from error


def _audit(cursor, intent, *, transaction_id, official_amount, official_currency, official_status,
           source, result, http_status=None, evidence_sha256=None, detail=""):
    cursor.execute("""INSERT INTO customer_bold_payment_audit
        (intent_id,customer_order_id,reference_id,transaction_id,expected_amount,official_amount,
         local_currency,official_currency,official_status,source,http_status,result,evidence_sha256,detail)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (intent["id"], intent["customer_order_id"], intent["reference_id"], transaction_id,
         intent["expected_amount"], official_amount, intent["expected_currency"], official_currency,
         official_status, source, http_status, result, evidence_sha256, detail[:240]))


def _record_rejection(intent_id, *, source, reason, transaction_id=None, official_amount=None,
                      official_currency=None, official_status=None, http_status=None,
                      evidence_sha256=None):
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE id=?", (intent_id,)).fetchone()
        if intent:
            _audit(conn.cursor(), intent, transaction_id=transaction_id, official_amount=official_amount,
                   official_currency=official_currency, official_status=official_status, source=source,
                   result="rejected", http_status=http_status, evidence_sha256=evidence_sha256,
                   detail=reason)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _confirm(intent_id, *, reference, transaction_id, amount, currency, official_status,
             source, http_status=None, evidence_sha256=None):
    if not TRANSACTION_RE.fullmatch(transaction_id or "") or reference is None:
        raise CustomerPaymentError("invalid_official_evidence")
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        intent = cursor.execute("SELECT * FROM customer_bold_payment_intents WHERE id=?", (intent_id,)).fetchone()
        order = cursor.execute("SELECT * FROM customer_orders WHERE id=?", (intent["customer_order_id"],)).fetchone() if intent else None
        if not intent or not order:
            raise CustomerPaymentError("intent_not_found", status=404)
        if intent["status"] == "approved" and order["status"] == "paid" and intent["external_transaction_id"] == transaction_id:
            conn.commit()
            return {"status": "duplicate", "reason": "already_processed"}
        if reference != intent["reference_id"] or official_status != "APPROVED" or amount != intent["expected_amount"]:
            raise CustomerPaymentError("official_evidence_mismatch")
        if currency is not None and currency != intent["expected_currency"]:
            raise CustomerPaymentError("currency_mismatch")
        if intent["expected_currency"] != CURRENCY or order["currency"] != CURRENCY or order["total"] != intent["expected_amount"]:
            raise CustomerPaymentError("local_basis_mismatch")
        if intent["status"] != "pending" or order["status"] != "pending_payment":
            # Un APPROVED tardío se preserva y queda bloqueado para revisión, sin fulfillment.
            if order["status"] == "expired" and intent["status"] in {"pending", "expired"}:
                _claim_transaction(cursor, transaction_id, intent)
                cursor.execute("UPDATE customer_bold_payment_intents SET status='payment_review',external_transaction_id=?,official_status='APPROVED',confirmation_source=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                               (transaction_id, source, intent["id"]))
                _audit(cursor, intent, transaction_id=transaction_id, official_amount=amount, official_currency=currency,
                       official_status=official_status, source=source, result="payment_review", http_status=http_status,
                       evidence_sha256=evidence_sha256, detail="official_approved_after_local_expiry")
                conn.commit()
                return {"status": "payment_review", "reason": "late_approved"}
            raise CustomerPaymentError("state_not_payable")
        _claim_transaction(cursor, transaction_id, intent)
        cursor.execute("""UPDATE customer_bold_payment_intents SET status='approved',external_transaction_id=?,
            official_status='APPROVED',confirmation_source=?,paid_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND status='pending'""", (transaction_id, source, intent["id"]))
        if cursor.rowcount != 1:
            raise CustomerPaymentError("intent_changed")
        cursor.execute("UPDATE customer_orders SET status='paid',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending_payment'", (order["id"],))
        if cursor.rowcount != 1:
            raise CustomerPaymentError("order_changed")
        _audit(cursor, intent, transaction_id=transaction_id, official_amount=amount, official_currency=currency,
               official_status=official_status, source=source, result="processed", http_status=http_status,
               evidence_sha256=evidence_sha256, detail="currency_confirmed_by_webhook" if currency else "currency_from_signed_local_checkout_not_returned_by_voucher")
        conn.commit()
        # Transaccion separada: un fallo de inventario nunca revierte ni desacredita el pago.
        try:
            customer_fulfillment.fulfill_customer_order(order["id"])
        except Exception:
            # El proveedor debe recibir confirmacion financiera aunque el subsistema
            # de fulfillment no pueda ni siquiera registrar su estado de revision.
            pass
        return {"status": "processed", "reason": "payment_confirmed"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_webhook(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Payload inválido.")
    event_id, event_type, data = payload.get("id"), payload.get("type"), payload["data"]
    metadata, amount_data = data.get("metadata"), data.get("amount")
    reference = metadata.get("reference") if isinstance(metadata, dict) else None
    transaction_id = data.get("payment_id")
    environment = os.environ.get("BOLD_ENV", "test").strip().lower()
    if not isinstance(event_id, str) or not event_id or not REFERENCE_RE.fullmatch(reference or ""):
        raise ValueError("Payload inválido.")
    initialize_schema()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT processing_status,result_reason FROM customer_bold_webhook_events WHERE event_id=?", (event_id,)).fetchone()
        if existing:
            conn.commit(); return {"status": "duplicate", "reason": "duplicate_event"}
        intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE reference_id=?", (reference,)).fetchone()
        conn.execute("""INSERT INTO customer_bold_webhook_events(event_id,intent_id,reference_id,transaction_id,event_type,environment,processing_status)
            VALUES(?,?,?,?,?,?,'processing')""", (event_id, intent["id"] if intent else None, reference, transaction_id if isinstance(transaction_id,str) else None, event_type if isinstance(event_type,str) else None, environment))
        if not intent or event_type not in KNOWN_EVENTS:
            reason = "unknown_order" if not intent else "unknown_event"
            conn.execute("UPDATE customer_bold_webhook_events SET processing_status='ignored',result_reason=?,processed_at=CURRENT_TIMESTAMP WHERE event_id=?", (reason,event_id))
            conn.commit(); return {"status":"ignored","reason":reason}
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
    if event_type != "SALE_APPROVED":
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if event_type == "SALE_REJECTED":
                conn.execute("UPDATE customer_bold_payment_intents SET status='rejected',official_status='REJECTED',last_event_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'", (event_id,intent["id"]))
            conn.execute("UPDATE customer_bold_webhook_events SET processing_status='processed',result_reason=?,processed_at=CURRENT_TIMESTAMP WHERE event_id=?", (event_type.lower(),event_id))
            conn.commit(); return {"status":"processed","reason":event_type.lower()}
        except Exception: conn.rollback(); raise
        finally: conn.close()
    try:
        total = bold_recharges._normalize_bold_total(amount_data.get("total")) if isinstance(amount_data,dict) else None
        currency = amount_data.get("currency") if isinstance(amount_data,dict) else None
        result = _confirm(intent["id"], reference=reference, transaction_id=transaction_id, amount=total,
                          currency=currency, official_status="APPROVED", source="webhook")
        if result["status"] == "processed":
            try:
                customer_order_email.send_payment_confirmation(intent["customer_order_id"])
            except Exception:
                # La notificación ocurre después del commit financiero y nunca
                # cambia la respuesta autoritativa entregada a Bold.
                pass
        event_status = "duplicate" if result["status"] == "duplicate" else "processed"
        reason = result["reason"]
    except (ValueError, CustomerPaymentError) as error:
        event_status, reason = "ignored", getattr(error,"reason","invalid_amount")
        result = {"status":event_status,"reason":reason}
        _record_rejection(intent["id"], source="webhook", reason=reason,
                          transaction_id=transaction_id if isinstance(transaction_id, str) else None,
                          official_amount=total if "total" in locals() else None,
                          official_currency=currency if "currency" in locals() else None,
                          official_status="APPROVED")
    conn = _connect()
    try:
        conn.execute("UPDATE customer_bold_webhook_events SET processing_status=?,result_reason=?,processed_at=CURRENT_TIMESTAMP WHERE event_id=?", (event_status,reason,event_id)); conn.commit()
    finally: conn.close()
    return result


def reconcile_customer_pending_from_bold(intent_id):
    initialize_schema()
    conn = _connect()
    try:
        intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE id=?", (int(intent_id),)).fetchone()
        if not intent: raise CustomerPaymentError("intent_not_found", status=404)
        if intent["status"] == "approved": return {"status":"duplicate","reason":"already_reconciled"}
        reference = intent["reference_id"]
    finally: conn.close()
    voucher = None
    http_status = None
    evidence_hash = None
    try:
        voucher, http_status, evidence_hash = bold_recharges.fetch_official_voucher(reference)
        transaction_id = voucher.get("transaction_id")
        status = voucher.get("payment_status")
        amount = bold_recharges._normalize_bold_total(voucher.get("total"))
        if status != "APPROVED":
            raise CustomerPaymentError("official_status_not_approved")
        result = _confirm(intent["id"], reference=voucher.get("reference_id"), transaction_id=transaction_id,
                          amount=amount, currency=None, official_status=status,
                          source="payment_voucher_reconciliation", http_status=http_status,
                          evidence_sha256=evidence_hash)
        if result["status"] == "processed":
            try:
                customer_order_email.send_payment_confirmation(intent["customer_order_id"])
            except Exception:
                # El pago y el fulfillment ya quedaron comprometidos. Un fallo de
                # notificación no puede revertir ni desacreditar esa confirmación.
                pass
        return result
    except (bold_recharges.RemoteReconciliationError, CustomerPaymentError, ValueError) as error:
        reason = getattr(error, "reason", "official_incomplete_response")
        _record_rejection(intent["id"], source="payment_voucher_reconciliation", reason=reason,
                          transaction_id=voucher.get("transaction_id") if isinstance(voucher,dict) else None,
                          official_amount=voucher.get("total") if isinstance(voucher,dict) and isinstance(voucher.get("total"),int) else None,
                          official_status=voucher.get("payment_status") if isinstance(voucher,dict) else None,
                          http_status=getattr(error,"http_status",None) or http_status,
                          evidence_sha256=evidence_hash)
        if isinstance(error, CustomerPaymentError):
            raise
        raise CustomerPaymentError(reason, status=503 if isinstance(error, bold_recharges.RemoteReconciliationError) else 409) from error


def get_status(public_order_id, guest_session_hash, *, reconcile=False):
    initialize_schema()
    conn = _connect()
    try:
        order = conn.execute("SELECT id,status,guest_session_hash FROM customer_orders WHERE public_order_id=?", (public_order_id,)).fetchone()
        if not order or order["guest_session_hash"] != guest_session_hash:
            raise CustomerPaymentError("order_not_found", "Pedido no encontrado.", 404)
        if order["status"] == "pending_payment":
            full_order = conn.execute("SELECT expires_at FROM customer_orders WHERE id=?", (order["id"],)).fetchone()
            if _parse_time(full_order["expires_at"]) <= _now():
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE customer_orders SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending_payment'", (order["id"],))
                conn.execute("UPDATE customer_bold_payment_intents SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE customer_order_id=? AND status='pending'", (order["id"],))
                conn.commit()
                order = conn.execute("SELECT id,status,guest_session_hash FROM customer_orders WHERE id=?", (order["id"],)).fetchone()
        intent = conn.execute("SELECT * FROM customer_bold_payment_intents WHERE customer_order_id=?", (order["id"],)).fetchone()
        should_reconcile = False
        if reconcile and intent and order["status"] == "pending_payment" and intent["environment"] == "production":
            last = _parse_time(intent["last_checked_at"]) if intent["last_checked_at"] else None
            should_reconcile = not last or (_now()-last).total_seconds() >= RECONCILE_COOLDOWN_SECONDS
            if should_reconcile:
                conn.execute("UPDATE customer_bold_payment_intents SET last_checked_at=CURRENT_TIMESTAMP WHERE id=?", (intent["id"],)); conn.commit()
        fulfillment = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_order_fulfillments'").fetchone():
            fulfillment = conn.execute(
                "SELECT status FROM customer_order_fulfillments WHERE order_id=?", (order["id"],)).fetchone()
        fulfillment_status = fulfillment["status"] if fulfillment else None
        result = {"order_id": public_order_id, "status": order["status"],
                  "payment_status": intent["status"] if intent else None,
                  "fulfillment_status": fulfillment_status,
                  "fulfilled": fulfillment_status == "fulfilled"}
    finally: conn.close()
    if should_reconcile:
        try: reconcile_customer_pending_from_bold(intent["id"])
        except CustomerPaymentError: pass
        return get_status(public_order_id, guest_session_hash, reconcile=False)
    return result


def get_payment_admin(order_id):
    initialize_schema()
    conn = _connect()
    try:
        row = conn.execute("""SELECT i.*,a.official_amount,a.official_currency,a.source,a.result,a.http_status,a.evidence_sha256,a.created_at AS audit_at
            FROM customer_bold_payment_intents i LEFT JOIN customer_bold_payment_audit a ON a.id=(SELECT id FROM customer_bold_payment_audit WHERE intent_id=i.id ORDER BY id DESC LIMIT 1)
            WHERE i.customer_order_id=?""", (order_id,)).fetchone()
        return dict(row) if row else None
    finally: conn.close()
