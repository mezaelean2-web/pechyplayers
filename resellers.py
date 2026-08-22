import re
import sqlite3
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

import database
import reseller_accounts


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ESTADOS = {"activo", "bloqueado"}


def _conectar():
    conn = database.conectar()
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def inicializar_revendedores():
    conn = _conectar()
    try:
        wallet_sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='reseller_wallet_transactions'").fetchone()
        if wallet_sql and "'recovery'" not in (wallet_sql[0] or ""):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.executescript("""
                CREATE TABLE reseller_wallet_transactions_v3b (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, wallet_id INTEGER NOT NULL,
                    revendedor_id INTEGER NOT NULL, tipo TEXT NOT NULL CHECK (tipo IN (
                      'manual_credit','manual_debit','recharge','purchase','renewal','recovery','refund','adjustment')),
                    monto INTEGER NOT NULL CHECK (monto > 0), saldo_anterior INTEGER NOT NULL CHECK (saldo_anterior >= 0),
                    saldo_posterior INTEGER NOT NULL CHECK (saldo_posterior >= 0), referencia TEXT,
                    descripcion TEXT NOT NULL, origen TEXT NOT NULL, actor TEXT, provider TEXT,
                    external_reference TEXT, idempotency_key TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (wallet_id) REFERENCES reseller_wallets(id),
                    FOREIGN KEY (revendedor_id) REFERENCES revendedores(id));
                INSERT INTO reseller_wallet_transactions_v3b SELECT * FROM reseller_wallet_transactions;
                DROP TABLE reseller_wallet_transactions;
                ALTER TABLE reseller_wallet_transactions_v3b RENAME TO reseller_wallet_transactions;
            """)
            conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS revendedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                negocio TEXT NOT NULL DEFAULT '',
                correo TEXT NOT NULL COLLATE NOCASE,
                telefono TEXT NOT NULL DEFAULT '',
                password_hash TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'activo'
                    CHECK (estado IN ('activo', 'bloqueado')),
                fecha_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ultima_actividad TEXT,
                UNIQUE (correo)
            );

            CREATE INDEX IF NOT EXISTS idx_revendedores_estado
                ON revendedores(estado);
            CREATE INDEX IF NOT EXISTS idx_revendedores_fecha
                ON revendedores(fecha_registro);

            CREATE TABLE IF NOT EXISTS precios_revendedor_generales (
                plan_id INTEGER PRIMARY KEY,
                precio INTEGER NOT NULL CHECK (precio > 0),
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES productos(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS precios_revendedor_personalizados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revendedor_id INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                precio INTEGER CHECK (precio IS NULL OR precio > 0),
                oferta_activa INTEGER NOT NULL DEFAULT 0 CHECK (oferta_activa IN (0, 1)),
                oferta_precio INTEGER CHECK (oferta_precio IS NULL OR oferta_precio > 0),
                oferta_inicio TEXT,
                oferta_fin TEXT,
                activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
                fecha_actualizacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES productos(id) ON DELETE CASCADE,
                UNIQUE (revendedor_id, plan_id),
                CHECK (oferta_activa = 0 OR oferta_precio IS NOT NULL)
            );

            CREATE INDEX IF NOT EXISTS idx_precios_personalizados_revendedor
                ON precios_revendedor_personalizados(revendedor_id);

            CREATE TABLE IF NOT EXISTS revendedores_actividad (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revendedor_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'admin',
                fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_revendedores_actividad_fecha
                ON revendedores_actividad(revendedor_id, id DESC);

            CREATE TABLE IF NOT EXISTS reseller_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                revendedor_id INTEGER NOT NULL UNIQUE,
                saldo INTEGER NOT NULL DEFAULT 0 CHECK (saldo >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id)
            );

            CREATE TABLE IF NOT EXISTS reseller_wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_id INTEGER NOT NULL,
                revendedor_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN (
                    'manual_credit', 'manual_debit', 'recharge',
                    'purchase', 'renewal', 'recovery', 'refund', 'adjustment'
                )),
                monto INTEGER NOT NULL CHECK (monto > 0),
                saldo_anterior INTEGER NOT NULL CHECK (saldo_anterior >= 0),
                saldo_posterior INTEGER NOT NULL CHECK (saldo_posterior >= 0),
                referencia TEXT,
                descripcion TEXT NOT NULL,
                origen TEXT NOT NULL,
                actor TEXT,
                provider TEXT,
                external_reference TEXT,
                idempotency_key TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wallet_id) REFERENCES reseller_wallets(id),
                FOREIGN KEY (revendedor_id) REFERENCES revendedores(id)
            );

            CREATE INDEX IF NOT EXISTS idx_wallet_transactions_recent
                ON reseller_wallet_transactions(wallet_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_wallet_transactions_reseller
                ON reseller_wallet_transactions(revendedor_id, id DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_wallet_transactions_idempotency
                ON reseller_wallet_transactions(idempotency_key)
                WHERE idempotency_key IS NOT NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS uq_wallet_transactions_provider_reference
                ON reseller_wallet_transactions(provider, external_reference)
                WHERE provider IS NOT NULL AND external_reference IS NOT NULL;

            INSERT OR IGNORE INTO reseller_wallets (revendedor_id, saldo)
                SELECT id, 0 FROM revendedores;
        """)
        reseller_accounts.inicializar_esquema(cursor=conn.cursor())
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(revendedores)")}
        if "auth_version" not in columnas:
            conn.execute("ALTER TABLE revendedores ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 1")
        if "password_changed_at" not in columnas:
            conn.execute("ALTER TABLE revendedores ADD COLUMN password_changed_at TEXT")
        conn.commit()
    finally:
        conn.close()


def _limpiar_texto(valor, limite):
    return " ".join(str(valor or "").strip().split())[:limite]


def _normalizar_correo(valor):
    return str(valor or "").strip().lower()[:254]


def _normalizar_telefono(valor):
    texto = str(valor or "").strip()
    if not texto:
        return ""
    prefijo = "+" if texto.startswith("+") else ""
    return prefijo + re.sub(r"\D", "", texto)[:20]


def _validar_password(password):
    password = str(password or "")
    if len(password) < 10:
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir letras y números.")
    return password


def _registrar_actividad(cursor, revendedor_id, tipo, descripcion, actor="admin"):
    cursor.execute(
        """INSERT INTO revendedores_actividad
           (revendedor_id, tipo, descripcion, actor)
           VALUES (?, ?, ?, ?)""",
        (revendedor_id, tipo, descripcion, _limpiar_texto(actor, 80) or "admin")
    )


def crear_revendedor(nombre, correo, telefono, negocio, password, actor="admin",
                     tipo_actividad="creacion"):
    nombre = _limpiar_texto(nombre, 120)
    negocio = _limpiar_texto(negocio, 120)
    correo = _normalizar_correo(correo)
    telefono = _normalizar_telefono(telefono)
    password = _validar_password(password)
    if not nombre:
        raise ValueError("El nombre es obligatorio.")
    if not EMAIL_RE.fullmatch(correo):
        raise ValueError("El correo no tiene un formato válido.")
    if telefono and len(re.sub(r"\D", "", telefono)) < 7:
        raise ValueError("El teléfono no tiene un formato válido.")

    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO revendedores
               (nombre, negocio, correo, telefono, password_hash)
               VALUES (?, ?, ?, ?, ?)""",
            (nombre, negocio, correo, telefono, generate_password_hash(password))
        )
        revendedor_id = cursor.lastrowid
        cursor.execute(
            "INSERT OR IGNORE INTO reseller_wallets (revendedor_id, saldo) VALUES (?, 0)",
            (revendedor_id,)
        )
        descripcion = (
            "Cuenta creada mediante registro público."
            if tipo_actividad == "registro_publico"
            else "Cuenta creada desde Administración."
        )
        _registrar_actividad(cursor, revendedor_id, tipo_actividad, descripcion, actor)
        conn.commit()
        return revendedor_id
    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "correo" in str(error).lower() or "unique" in str(error).lower():
            raise ValueError("Ya existe un revendedor con ese correo.") from error
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_revendedores():
    conn = _conectar()
    try:
        return [dict(fila) for fila in conn.execute(
            """SELECT id, nombre, negocio, correo, telefono, estado,
                      fecha_registro, ultima_actividad
               FROM revendedores ORDER BY id DESC"""
        ).fetchall()]
    finally:
        conn.close()


def resumen_revendedores():
    conn = _conectar()
    try:
        fila = conn.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN estado='activo' THEN 1 ELSE 0 END) AS activos,
                   SUM(CASE WHEN estado='bloqueado' THEN 1 ELSE 0 END) AS bloqueados,
                   SUM(CASE WHEN datetime(fecha_registro) >= datetime('now', '-30 days')
                            THEN 1 ELSE 0 END) AS nuevos
            FROM revendedores
        """).fetchone()
        return {clave: int(fila[clave] or 0) for clave in fila.keys()}
    finally:
        conn.close()


def obtener_revendedor(revendedor_id):
    conn = _conectar()
    try:
        fila = conn.execute(
            """SELECT id, nombre, negocio, correo, telefono, estado,
                      fecha_registro, fecha_actualizacion, ultima_actividad,
                      auth_version, password_changed_at
               FROM revendedores WHERE id=?""", (revendedor_id,)
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        conn.close()


def actualizar_revendedor(revendedor_id, nombre, negocio, correo, telefono, actor="admin"):
    nombre = _limpiar_texto(nombre, 120)
    negocio = _limpiar_texto(negocio, 120)
    correo = _normalizar_correo(correo)
    telefono = _normalizar_telefono(telefono)
    if not nombre or not EMAIL_RE.fullmatch(correo):
        raise ValueError("Nombre y correo válido son obligatorios.")
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE revendedores SET nombre=?, negocio=?, correo=?, telefono=?,
                      fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?""",
            (nombre, negocio, correo, telefono, revendedor_id)
        )
        if cursor.rowcount != 1:
            raise LookupError("Revendedor no encontrado.")
        _registrar_actividad(cursor, revendedor_id, "datos_actualizados", "Información general actualizada.", actor)
        conn.commit()
        return {
            "nombre": nombre,
            "negocio": negocio,
            "correo": correo,
            "telefono": telefono,
        }
    except sqlite3.IntegrityError as error:
        conn.rollback()
        raise ValueError("Ya existe un revendedor con ese correo.") from error
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cambiar_estado_revendedor(revendedor_id, estado, actor="admin"):
    if estado not in ESTADOS:
        raise ValueError("Estado no válido.")
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE revendedores SET estado=?, fecha_actualizacion=CURRENT_TIMESTAMP
               WHERE id=? AND estado<>?""", (estado, revendedor_id, estado)
        )
        if cursor.rowcount != 1:
            existe = cursor.execute("SELECT 1 FROM revendedores WHERE id=?", (revendedor_id,)).fetchone()
            if not existe:
                raise LookupError("Revendedor no encontrado.")
            conn.rollback()
            return False
        _registrar_actividad(cursor, revendedor_id, estado, f"Acceso {estado} por Administración.", actor)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cambiar_password_revendedor(revendedor_id, password, actor="admin"):
    password = _validar_password(password)
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE revendedores SET password_hash=?, auth_version=auth_version+1,
                      password_changed_at=CURRENT_TIMESTAMP,
                      fecha_actualizacion=CURRENT_TIMESTAMP
               WHERE id=?""", (generate_password_hash(password), revendedor_id)
        )
        if cursor.rowcount != 1:
            raise LookupError("Revendedor no encontrado.")
        _registrar_actividad(cursor, revendedor_id, "password_actualizado", "Contraseña restablecida por Administración.", actor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def autenticar_revendedor(correo, password):
    correo = _normalizar_correo(correo)
    conn = _conectar()
    try:
        fila = conn.execute(
            """SELECT id, nombre, correo, password_hash, estado, auth_version
               FROM revendedores WHERE correo=?""", (correo,)
        ).fetchone()
        if not fila or not check_password_hash(fila["password_hash"], str(password or "")):
            return {"ok": False, "codigo": "credenciales"}
        if fila["estado"] != "activo":
            return {"ok": False, "codigo": "bloqueado"}
        conn.execute(
            "UPDATE revendedores SET ultima_actividad=CURRENT_TIMESTAMP WHERE id=?",
            (fila["id"],)
        )
        conn.commit()
        return {
            "ok": True, "id": fila["id"], "nombre": fila["nombre"],
            "auth_version": int(fila["auth_version"] or 1)
        }
    finally:
        conn.close()


def cambiar_password_propia(revendedor_id, password_actual, password_nueva):
    password_nueva = _validar_password(password_nueva)
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        fila = cursor.execute(
            "SELECT password_hash, estado FROM revendedores WHERE id=?",
            (revendedor_id,)
        ).fetchone()
        if not fila or fila["estado"] != "activo":
            raise LookupError("La cuenta no está disponible.")
        if not check_password_hash(fila["password_hash"], str(password_actual or "")):
            raise ValueError("La contraseña actual no es correcta.")
        cursor.execute("""
            UPDATE revendedores SET password_hash=?, auth_version=auth_version+1,
              password_changed_at=CURRENT_TIMESTAMP,
              fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?
        """, (generate_password_hash(password_nueva), revendedor_id))
        _registrar_actividad(cursor, revendedor_id, "password_propio", "Contraseña actualizada desde Mi cuenta.", "revendedor")
        conn.commit()
        return obtener_revendedor(revendedor_id)["auth_version"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def actualizar_perfil_propio(revendedor_id, nombre, negocio, telefono):
    revendedor = obtener_revendedor(revendedor_id)
    if not revendedor:
        raise LookupError("Revendedor no encontrado.")
    actualizar_revendedor(
        revendedor_id, nombre, negocio, revendedor["correo"], telefono,
        actor="revendedor"
    )


def resolver_precios_revendedor(revendedor_id, plan_ids, ahora=None):
    ids = sorted({int(plan_id) for plan_id in plan_ids})
    if not ids:
        return {}
    ahora = ahora or datetime.now(timezone.utc).date().isoformat()
    marcadores = ",".join("?" for _ in ids)
    conn = _conectar()
    try:
        filas = conn.execute(f"""
            SELECT p.id AS plan_id, g.precio AS general, g.activo AS general_activo,
                   o.precio AS personalizado, o.oferta_activa, o.oferta_precio,
                   o.oferta_inicio, o.oferta_fin, o.activo AS override_activo
            FROM productos p
            LEFT JOIN precios_revendedor_generales g ON g.plan_id=p.id
            LEFT JOIN precios_revendedor_personalizados o
              ON o.plan_id=p.id AND o.revendedor_id=?
            WHERE p.id IN ({marcadores})
        """, (revendedor_id, *ids)).fetchall()
        resultado = {}
        for fila in filas:
            oferta_vigente = bool(
                fila["override_activo"] and fila["oferta_activa"] and fila["oferta_precio"]
                and (not fila["oferta_inicio"] or fila["oferta_inicio"] <= ahora)
                and (not fila["oferta_fin"] or fila["oferta_fin"] >= ahora)
            )
            if oferta_vigente:
                resultado[fila["plan_id"]] = {"precio": fila["oferta_precio"], "origen": "oferta_personalizada", "precio_base": fila["personalizado"] or fila["general"]}
            elif fila["override_activo"] and fila["personalizado"]:
                resultado[fila["plan_id"]] = {"precio": fila["personalizado"], "origen": "precio_personalizado", "precio_base": None}
            elif fila["general_activo"] and fila["general"]:
                resultado[fila["plan_id"]] = {"precio": fila["general"], "origen": "precio_general", "precio_base": None}
            else:
                resultado[fila["plan_id"]] = {"precio": None, "origen": "sin_precio_reseller", "precio_base": None}
        return resultado
    finally:
        conn.close()


def obtener_planes_revendedor(revendedor_id):
    conn = _conectar()
    try:
        filas = conn.execute("""
            SELECT p.id AS plan_id, p.nombre AS producto, p.plan, p.precio AS precio_publico,
                   g.precio AS precio_general, g.activo AS general_activo,
                   o.id AS override_id, o.precio AS precio_personalizado,
                   o.oferta_activa, o.oferta_precio, o.oferta_inicio, o.oferta_fin,
                   o.activo AS override_activo
            FROM productos p
            LEFT JOIN precios_revendedor_generales g ON g.plan_id=p.id
            LEFT JOIN precios_revendedor_personalizados o
              ON o.plan_id=p.id AND o.revendedor_id=?
            ORDER BY p.nombre COLLATE NOCASE, p.id
        """, (revendedor_id,)).fetchall()
        return [dict(fila) for fila in filas]
    finally:
        conn.close()


def guardar_precio_general_en_cursor(cursor, plan_id, precio, actor="admin"):
    """Persiste el precio general usando la transaccion activa del llamador."""
    precio = int(precio)
    if precio <= 0:
        raise ValueError("El precio reseller general debe ser mayor que cero.")
    if not cursor.execute("SELECT 1 FROM productos WHERE id=?", (plan_id,)).fetchone():
        raise LookupError("Plan no encontrado.")
    cursor.execute("""
        INSERT INTO precios_revendedor_generales(plan_id, precio, activo)
        VALUES (?, ?, 1)
        ON CONFLICT(plan_id) DO UPDATE SET precio=excluded.precio, activo=1,
            fecha_actualizacion=CURRENT_TIMESTAMP
    """, (plan_id, precio))


def guardar_precio_general(plan_id, precio, actor="admin"):
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        guardar_precio_general_en_cursor(conn.cursor(), plan_id, precio, actor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def guardar_precio_personalizado(revendedor_id, plan_id, precio, oferta_activa=False,
                                  oferta_precio=None, oferta_inicio=None, oferta_fin=None,
                                  actor="admin"):
    precio = int(precio) if str(precio or "").strip() else None
    oferta_precio = int(oferta_precio) if str(oferta_precio or "").strip() else None
    oferta_activa = bool(oferta_activa)
    if precio is not None and precio <= 0:
        raise ValueError("El precio personalizado debe ser mayor que cero.")
    if oferta_activa and (oferta_precio is None or oferta_precio <= 0):
        raise ValueError("La oferta activa necesita un precio válido.")
    if precio is None and not oferta_activa:
        raise ValueError("Indica un precio personalizado o una oferta.")
    if oferta_inicio and oferta_fin and oferta_inicio > oferta_fin:
        raise ValueError("La fecha final de la oferta no puede ser anterior al inicio.")

    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        if not cursor.execute("SELECT 1 FROM revendedores WHERE id=?", (revendedor_id,)).fetchone():
            raise LookupError("Revendedor no encontrado.")
        if not cursor.execute("SELECT 1 FROM productos WHERE id=?", (plan_id,)).fetchone():
            raise LookupError("Plan no encontrado.")
        cursor.execute("""
            INSERT INTO precios_revendedor_personalizados
              (revendedor_id, plan_id, precio, oferta_activa, oferta_precio,
               oferta_inicio, oferta_fin, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(revendedor_id, plan_id) DO UPDATE SET
              precio=excluded.precio, oferta_activa=excluded.oferta_activa,
              oferta_precio=excluded.oferta_precio, oferta_inicio=excluded.oferta_inicio,
              oferta_fin=excluded.oferta_fin, activo=1,
              fecha_actualizacion=CURRENT_TIMESTAMP
        """, (revendedor_id, plan_id, precio, int(oferta_activa), oferta_precio,
              oferta_inicio or None, oferta_fin or None))
        _registrar_actividad(cursor, revendedor_id, "precio_personalizado", f"Precio personalizado actualizado para el plan #{plan_id}.", actor)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def restaurar_precio_general(revendedor_id, plan_id, actor="admin"):
    conn = _conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        if not cursor.execute("SELECT 1 FROM revendedores WHERE id=?", (revendedor_id,)).fetchone():
            raise LookupError("Revendedor no encontrado.")
        cursor.execute(
            "DELETE FROM precios_revendedor_personalizados WHERE revendedor_id=? AND plan_id=?",
            (revendedor_id, plan_id)
        )
        if cursor.rowcount:
            _registrar_actividad(cursor, revendedor_id, "precio_restaurado", f"Plan #{plan_id} restaurado al precio reseller general.", actor)
        conn.commit()
        return bool(cursor.rowcount)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_actividad_revendedor(revendedor_id, limite=20):
    conn = _conectar()
    try:
        return [dict(fila) for fila in conn.execute("""
            SELECT tipo, descripcion, actor, fecha FROM revendedores_actividad
            WHERE revendedor_id=? ORDER BY id DESC LIMIT ?
        """, (revendedor_id, min(max(int(limite), 1), 50))).fetchall()]
    finally:
        conn.close()


def resolver_precio_revendedor(plan_id, revendedor_id, ahora=None):
    ahora = ahora or datetime.now(timezone.utc).date().isoformat()
    conn = _conectar()
    try:
        fila = conn.execute("""
            SELECT g.precio AS general, g.activo AS general_activo,
                   o.precio AS personalizado, o.oferta_activa, o.oferta_precio,
                   o.oferta_inicio, o.oferta_fin, o.activo AS override_activo
            FROM productos p
            LEFT JOIN precios_revendedor_generales g ON g.plan_id=p.id
            LEFT JOIN precios_revendedor_personalizados o
              ON o.plan_id=p.id AND o.revendedor_id=?
            WHERE p.id=?
        """, (revendedor_id, plan_id)).fetchone()
        if not fila:
            raise LookupError("Plan no encontrado.")
        oferta_vigente = bool(
            fila["override_activo"] and fila["oferta_activa"] and fila["oferta_precio"]
            and (not fila["oferta_inicio"] or fila["oferta_inicio"] <= ahora)
            and (not fila["oferta_fin"] or fila["oferta_fin"] >= ahora)
        )
        if oferta_vigente:
            return {"precio": fila["oferta_precio"], "origen": "oferta_personalizada"}
        if fila["override_activo"] and fila["personalizado"]:
            return {"precio": fila["personalizado"], "origen": "precio_personalizado"}
        if fila["general_activo"] and fila["general"]:
            return {"precio": fila["general"], "origen": "precio_general"}
        return {"precio": None, "origen": "sin_precio_reseller"}
    finally:
        conn.close()
