import base64
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.request

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
            CREATE TABLE IF NOT EXISTS bold_reconciliation_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id INTEGER NOT NULL UNIQUE,
                payment_id TEXT NOT NULL UNIQUE,
                order_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency_basis TEXT NOT NULL,
                sale_event_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                reconciled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (intent_id) REFERENCES reseller_recharge_intents(id)
            );
            CREATE TABLE IF NOT EXISTS bold_remote_reconciliation_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intent_id INTEGER NOT NULL,
                reseller_id INTEGER NOT NULL,
                wallet_id INTEGER NOT NULL,
                order_id TEXT NOT NULL,
                payment_id TEXT,
                amount INTEGER NOT NULL,
                local_currency TEXT NOT NULL,
                official_status TEXT,
                queried_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                http_status INTEGER,
                environment TEXT NOT NULL,
                verification_source TEXT NOT NULL,
                result TEXT NOT NULL,
                movement_id INTEGER,
                evidence_sha256 TEXT,
                detail TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (intent_id) REFERENCES reseller_recharge_intents(id),
                FOREIGN KEY (reseller_id) REFERENCES revendedores(id),
                FOREIGN KEY (wallet_id) REFERENCES reseller_wallets(id),
                FOREIGN KEY (movement_id) REFERENCES reseller_wallet_transactions(id)
            );
            CREATE INDEX IF NOT EXISTS idx_bold_remote_audit_intent
                ON bold_remote_reconciliation_audit(intent_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_bold_remote_audit_payment
                ON bold_remote_reconciliation_audit(payment_id);
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
    if environment not in {"test", "production"}:
        raise RuntimeError("BOLD_ENV debe ser test o production.")
    identity = os.environ.get("BOLD_IDENTITY_KEY", "").strip()
    secret = os.environ.get("BOLD_SECRET_KEY", "").strip()
    if not identity or not secret:
        raise RuntimeError(f"La integración Bold {environment.upper()} no está configurada.")
    return {"environment": environment, "identity": identity, "secret": secret}


def _test_config():
    config = _bold_config()
    return config["identity"], config["secret"]


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


def _safe_bold_identifier(value, maximum=180):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return None
    return value if len(value) <= maximum else None


def _normalize_bold_total(value):
    """Normaliza un JSON number de Bold a pesos enteros sin perder exactitud."""
    if isinstance(value, bool) or type(value) not in {int, float}:
        raise ValueError("Monto Bold invalido.")
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("Monto Bold invalido.")
        value = int(value)
    if value <= 0:
        raise ValueError("Monto Bold invalido.")
    return value


class ReconciliationError(ValueError):
    """Discrepancia segura: la reconciliacion completa debe abortarse."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class RemoteReconciliationError(ReconciliationError):
    """Fallo cerrado al consultar o reconciliar directamente contra Bold."""

    def __init__(self, reason, *, http_status=None):
        self.http_status = http_status
        super().__init__(reason)


def fetch_official_voucher(order_id, *, timeout=10):
    """Consulta Bold desde backend; nunca recibe evidencia aportada por el cliente."""
    order_id = _safe_bold_identifier(order_id, 60)
    if not order_id:
        raise RemoteReconciliationError("invalid_local_order_id")
    config = _bold_config()
    if config["environment"] != "production":
        raise RemoteReconciliationError("environment_not_production")
    request = urllib.request.Request(
        f"https://payments.api.bold.co/v2/payment-voucher/{order_id}",
        headers={"Authorization": f"x-api-key {config['identity']}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise RemoteReconciliationError("official_http_error", http_status=error.code) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = "official_timeout" if isinstance(getattr(error, "reason", error), TimeoutError) else "official_network_error"
        raise RemoteReconciliationError(reason) from error
    if status < 200 or status >= 300:
        raise RemoteReconciliationError("official_http_error", http_status=status)
    try:
        voucher = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RemoteReconciliationError("official_invalid_json", http_status=status) from error
    if not isinstance(voucher, dict):
        raise RemoteReconciliationError("official_incomplete_response", http_status=status)
    return voucher, status, hashlib.sha256(raw).hexdigest()


def _insert_remote_audit(cursor, *, intent, wallet_id, payment_id, official_status,
                         http_status, result, movement_id=None, evidence_sha256=None,
                         detail=""):
    cursor.execute(
        """INSERT INTO bold_remote_reconciliation_audit
           (intent_id, reseller_id, wallet_id, order_id, payment_id, amount,
            local_currency, official_status, http_status, environment,
            verification_source, result, movement_id, evidence_sha256, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   'bold_payment_voucher_v2', ?, ?, ?, ?)""",
        (intent["id"], intent["revendedor_id"], wallet_id, intent["order_id"],
         payment_id, intent["monto"], intent["moneda"], official_status,
         http_status, intent["environment"], result, movement_id,
         evidence_sha256, detail[:180]),
    )


def _audit_remote_rejection(intent, wallet_id, reason, *, payment_id=None,
                            official_status=None, http_status=None,
                            evidence_sha256=None):
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _insert_remote_audit(
            conn.cursor(), intent=intent, wallet_id=wallet_id,
            payment_id=payment_id, official_status=official_status,
            http_status=http_status, result="rejected",
            evidence_sha256=evidence_sha256, detail=reason,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reconcile_pending_from_bold(intent_id):
    """Recupera un pending mediante consulta oficial, sin depender del navegador.

    payment-voucher v2 no devuelve moneda. Se valida COP contra el intent local
    firmado al crear el checkout, pero no se afirma que Bold haya confirmado COP.
    """
    try:
        intent_id = int(intent_id)
    except (TypeError, ValueError) as error:
        raise RemoteReconciliationError("invalid_intent_id") from error
    if intent_id <= 0:
        raise RemoteReconciliationError("invalid_intent_id")
    actor = "system:bold-recovery"

    initialize()
    conn = _connect()
    try:
        intent_row = conn.execute(
            "SELECT * FROM reseller_recharge_intents WHERE id=?", (intent_id,)
        ).fetchone()
        if not intent_row:
            raise RemoteReconciliationError("intent_not_found")
        intent = dict(intent_row)
        wallet = conn.execute(
            "SELECT * FROM reseller_wallets WHERE revendedor_id=?",
            (intent["revendedor_id"],),
        ).fetchone()
        if not wallet:
            raise RemoteReconciliationError("wallet_not_found")
        wallet_id = wallet["id"]
        if intent["estado"] == "approved" and intent["external_transaction_id"]:
            ledger = conn.execute(
                """SELECT * FROM reseller_wallet_transactions
                   WHERE provider=? AND external_reference=?""",
                (PROVIDER, intent["external_transaction_id"]),
            ).fetchone()
            if (ledger and ledger["revendedor_id"] == intent["revendedor_id"] and
                    ledger["wallet_id"] == wallet_id and
                    ledger["idempotency_key"] == f"bold:payment:{intent['external_transaction_id']}"):
                return {"status": "duplicate", "reason": "already_reconciled",
                        "movement_id": ledger["id"],
                        "currency_confirmed_by_voucher": False}
        if intent["estado"] != "pending":
            raise RemoteReconciliationError("intent_not_pending")
        if (intent["provider"] != PROVIDER or intent["environment"] != "production" or
                intent["moneda"] != CURRENCY):
            raise RemoteReconciliationError("invalid_local_payment_basis")
        reseller = conn.execute(
            "SELECT id, estado FROM revendedores WHERE id=?", (intent["revendedor_id"],)
        ).fetchone()
        if not reseller or reseller["estado"] != "activo":
            raise RemoteReconciliationError("reseller_not_active")
    finally:
        conn.close()

    try:
        voucher, http_status, evidence_sha256 = fetch_official_voucher(intent["order_id"])
    except RemoteReconciliationError as error:
        _audit_remote_rejection(intent, wallet_id, error.reason,
                                http_status=error.http_status)
        raise
    except Exception as error:
        _audit_remote_rejection(intent, wallet_id, "official_network_error")
        raise RemoteReconciliationError("official_network_error") from error

    payment_id = _safe_bold_identifier(voucher.get("transaction_id")) if isinstance(voucher, dict) else None
    official_status = voucher.get("payment_status") if isinstance(voucher, dict) else None
    reason = None
    if not isinstance(voucher, dict):
        reason = "official_incomplete_response"
    elif official_status != "APPROVED":
        reason = "official_status_not_approved"
    elif _safe_bold_identifier(voucher.get("reference_id"), 60) != intent["order_id"]:
        reason = "reference_id_mismatch"
    elif not payment_id:
        reason = "invalid_transaction_id"
    else:
        try:
            if _normalize_bold_total(voucher.get("total")) != intent["monto"]:
                reason = "amount_mismatch"
        except ValueError:
            reason = "amount_mismatch"
    if reason:
        _audit_remote_rejection(
            intent, wallet_id, reason, payment_id=payment_id,
            official_status=official_status, http_status=http_status,
            evidence_sha256=evidence_sha256,
        )
        raise RemoteReconciliationError(reason, http_status=http_status)

    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        current = cursor.execute(
            "SELECT * FROM reseller_recharge_intents WHERE id=?", (intent_id,)
        ).fetchone()
        if not current:
            raise RemoteReconciliationError("intent_not_found")
        invariant_fields = ("order_id", "monto", "moneda", "provider", "environment", "revendedor_id")
        if any(current[field] != intent[field] for field in invariant_fields):
            raise RemoteReconciliationError("intent_changed")
        reseller = cursor.execute(
            "SELECT id, estado FROM revendedores WHERE id=?", (current["revendedor_id"],)
        ).fetchone()
        locked_wallet = cursor.execute(
            "SELECT * FROM reseller_wallets WHERE id=? AND revendedor_id=?",
            (wallet_id, current["revendedor_id"]),
        ).fetchone()
        if not reseller or reseller["estado"] != "activo":
            raise RemoteReconciliationError("reseller_not_active")
        if not locked_wallet:
            raise RemoteReconciliationError("wallet_changed")

        ledger = cursor.execute(
            """SELECT * FROM reseller_wallet_transactions
               WHERE provider=? AND external_reference=?""",
            (PROVIDER, payment_id),
        ).fetchone()
        if current["estado"] == "approved":
            if (current["external_transaction_id"] == payment_id and ledger and
                    ledger["revendedor_id"] == current["revendedor_id"] and
                    ledger["wallet_id"] == wallet_id and
                    ledger["idempotency_key"] == f"bold:payment:{payment_id}"):
                _insert_remote_audit(
                    cursor, intent=current, wallet_id=wallet_id,
                    payment_id=payment_id, official_status=official_status,
                    http_status=http_status, result="already_reconciled",
                    movement_id=ledger["id"], evidence_sha256=evidence_sha256,
                    detail="concurrent_credit_won_before_remote_reconciliation",
                )
                conn.commit()
                return {"status": "duplicate", "reason": "already_reconciled",
                        "movement_id": ledger["id"],
                        "currency_confirmed_by_voucher": False}
            raise RemoteReconciliationError("intent_changed")
        if current["estado"] != "pending":
            raise RemoteReconciliationError("intent_changed")
        if cursor.execute(
            """SELECT 1 FROM reseller_recharge_intents
               WHERE provider=? AND external_transaction_id=? AND id<>? LIMIT 1""",
            (PROVIDER, payment_id, current["id"]),
        ).fetchone():
            raise RemoteReconciliationError("payment_owned_by_other_intent")
        if ledger:
            raise RemoteReconciliationError("bold_ledger_already_exists")

        movement = wallets.apply_wallet_transaction(
            current["revendedor_id"], "recharge", current["monto"],
            "Recuperacion automatica Bold", origen="bold_remote_reconciliation",
            actor=actor, referencia=current["order_id"], provider=PROVIDER,
            external_reference=payment_id,
            idempotency_key=f"bold:payment:{payment_id}", cursor=cursor,
        )
        if movement.get("duplicado"):
            raise RemoteReconciliationError("bold_ledger_already_exists")
        cursor.execute(
            """UPDATE reseller_recharge_intents SET estado='approved',
               external_transaction_id=?, paid_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP WHERE id=? AND estado='pending'""",
            (payment_id, current["id"]),
        )
        if cursor.rowcount != 1:
            raise RemoteReconciliationError("intent_changed")
        _insert_remote_audit(
            cursor, intent=current, wallet_id=wallet_id, payment_id=payment_id,
            official_status=official_status, http_status=http_status,
            result="processed", movement_id=movement["id"],
            evidence_sha256=evidence_sha256,
            detail="currency_from_local_intent_not_confirmed_by_voucher",
        )
        conn.commit()
        return {"status": "processed", "reason": "reconciled_from_official_voucher",
                "movement_id": movement["id"],
                "currency_confirmed_by_voucher": False}
    except Exception as error:
        conn.rollback()
        reason = error.reason if isinstance(error, RemoteReconciliationError) else "transaction_failed"
        try:
            _audit_remote_rejection(
                intent, wallet_id, reason, payment_id=payment_id,
                official_status=official_status, http_status=http_status,
                evidence_sha256=evidence_sha256,
            )
        except Exception:
            pass
        if isinstance(error, RemoteReconciliationError):
            raise
        raise
    finally:
        conn.close()


def reconcile_approved_payment(intent_id, official_voucher, *,
                               expected_transaction_id, expected_reference_id,
                               actor):
    """Reconcilia un voucher ya consultado; esta funcion nunca consulta Bold.

    payment-voucher no acredita moneda. Por eso la base monetaria se limita al
    intent COP creado por este sistema, ligado por referencia unica, payment_id,
    total exacto y el SALE_APPROVED local. La ausencia de cualquiera de esas
    pruebas aborta toda la transaccion.
    """
    if not isinstance(official_voucher, dict):
        raise ReconciliationError("invalid_official_response")
    transaction_id = _safe_identifier(official_voucher.get("transaction_id"))
    reference_id = _safe_identifier(official_voucher.get("reference_id"), 60)
    expected_transaction_id = _safe_identifier(expected_transaction_id)
    expected_reference_id = _safe_identifier(expected_reference_id, 60)
    actor = _safe_identifier(actor, 80)
    if not expected_transaction_id or transaction_id != expected_transaction_id:
        raise ReconciliationError("transaction_id_mismatch")
    if not expected_reference_id or reference_id != expected_reference_id:
        raise ReconciliationError("reference_id_mismatch")
    if official_voucher.get("payment_status") != "APPROVED":
        raise ReconciliationError("official_status_not_approved")
    try:
        total = _normalize_bold_total(official_voucher.get("total"))
    except ValueError as error:
        raise ReconciliationError("amount_mismatch") from error
    if not actor:
        raise ReconciliationError("invalid_actor")

    initialize()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        intent = cursor.execute(
            "SELECT * FROM reseller_recharge_intents WHERE id=?", (intent_id,)
        ).fetchone()
        if not intent:
            raise ReconciliationError("intent_not_found")
        if intent["environment"] != "production":
            raise ReconciliationError("environment_not_production")
        if intent["provider"] != PROVIDER or intent["moneda"] != CURRENCY:
            raise ReconciliationError("invalid_local_payment_basis")
        if intent["order_id"] != reference_id:
            raise ReconciliationError("reference_id_mismatch")
        if intent["monto"] != total:
            raise ReconciliationError("amount_mismatch")
        if not cursor.execute(
            "SELECT id FROM revendedores WHERE id=?", (intent["revendedor_id"],)
        ).fetchone():
            raise ReconciliationError("reseller_not_found")

        sale = cursor.execute(
            """SELECT * FROM bold_webhook_events
               WHERE payment_id=? AND order_id=? AND intent_id=?
                 AND event_type='SALE_APPROVED' AND environment='production'
               ORDER BY id ASC LIMIT 1""",
            (transaction_id, reference_id, intent["id"]),
        ).fetchone()
        if not sale:
            related = cursor.execute(
                """SELECT 1 FROM bold_webhook_events
                   WHERE (payment_id=? OR order_id=?) AND intent_id=? LIMIT 1""",
                (transaction_id, reference_id, intent["id"]),
            ).fetchone()
            raise ReconciliationError(
                "local_event_incorrect" if related else "local_sale_event_not_found"
            )
        if cursor.execute(
            """SELECT 1 FROM bold_webhook_events
               WHERE payment_id=? AND order_id=? AND intent_id=?
                 AND event_type='VOID_APPROVED' AND id>? LIMIT 1""",
            (transaction_id, reference_id, intent["id"], sale["id"]),
        ).fetchone():
            raise ReconciliationError("later_void_approved")
        if cursor.execute(
            """SELECT 1 FROM reseller_recharge_intents
               WHERE provider=? AND external_transaction_id=? AND id<>? LIMIT 1""",
            (PROVIDER, transaction_id, intent["id"]),
        ).fetchone():
            raise ReconciliationError("payment_owned_by_other_intent")

        ledger = cursor.execute(
            """SELECT * FROM reseller_wallet_transactions
               WHERE provider=? AND external_reference=?""",
            (PROVIDER, transaction_id),
        ).fetchone()
        audit = cursor.execute(
            "SELECT * FROM bold_reconciliation_audit WHERE intent_id=?",
            (intent["id"],),
        ).fetchone()
        if intent["estado"] != "pending":
            if (intent["estado"] == "approved" and
                    intent["external_transaction_id"] == transaction_id and
                    ledger and ledger["idempotency_key"] == f"bold:payment:{transaction_id}" and
                    ledger["revendedor_id"] == intent["revendedor_id"] and audit):
                conn.commit()
                return {"status": "duplicate", "reason": "already_reconciled",
                        "movement_id": ledger["id"], "currency_confirmed_by_voucher": False}
            raise ReconciliationError("intent_not_pending")
        if ledger:
            raise ReconciliationError("bold_ledger_already_exists")

        movement = wallets.apply_wallet_transaction(
            intent["revendedor_id"], "recharge", intent["monto"],
            "Reconciliacion administrativa Bold", origen="bold_reconciliation",
            actor=actor, referencia=reference_id, provider=PROVIDER,
            external_reference=transaction_id,
            idempotency_key=f"bold:payment:{transaction_id}", cursor=cursor,
        )
        if movement.get("duplicado"):
            raise ReconciliationError("bold_ledger_already_exists")
        cursor.execute(
            """UPDATE reseller_recharge_intents SET estado='approved',
               external_transaction_id=?, last_event_id=?, paid_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP WHERE id=? AND estado='pending'""",
            (transaction_id, sale["event_id"], intent["id"]),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("No se pudo cerrar la intencion de forma atomica.")
        cursor.execute(
            """INSERT INTO bold_reconciliation_audit
               (intent_id, payment_id, order_id, amount, currency_basis,
                sale_event_id, actor) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (intent["id"], transaction_id, reference_id, total,
             "local_intent_COP_voucher_currency_absent", sale["event_id"], actor),
        )
        conn.commit()
        return {"status": "processed", "reason": "reconciled",
                "movement_id": movement["id"],
                "saldo_anterior": movement["saldo_anterior"],
                "saldo_posterior": movement["saldo_posterior"],
                "currency_confirmed_by_voucher": False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def process_webhook(payload):
    if not isinstance(payload, dict):
        raise ValueError("Payload inválido.")
    event_id = payload.get("id")
    event_type = payload.get("type")
    stored_event_type = event_type if isinstance(event_type, str) else None
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
            (event_id, transaction_id, order_id, stored_event_type, environment),
        )
        if not isinstance(event_type, str) or event_type not in KNOWN_EVENTS:
            result = _event_result(
                cursor, event_id, "ignored", "unknown_event", event_type=stored_event_type
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
        try:
            normalized_total = _normalize_bold_total(total)
        except ValueError:
            normalized_total = None
        if normalized_total != intent["monto"]:
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
