"""Capa comercial pura del carrito público (sin pedidos, pagos ni inventario)."""

import re

import database


MAX_CART_SERVICES = 5
_ITEM_FIELDS = {"plan_id", "quantity"}
_COP_PLAIN = re.compile(r"^[0-9]+$")
_COP_GROUPED = re.compile(r"^[0-9]{1,3}(?:\.[0-9]{3})+$")


class CartValidationError(ValueError):
    def __init__(self, message, code="invalid_cart"):
        super().__init__(message)
        self.code = code


def parse_cop(value):
    """Convierte los formatos COP históricos inequívocos a pesos enteros."""
    if isinstance(value, bool) or value is None:
        raise ValueError("El valor monetario no es válido.")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("El valor monetario no puede ser negativo.")
        return value
    if not isinstance(value, str):
        raise ValueError("El valor monetario debe ser texto o entero.")
    text = value.strip()
    if text.startswith("$"):
        text = text[1:].strip()
    if not text or not (_COP_PLAIN.fullmatch(text) or _COP_GROUPED.fullmatch(text)):
        raise ValueError("El formato monetario COP es inválido o ambiguo.")
    amount = int(text.replace(".", ""))
    if amount < 0:
        raise ValueError("El valor monetario no puede ser negativo.")
    return amount


def initialize_schema(connection=None):
    owns_connection = connection is None
    conn = connection or database.conectar()
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(productos)")}
        if "participa_descuento_carrito" not in columns:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN participa_descuento_carrito "
                "INTEGER NOT NULL DEFAULT 0 CHECK (participa_descuento_carrito IN (0,1))"
            )
        if "descuento_carrito_bps" not in columns:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN descuento_carrito_bps "
                "INTEGER NOT NULL DEFAULT 0 CHECK (descuento_carrito_bps BETWEEN 0 AND 10000)"
            )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_cart_discount_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                minimum_eligible_services INTEGER NOT NULL UNIQUE
                    CHECK (minimum_eligible_services >= 2),
                discount_bps INTEGER NOT NULL
                    CHECK (discount_bps BETWEEN 0 AND 10000),
                active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if owns_connection:
            conn.close()


def list_discount_rules():
    conn = database.conectar()
    try:
        return [dict(row) for row in conn.execute(
            "SELECT id, minimum_eligible_services, discount_bps, active, "
            "created_at, updated_at FROM customer_cart_discount_rules "
            "ORDER BY minimum_eligible_services"
        )]
    finally:
        conn.close()


def save_discount_rule(rule_id, minimum, discount_bps, active):
    if (isinstance(minimum, bool) or not isinstance(minimum, int)
            or isinstance(discount_bps, bool) or not isinstance(discount_bps, int)):
        raise ValueError("Los valores de la regla deben ser enteros.")
    if minimum < 2 or not 0 <= discount_bps <= 10000:
        raise ValueError("La regla de descuento está fuera del rango permitido.")
    active = 1 if active is True else 0 if active is False else None
    if active is None:
        raise ValueError("El estado de la regla no es válido.")
    conn = database.conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if rule_id is None:
            cursor = conn.execute(
                "INSERT INTO customer_cart_discount_rules "
                "(minimum_eligible_services, discount_bps, active) VALUES (?,?,?)",
                (minimum, discount_bps, active),
            )
            rule_id = cursor.lastrowid
        else:
            cursor = conn.execute(
                "UPDATE customer_cart_discount_rules SET minimum_eligible_services=?, "
                "discount_bps=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (minimum, discount_bps, active, int(rule_id)),
            )
            if cursor.rowcount != 1:
                raise LookupError("La regla no existe.")
        conn.commit()
        return int(rule_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_discount_rule(rule_id):
    conn = database.conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "DELETE FROM customer_cart_discount_rules WHERE id=?", (int(rule_id),)
        )
        if cursor.rowcount != 1:
            raise LookupError("La regla no existe.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_plan_discount_configuration(plan_id, eligible, discount_bps):
    if eligible is not True and eligible is not False:
        raise ValueError("La elegibilidad debe ser true o false.")
    if isinstance(discount_bps, bool) or not isinstance(discount_bps, int):
        raise ValueError("El porcentaje debe expresarse en puntos base enteros.")
    if not 0 <= discount_bps <= 10000:
        raise ValueError("El porcentaje debe estar entre 0% y 100%.")
    conn = database.conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "UPDATE productos SET participa_descuento_carrito=?,descuento_carrito_bps=? WHERE id=?",
            (1 if eligible else 0, discount_bps, int(plan_id)),
        )
        if cursor.rowcount != 1:
            raise LookupError("El plan no existe.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _validated_items(payload):
    if not isinstance(payload, dict) or set(payload) != {"items"}:
        raise CartValidationError("El payload solo puede contener items.")
    items = payload["items"]
    if not isinstance(items, list):
        raise CartValidationError("items debe ser una lista.")
    normalized = []
    total = 0
    for item in items:
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise CartValidationError("Cada item solo admite plan_id y quantity.")
        plan_id, quantity = item["plan_id"], item["quantity"]
        if isinstance(plan_id, bool) or not isinstance(plan_id, int) or plan_id <= 0:
            raise CartValidationError("plan_id debe ser un entero positivo.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise CartValidationError("quantity debe ser un entero positivo.")
        total += quantity
        if total > MAX_CART_SERVICES:
            raise CartValidationError(f"El carrito admite máximo {MAX_CART_SERVICES} servicios.", "cart_limit")
        normalized.append((plan_id, quantity))
    return normalized


def calculate_cart(payload, connection=None):
    requested = _validated_items(payload)
    owns_connection = connection is None
    conn = connection or database.conectar()
    try:
        lines = []
        for plan_id, quantity in requested:
            row = conn.execute(
                """SELECT id, nombre, plan, precio, oferta_precio, oferta_activa,
                          visible, estado, participa_descuento_carrito,descuento_carrito_bps
                   FROM productos WHERE id=?""",
                (plan_id,),
            ).fetchone()
            if not row:
                raise CartValidationError(f"El plan #{plan_id} no existe.", "plan_not_found")
            if row["visible"] != 1 or str(row["estado"] or "").lower() != "disponible":
                raise CartValidationError(f"El plan #{plan_id} no está disponible en el catálogo.", "plan_unavailable")
            try:
                list_price = parse_cop(row["precio"])
                offer_applied = row["oferta_activa"] == 1 and bool(str(row["oferta_precio"] or "").strip())
                effective_price = parse_cop(row["oferta_precio"]) if offer_applied else list_price
            except ValueError as error:
                raise CartValidationError(f"El plan #{plan_id} tiene un precio comercial inválido.", "invalid_plan_price") from error
            for _ in range(quantity):
                lines.append({
                    "line_number": len(lines) + 1, "plan_id": row["id"],
                    "producto": row["nombre"], "plan": row["plan"],
                    "precio_lista": list_price, "precio_efectivo": effective_price,
                    "oferta_aplicada": offer_applied,
                    "discount_eligible": row["participa_descuento_carrito"] == 1,
                    "discount_contribution_bps": row["descuento_carrito_bps"] if row["participa_descuento_carrito"] == 1 else 0,
                })
        eligible_count = sum(1 for line in lines if line["discount_eligible"])
    finally:
        if owns_connection:
            conn.close()
    bps = min(sum(line["discount_contribution_bps"] for line in lines), 10000)
    eligible_subtotal = sum(line["precio_efectivo"] for line in lines if line["discount_eligible"])
    excluded_subtotal = sum(line["precio_efectivo"] for line in lines if not line["discount_eligible"])
    discount_total = (eligible_subtotal * bps + 5000) // 10000
    allocations = []
    for line in lines:
        numerator = line["precio_efectivo"] * bps if line["discount_eligible"] else 0
        allocations.append([numerator // 10000, numerator % 10000])
    missing = discount_total - sum(item[0] for item in allocations)
    order = sorted(range(len(lines)), key=lambda i: (-allocations[i][1], lines[i]["line_number"]))
    for index in order[:missing]:
        allocations[index][0] += 1
    for line, allocation in zip(lines, allocations):
        line["discount_bps"] = bps if line["discount_eligible"] else 0
        line["discount_amount"] = allocation[0]
        line["line_total_final"] = line["precio_efectivo"] - allocation[0]
    gross = eligible_subtotal + excluded_subtotal
    return {
        "items": lines, "item_count": len(lines), "eligible_item_count": eligible_count,
        "subtotal_lista": sum(line["precio_lista"] for line in lines),
        "subtotal_bruto": gross, "subtotal_elegible": eligible_subtotal,
        "subtotal_excluido": excluded_subtotal,
        "discount_rule_id": None, "discount_min_items": None,
        "discount_bps": bps, "discount_total": discount_total,
        "total_final": gross - discount_total, "currency": "COP",
    }
