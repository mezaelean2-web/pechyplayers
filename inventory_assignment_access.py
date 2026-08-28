"""Autorizacion interna y fail-closed sobre asignaciones de inventario reseller."""

import hashlib
import json
from datetime import date, datetime

import database


MAX_REPLACEMENT_DEPTH = 16
PURCHASE_ACTIVE_STATE = "active"
AUTHORIZABLE_UNIT_STATES = frozenset({"activa", "por_vencer"})
AUTHORIZABLE_PROFILE_PARENT_STATES = frozenset({"disponible", "activa", "por_vencer"})
SAFE_CODES = frozenset({
    "authorized",
    "invalid_request",
    "purchase_not_found",
    "ownership_mismatch",
    "purchase_inactive",
    "purchase_expired",
    "purchase_cut",
    "inventory_missing",
    "inventory_inactive",
    "inventory_expired",
    "assignment_mismatch",
    "replacement_unresolved",
    "replacement_cycle",
    "replacement_ambiguous",
    "ambiguous_assignment",
})


def _denied(code):
    if code not in SAFE_CODES or code == "authorized":
        code = "invalid_request"
    return {
        "authorized": False,
        "safe_code": code,
        "purchase_id": None,
        "inventory_unit": None,
        "assignment_version": None,
    }


def _parse_identifier(value):
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or "")[:10])
    except (TypeError, ValueError):
        return None


def _today(now=None):
    if now is None:
        return date.today()
    if isinstance(now, datetime):
        return now.date()
    if isinstance(now, date):
        return now
    parsed = _parse_date(now)
    return parsed or date.today()


def _valid_window(start, end, today):
    activation = _parse_date(start)
    expiry = _parse_date(end)
    if activation is None or activation > today:
        return "purchase_inactive"
    if expiry is None or expiry <= today:
        return "purchase_expired"
    return None


def _table_exists(cursor, table):
    return cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _load_purchase(cursor, purchase_id):
    return cursor.execute(
        """SELECT rp.*, r.nombre AS reseller_nombre, r.estado AS reseller_estado
           FROM reseller_purchases rp
           JOIN revendedores r ON r.id=rp.revendedor_id
           WHERE rp.id=?""",
        (purchase_id,),
    ).fetchone()


def _resolve_profile_replacement(cursor, account, profile):
    """Sigue A -> B de forma unica; cualquier inconsistencia deniega."""
    if not _table_exists(cursor, "nube_reemplazos_perfiles"):
        return None, None, "replacement_unresolved"
    visited = set()
    current_account = account
    current_profile = profile
    for _ in range(MAX_REPLACEMENT_DEPTH + 1):
        profile_id = int(current_profile["id"])
        if profile_id in visited:
            return None, None, "replacement_cycle"
        visited.add(profile_id)
        successors = cursor.execute(
            """SELECT * FROM nube_reemplazos_perfiles
               WHERE perfil_anterior_id=? ORDER BY id""",
            (profile_id,),
        ).fetchall()
        state = str(current_profile["estado"] or "").strip().lower()
        if state != "reemplazada":
            if successors:
                return None, None, "replacement_ambiguous"
            return current_account, current_profile, None
        if len(successors) != 1:
            code = "replacement_ambiguous" if len(successors) > 1 else "replacement_unresolved"
            return None, None, code
        replacement = successors[0]
        if (int(replacement["cuenta_anterior_id"]) != int(current_account["id"])
                or int(replacement["perfil_anterior_id"]) != profile_id):
            return None, None, "replacement_ambiguous"
        next_account = cursor.execute(
            "SELECT * FROM nube_cuentas WHERE id=?", (replacement["cuenta_nueva_id"],)
        ).fetchone()
        next_profile = cursor.execute(
            "SELECT * FROM nube_perfiles WHERE id=?", (replacement["perfil_nuevo_id"],)
        ).fetchone()
        if not next_account or not next_profile:
            return None, None, "replacement_unresolved"
        if (int(next_profile["cuenta_id"]) != int(next_account["id"])
                or int(next_profile["id"]) != int(replacement["perfil_nuevo_id"])):
            return None, None, "replacement_ambiguous"
        current_account, current_profile = next_account, next_profile
    return None, None, "replacement_cycle"


def _resolve_inventory_unit(cursor, purchase):
    account = cursor.execute(
        "SELECT * FROM nube_cuentas WHERE id=?", (purchase["cuenta_id"],)
    ).fetchone()
    if not account:
        return None, None, "inventory_missing"
    unit_type = str(purchase["tipo_unidad"] or "").strip().lower()
    if unit_type == "cuenta":
        if purchase["perfil_id"] is not None:
            return None, None, "assignment_mismatch"
        outgoing = []
        if _table_exists(cursor, "nube_reemplazos"):
            outgoing = cursor.execute(
                "SELECT id FROM nube_reemplazos WHERE cuenta_anterior_id=?", (account["id"],)
            ).fetchall()
        if str(account["estado"] or "").strip().lower() == "reemplazada" or outgoing:
            # El esquema existe, pero no hay un flujo productivo demostrado que actualice
            # la asignacion comercial de cuentas completas. Se cierra el acceso.
            return None, None, "replacement_unresolved"
        return account, None, None
    if unit_type != "perfil" or purchase["perfil_id"] is None:
        return None, None, "assignment_mismatch"
    profile = cursor.execute(
        "SELECT * FROM nube_perfiles WHERE id=?", (purchase["perfil_id"],)
    ).fetchone()
    if not profile:
        return None, None, "inventory_missing"
    if int(profile["cuenta_id"]) != int(account["id"]):
        return None, None, "assignment_mismatch"
    return _resolve_profile_replacement(cursor, account, profile)


def _unit_window_is_current(unit, today):
    expiry = _parse_date(unit["fecha_vencimiento"])
    delivery = _parse_date(unit["fecha_entrega"])
    try:
        days = int(unit["dias_cuenta"] or 0)
    except (TypeError, ValueError):
        return False
    return bool(delivery and delivery <= today and days > 0 and expiry and expiry > today)


def _validate_inventory(account, profile, purchase, reseller_id, today):
    expected = f"Reseller #{reseller_id} - {purchase['reseller_nombre']}"[:160]
    account_state = str(account["estado"] or "").strip().lower()
    if profile is None:
        if account["modalidad"] not in (None, "", "cuenta_completa"):
            return "assignment_mismatch"
        if account_state not in AUTHORIZABLE_UNIT_STATES:
            return "inventory_inactive"
        if not _unit_window_is_current(account, today):
            return "inventory_expired"
        assigned = account["cliente_id"] is not None and account["nombre_cliente"] == expected
        return None if assigned else "assignment_mismatch"
    if account["modalidad"] != "perfiles" or int(profile["cuenta_id"]) != int(account["id"]):
        return "assignment_mismatch"
    if account_state not in AUTHORIZABLE_PROFILE_PARENT_STATES:
        return "inventory_inactive"
    if account_state in AUTHORIZABLE_UNIT_STATES and account["fecha_vencimiento"]:
        if _parse_date(account["fecha_vencimiento"]) is None or _parse_date(account["fecha_vencimiento"]) <= today:
            return "inventory_expired"
    profile_state = str(profile["estado"] or "").strip().lower()
    if profile_state not in AUTHORIZABLE_UNIT_STATES:
        return "inventory_inactive"
    if not _unit_window_is_current(profile, today):
        return "inventory_expired"
    assigned = profile["cliente_id"] is not None and profile["nombre_cliente"] == expected
    return None if assigned else "assignment_mismatch"


def _has_competing_purchase(cursor, purchase, account, profile):
    if profile is None:
        row = cursor.execute(
            """SELECT 1 FROM reseller_purchases
               WHERE id<>? AND cuenta_id=? AND perfil_id IS NULL
                 AND tipo_unidad='cuenta' AND estado_persistido='active'
                 AND cortada_at IS NULL LIMIT 1""",
            (purchase["id"], account["id"]),
        ).fetchone()
    else:
        row = cursor.execute(
            """SELECT 1 FROM reseller_purchases
               WHERE id<>? AND cuenta_id=? AND perfil_id=?
                 AND tipo_unidad='perfil' AND estado_persistido='active'
                 AND cortada_at IS NULL LIMIT 1""",
            (purchase["id"], account["id"], profile["id"]),
        ).fetchone()
    return row is not None


def _assignment_version(purchase, account, profile):
    material = {
        "purchase_id": int(purchase["id"]),
        "purchase_updated_at": purchase["updated_at"] or "",
        "purchase_expires_at": purchase["fecha_vencimiento"] or "",
        "account_id": int(account["id"]),
        "account_updated_at": account["fecha_actualizacion"] or "",
        "profile_id": int(profile["id"]) if profile is not None else None,
        "profile_updated_at": profile["fecha_actualizacion"] if profile is not None else None,
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def authorize_reseller_message_access(reseller_id, reseller_purchase_id, *, now=None,
                                      connection=None):
    """Autoriza una adquisicion propia vigente sin exponer credenciales ni correo."""
    reseller_id = _parse_identifier(reseller_id)
    purchase_id = _parse_identifier(reseller_purchase_id)
    if reseller_id is None or purchase_id is None:
        return _denied("invalid_request")
    own_connection = connection is None
    conn = connection or database.conectar()
    try:
        cursor = conn.cursor()
        purchase = _load_purchase(cursor, purchase_id)
        if not purchase:
            return _denied("purchase_not_found")
        if int(purchase["revendedor_id"]) != reseller_id:
            return _denied("ownership_mismatch")
        if str(purchase["reseller_estado"] or "").strip().lower() != "activo":
            return _denied("purchase_inactive")
        if purchase["cortada_at"]:
            return _denied("purchase_cut")
        if str(purchase["estado_persistido"] or "").strip().lower() != PURCHASE_ACTIVE_STATE:
            return _denied("purchase_inactive")
        today = _today(now)
        window_error = _valid_window(
            purchase["fecha_activacion"], purchase["fecha_vencimiento"], today
        )
        if window_error:
            return _denied(window_error)
        account, profile, resolution_error = _resolve_inventory_unit(cursor, purchase)
        if resolution_error:
            return _denied(resolution_error)
        inventory_error = _validate_inventory(account, profile, purchase, reseller_id, today)
        if inventory_error:
            return _denied(inventory_error)
        if _has_competing_purchase(cursor, purchase, account, profile):
            return _denied("ambiguous_assignment")
        unit = {
            "type": "perfil" if profile is not None else "cuenta",
            "account_id": int(account["id"]),
            "profile_id": int(profile["id"]) if profile is not None else None,
        }
        return {
            "authorized": True,
            "safe_code": "authorized",
            "purchase_id": purchase_id,
            "inventory_unit": unit,
            "assignment_version": _assignment_version(purchase, account, profile),
        }
    except Exception:
        # Una tabla/columna ausente o un dato historico inesperado nunca abre acceso.
        return _denied("invalid_request")
    finally:
        if own_connection:
            conn.close()
