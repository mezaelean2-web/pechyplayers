import re
import sqlite3
import uuid

import database


TIPOS_CREDITO = {"manual_credit", "recharge", "refund"}
TIPOS_DEBITO = {"manual_debit", "purchase", "renewal", "recovery"}
TIPOS_VALIDOS = TIPOS_CREDITO | TIPOS_DEBITO | {"adjustment"}


def _conectar():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _texto(valor, limite):
    return " ".join(str(valor or "").strip().split())[:limite]


def _monto_entero(valor):
    if isinstance(valor, bool):
        raise ValueError("El monto debe ser un entero positivo.")
    texto = str(valor if valor is not None else "").strip()
    if not re.fullmatch(r"-?[0-9]+", texto):
        raise ValueError("El monto debe ser un entero positivo.")
    monto = int(texto)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que cero.")
    return monto


def formato_cop(valor):
    return f"${int(valor or 0):,}".replace(",", ".") + " COP"


def asegurar_wallet(revendedor_id, cursor=None):
    propia = cursor is None
    conn = _conectar() if propia else None
    cur = conn.cursor() if propia else cursor
    try:
        if propia:
            conn.execute("BEGIN IMMEDIATE")
        existe = cur.execute("SELECT 1 FROM revendedores WHERE id=?", (revendedor_id,)).fetchone()
        if not existe:
            raise LookupError("Revendedor no encontrado.")
        cur.execute(
            "INSERT OR IGNORE INTO reseller_wallets (revendedor_id, saldo) VALUES (?, 0)",
            (revendedor_id,)
        )
        wallet = cur.execute(
            "SELECT id, revendedor_id, saldo, created_at, updated_at FROM reseller_wallets WHERE revendedor_id=?",
            (revendedor_id,)
        ).fetchone()
        if propia:
            conn.commit()
        return dict(wallet)
    except Exception:
        if propia:
            conn.rollback()
        raise
    finally:
        if propia:
            conn.close()


def apply_wallet_transaction(revendedor_id, tipo, monto, motivo, origen="admin",
                             actor="admin", referencia=None, provider=None,
                             external_reference=None, idempotency_key=None,
                             cursor=None):
    """Aplica saldo y ledger atómicamente; BEGIN IMMEDIATE serializa escritores SQLite."""
    tipo = _texto(tipo, 40)
    if tipo not in TIPOS_VALIDOS or tipo == "adjustment":
        raise ValueError("Tipo de movimiento no válido para esta operación.")
    monto = _monto_entero(monto)
    motivo = _texto(motivo, 500)
    if not motivo:
        raise ValueError("El motivo es obligatorio.")
    origen = _texto(origen, 80) or "admin"
    actor = _texto(actor, 80) or "admin"
    referencia = _texto(referencia, 160) or f"wallet-{uuid.uuid4()}"
    provider = _texto(provider, 80) or None
    external_reference = _texto(external_reference, 180) or None
    idempotency_key = _texto(idempotency_key, 180) or None

    propia = cursor is None
    conn = _conectar() if propia else cursor.connection
    try:
        if propia:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
        wallet = asegurar_wallet(revendedor_id, cursor)
        if idempotency_key:
            previo = cursor.execute(
                "SELECT * FROM reseller_wallet_transactions WHERE idempotency_key=?",
                (idempotency_key,)
            ).fetchone()
            if previo:
                if propia:
                    conn.commit()
                resultado = dict(previo)
                resultado["duplicado"] = True
                return resultado
        if provider and external_reference:
            previo = cursor.execute(
                """SELECT * FROM reseller_wallet_transactions
                   WHERE provider=? AND external_reference=?""",
                (provider, external_reference)
            ).fetchone()
            if previo:
                if propia:
                    conn.commit()
                resultado = dict(previo)
                resultado["duplicado"] = True
                return resultado

        saldo_anterior = int(wallet["saldo"])
        direccion = 1 if tipo in TIPOS_CREDITO else -1
        saldo_posterior = saldo_anterior + (direccion * monto)
        if saldo_posterior < 0:
            raise ValueError("Saldo insuficiente. La operación no fue aplicada.")

        cursor.execute(
            """INSERT INTO reseller_wallet_transactions
               (wallet_id, revendedor_id, tipo, monto, saldo_anterior,
                saldo_posterior, referencia, descripcion, origen, actor,
                provider, external_reference, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (wallet["id"], revendedor_id, tipo, monto, saldo_anterior,
             saldo_posterior, referencia, motivo, origen, actor, provider,
             external_reference, idempotency_key)
        )
        movimiento_id = cursor.lastrowid
        cursor.execute(
            """UPDATE reseller_wallets SET saldo=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND saldo=?""",
            (saldo_posterior, wallet["id"], saldo_anterior)
        )
        if cursor.rowcount != 1:
            raise RuntimeError("No se pudo actualizar el saldo de forma segura.")
        if propia:
            conn.commit()
        return {
            "id": movimiento_id, "wallet_id": wallet["id"],
            "revendedor_id": revendedor_id, "tipo": tipo, "monto": monto,
            "saldo_anterior": saldo_anterior, "saldo_posterior": saldo_posterior,
            "referencia": referencia, "descripcion": motivo, "origen": origen,
            "actor": actor, "duplicado": False,
        }
    except sqlite3.IntegrityError as error:
        if propia:
            conn.rollback()
        if idempotency_key or (provider and external_reference):
            raise ValueError("La referencia de este movimiento ya fue procesada.") from error
        raise
    except Exception:
        if propia:
            conn.rollback()
        raise
    finally:
        if propia:
            conn.close()


def obtener_saldo(revendedor_id):
    return asegurar_wallet(revendedor_id)["saldo"]


def obtener_resumen_dashboard(revendedor_id, limite_movimientos=5):
    """Devuelve datos financieros de solo lectura para el dashboard privado."""
    wallet = asegurar_wallet(revendedor_id)
    limite = max(1, min(int(limite_movimientos), 10))
    conn = _conectar()
    try:
        total_recargado = conn.execute(
            """SELECT COALESCE(SUM(monto), 0)
               FROM reseller_wallet_transactions
               WHERE revendedor_id=? AND tipo='recharge'""",
            (revendedor_id,)
        ).fetchone()[0]
        movimientos = conn.execute(
            """SELECT tipo, monto, saldo_posterior, descripcion, provider,
                      referencia, created_at
               FROM reseller_wallet_transactions
               WHERE revendedor_id=?
               ORDER BY id DESC LIMIT ?""",
            (revendedor_id, limite)
        ).fetchall()
        return {
            "saldo": int(wallet["saldo"]),
            "total_recargado": int(total_recargado or 0),
            "movimientos": [dict(fila) for fila in movimientos],
        }
    finally:
        conn.close()


def listar_saldos():
    conn = _conectar()
    try:
        filas = conn.execute("""
            SELECT r.id, r.nombre, r.negocio, r.correo, r.telefono, r.estado,
                   COALESCE(w.saldo, 0) AS saldo, w.updated_at
            FROM revendedores AS r
            LEFT JOIN reseller_wallets AS w ON w.revendedor_id=r.id
            ORDER BY r.id DESC
        """).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conn.close()


def resumen_saldos():
    conn = _conectar()
    try:
        fila = conn.execute("""
            SELECT
                (SELECT COALESCE(SUM(saldo), 0) FROM reseller_wallets) AS saldo_total,
                (SELECT COUNT(*) FROM reseller_wallets WHERE saldo > 0) AS con_saldo,
                (SELECT COALESCE(SUM(monto), 0) FROM reseller_wallet_transactions
                 WHERE tipo='manual_credit' AND date(created_at,'localtime')=date('now','localtime')) AS creditos_hoy,
                (SELECT COALESCE(SUM(monto), 0) FROM reseller_wallet_transactions
                 WHERE tipo='manual_debit' AND date(created_at,'localtime')=date('now','localtime')) AS debitos_hoy
        """).fetchone()
        return {clave: int(fila[clave] or 0) for clave in fila.keys()}
    finally:
        conn.close()


def obtener_control_saldo(revendedor_id, limite=30):
    wallet = asegurar_wallet(revendedor_id)
    conn = _conectar()
    try:
        revendedor = conn.execute(
            "SELECT id, nombre, correo, estado FROM revendedores WHERE id=?",
            (revendedor_id,)
        ).fetchone()
        movimientos = conn.execute(
            """SELECT id, tipo, monto, saldo_anterior, saldo_posterior,
                      descripcion, origen, actor, referencia, provider,
                      external_reference, created_at
               FROM reseller_wallet_transactions WHERE wallet_id=?
               ORDER BY id DESC LIMIT ?""",
            (wallet["id"], max(1, min(int(limite), 100)))
        ).fetchall()
        return dict(revendedor), wallet, [dict(fila) for fila in movimientos]
    finally:
        conn.close()
