import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import database
import wallets


try:
    ZONA_HORARIA = ZoneInfo("America/Bogota")
except ZoneInfoNotFoundError:
    # Colombia mantiene UTC-05:00 todo el año; Windows puede no incluir tzdata IANA.
    ZONA_HORARIA = timezone(timedelta(hours=-5), "America/Bogota")
UMBRAL_PROXIMO_VENCIMIENTO_DIAS = 3
TIPOS_UNIDAD = {"cuenta", "perfil"}
ORIGENES_COMPRA = {"purchase", "recovery"}
TIPOS_OPERACION = {"purchase", "renewal", "recovery", "mark_no_renew"}
ESTADOS_OPERACION = {"processing", "completed", "failed"}
TIPOS_EVENTO = {
    "purchase", "renewal", "marked_no_renew", "unmarked_no_renew", "cut", "recovery", "expired"
}
MAX_CANTIDAD_PERIODOS = 12
CLAVES_SENSIBLES = re.compile(
    r"(^|_)(password|contrasena|contraseña|pin|secret|token|credential|credencial|correo_acceso|email_acceso)($|_)",
    re.IGNORECASE,
)


class ResellerPurchaseError(Exception):
    """Error de dominio seguro del motor de compras reseller."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


ESTADO_PERSISTIDO_COMPRA = "active"


def _conectar():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def inicializar_esquema(cursor=None):
    """Crea la fundación reseller de forma aditiva dentro del cursor recibido."""
    propia = cursor is None
    conn = _conectar() if propia else cursor.connection
    cur = conn.cursor() if propia else cursor
    try:
        if propia:
            conn.execute("BEGIN IMMEDIATE")
        eventos_sql = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reseller_purchase_events'").fetchone()
        if eventos_sql and "'unmarked_no_renew'" not in (eventos_sql[0] or ""):
            cur.executescript("""
                DROP TRIGGER IF EXISTS trg_reseller_purchase_events_immutable_update;
                DROP TRIGGER IF EXISTS trg_reseller_purchase_events_immutable_delete;
                CREATE TABLE reseller_purchase_events_v3b (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL,
                    tipo TEXT NOT NULL CHECK (tipo IN ('purchase','renewal','marked_no_renew','unmarked_no_renew','cut','recovery','expired')),
                    fecha TEXT NOT NULL, precio_aplicado INTEGER CHECK (precio_aplicado IS NULL OR precio_aplicado >= 0),
                    vencimiento_anterior TEXT, vencimiento_nuevo TEXT, wallet_transaction_id INTEGER,
                    actor_tipo TEXT NOT NULL, actor_id INTEGER, datos_publicos_json TEXT NOT NULL DEFAULT '{}',
                    idempotency_key TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (purchase_id) REFERENCES reseller_purchases(id),
                    FOREIGN KEY (wallet_transaction_id) REFERENCES reseller_wallet_transactions(id));
                INSERT INTO reseller_purchase_events_v3b SELECT * FROM reseller_purchase_events;
                DROP TABLE reseller_purchase_events;
                ALTER TABLE reseller_purchase_events_v3b RENAME TO reseller_purchase_events;
            """)
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS reseller_plan_inventory_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL UNIQUE,
                plataforma TEXT NOT NULL COLLATE NOCASE,
                tipo_unidad TEXT NOT NULL
                    CHECK (tipo_unidad IN ('cuenta', 'perfil')),
                duracion_dias INTEGER NOT NULL CHECK (duracion_dias > 0),
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES productos(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_reseller_plan_rules_activo
                ON reseller_plan_inventory_rules(activo, plan_id);

            CREATE TABLE IF NOT EXISTS reseller_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revendedor_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                cuenta_id INTEGER NOT NULL,
                perfil_id INTEGER,
                tipo_unidad TEXT NOT NULL
                    CHECK (tipo_unidad IN ('cuenta', 'perfil')),
                operacion_origen TEXT NOT NULL
                    CHECK (operacion_origen IN ('purchase', 'recovery')),
                compra_anterior_id INTEGER,
                fecha_compra TEXT NOT NULL,
                fecha_activacion TEXT,
                fecha_vencimiento TEXT,
                dias_contratados INTEGER NOT NULL CHECK (dias_contratados > 0),
                precio_pagado INTEGER NOT NULL CHECK (precio_pagado >= 0),
                precio_unitario_pagado INTEGER CHECK (
                    precio_unitario_pagado IS NULL OR precio_unitario_pagado >= 0
                ),
                cantidad_periodos INTEGER CHECK (
                    cantidad_periodos IS NULL OR cantidad_periodos > 0
                ),
                duracion_base_dias INTEGER CHECK (
                    duracion_base_dias IS NULL OR duracion_base_dias > 0
                ),
                estado_persistido TEXT NOT NULL DEFAULT 'pending',
                no_renovar INTEGER NOT NULL DEFAULT 0 CHECK (no_renovar IN (0, 1)),
                no_renovar_at TEXT,
                cortada_at TEXT,
                wallet_transaction_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (
                    (tipo_unidad = 'cuenta' AND perfil_id IS NULL) OR
                    (tipo_unidad = 'perfil' AND perfil_id IS NOT NULL)
                ),
                CHECK (compra_anterior_id IS NULL OR compra_anterior_id <> id),
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id),
                FOREIGN KEY (plan_id) REFERENCES productos(id),
                FOREIGN KEY (cuenta_id) REFERENCES nube_cuentas(id),
                FOREIGN KEY (perfil_id) REFERENCES nube_perfiles(id),
                FOREIGN KEY (wallet_transaction_id)
                    REFERENCES reseller_wallet_transactions(id),
                FOREIGN KEY (compra_anterior_id) REFERENCES reseller_purchases(id)
            );

            CREATE INDEX IF NOT EXISTS idx_reseller_purchases_owner
                ON reseller_purchases(revendedor_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_reseller_purchases_expiry
                ON reseller_purchases(revendedor_id, fecha_vencimiento);
            CREATE INDEX IF NOT EXISTS idx_reseller_purchases_inventory
                ON reseller_purchases(cuenta_id, perfil_id);
            CREATE INDEX IF NOT EXISTS idx_reseller_purchases_state
                ON reseller_purchases(revendedor_id, estado_persistido, no_renovar);

            CREATE TABLE IF NOT EXISTS reseller_purchase_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN (
                    'purchase', 'renewal', 'marked_no_renew', 'unmarked_no_renew', 'cut',
                    'recovery', 'expired'
                )),
                fecha TEXT NOT NULL,
                precio_aplicado INTEGER CHECK (
                    precio_aplicado IS NULL OR precio_aplicado >= 0
                ),
                vencimiento_anterior TEXT,
                vencimiento_nuevo TEXT,
                wallet_transaction_id INTEGER,
                actor_tipo TEXT NOT NULL,
                actor_id INTEGER,
                datos_publicos_json TEXT NOT NULL DEFAULT '{}',
                idempotency_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (purchase_id) REFERENCES reseller_purchases(id),
                FOREIGN KEY (wallet_transaction_id)
                    REFERENCES reseller_wallet_transactions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_reseller_purchase_events_purchase
                ON reseller_purchase_events(purchase_id, id);
            CREATE INDEX IF NOT EXISTS idx_reseller_purchase_events_date
                ON reseller_purchase_events(fecha);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_reseller_purchase_event_key
                ON reseller_purchase_events(idempotency_key)
                WHERE idempotency_key IS NOT NULL;

            CREATE TRIGGER IF NOT EXISTS trg_reseller_purchase_events_immutable_update
            BEFORE UPDATE ON reseller_purchase_events
            BEGIN
                SELECT RAISE(ABORT, 'reseller_purchase_events is immutable');
            END;
            CREATE TRIGGER IF NOT EXISTS trg_reseller_purchase_events_immutable_delete
            BEFORE DELETE ON reseller_purchase_events
            BEGIN
                SELECT RAISE(ABORT, 'reseller_purchase_events is immutable');
            END;

            CREATE TABLE IF NOT EXISTS reseller_purchase_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) > 0),
                purchase_id INTEGER,
                revendedor_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN (
                    'purchase', 'renewal', 'recovery', 'mark_no_renew'
                )),
                estado TEXT NOT NULL DEFAULT 'processing'
                    CHECK (estado IN ('processing', 'completed', 'failed')),
                request_fingerprint TEXT NOT NULL,
                wallet_transaction_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (purchase_id) REFERENCES reseller_purchases(id),
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id),
                FOREIGN KEY (wallet_transaction_id)
                    REFERENCES reseller_wallet_transactions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_reseller_purchase_ops_owner
                ON reseller_purchase_operations(revendedor_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_reseller_purchase_ops_purchase
                ON reseller_purchase_operations(purchase_id, id DESC);
        """)
        # Migración aditiva: NULL evita inventar desgloses en compras históricas.
        columnas = {
            fila[1] for fila in cur.execute("PRAGMA table_info(reseller_purchases)")
        }
        adiciones = {
            "precio_unitario_pagado": "INTEGER CHECK (precio_unitario_pagado IS NULL OR precio_unitario_pagado >= 0)",
            "cantidad_periodos": "INTEGER CHECK (cantidad_periodos IS NULL OR cantidad_periodos > 0)",
            "duracion_base_dias": "INTEGER CHECK (duracion_base_dias IS NULL OR duracion_base_dias > 0)",
        }
        for nombre, definicion in adiciones.items():
            if nombre not in columnas:
                cur.execute(f"ALTER TABLE reseller_purchases ADD COLUMN {nombre} {definicion}")
        if propia:
            conn.commit()
    except Exception:
        if propia:
            conn.rollback()
        raise
    finally:
        if propia:
            conn.close()


def _fecha_iso(valor, campo, permitir_vacio=False):
    if valor in (None, "") and permitir_vacio:
        return None
    texto = str(valor or "").strip()
    try:
        date.fromisoformat(texto[:10])
    except ValueError as error:
        raise ValueError(f"{campo} debe usar formato YYYY-MM-DD.") from error
    return texto[:10]


def validar_regla_inventario(plan_id, plataforma, tipo_unidad, duracion_dias):
    try:
        plan_id = int(plan_id)
        duracion_dias = int(duracion_dias)
    except (TypeError, ValueError) as error:
        raise ValueError("Plan y duración deben ser enteros válidos.") from error
    plataforma = " ".join(str(plataforma or "").strip().split())
    tipo_unidad = str(tipo_unidad or "").strip().lower()
    if plan_id <= 0:
        raise ValueError("El plan no es válido.")
    if not plataforma:
        raise ValueError("La plataforma de inventario es obligatoria.")
    if tipo_unidad not in TIPOS_UNIDAD:
        raise ValueError("El tipo de unidad no es válido.")
    if duracion_dias <= 0:
        raise ValueError("La duración debe ser mayor que cero.")
    return plan_id, plataforma, tipo_unidad, duracion_dias


def guardar_regla_inventario_plan(plan_id, plataforma, tipo_unidad,
                                   duracion_dias, activo=True):
    plan_id, plataforma, tipo_unidad, duracion_dias = validar_regla_inventario(
        plan_id, plataforma, tipo_unidad, duracion_dias
    )
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM productos WHERE id=?", (plan_id,)).fetchone():
            raise LookupError("Plan no encontrado.")
        modalidad = "cuenta_completa" if tipo_unidad == "cuenta" else "perfiles"
        if not conn.execute("""
            SELECT 1 FROM nube_cuentas
            WHERE lower(trim(plataforma))=lower(trim(?))
              AND COALESCE(modalidad, 'cuenta_completa')=? LIMIT 1
        """, (plataforma, modalidad)).fetchone():
            raise ValueError("La plataforma no tiene inventario real compatible con el tipo de unidad.")
        conn.execute("""
            INSERT INTO reseller_plan_inventory_rules
                (plan_id, plataforma, tipo_unidad, duracion_dias, activo)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                plataforma=excluded.plataforma,
                tipo_unidad=excluded.tipo_unidad,
                duracion_dias=excluded.duracion_dias,
                activo=excluded.activo,
                updated_at=CURRENT_TIMESTAMP
        """, (plan_id, plataforma, tipo_unidad, duracion_dias, int(bool(activo))))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return obtener_regla_inventario_plan(plan_id, incluir_inactiva=True)


def obtener_regla_inventario_plan(plan_id, incluir_inactiva=False):
    conn = _conectar()
    try:
        sql = "SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?"
        parametros = [int(plan_id)]
        if not incluir_inactiva:
            sql += " AND activo=1"
        fila = conn.execute(sql, parametros).fetchone()
        return dict(fila) if fila else None
    finally:
        conn.close()


def listar_reglas_inventario_admin():
    conn = _conectar()
    try:
        return [dict(fila) for fila in conn.execute("""
            SELECT p.id AS plan_id, p.nombre AS producto, p.plan,
                   r.id AS regla_id, r.plataforma, r.tipo_unidad,
                   r.duracion_dias, r.activo, r.updated_at
            FROM productos AS p
            LEFT JOIN reseller_plan_inventory_rules AS r ON r.plan_id=p.id
            ORDER BY p.nombre COLLATE NOCASE, p.plan COLLATE NOCASE, p.id
        """).fetchall()]
    finally:
        conn.close()


def listar_plataformas_inventario():
    conn = _conectar()
    try:
        return [fila[0] for fila in conn.execute("""
            SELECT MIN(trim(plataforma)) FROM nube_cuentas
            WHERE trim(COALESCE(plataforma, '')) != ''
            GROUP BY lower(trim(plataforma)) ORDER BY lower(trim(plataforma))
        """).fetchall()]
    finally:
        conn.close()


def validar_unidad_compra(cursor, cuenta_id, perfil_id, tipo_unidad):
    try:
        cuenta_id = int(cuenta_id)
        perfil_id = int(perfil_id) if perfil_id not in (None, "") else None
    except (TypeError, ValueError) as error:
        raise ValueError("La unidad de inventario no es válida.") from error
    tipo_unidad = str(tipo_unidad or "").strip().lower()
    if tipo_unidad not in TIPOS_UNIDAD or cuenta_id <= 0:
        raise ValueError("La unidad de inventario no es válida.")
    cuenta = cursor.execute(
        "SELECT id, plataforma, modalidad FROM nube_cuentas WHERE id=?", (cuenta_id,)
    ).fetchone()
    if not cuenta:
        raise LookupError("Cuenta de inventario no encontrada.")
    if tipo_unidad == "cuenta":
        if perfil_id is not None:
            raise ValueError("Una cuenta completa no puede indicar perfil.")
        if (cuenta["modalidad"] or "cuenta_completa") != "cuenta_completa":
            raise ValueError("La cuenta de inventario no es de modalidad completa.")
    else:
        if perfil_id is None:
            raise ValueError("Una compra de perfil requiere perfil.")
        perfil = cursor.execute(
            "SELECT id FROM nube_perfiles WHERE id=? AND cuenta_id=?",
            (perfil_id, cuenta_id),
        ).fetchone()
        if not perfil:
            raise ValueError("El perfil no pertenece a la cuenta indicada.")
        if (cuenta["modalidad"] or "") != "perfiles":
            raise ValueError("La cuenta de inventario no admite perfiles.")
    return dict(cuenta)


def crear_purchase_fundacion(revendedor_id, plan_id, cuenta_id, perfil_id,
                              tipo_unidad, operacion_origen, fecha_compra,
                              fecha_activacion, fecha_vencimiento,
                              dias_contratados, precio_pagado,
                              compra_anterior_id=None, estado_persistido="pending"):
    """Crea sólo persistencia de prueba/fundación; no toca wallet ni inventario."""
    tipo_unidad = str(tipo_unidad or "").strip().lower()
    operacion_origen = str(operacion_origen or "").strip().lower()
    if operacion_origen not in ORIGENES_COMPRA:
        raise ValueError("El origen de la compra no es válido.")
    try:
        revendedor_id, plan_id = int(revendedor_id), int(plan_id)
        dias_contratados, precio_pagado = int(dias_contratados), int(precio_pagado)
    except (TypeError, ValueError) as error:
        raise ValueError("Los datos numéricos de la compra no son válidos.") from error
    if dias_contratados <= 0 or precio_pagado < 0:
        raise ValueError("Duración y precio pagado no son válidos.")
    fecha_compra = _fecha_iso(fecha_compra, "fecha_compra")
    fecha_activacion = _fecha_iso(fecha_activacion, "fecha_activacion", True)
    fecha_vencimiento = _fecha_iso(fecha_vencimiento, "fecha_vencimiento", True)
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        validar_unidad_compra(cursor, cuenta_id, perfil_id, tipo_unidad)
        if not cursor.execute("SELECT 1 FROM revendedores WHERE id=?", (revendedor_id,)).fetchone():
            raise LookupError("Revendedor no encontrado.")
        if not cursor.execute("SELECT 1 FROM productos WHERE id=?", (plan_id,)).fetchone():
            raise LookupError("Plan no encontrado.")
        regla = cursor.execute(
            "SELECT tipo_unidad FROM reseller_plan_inventory_rules WHERE plan_id=? AND activo=1",
            (plan_id,),
        ).fetchone()
        if not regla:
            raise ValueError("El plan no tiene una regla de inventario activa.")
        if regla["tipo_unidad"] != tipo_unidad:
            raise ValueError("El plan no corresponde al tipo de unidad indicado.")
        if compra_anterior_id is not None:
            compra_anterior_id = int(compra_anterior_id)
            anterior = cursor.execute(
                "SELECT id, revendedor_id FROM reseller_purchases WHERE id=?",
                (compra_anterior_id,),
            ).fetchone()
            if not anterior or anterior["revendedor_id"] != revendedor_id:
                raise ValueError("La compra anterior no pertenece al reseller.")
        cursor.execute("""
            INSERT INTO reseller_purchases (
                revendedor_id, plan_id, cuenta_id, perfil_id, tipo_unidad,
                operacion_origen, compra_anterior_id, fecha_compra,
                fecha_activacion, fecha_vencimiento, dias_contratados,
                precio_pagado, estado_persistido
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (revendedor_id, plan_id, cuenta_id, perfil_id, tipo_unidad,
              operacion_origen, compra_anterior_id, fecha_compra,
              fecha_activacion, fecha_vencimiento, dias_contratados,
              precio_pagado, str(estado_persistido or "pending")[:40]))
        purchase_id = cursor.lastrowid
        conn.commit()
        return obtener_purchase_reseller(purchase_id, revendedor_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_purchase_reseller(purchase_id, revendedor_id):
    conn = _conectar()
    try:
        fila = conn.execute(
            "SELECT * FROM reseller_purchases WHERE id=? AND revendedor_id=?",
            (int(purchase_id), int(revendedor_id)),
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        conn.close()


def listar_purchases_reseller(revendedor_id):
    conn = _conectar()
    try:
        return [dict(fila) for fila in conn.execute(
            "SELECT * FROM reseller_purchases WHERE revendedor_id=? ORDER BY id DESC",
            (int(revendedor_id),),
        ).fetchall()]
    finally:
        conn.close()


ETIQUETAS_ESTADO_VISUAL = {
    "ACTIVA": "Activa", "PROXIMA_A_VENCER": "Próxima a vencer",
    "VENCE_HOY": "Vence hoy", "VENCIDA": "Vencida", "NO_RENOVADA": "No renovada",
    "CORTADA": "Servicio cortado",
}
PRIORIDAD_ESTADO_VISUAL = {
    "VENCE_HOY": 0, "PROXIMA_A_VENCER": 1, "ACTIVA": 2,
    "VENCIDA": 3, "NO_RENOVADA": 4, "CORTADA": 5,
}
ESTADOS_UNIDAD_INCOMPATIBLES = {
    "disponible", "caida", "bloqueada", "retirada", "papelera", "garantia",
    "reemplazada", "no_disponible", "cortada", "cortado",
}


def _estado_visual_seguro(purchase, ahora=None):
    try:
        return calcular_estado_visual(purchase.get("fecha_vencimiento"), purchase.get("no_renovar"), ahora,
                                      cortada_at=purchase.get("cortada_at"))
    except (TypeError, ValueError):
        return "NO_RENOVADA" if purchase.get("no_renovar") else "ACTIVA"


def listar_mis_cuentas(revendedor_id, estado=None, tipo=None, busqueda=None, ahora=None):
    """Listado privado y no sensible; ownership nace exclusivamente de la sesión."""
    conn = _conectar()
    try:
        filas = conn.execute("""
            SELECT rp.*, p.nombre AS producto, p.plan AS plan_nombre,
                   c.plataforma AS plataforma
            FROM reseller_purchases rp
            JOIN productos p ON p.id=rp.plan_id
            LEFT JOIN nube_cuentas c ON c.id=rp.cuenta_id
            WHERE rp.revendedor_id=?
        """, (int(revendedor_id),)).fetchall()
    finally:
        conn.close()
    estado = str(estado or "todas").strip().upper()
    tipo = str(tipo or "todas").strip().lower()
    busqueda = " ".join(str(busqueda or "").strip().lower().split())
    resultado = []
    for fila in filas:
        item = dict(fila)
        item["estado_visual"] = _estado_visual_seguro(item, ahora)
        item["estado_etiqueta"] = ETIQUETAS_ESTADO_VISUAL[item["estado_visual"]]
        item["tipo_etiqueta"] = "Cuenta completa" if item["tipo_unidad"] == "cuenta" else "Perfil"
        item["identificador"] = f"MC-{item['id']:06d}"
        item["recuperada_de"] = (f"MC-{item['compra_anterior_id']:06d}"
                                  if item.get("compra_anterior_id") else None)
        item["precio_pagado_cop"] = wallets.formato_cop(item["precio_pagado"])
        if estado not in {"", "TODAS"} and item["estado_visual"] != estado:
            continue
        if tipo in TIPOS_UNIDAD and item["tipo_unidad"] != tipo:
            continue
        texto = " ".join(str(item.get(k) or "").lower() for k in ("producto", "plataforma", "plan_nombre"))
        if busqueda and busqueda not in texto:
            continue
        resultado.append(item)
    resultado.sort(key=lambda item: (PRIORIDAD_ESTADO_VISUAL[item["estado_visual"]],
                                     str(item.get("fecha_vencimiento") or "9999-12-31"), item["id"]))
    return resultado


def resumen_mis_cuentas(revendedor_id, ahora=None):
    items = listar_mis_cuentas(revendedor_id, ahora=ahora)
    conteos = {clave: 0 for clave in ETIQUETAS_ESTADO_VISUAL}
    for item in items:
        conteos[item["estado_visual"]] += 1
    return {"total": len(items), "activas": conteos["ACTIVA"],
            "proximas": conteos["PROXIMA_A_VENCER"], "vencen_hoy": conteos["VENCE_HOY"],
            "vencidas": conteos["VENCIDA"], "no_renovadas": conteos["NO_RENOVADA"]}


def obtener_detalle_mi_cuenta(purchase_id, revendedor_id, ahora=None):
    return next((item for item in listar_mis_cuentas(revendedor_id, ahora=ahora)
                 if item["id"] == int(purchase_id)), None)


def obtener_credenciales_autorizadas(purchase_id, revendedor_id):
    """Lee secretos actuales de Nube sólo tras validar ownership y asignación real."""
    conn = _conectar()
    try:
        purchase = conn.execute("""SELECT rp.*, r.nombre AS reseller_nombre
            FROM reseller_purchases rp JOIN revendedores r ON r.id=rp.revendedor_id
            WHERE rp.id=? AND rp.revendedor_id=?""", (int(purchase_id), int(revendedor_id))).fetchone()
        if not purchase:
            return None
        purchase = dict(purchase)
        if purchase.get("cortada_at") or purchase.get("estado_persistido") != "active":
            return {"autorizadas": False, "motivo": "Acceso no disponible"}
        cuenta = conn.execute("SELECT * FROM nube_cuentas WHERE id=?", (purchase["cuenta_id"],)).fetchone()
        if not cuenta:
            return {"autorizadas": False, "motivo": "Acceso no disponible"}
        cuenta = dict(cuenta)
        esperado = f"Reseller #{int(revendedor_id)} - {purchase['reseller_nombre']}"[:160]
        if purchase["tipo_unidad"] == "cuenta":
            if str(cuenta.get("estado") or "").strip().lower() in ESTADOS_UNIDAD_INCOMPATIBLES:
                return {"autorizadas": False, "motivo": "Cuenta fuera de servicio"}
            coherente = (purchase.get("perfil_id") is None
                         and (cuenta.get("modalidad") or "cuenta_completa") == "cuenta_completa"
                         and cuenta.get("nombre_cliente") == esperado)
            if not coherente:
                return {"autorizadas": False, "motivo": "Acceso no disponible"}
            return {"autorizadas": True, "tipo": "cuenta", "campos": [
                {"etiqueta": "Correo de acceso", "valor": cuenta.get("correo") or "", "sensible": False},
                {"etiqueta": "Contraseña", "valor": cuenta.get("contrasena") or "", "sensible": True},
                {"etiqueta": "PIN", "valor": cuenta.get("pin") or "", "sensible": True}]}
        perfil = conn.execute("SELECT * FROM nube_perfiles WHERE id=? AND cuenta_id=?",
                              (purchase.get("perfil_id"), purchase["cuenta_id"])).fetchone()
        if not perfil:
            return {"autorizadas": False, "motivo": "Acceso no disponible"}
        perfil = dict(perfil)
        if str(cuenta.get("estado") or "").strip().lower() in (
                ESTADOS_UNIDAD_INCOMPATIBLES - {"disponible"}):
            return {"autorizadas": False, "motivo": "Cuenta fuera de servicio"}
        coherente = (cuenta.get("modalidad") == "perfiles" and perfil.get("nombre_cliente") == esperado
                     and str(perfil.get("estado") or "").strip().lower() not in ESTADOS_UNIDAD_INCOMPATIBLES)
        if not coherente:
            return {"autorizadas": False, "motivo": "Acceso no disponible"}
        return {"autorizadas": True, "tipo": "perfil", "campos": [
            {"etiqueta": "Correo de acceso", "valor": cuenta.get("correo") or "", "sensible": False},
            {"etiqueta": "Contraseña", "valor": cuenta.get("contrasena") or "", "sensible": True},
            {"etiqueta": "Perfil", "valor": perfil.get("nombre_perfil") or "", "sensible": False},
            {"etiqueta": "PIN del perfil", "valor": perfil.get("pin") or "", "sensible": True}]}
    finally:
        conn.close()


def registrar_corte_purchase_reseller(*, cursor, cuenta_id, perfil_id=None,
                                      motivo="", actor_id=None, ahora=None):
    """Marca, dentro de la transaccion de Nube, la compra de la unidad cortada."""
    if not cursor.execute("""SELECT 1 FROM sqlite_master
        WHERE type='table' AND name='reseller_purchases'""").fetchone():
        return None
    momento = _momento_bogota(ahora).isoformat()
    if perfil_id is None:
        fila = cursor.execute("""SELECT * FROM reseller_purchases
            WHERE cuenta_id=? AND perfil_id IS NULL AND tipo_unidad='cuenta'
              AND cortada_at IS NULL AND estado_persistido='active'
            ORDER BY id DESC LIMIT 1""", (int(cuenta_id),)).fetchone()
        tipo_unidad = "cuenta"
    else:
        fila = cursor.execute("""SELECT * FROM reseller_purchases
            WHERE cuenta_id=? AND perfil_id=? AND tipo_unidad='perfil'
              AND cortada_at IS NULL AND estado_persistido='active'
            ORDER BY id DESC LIMIT 1""", (int(cuenta_id), int(perfil_id))).fetchone()
        tipo_unidad = "perfil"
    if not fila:
        return None
    purchase = dict(fila)
    cursor.execute("""UPDATE reseller_purchases
        SET cortada_at=?, estado_persistido='cut', updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND cortada_at IS NULL""", (momento, purchase["id"]))
    if cursor.rowcount != 1:
        return None
    datos = {"purchase_id": purchase["id"], "tipo_unidad": tipo_unidad,
             "fecha_corte": momento, "estado_operativo": "cortada",
             "ciclo": purchase.get("fecha_vencimiento") or ""}
    if str(motivo or "").strip():
        datos["motivo"] = str(motivo).strip()[:240]
    _validar_metadata_publica(datos)
    cursor.execute("""INSERT OR IGNORE INTO reseller_purchase_events
        (purchase_id,tipo,fecha,actor_tipo,actor_id,datos_publicos_json,idempotency_key)
        VALUES (?,'cut',?,'admin',?,?,?)""",
        (purchase["id"], momento, actor_id,
         json.dumps(datos, ensure_ascii=False, sort_keys=True),
         f"cut:purchase:{purchase['id']}"))
    return purchase["id"]


MENSAJES_DISPONIBILIDAD = {
    "AVAILABLE": "Esta cuenta está disponible nuevamente.",
    "SOLD": "Esta cuenta ya fue asignada a otro cliente y no puede recuperarse.",
    "DOWN": "Esta cuenta se encuentra fuera de servicio y no está disponible para recuperación.",
    "BLOCKED": "Esta cuenta no está disponible actualmente.",
    "RETIRED": "Esta cuenta fue retirada del inventario y no puede recuperarse.",
    "REPLACED": "Esta cuenta fue reemplazada y no puede recuperarse.",
    "WARRANTY": "Esta cuenta se encuentra en garantía y no puede recuperarse.",
    "TRASHED": "Esta cuenta fue retirada del inventario y no puede recuperarse.",
    "NOT_FOUND": "Esta cuenta ya no se encuentra disponible en el inventario.",
    "NOT_CUT": "Este servicio todavía no ha sido cortado.",
    "UNAVAILABLE": "Esta cuenta no está disponible para recuperación.",
}


def consultar_disponibilidad_recuperacion(revendedor_id, purchase_id, ahora=None):
    """Consulta en vivo la misma unidad historica sin reservarla ni exponer secretos."""
    conn = _conectar()
    try:
        fila = conn.execute("""SELECT rp.*, p.nombre producto, p.plan plan_nombre
            FROM reseller_purchases rp JOIN productos p ON p.id=rp.plan_id
            WHERE rp.id=? AND rp.revendedor_id=?""",
            (int(purchase_id), int(revendedor_id))).fetchone()
        if not fila:
            return None
        purchase = dict(fila)
        code = "NOT_CUT"
        if purchase.get("cortada_at"):
            cuenta_fila = conn.execute("SELECT * FROM nube_cuentas WHERE id=?",
                                       (purchase["cuenta_id"],)).fetchone()
            if not cuenta_fila:
                code = "NOT_FOUND"
            else:
                cuenta = dict(cuenta_fila)
                unidad = cuenta
                if purchase["tipo_unidad"] == "perfil":
                    perfil = conn.execute("SELECT * FROM nube_perfiles WHERE id=? AND cuenta_id=?",
                                          (purchase["perfil_id"], purchase["cuenta_id"])).fetchone()
                    unidad = dict(perfil) if perfil else None
                    if unidad is None:
                        code = "NOT_FOUND"
                if unidad is not None:
                    estado_cuenta = str(cuenta.get("estado") or "").strip().lower()
                    estado = str(unidad.get("estado") or "").strip().lower()
                    estados = {estado, estado_cuenta}
                    mapa = {"caida": "DOWN", "bloqueada": "BLOCKED", "retirada": "RETIRED",
                            "reemplazada": "REPLACED", "garantia": "WARRANTY", "papelera": "TRASHED"}
                    code = next((mapa[e] for e in mapa if e in estados), "")
                    asignada = any(unidad.get(k) not in (None, "", 0) for k in
                                   ("cliente_id", "nombre_cliente", "telefono", "fecha_entrega", "dias_cuenta", "fecha_vencimiento"))
                    if not code and conn.execute("""SELECT 1 FROM reseller_purchases
                        WHERE id<>? AND estado_persistido='active' AND cortada_at IS NULL
                          AND ((?='cuenta' AND tipo_unidad='cuenta' AND cuenta_id=? AND perfil_id IS NULL)
                            OR (?='perfil' AND tipo_unidad='perfil' AND perfil_id=? AND cuenta_id=?)) LIMIT 1""",
                        (purchase["id"], purchase["tipo_unidad"], purchase["cuenta_id"],
                         purchase["tipo_unidad"], purchase.get("perfil_id"), purchase["cuenta_id"])).fetchone():
                        asignada = True
                    if not code:
                        modalidad_ok = ((purchase["tipo_unidad"] == "cuenta" and
                                         (cuenta.get("modalidad") or "cuenta_completa") == "cuenta_completa") or
                                        (purchase["tipo_unidad"] == "perfil" and cuenta.get("modalidad") == "perfiles"))
                        if asignada or estado not in {"", "disponible"}:
                            code = "SOLD" if asignada else "UNAVAILABLE"
                        else:
                            code = "AVAILABLE" if modalidad_ok else "UNAVAILABLE"
        return {"purchase_id": purchase["id"], "code": code,
                "recoverable": code == "AVAILABLE", "message": MENSAJES_DISPONIBILIDAD[code],
                "checked_at": _momento_bogota(ahora).isoformat(),
                "tipo_unidad": purchase["tipo_unidad"], "producto": purchase["producto"],
                "plan": purchase["plan_nombre"]}
    finally:
        conn.close()


def _validar_metadata_publica(valor, ruta="datos_publicos"):
    if isinstance(valor, dict):
        for clave, contenido in valor.items():
            if CLAVES_SENSIBLES.search(str(clave)):
                raise ValueError(f"{ruta} contiene una clave sensible.")
            _validar_metadata_publica(contenido, f"{ruta}.{clave}")
    elif isinstance(valor, list):
        for indice, contenido in enumerate(valor):
            _validar_metadata_publica(contenido, f"{ruta}[{indice}]")
    elif not isinstance(valor, (str, int, float, bool, type(None))):
        raise ValueError("La metadata pública no es serializable.")


def registrar_evento_seguro(purchase_id, tipo, actor_tipo, actor_id=None,
                             datos_publicos=None, fecha=None,
                             precio_aplicado=None, vencimiento_anterior=None,
                             vencimiento_nuevo=None, idempotency_key=None):
    tipo = str(tipo or "").strip().lower()
    if tipo not in TIPOS_EVENTO:
        raise ValueError("El tipo de evento no es válido.")
    datos_publicos = datos_publicos or {}
    _validar_metadata_publica(datos_publicos)
    fecha = fecha or datetime.now(ZONA_HORARIA).isoformat()
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute("""
            INSERT INTO reseller_purchase_events (
                purchase_id, tipo, fecha, precio_aplicado,
                vencimiento_anterior, vencimiento_nuevo, actor_tipo,
                actor_id, datos_publicos_json, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(purchase_id), tipo, fecha, precio_aplicado,
              vencimiento_anterior, vencimiento_nuevo,
              str(actor_tipo or "system")[:40], actor_id,
              json.dumps(datos_publicos, ensure_ascii=False, sort_keys=True),
              str(idempotency_key).strip() if idempotency_key else None))
        evento_id = cursor.lastrowid
        conn.commit()
        return evento_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _huella_operacion(revendedor_id, tipo, purchase_id, contexto):
    carga = {
        "revendedor_id": int(revendedor_id),
        "tipo": tipo,
        "purchase_id": int(purchase_id) if purchase_id is not None else None,
        "contexto": contexto or {},
    }
    bruto = json.dumps(carga, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def iniciar_operacion_idempotente(idempotency_key, revendedor_id, tipo,
                                   purchase_id=None, contexto=None):
    clave = str(idempotency_key or "").strip()
    tipo = str(tipo or "").strip().lower()
    if not clave:
        raise ValueError("La idempotency key es obligatoria.")
    if tipo not in TIPOS_OPERACION:
        raise ValueError("El tipo de operación no es válido.")
    huella = _huella_operacion(revendedor_id, tipo, purchase_id, contexto)
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        previa = conn.execute(
            "SELECT * FROM reseller_purchase_operations WHERE idempotency_key=?",
            (clave,),
        ).fetchone()
        if previa:
            if previa["request_fingerprint"] != huella:
                raise ValueError("La idempotency key ya pertenece a otra operación.")
            conn.commit()
            resultado = dict(previa)
            resultado["duplicado"] = True
            return resultado
        if purchase_id is not None:
            purchase = conn.execute(
                "SELECT revendedor_id FROM reseller_purchases WHERE id=? AND revendedor_id=?",
                (int(purchase_id), int(revendedor_id)),
            ).fetchone()
            if not purchase:
                raise LookupError("Adquisición no encontrada.")
        cursor = conn.execute("""
            INSERT INTO reseller_purchase_operations (
                idempotency_key, purchase_id, revendedor_id, tipo,
                estado, request_fingerprint
            ) VALUES (?, ?, ?, ?, 'processing', ?)
        """, (clave, purchase_id, int(revendedor_id), tipo, huella))
        operacion_id = cursor.lastrowid
        conn.commit()
        resultado = dict(conn.execute(
            "SELECT * FROM reseller_purchase_operations WHERE id=?", (operacion_id,)
        ).fetchone())
        resultado["duplicado"] = False
        return resultado
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def calcular_estado_visual(fecha_vencimiento, no_renovar=False, ahora=None,
                           umbral=UMBRAL_PROXIMO_VENCIMIENTO_DIAS, cortada_at=None):
    # El corte operativo prevalece sobre no-renovar y vencimiento comercial.
    if cortada_at:
        return "CORTADA"
    if bool(no_renovar):
        return "NO_RENOVADA"
    vencimiento = date.fromisoformat(str(fecha_vencimiento or "")[:10])
    if ahora is None:
        hoy = datetime.now(ZONA_HORARIA).date()
    elif isinstance(ahora, datetime):
        hoy = (ahora if ahora.tzinfo else ahora.replace(tzinfo=ZONA_HORARIA)).astimezone(
            ZONA_HORARIA
        ).date()
    elif isinstance(ahora, date):
        hoy = ahora
    else:
        hoy = date.fromisoformat(str(ahora)[:10])
    dias = (vencimiento - hoy).days
    if dias < 0:
        return "VENCIDA"
    if dias == 0:
        return "VENCE_HOY"
    if dias <= int(umbral):
        return "PROXIMA_A_VENCER"
    return "ACTIVA"


def _resolver_precio_en_cursor(cursor, plan_id, revendedor_id, hoy):
    fila = cursor.execute("""
        SELECT p.id, p.nombre, p.plan, g.precio AS general,
               g.activo AS general_activo, o.precio AS personalizado,
               o.oferta_activa, o.oferta_precio, o.oferta_inicio, o.oferta_fin,
               o.activo AS override_activo
        FROM productos p
        LEFT JOIN precios_revendedor_generales g ON g.plan_id=p.id
        LEFT JOIN precios_revendedor_personalizados o
          ON o.plan_id=p.id AND o.revendedor_id=? WHERE p.id=?
    """, (revendedor_id, plan_id)).fetchone()
    if not fila:
        raise ResellerPurchaseError("plan_inexistente", "Plan no encontrado.")
    oferta = bool(fila["override_activo"] and fila["oferta_activa"] and fila["oferta_precio"]
                  and (not fila["oferta_inicio"] or fila["oferta_inicio"] <= hoy)
                  and (not fila["oferta_fin"] or fila["oferta_fin"] >= hoy))
    if oferta:
        precio, origen = fila["oferta_precio"], "oferta_personalizada"
    elif fila["override_activo"] and fila["personalizado"]:
        precio, origen = fila["personalizado"], "precio_personalizado"
    elif fila["general_activo"] and fila["general"]:
        precio, origen = fila["general"], "precio_general"
    else:
        raise ResellerPurchaseError("precio_reseller_no_configurado",
                                    "El plan no tiene una tarifa reseller disponible.")
    return dict(fila), int(precio), origen


def validar_cantidad_periodos(cantidad_periodos):
    """Valida el concepto reutilizable por compras y futuras renovaciones."""
    if isinstance(cantidad_periodos, bool) or not isinstance(cantidad_periodos, int):
        raise ResellerPurchaseError(
            "cantidad_periodos_invalida",
            "La cantidad de períodos debe ser un entero positivo.",
        )
    if cantidad_periodos < 1:
        raise ResellerPurchaseError(
            "cantidad_periodos_invalida",
            "La cantidad de períodos debe ser mayor o igual a uno.",
        )
    if cantidad_periodos > MAX_CANTIDAD_PERIODOS:
        raise ResellerPurchaseError(
            "cantidad_periodos_excedida",
            f"La cantidad de perÃ­odos no puede superar {MAX_CANTIDAD_PERIODOS}.",
        )
    return cantidad_periodos


def validar_cantidad_unidades(cantidad_unidades, disponibilidad=None):
    """Valida unidades distintas; el tope siempre proviene del inventario real."""
    if isinstance(cantidad_unidades, bool) or not isinstance(cantidad_unidades, int):
        raise ResellerPurchaseError(
            "cantidad_unidades_invalida",
            "La cantidad de unidades debe ser un entero positivo.",
        )
    if cantidad_unidades < 1:
        raise ResellerPurchaseError(
            "cantidad_unidades_invalida",
            "La cantidad de unidades debe ser mayor o igual a uno.",
        )
    if disponibilidad is not None and cantidad_unidades > int(disponibilidad):
        raise ResellerPurchaseError(
            "cantidad_unidades_excedida",
            f"Solo hay {int(disponibilidad)} unidad(es) elegible(s) actualmente.",
        )
    return cantidad_unidades


def _unidades_elegibles_en_cursor(cursor, regla, limite=None):
    """Única fuente de verdad para selección y conteo de inventario elegible."""
    if regla["tipo_unidad"] == "cuenta":
        sql = """
            SELECT c.id cuenta_id, NULL perfil_id FROM nube_cuentas c
            WHERE lower(trim(c.plataforma))=lower(trim(?))
              AND COALESCE(c.modalidad,'cuenta_completa')='cuenta_completa'
              AND lower(COALESCE(c.estado,'disponible'))='disponible'
              AND trim(COALESCE(c.nombre_cliente,''))=''
              AND trim(COALESCE(c.fecha_entrega,''))=''
              AND NOT EXISTS (SELECT 1 FROM reseller_purchases rp
                WHERE rp.cuenta_id=c.id AND rp.estado_persistido='active')
            ORDER BY c.id
        """
    else:
        sql = """
            SELECT c.id cuenta_id, p.id perfil_id FROM nube_perfiles p
            JOIN nube_cuentas c ON c.id=p.cuenta_id
            WHERE lower(trim(c.plataforma))=lower(trim(?)) AND c.modalidad='perfiles'
              AND lower(COALESCE(p.estado,'disponible'))='disponible'
              AND lower(COALESCE(c.estado,'disponible')) NOT IN
                ('caida','bloqueada','retirada','papelera','garantia','reemplazada','no_disponible')
              AND trim(COALESCE(p.nombre_cliente,''))=''
              AND trim(COALESCE(p.fecha_entrega,''))=''
              AND NOT EXISTS (SELECT 1 FROM reseller_purchases rp
                WHERE rp.perfil_id=p.id AND rp.estado_persistido='active')
            ORDER BY p.id
        """
    if limite is not None:
        sql += " LIMIT ?"
        filas = cursor.execute(sql, (regla["plataforma"], int(limite))).fetchall()
    else:
        filas = cursor.execute(sql, (regla["plataforma"],)).fetchall()
    return [dict(fila) for fila in filas]


def _seleccionar_unidad_en_cursor(cursor, regla):
    unidades = _unidades_elegibles_en_cursor(cursor, regla, limite=1)
    fila = unidades[0] if unidades else None
    if not fila:
        raise ResellerPurchaseError("inventario_agotado", "No hay inventario elegible para este plan.")
    return fila


def previsualizar_compra_plan(revendedor_id, plan_id, cantidad_periodos=1,
                              cantidad_unidades=1, ahora=None):
    """Calcula una intención de compra sin reservar inventario ni escribir datos."""
    try:
        revendedor_id, plan_id = int(revendedor_id), int(plan_id)
    except (TypeError, ValueError) as error:
        raise ResellerPurchaseError("solicitud_invalida", "Plan no válido.") from error
    cantidad = validar_cantidad_periodos(cantidad_periodos)
    unidades_solicitadas = validar_cantidad_unidades(cantidad_unidades)
    momento = _momento_bogota(ahora)
    conn = _conectar()
    try:
        cursor = conn.cursor()
        plan = cursor.execute(
            "SELECT id, nombre producto, plan, visible, estado FROM productos WHERE id=?",
            (plan_id,),
        ).fetchone()
        if not plan or not int(plan["visible"] or 0):
            raise ResellerPurchaseError("plan_inexistente", "Plan no encontrado.")
        regla_fila = cursor.execute(
            "SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?", (plan_id,)
        ).fetchone()
        regla = dict(regla_fila) if regla_fila else None
        configuracion_inventario = bool(regla and regla.get("activo"))
        tipo_unidad = regla.get("tipo_unidad") if configuracion_inventario else None
        duracion_base = int(regla["duracion_dias"]) if configuracion_inventario else None
        precio_unitario = origen_precio = None
        try:
            _, precio_unitario, origen_precio = _resolver_precio_en_cursor(
                cursor, plan_id, revendedor_id, momento.date().isoformat())
        except ResellerPurchaseError as error:
            if error.codigo != "precio_reseller_no_configurado":
                raise
        disponibilidad_unidades = 0
        if configuracion_inventario:
            disponibilidad_unidades = len(_unidades_elegibles_en_cursor(cursor, regla))
            if disponibilidad_unidades:
                validar_cantidad_unidades(unidades_solicitadas, disponibilidad_unidades)
        disponible = disponibilidad_unidades > 0
        wallet = cursor.execute(
            "SELECT saldo FROM reseller_wallets WHERE revendedor_id=?", (revendedor_id,)
        ).fetchone()
        saldo = int(wallet["saldo"]) if wallet else 0
        precio_por_unidad = precio_unitario * cantidad if precio_unitario is not None else None
        precio_total = (precio_por_unidad * unidades_solicitadas
                        if precio_por_unidad is not None else None)
        duracion_total = duracion_base * cantidad if duracion_base is not None else None
        saldo_estimado = saldo - precio_total if precio_total is not None else None
        if not configuracion_inventario:
            estado_disponibilidad = "configuracion_pendiente"
        elif disponible:
            estado_disponibilidad = "disponible"
        else:
            estado_disponibilidad = "agotado"
        saldo_suficiente = bool(precio_total is not None and precio_total <= saldo)
        return {
            "producto": plan["producto"], "plan": plan["plan"],
            "tipo_unidad": tipo_unidad,
            "tipo_unidad_etiqueta": {"cuenta": "Cuenta completa", "perfil": "Perfil"}.get(tipo_unidad),
            "precio_unitario": precio_unitario,
            "precio_unitario_cop": wallets.formato_cop(precio_unitario) if precio_unitario is not None else None,
            "origen_precio": origen_precio,
            "duracion_base_dias": duracion_base,
            "cantidad_periodos": cantidad, "min_periodos": 1,
            "max_periodos": MAX_CANTIDAD_PERIODOS,
            "cantidad_unidades": unidades_solicitadas, "min_unidades": 1,
            "max_unidades": disponibilidad_unidades,
            "disponibilidad_unidades": disponibilidad_unidades,
            "duracion_total_dias": duracion_total,
            "precio_por_unidad": precio_por_unidad,
            "precio_por_unidad_cop": wallets.formato_cop(precio_por_unidad) if precio_por_unidad is not None else None,
            "precio_total": precio_total,
            "precio_total_cop": wallets.formato_cop(precio_total) if precio_total is not None else None,
            "saldo": saldo, "saldo_cop": wallets.formato_cop(saldo),
            "saldo_estimado": saldo_estimado,
            "saldo_estimado_cop": wallets.formato_cop(saldo_estimado) if saldo_estimado is not None else None,
            "saldo_suficiente": saldo_suficiente,
            "estado_disponibilidad": estado_disponibilidad,
            "disponibilidad": {"disponible": "Disponible", "agotado": "Agotado",
                                "configuracion_pendiente": "Configuración pendiente"}[estado_disponibilidad],
            "tarifa_configurada": precio_unitario is not None,
            "puede_prepararse": bool(precio_unitario is not None and configuracion_inventario
                                      and disponible and saldo_suficiente),
            "aviso_inventario": "La disponibilidad es una fotografía actual y no reserva inventario.",
        }
    finally:
        conn.close()


def previsualizar_carrito_reseller(revendedor_id, lineas, cart_intent_id=None, ahora=None):
    """Revalida un pedido completo sin reservar, debitar ni persistir información."""
    try:
        revendedor_id = int(revendedor_id)
    except (TypeError, ValueError) as error:
        raise ResellerPurchaseError("solicitud_invalida", "Revendedor no válido.") from error
    if not isinstance(lineas, list) or not lineas:
        raise ResellerPurchaseError("carrito_invalido", "El carrito debe contener al menos una línea.")
    if len(lineas) > 50:
        raise ResellerPurchaseError("carrito_invalido", "El carrito contiene demasiadas líneas.")
    consolidadas = {}
    for linea in lineas:
        if not isinstance(linea, dict) or set(linea) != {"plan_id", "cantidad_unidades", "cantidad_periodos"}:
            raise ResellerPurchaseError("payload_invalido", "Cada línea debe contener solo plan_id, cantidad_unidades y cantidad_periodos.")
        try:
            plan_id = int(linea["plan_id"])
        except (TypeError, ValueError) as error:
            raise ResellerPurchaseError("solicitud_invalida", "Plan no válido.") from error
        periodos = validar_cantidad_periodos(linea["cantidad_periodos"])
        unidades = validar_cantidad_unidades(linea["cantidad_unidades"])
        clave = (plan_id, periodos)
        consolidadas[clave] = consolidadas.get(clave, 0) + unidades
    previews = []
    for (plan_id, periodos), unidades in consolidadas.items():
        preview = previsualizar_compra_plan(
            revendedor_id, plan_id, periodos, unidades, ahora=ahora)
        previews.append({"plan_id": plan_id, **preview})
    unidades_por_plan = {}
    disponibilidad_por_plan = {}
    for linea in previews:
        unidades_por_plan[linea["plan_id"]] = (
            unidades_por_plan.get(linea["plan_id"], 0) + linea["cantidad_unidades"])
        disponibilidad_por_plan[linea["plan_id"]] = linea["disponibilidad_unidades"]
    for plan_id, unidades in unidades_por_plan.items():
        disponibilidad = disponibilidad_por_plan[plan_id]
        if disponibilidad:
            validar_cantidad_unidades(unidades, disponibilidad)
    total = sum(linea["precio_total"] for linea in previews
                if linea["precio_total"] is not None)
    saldo = previews[0]["saldo"] if previews else 0
    total_unidades = sum(linea["cantidad_unidades"] for linea in previews)
    saldo_estimado = saldo - total
    listo = all(linea["tarifa_configurada"] and
                linea["estado_disponibilidad"] == "disponible" for linea in previews)
    return {
        "cart_intent_id": str(cart_intent_id or ""),
        "lineas": previews,
        "total_productos": len(previews),
        "total_unidades": total_unidades,
        "total": total,
        "total_cop": wallets.formato_cop(total),
        "saldo": saldo,
        "saldo_cop": wallets.formato_cop(saldo),
        "saldo_estimado": saldo_estimado,
        "saldo_estimado_cop": wallets.formato_cop(saldo_estimado),
        "saldo_suficiente": total <= saldo,
        "puede_prepararse": bool(listo and total <= saldo),
    }


def _resultado_compra(cursor, purchase_id, duplicado=False):
    fila = cursor.execute("""
        SELECT rp.id purchase_id, rp.plan_id, p.nombre producto, p.plan,
               rp.tipo_unidad, rp.fecha_activacion, rp.fecha_vencimiento,
               rp.precio_unitario_pagado precio_unitario,
               rp.cantidad_periodos, rp.precio_pagado precio_total,
               rp.duracion_base_dias, rp.dias_contratados duracion_total_dias,
               rp.precio_pagado, rp.estado_persistido estado,
               rp.operacion_origen, rp.compra_anterior_id,
               rp.wallet_transaction_id,
               wt.saldo_posterior saldo_restante
        FROM reseller_purchases rp JOIN productos p ON p.id=rp.plan_id
        JOIN reseller_wallet_transactions wt ON wt.id=rp.wallet_transaction_id
        WHERE rp.id=?
    """, (purchase_id,)).fetchone()
    if not fila:
        raise ResellerPurchaseError("error_integridad", "La compra no pudo recuperarse de forma segura.")
    resultado = dict(fila); resultado["duplicado"] = duplicado
    return resultado


def _cargar_contexto_recovery(cursor, purchase_id, revendedor_id, momento,
                              resolver_comercial=True):
    """Carga y revalida exclusivamente la unidad de la compra cortada."""
    fila = cursor.execute("""SELECT rp.*, r.nombre reseller_nombre,
        r.telefono reseller_telefono, r.estado reseller_estado,
        p.nombre producto, p.plan plan_nombre
        FROM reseller_purchases rp
        JOIN revendedores r ON r.id=rp.revendedor_id
        JOIN productos p ON p.id=rp.plan_id
        WHERE rp.id=? AND rp.revendedor_id=?""",
        (int(purchase_id), int(revendedor_id))).fetchone()
    if not fila:
        raise ResellerPurchaseError("purchase_inexistente", "Adquisición no encontrada.")
    purchase = dict(fila)
    if not purchase.get("cortada_at") or purchase.get("estado_persistido") != "cut":
        raise ResellerPurchaseError("purchase_no_cortada", "Este servicio no está cortado.")
    if str(purchase.get("reseller_estado") or "").lower() != "activo":
        raise ResellerPurchaseError("reseller_inactivo", "El revendedor no está activo.")
    regla_fila = cursor.execute(
        "SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?",
        (purchase["plan_id"],)).fetchone()
    if not regla_fila:
        raise ResellerPurchaseError("regla_inexistente", "El plan no tiene regla de inventario.")
    regla = dict(regla_fila)
    if not regla["activo"]:
        raise ResellerPurchaseError("regla_inactiva", "La regla de inventario está inactiva.")
    if regla["tipo_unidad"] != purchase["tipo_unidad"]:
        raise ResellerPurchaseError("modalidad_incompatible", "La modalidad actual del plan no corresponde a la unidad original.")
    cuenta_fila = cursor.execute("SELECT * FROM nube_cuentas WHERE id=?",
                                 (purchase["cuenta_id"],)).fetchone()
    if not cuenta_fila:
        raise ResellerPurchaseError("unidad_inexistente", MENSAJES_DISPONIBILIDAD["NOT_FOUND"])
    cuenta = dict(cuenta_fila)
    if str(cuenta.get("plataforma") or "").strip().casefold() != str(regla["plataforma"]).strip().casefold():
        raise ResellerPurchaseError("plataforma_incompatible", "La plataforma de la unidad original ya no corresponde al plan.")
    estados_bloqueados = {
        "caida": "DOWN", "bloqueada": "BLOCKED", "retirada": "RETIRED",
        "reemplazada": "REPLACED", "garantia": "WARRANTY", "papelera": "TRASHED",
    }
    perfil = None
    if purchase["tipo_unidad"] == "cuenta":
        unidad = cuenta
        modalidad_ok = (purchase.get("perfil_id") is None and
                        (cuenta.get("modalidad") or "cuenta_completa") == "cuenta_completa")
    else:
        perfil_fila = cursor.execute("SELECT * FROM nube_perfiles WHERE id=? AND cuenta_id=?",
                                     (purchase.get("perfil_id"), purchase["cuenta_id"])).fetchone()
        if not perfil_fila:
            raise ResellerPurchaseError("unidad_inexistente", MENSAJES_DISPONIBILIDAD["NOT_FOUND"])
        perfil = dict(perfil_fila); unidad = perfil
        modalidad_ok = cuenta.get("modalidad") == "perfiles"
    if not modalidad_ok:
        raise ResellerPurchaseError("modalidad_incompatible", "La modalidad de la unidad original cambió.")
    if purchase["tipo_unidad"] == "perfil" and str(cuenta.get("estado") or "").strip().lower() not in {
            "", "disponible", "activa", "activo"}:
        raise ResellerPurchaseError("unidad_no_disponible", "La cuenta madre no está operativamente disponible.")
    estados = [str(unidad.get("estado") or "").strip().lower(),
               str(cuenta.get("estado") or "").strip().lower()]
    codigo_bloqueo = next((codigo for estado, codigo in estados_bloqueados.items()
                           if estado in estados), None)
    if codigo_bloqueo:
        raise ResellerPurchaseError("unidad_no_disponible", MENSAJES_DISPONIBILIDAD[codigo_bloqueo])
    asignada = any(unidad.get(k) not in (None, "", 0) for k in
                   ("cliente_id", "nombre_cliente", "telefono", "fecha_entrega",
                    "dias_cuenta", "fecha_vencimiento"))
    activa = cursor.execute("""SELECT 1 FROM reseller_purchases
        WHERE id<>? AND estado_persistido='active' AND cortada_at IS NULL
          AND ((?='cuenta' AND tipo_unidad='cuenta' AND cuenta_id=? AND perfil_id IS NULL)
            OR (?='perfil' AND tipo_unidad='perfil' AND perfil_id=? AND cuenta_id=?)) LIMIT 1""",
        (purchase["id"], purchase["tipo_unidad"], purchase["cuenta_id"],
         purchase["tipo_unidad"], purchase.get("perfil_id"), purchase["cuenta_id"])).fetchone()
    if asignada or activa or str(unidad.get("estado") or "").strip().lower() != "disponible":
        raise ResellerPurchaseError("unidad_no_disponible", MENSAJES_DISPONIBILIDAD["SOLD"] if asignada or activa else MENSAJES_DISPONIBILIDAD["UNAVAILABLE"])
    if purchase["tipo_unidad"] == "perfil" and str(cuenta.get("estado") or "").strip().lower() in {"", "disponible"}:
        # Una madre de perfiles puede estar activa; "disponible" también es apto.
        pass
    contexto = {"purchase": purchase, "regla": regla, "cuenta": cuenta,
                "perfil": perfil, "precio_unitario": None, "origen_precio": None}
    if resolver_comercial:
        try:
            _, precio, origen = _resolver_precio_en_cursor(
                cursor, purchase["plan_id"], revendedor_id, momento.date().isoformat())
        except ResellerPurchaseError as error:
            if error.codigo == "precio_reseller_no_configurado":
                raise ResellerPurchaseError(error.codigo, "Este servicio no tiene una tarifa reseller disponible actualmente.") from error
            raise
        contexto.update(precio_unitario=precio, origen_precio=origen)
    return contexto


def previsualizar_recovery(purchase_id, revendedor_id, cantidad_periodos=1, ahora=None):
    cantidad = validar_cantidad_periodos(cantidad_periodos)
    momento = _momento_bogota(ahora)
    conn = _conectar()
    try:
        cursor = conn.cursor()
        contexto = _cargar_contexto_recovery(cursor, purchase_id, revendedor_id, momento)
        purchase, regla = contexto["purchase"], contexto["regla"]
        total_dias = int(regla["duracion_dias"]) * cantidad
        precio_total = contexto["precio_unitario"] * cantidad
        vencimiento = momento + timedelta(days=total_dias)
        wallet = wallets.asegurar_wallet(revendedor_id, cursor)
        return {"recoverable": True, "purchase_id": purchase["id"],
                "producto": purchase["producto"], "plan": purchase["plan_nombre"],
                "tipo_unidad": purchase["tipo_unidad"],
                "precio_unitario": contexto["precio_unitario"],
                "precio_unitario_cop": wallets.formato_cop(contexto["precio_unitario"]),
                "duracion_base_dias": int(regla["duracion_dias"]),
                "cantidad_periodos": cantidad, "duracion_total_dias": total_dias,
                "precio_total": precio_total, "precio_total_cop": wallets.formato_cop(precio_total),
                "saldo": int(wallet["saldo"]), "saldo_cop": wallets.formato_cop(wallet["saldo"]),
                "nueva_vigencia_estimada": vencimiento.isoformat(),
                "min_periodos": 1, "max_periodos": MAX_CANTIDAD_PERIODOS}
    finally:
        conn.close()


def recuperar_purchase_reseller(revendedor_id, purchase_anterior_id, cantidad_periodos,
                                idempotency_key, ahora=None):
    try:
        revendedor_id, purchase_anterior_id = int(revendedor_id), int(purchase_anterior_id)
    except (TypeError, ValueError) as error:
        raise ResellerPurchaseError("solicitud_invalida", "Adquisición no válida.") from error
    cantidad = validar_cantidad_periodos(cantidad_periodos)
    clave = str(idempotency_key or "").strip()
    if not clave or len(clave) > 180:
        raise ResellerPurchaseError("idempotencia_invalida", "La idempotency key no es válida.")
    momento = _momento_bogota(ahora)
    huella = _huella_operacion(revendedor_id, "recovery", purchase_anterior_id,
                               {"cantidad_periodos": cantidad})
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); cursor = conn.cursor()
        previa = cursor.execute("SELECT * FROM reseller_purchase_operations WHERE idempotency_key=?",
                                (clave,)).fetchone()
        if previa:
            if previa["request_fingerprint"] != huella:
                raise ResellerPurchaseError("idempotencia_incompatible", "La idempotency key ya pertenece a otra operación.")
            if previa["estado"] != "completed" or not previa["purchase_id"]:
                raise ResellerPurchaseError("operacion_incompleta", "La operación previa no está completa.")
            resultado = _resultado_compra(cursor, previa["purchase_id"], True); conn.commit(); return resultado
        contexto = _cargar_contexto_recovery(cursor, purchase_anterior_id, revendedor_id, momento)
        purchase, regla = contexto["purchase"], contexto["regla"]
        cursor.execute("""INSERT INTO reseller_purchase_operations
            (idempotency_key,revendedor_id,tipo,estado,request_fingerprint)
            VALUES (?,?,'recovery','processing',?)""", (clave, revendedor_id, huella))
        operacion_id = cursor.lastrowid
        duracion_base = int(regla["duracion_dias"]); duracion_total = duracion_base * cantidad
        precio_total = contexto["precio_unitario"] * cantidad
        vencimiento = momento + timedelta(days=duracion_total)
        momento_iso, vencimiento_iso = momento.isoformat(), vencimiento.isoformat()
        etiqueta = f"Reseller #{revendedor_id} - {purchase['reseller_nombre']}"[:160]
        cliente_id = database._obtener_o_crear_cliente_nube(cursor, etiqueta, purchase.get("reseller_telefono") or "")
        tabla = "nube_cuentas" if purchase["tipo_unidad"] == "cuenta" else "nube_perfiles"
        unidad_id = purchase["cuenta_id"] if purchase["tipo_unidad"] == "cuenta" else purchase["perfil_id"]
        cursor.execute(f"""UPDATE {tabla} SET cliente_id=?,nombre_cliente=?,telefono=?,fecha_entrega=?,
            dias_cuenta=?,fecha_vencimiento=?,estado='activa',fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=? AND lower(COALESCE(estado,'disponible'))='disponible'
              AND trim(COALESCE(nombre_cliente,''))='' AND cliente_id IS NULL""",
            (cliente_id, etiqueta, purchase.get("reseller_telefono") or "", momento.date().isoformat(),
             duracion_total, vencimiento.date().isoformat(), unidad_id))
        if cursor.rowcount != 1:
            raise ResellerPurchaseError("unidad_no_disponible", "Esta unidad ya fue asignada a otro cliente.")
        cursor.execute("""INSERT INTO reseller_purchases
            (revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,compra_anterior_id,
             fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,precio_pagado,
             precio_unitario_pagado,cantidad_periodos,duracion_base_dias,estado_persistido,no_renovar,cortada_at)
            VALUES (?,?,?,?,?,'recovery',?,?,?,?,?,?,?,?,?,'active',0,NULL)""",
            (revendedor_id,purchase["plan_id"],purchase["cuenta_id"],purchase.get("perfil_id"),
             purchase["tipo_unidad"],purchase["id"],momento_iso,momento_iso,vencimiento_iso,
             duracion_total,precio_total,contexto["precio_unitario"],cantidad,duracion_base))
        nueva_id = cursor.lastrowid
        try:
            movimiento = wallets.apply_wallet_transaction(
                revendedor_id, "recovery", precio_total,
                f"Recuperación reseller: {purchase['producto']} - {purchase['plan_nombre']}",
                origen="reseller_recovery", actor=f"reseller:{revendedor_id}",
                referencia=f"reseller_recovery:{nueva_id}",
                idempotency_key=f"reseller_recovery:{clave}", cursor=cursor)
        except ValueError as error:
            if "Saldo insuficiente" in str(error):
                raise ResellerPurchaseError("saldo_insuficiente", "Saldo insuficiente para recuperar este servicio.") from error
            raise
        cursor.execute("UPDATE reseller_purchases SET wallet_transaction_id=? WHERE id=?",
                       (movimiento["id"], nueva_id))
        datos = {"purchase_anterior": purchase["id"], "precio_unitario": contexto["precio_unitario"],
                 "cantidad_periodos": cantidad, "precio_total": precio_total,
                 "duracion_base_dias": duracion_base, "duracion_total_dias": duracion_total,
                 "fecha_activacion": momento_iso, "fecha_vencimiento": vencimiento_iso,
                 "tipo_unidad": purchase["tipo_unidad"], "origen_precio": contexto["origen_precio"]}
        _validar_metadata_publica(datos)
        cursor.execute("""INSERT INTO reseller_purchase_events
            (purchase_id,tipo,fecha,precio_aplicado,vencimiento_nuevo,wallet_transaction_id,
             actor_tipo,actor_id,datos_publicos_json,idempotency_key)
            VALUES (?,'recovery',?,?,?,?,'reseller',?,?,?)""",
            (nueva_id,momento_iso,contexto["precio_unitario"],vencimiento_iso,movimiento["id"],
             revendedor_id,json.dumps(datos,ensure_ascii=False,sort_keys=True),f"recovery:{clave}"))
        cursor.execute("""INSERT INTO nube_movimientos
            (cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo,cliente_nombre)
            VALUES (?,'recuperacion_reseller',?,'disponible','activa',?)""",
            (purchase["cuenta_id"],f"Unidad {purchase['tipo_unidad']} reasignada por recuperación reseller",etiqueta))
        cursor.execute("""UPDATE reseller_purchase_operations SET purchase_id=?,wallet_transaction_id=?,
            estado='completed',completed_at=? WHERE id=? AND estado='processing'""",
            (nueva_id,movimiento["id"],momento_iso,operacion_id))
        resultado = _resultado_compra(cursor,nueva_id); conn.commit(); return resultado
    except ResellerPurchaseError:
        conn.rollback(); raise
    except sqlite3.IntegrityError as error:
        conn.rollback(); raise ResellerPurchaseError("error_integridad", "La recuperación no pudo completarse de forma íntegra.") from error
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def comprar_plan_reseller(revendedor_id, plan_id, idempotency_key, ahora=None,
                          cantidad_periodos=1):
    """Motor interno atómico; deliberadamente no conectado a una ruta HTTP.

    El default de un período conserva las llamadas internas de Fases 1/2.
    """
    try:
        revendedor_id, plan_id = int(revendedor_id), int(plan_id)
    except (TypeError, ValueError) as error:
        raise ResellerPurchaseError("solicitud_invalida", "Reseller o plan no válido.") from error
    clave = str(idempotency_key or "").strip()
    if not clave or len(clave) > 180:
        raise ResellerPurchaseError("idempotencia_invalida", "La idempotency key no es válida.")
    cantidad_periodos = validar_cantidad_periodos(cantidad_periodos)
    momento = ahora or datetime.now(ZONA_HORARIA)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_HORARIA)
    momento = momento.astimezone(ZONA_HORARIA)
    huella = _huella_operacion(
        revendedor_id, "purchase", None,
        {"plan_id": plan_id, "cantidad_periodos": cantidad_periodos},
    )
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); cursor = conn.cursor()
        previa = cursor.execute("SELECT * FROM reseller_purchase_operations WHERE idempotency_key=?", (clave,)).fetchone()
        if previa:
            if previa["request_fingerprint"] != huella:
                raise ResellerPurchaseError("idempotencia_incompatible", "La idempotency key ya pertenece a otra operación.")
            if previa["estado"] != "completed" or not previa["purchase_id"]:
                raise ResellerPurchaseError("operacion_incompleta", "La operación previa no está completa.")
            resultado = _resultado_compra(cursor, previa["purchase_id"], True); conn.commit(); return resultado
        revendedor = cursor.execute("SELECT id,nombre,telefono,estado FROM revendedores WHERE id=?", (revendedor_id,)).fetchone()
        if not revendedor:
            raise ResellerPurchaseError("reseller_inexistente", "Revendedor no encontrado.")
        if (revendedor["estado"] or "").lower() != "activo":
            raise ResellerPurchaseError("reseller_inactivo", "El revendedor no está activo.")
        producto, precio_unitario, origen_precio = _resolver_precio_en_cursor(cursor, plan_id, revendedor_id, momento.date().isoformat())
        regla = cursor.execute("SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?", (plan_id,)).fetchone()
        if not regla:
            raise ResellerPurchaseError("regla_inexistente", "El plan no tiene regla de inventario.")
        if not regla["activo"]:
            raise ResellerPurchaseError("regla_inactiva", "La regla de inventario está inactiva.")
        unidad = _seleccionar_unidad_en_cursor(cursor, regla)
        cursor.execute("INSERT INTO reseller_purchase_operations (idempotency_key,revendedor_id,tipo,estado,request_fingerprint) VALUES (?,?,'purchase','processing',?)", (clave, revendedor_id, huella))
        operacion_id = cursor.lastrowid
        duracion_base_dias = int(regla["duracion_dias"])
        duracion_total_dias = duracion_base_dias * cantidad_periodos
        precio_total = precio_unitario * cantidad_periodos
        vencimiento = momento + timedelta(days=duracion_total_dias)
        compra_iso, activacion_iso, vencimiento_iso = momento.isoformat(), momento.isoformat(), vencimiento.isoformat()
        etiqueta = f"Reseller #{revendedor_id} - {revendedor['nombre']}"[:160]
        cliente_id = database._obtener_o_crear_cliente_nube(cursor, etiqueta, revendedor["telefono"] or "")
        tabla = "nube_cuentas" if regla["tipo_unidad"] == "cuenta" else "nube_perfiles"
        unidad_id = unidad["cuenta_id"] if regla["tipo_unidad"] == "cuenta" else unidad["perfil_id"]
        cursor.execute(f"""UPDATE {tabla} SET cliente_id=?,nombre_cliente=?,telefono=?,fecha_entrega=?,
            dias_cuenta=?,fecha_vencimiento=?,estado='activa',fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=? AND estado='disponible' AND trim(COALESCE(nombre_cliente,''))=''""",
            (cliente_id, etiqueta, revendedor["telefono"] or "", momento.date().isoformat(),
             duracion_total_dias, vencimiento.date().isoformat(), unidad_id))
        if cursor.rowcount != 1:
            raise ResellerPurchaseError("unidad_no_disponible", "La unidad dejó de estar disponible.")
        cursor.execute("""INSERT INTO reseller_purchases
            (revendedor_id,plan_id,cuenta_id,perfil_id,tipo_unidad,operacion_origen,
             fecha_compra,fecha_activacion,fecha_vencimiento,dias_contratados,precio_pagado,
             precio_unitario_pagado,cantidad_periodos,duracion_base_dias,estado_persistido)
            VALUES (?,?,?,?,?,'purchase',?,?,?,?,?,?,?,?,?)""",
            (revendedor_id,plan_id,unidad["cuenta_id"],unidad["perfil_id"],regla["tipo_unidad"],
             compra_iso,activacion_iso,vencimiento_iso,duracion_total_dias,precio_total,
             precio_unitario,cantidad_periodos,duracion_base_dias,ESTADO_PERSISTIDO_COMPRA))
        purchase_id = cursor.lastrowid
        try:
            movimiento = wallets.apply_wallet_transaction(revendedor_id,"purchase",precio_total,
                f"Compra reseller: {producto['nombre']} - {producto['plan']}", origen="reseller_purchase",
                actor=f"reseller:{revendedor_id}",referencia=f"reseller_purchase:{purchase_id}",
                idempotency_key=f"reseller_purchase:{clave}",cursor=cursor)
        except ValueError as error:
            if "Saldo insuficiente" in str(error):
                raise ResellerPurchaseError("saldo_insuficiente", "Saldo insuficiente para completar la compra.") from error
            raise
        cursor.execute("UPDATE reseller_purchases SET wallet_transaction_id=? WHERE id=?", (movimiento["id"],purchase_id))
        datos = {
            "producto": producto["nombre"], "plan": producto["plan"],
            "tipo_unidad": regla["tipo_unidad"], "origen_precio": origen_precio,
            "precio_unitario": precio_unitario,
            "cantidad_periodos": cantidad_periodos,
            "precio_total": precio_total,
            "duracion_base_dias": duracion_base_dias,
            "duracion_total_dias": duracion_total_dias,
            "fecha_activacion": activacion_iso,
            "fecha_vencimiento": vencimiento_iso,
        }
        _validar_metadata_publica(datos)
        cursor.execute("""INSERT INTO reseller_purchase_events
            (purchase_id,tipo,fecha,precio_aplicado,vencimiento_nuevo,wallet_transaction_id,
             actor_tipo,actor_id,datos_publicos_json,idempotency_key)
            VALUES (?,'purchase',?,?,?,?,'reseller',?,?,?)""",
            (purchase_id,compra_iso,precio_total,vencimiento_iso,movimiento["id"],revendedor_id,
             json.dumps(datos,ensure_ascii=False,sort_keys=True),f"purchase:{clave}"))
        cursor.execute("""INSERT INTO nube_movimientos
            (cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo,cliente_nombre)
            VALUES (?,?,?,'disponible','activa',?)""",
            (unidad["cuenta_id"],"asignacion_reseller_"+regla["tipo_unidad"],"Unidad asignada por compra reseller",etiqueta))
        cursor.execute("""UPDATE reseller_purchase_operations SET purchase_id=?,wallet_transaction_id=?,
            estado='completed',completed_at=? WHERE id=? AND estado='processing'""",
            (purchase_id,movimiento["id"],compra_iso,operacion_id))
        resultado = _resultado_compra(cursor,purchase_id); conn.commit(); return resultado
    except ResellerPurchaseError:
        conn.rollback(); raise
    except sqlite3.IntegrityError as error:
        conn.rollback(); raise ResellerPurchaseError("error_integridad","La compra no pudo completarse de forma íntegra.") from error
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def _momento_bogota(ahora=None):
    momento = ahora or datetime.now(ZONA_HORARIA)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_HORARIA)
    return momento.astimezone(ZONA_HORARIA)


def _cargar_contexto_renovacion(cursor, purchase_id, revendedor_id, momento,
                                resolver_comercial=True):
    purchase = cursor.execute("""SELECT rp.*, r.nombre AS reseller_nombre,
        r.estado AS reseller_estado, p.nombre AS producto, p.plan AS plan_nombre
        FROM reseller_purchases rp
        JOIN revendedores r ON r.id=rp.revendedor_id
        JOIN productos p ON p.id=rp.plan_id
        WHERE rp.id=? AND rp.revendedor_id=?""",
        (int(purchase_id), int(revendedor_id))).fetchone()
    if not purchase:
        raise ResellerPurchaseError("purchase_inexistente", "AdquisiciÃ³n no encontrada.")
    purchase = dict(purchase)
    if purchase.get("cortada_at") or purchase.get("estado_persistido") != "active":
        raise ResellerPurchaseError("purchase_cortada", "Este servicio ya no admite renovaciÃ³n normal.")
    if str(purchase.get("reseller_estado") or "").lower() != "activo":
        raise ResellerPurchaseError("reseller_inactivo", "El revendedor no estÃ¡ activo.")
    regla = cursor.execute("SELECT * FROM reseller_plan_inventory_rules WHERE plan_id=?",
                           (purchase["plan_id"],)).fetchone()
    if not regla:
        raise ResellerPurchaseError("regla_inexistente", "El plan no tiene regla de inventario.")
    regla = dict(regla)
    if not regla["activo"]:
        raise ResellerPurchaseError("regla_inactiva", "La regla de inventario estÃ¡ inactiva.")
    if regla["tipo_unidad"] != purchase["tipo_unidad"]:
        raise ResellerPurchaseError("modalidad_incompatible", "La modalidad del plan ya no corresponde al servicio.")
    cuenta = cursor.execute("SELECT * FROM nube_cuentas WHERE id=?", (purchase["cuenta_id"],)).fetchone()
    if not cuenta:
        raise ResellerPurchaseError("unidad_inexistente", "La unidad asignada ya no existe.")
    cuenta = dict(cuenta)
    esperado = f"Reseller #{int(revendedor_id)} - {purchase['reseller_nombre']}"[:160]
    if str(cuenta.get("estado") or "").strip().lower() in ESTADOS_UNIDAD_INCOMPATIBLES:
        raise ResellerPurchaseError("unidad_incompatible", "La cuenta asignada no estÃ¡ operativamente disponible.")
    perfil = None
    if purchase["tipo_unidad"] == "cuenta":
        coherente = (purchase.get("perfil_id") is None
                     and (cuenta.get("modalidad") or "cuenta_completa") == "cuenta_completa"
                     and cuenta.get("nombre_cliente") == esperado)
    else:
        perfil_fila = cursor.execute("SELECT * FROM nube_perfiles WHERE id=? AND cuenta_id=?",
                                     (purchase.get("perfil_id"), purchase["cuenta_id"])).fetchone()
        perfil = dict(perfil_fila) if perfil_fila else None
        coherente = bool(perfil and cuenta.get("modalidad") == "perfiles"
                         and perfil.get("nombre_cliente") == esperado
                         and str(perfil.get("estado") or "").strip().lower()
                         not in ESTADOS_UNIDAD_INCOMPATIBLES)
    if not coherente:
        raise ResellerPurchaseError("unidad_reasignada", "La unidad ya no corresponde a esta adquisiciÃ³n.")
    contexto = {"purchase": purchase, "regla": regla, "cuenta": cuenta,
                "perfil": perfil, "precio_unitario": None, "origen_precio": None}
    if resolver_comercial:
        _, precio, origen = _resolver_precio_en_cursor(
            cursor, purchase["plan_id"], revendedor_id, momento.date().isoformat())
        contexto.update(precio_unitario=precio, origen_precio=origen)
    return contexto


def puede_renovarse(purchase, unidad_real=None, regla=None):
    """PolÃ­tica pura complementaria; la carga transaccional valida ownership y unidad real."""
    if not purchase or purchase.get("cortada_at") or purchase.get("estado_persistido") != "active":
        return False
    if regla is not None and (not regla.get("activo") or regla.get("tipo_unidad") != purchase.get("tipo_unidad")):
        return False
    if unidad_real is not None and str(unidad_real.get("estado") or "").lower() in ESTADOS_UNIDAD_INCOMPATIBLES:
        return False
    return True


def previsualizar_renovacion(purchase_id, revendedor_id, cantidad_periodos=1, ahora=None):
    cantidad = validar_cantidad_periodos(cantidad_periodos)
    momento = _momento_bogota(ahora)
    conn = _conectar()
    try:
        cursor = conn.cursor()
        contexto = _cargar_contexto_renovacion(cursor, purchase_id, revendedor_id, momento)
        purchase, regla = contexto["purchase"], contexto["regla"]
        anterior = datetime.fromisoformat(purchase["fecha_vencimiento"])
        if anterior.tzinfo is None:
            anterior = anterior.replace(tzinfo=ZONA_HORARIA)
        base = anterior if anterior > momento else momento
        total_dias = int(regla["duracion_dias"]) * cantidad
        nuevo = base + timedelta(days=total_dias)
        wallet = wallets.asegurar_wallet(revendedor_id, cursor)
        return {
            "renovable": True, "purchase_id": int(purchase_id),
            "producto": purchase["producto"], "plan": purchase["plan_nombre"],
            "fecha_vencimiento": purchase["fecha_vencimiento"],
            "precio_unitario": contexto["precio_unitario"],
            "precio_unitario_cop": wallets.formato_cop(contexto["precio_unitario"]),
            "duracion_base_dias": int(regla["duracion_dias"]),
            "cantidad_periodos": cantidad, "duracion_total_dias": total_dias,
            "precio_total": contexto["precio_unitario"] * cantidad,
            "precio_total_cop": wallets.formato_cop(contexto["precio_unitario"] * cantidad),
            "nuevo_vencimiento_estimado": nuevo.isoformat(), "saldo": int(wallet["saldo"]),
            "saldo_cop": wallets.formato_cop(wallet["saldo"]), "min_periodos": 1,
            "max_periodos": MAX_CANTIDAD_PERIODOS,
        }
    finally:
        conn.close()


def _resultado_renovacion(cursor, operacion, duplicado=False):
    fila = cursor.execute("""SELECT rp.id purchase_id, rp.fecha_vencimiento,
        o.wallet_transaction_id, wt.monto precio_total, wt.saldo_posterior saldo_restante,
        e.datos_publicos_json FROM reseller_purchase_operations o
        JOIN reseller_purchases rp ON rp.id=o.purchase_id
        JOIN reseller_wallet_transactions wt ON wt.id=o.wallet_transaction_id
        JOIN reseller_purchase_events e ON e.purchase_id=o.purchase_id
          AND e.idempotency_key='renewal:' || o.idempotency_key
        WHERE o.id=?""", (operacion["id"],)).fetchone()
    if not fila:
        raise ResellerPurchaseError("error_integridad", "La renovaciÃ³n no pudo recuperarse.")
    resultado = dict(fila)
    resultado.update(json.loads(resultado.pop("datos_publicos_json")))
    resultado["precio_total_cop"] = wallets.formato_cop(resultado["precio_total"])
    resultado["duplicado"] = duplicado
    return resultado


def renovar_purchase_reseller(revendedor_id, purchase_id, cantidad_periodos,
                              idempotency_key, ahora=None):
    try:
        revendedor_id, purchase_id = int(revendedor_id), int(purchase_id)
    except (TypeError, ValueError) as error:
        raise ResellerPurchaseError("solicitud_invalida", "AdquisiciÃ³n no vÃ¡lida.") from error
    cantidad = validar_cantidad_periodos(cantidad_periodos)
    clave = str(idempotency_key or "").strip()
    if not clave or len(clave) > 180:
        raise ResellerPurchaseError("idempotencia_invalida", "La idempotency key no es vÃ¡lida.")
    momento = _momento_bogota(ahora)
    huella = _huella_operacion(revendedor_id, "renewal", purchase_id,
                               {"cantidad_periodos": cantidad})
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); cursor = conn.cursor()
        previa = cursor.execute("SELECT * FROM reseller_purchase_operations WHERE idempotency_key=?",
                                (clave,)).fetchone()
        if previa:
            if previa["request_fingerprint"] != huella:
                raise ResellerPurchaseError("idempotencia_incompatible", "La idempotency key ya pertenece a otra operaciÃ³n.")
            if previa["estado"] != "completed":
                raise ResellerPurchaseError("operacion_incompleta", "La operaciÃ³n previa no estÃ¡ completa.")
            resultado = _resultado_renovacion(cursor, dict(previa), True); conn.commit(); return resultado
        contexto = _cargar_contexto_renovacion(cursor, purchase_id, revendedor_id, momento)
        purchase, regla = contexto["purchase"], contexto["regla"]
        cursor.execute("""INSERT INTO reseller_purchase_operations
            (idempotency_key,purchase_id,revendedor_id,tipo,estado,request_fingerprint)
            VALUES (?,?,?,'renewal','processing',?)""", (clave,purchase_id,revendedor_id,huella))
        operacion_id = cursor.lastrowid
        anterior = datetime.fromisoformat(purchase["fecha_vencimiento"])
        if anterior.tzinfo is None: anterior = anterior.replace(tzinfo=ZONA_HORARIA)
        anterior = anterior.astimezone(ZONA_HORARIA)
        base = anterior if anterior > momento else momento
        duracion_base = int(regla["duracion_dias"]); duracion_total = duracion_base * cantidad
        precio_total = contexto["precio_unitario"] * cantidad
        nuevo = base + timedelta(days=duracion_total); nuevo_iso = nuevo.isoformat()
        try:
            movimiento = wallets.apply_wallet_transaction(
                revendedor_id, "renewal", precio_total,
                f"RenovaciÃ³n reseller: {purchase['producto']} - {purchase['plan_nombre']}",
                origen="reseller_renewal", actor=f"reseller:{revendedor_id}",
                referencia=f"reseller_renewal:{purchase_id}:{operacion_id}",
                idempotency_key=f"reseller_renewal:{clave}", cursor=cursor)
        except ValueError as error:
            if "Saldo insuficiente" in str(error):
                raise ResellerPurchaseError("saldo_insuficiente", "Saldo insuficiente para renovar este servicio.") from error
            raise
        tabla = "nube_cuentas" if purchase["tipo_unidad"] == "cuenta" else "nube_perfiles"
        unidad_id = purchase["cuenta_id"] if purchase["tipo_unidad"] == "cuenta" else purchase["perfil_id"]
        cursor.execute(f"""UPDATE {tabla} SET fecha_vencimiento=?,dias_cuenta=?,estado='activa',
            fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?""",
            (nuevo.date().isoformat(), duracion_total, unidad_id))
        if cursor.rowcount != 1:
            raise ResellerPurchaseError("unidad_inexistente", "La unidad asignada ya no existe.")
        cursor.execute("""UPDATE reseller_purchases SET fecha_vencimiento=?,no_renovar=0,
            no_renovar_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (nuevo_iso,purchase_id))
        datos = {"producto": purchase["producto"], "plan": purchase["plan_nombre"],
                 "origen_precio": contexto["origen_precio"],
                 "precio_unitario": contexto["precio_unitario"], "cantidad_periodos": cantidad,
                 "precio_total": precio_total, "duracion_base_dias": duracion_base,
                 "duracion_total_dias": duracion_total,
                 "vencimiento_anterior": purchase["fecha_vencimiento"],
                 "vencimiento_nuevo": nuevo_iso, "no_renovar_limpiado": bool(purchase["no_renovar"])}
        _validar_metadata_publica(datos)
        cursor.execute("""INSERT INTO reseller_purchase_events
            (purchase_id,tipo,fecha,precio_aplicado,vencimiento_anterior,vencimiento_nuevo,
             wallet_transaction_id,actor_tipo,actor_id,datos_publicos_json,idempotency_key)
            VALUES (?,'renewal',?,?,?,?,?,'reseller',?,?,?)""",
            (purchase_id,momento.isoformat(),contexto["precio_unitario"],purchase["fecha_vencimiento"],
             nuevo_iso,movimiento["id"],revendedor_id,json.dumps(datos,ensure_ascii=False,sort_keys=True),
             f"renewal:{clave}"))
        cursor.execute("""UPDATE reseller_purchase_operations SET wallet_transaction_id=?,estado='completed',
            completed_at=? WHERE id=? AND estado='processing'""", (movimiento["id"],momento.isoformat(),operacion_id))
        operacion = dict(cursor.execute("SELECT * FROM reseller_purchase_operations WHERE id=?",(operacion_id,)).fetchone())
        resultado = _resultado_renovacion(cursor, operacion); conn.commit(); return resultado
    except ResellerPurchaseError:
        conn.rollback(); raise
    except sqlite3.IntegrityError as error:
        conn.rollback(); raise ResellerPurchaseError("error_integridad", "La renovaciÃ³n no pudo completarse de forma Ã­ntegra.") from error
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def cambiar_no_renovar(purchase_id, revendedor_id, marcado, ahora=None):
    momento = _momento_bogota(ahora)
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); cursor = conn.cursor()
        contexto = _cargar_contexto_renovacion(cursor, purchase_id, revendedor_id, momento,
                                                resolver_comercial=False)
        purchase = contexto["purchase"]
        marcado = bool(marcado)
        if bool(purchase["no_renovar"]) == marcado:
            conn.commit()
            return {"ok": True, "cambio": False, "no_renovar": marcado}
        fecha = momento.isoformat() if marcado else None
        cursor.execute("UPDATE reseller_purchases SET no_renovar=?,no_renovar_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (int(marcado),fecha,int(purchase_id)))
        tipo = "marked_no_renew" if marcado else "unmarked_no_renew"
        datos = {"no_renovar": marcado}
        cursor.execute("""INSERT INTO reseller_purchase_events
            (purchase_id,tipo,fecha,actor_tipo,actor_id,datos_publicos_json)
            VALUES (?,?,?,'reseller',?,?)""", (int(purchase_id),tipo,momento.isoformat(),
            int(revendedor_id),json.dumps(datos,ensure_ascii=False,sort_keys=True)))
        conn.commit()
        return {"ok": True, "cambio": True, "no_renovar": marcado, "no_renovar_at": fecha}
    except ResellerPurchaseError:
        conn.rollback(); raise
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()
