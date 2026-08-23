import json
import os
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path

REAL_DB = Path(__file__).with_name("pechy.db").resolve()
DB = os.environ.get("PECHY_DB") or str(REAL_DB)


class UnsafeTestDatabaseError(RuntimeError):
    """Impide que una ejecución de tests abra la base real para escritura."""


def _variable_booleana(nombre):
    return os.environ.get(nombre, "").strip().lower() in {"1", "true", "yes", "on"}


def testing_activo():
    """El modo de tests es explícito; no se infiere de pytest/unittest ni de argv."""
    return _variable_booleana("PECHY_TESTING")


def _ruta_resuelta_db(ruta=None):
    return Path(ruta if ruta is not None else DB).expanduser().resolve()


def _proteger_base_real_en_tests(ruta=None):
    ruta_resuelta = _ruta_resuelta_db(ruta)
    if testing_activo():
        ruta_configurada = os.environ.get("PECHY_DB", "").strip()
        if not ruta_configurada:
            raise UnsafeTestDatabaseError(
                "PECHY_TESTING requiere PECHY_DB explícita; no existe fallback seguro."
            )
        if ruta_resuelta == REAL_DB:
            raise UnsafeTestDatabaseError(
                f"Modo test rechazó la apertura de la base real: {REAL_DB}"
            )
    return ruta_resuelta


def _normalizar_clave_categoria_cartelera(valor):
    texto = unicodedata.normalize("NFD", str(valor or "").strip().lower())
    texto_sin_acentos = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )
    return " ".join(texto_sin_acentos.split())

def conectar():
    ruta = _proteger_base_real_en_tests()
    conn = sqlite3.connect(str(ruta))
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")

    return conn


def politica_duracion_inventario(plataforma, modalidad, cursor=None):
    """Indica si las reglas activas exigen clasificar fisicamente por duracion."""
    plataforma = " ".join(str(plataforma or "").strip().split())
    modalidad = str(modalidad or "cuenta_completa").strip().lower()
    tipo_unidad = "perfil" if modalidad in {"perfil", "perfiles"} else "cuenta"
    propia = cursor is None
    conn = conectar() if propia else cursor.connection
    cur = conn.cursor() if propia else cursor
    try:
        existe = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reseller_plan_inventory_rules'"
        ).fetchone()
        duraciones = [] if not existe or not plataforma else [
            int(fila[0]) for fila in cur.execute("""
                SELECT DISTINCT duracion_dias FROM reseller_plan_inventory_rules
                WHERE activo=1 AND lower(trim(plataforma))=lower(trim(?))
                  AND tipo_unidad=? ORDER BY duracion_dias
            """, (plataforma, tipo_unidad)).fetchall()
        ]
        requiere = len(duraciones) > 1
        return {"requiere_duracion_inventario": requiere,
                "duraciones_disponibles": duraciones if requiere else []}
    finally:
        if propia:
            conn.close()


def validar_duracion_unidad_inventario(plataforma, modalidad, valor, cursor=None):
    politica = politica_duracion_inventario(plataforma, modalidad, cursor=cursor)
    if not politica["requiere_duracion_inventario"]:
        return None
    try:
        duracion = int(valor) if valor not in (None, "") else None
    except (TypeError, ValueError) as error:
        raise ValueError("La duracion de inventario no es valida.") from error
    if duracion not in politica["duraciones_disponibles"]:
        permitidas = ", ".join(str(item) for item in politica["duraciones_disponibles"])
        raise ValueError(f"Selecciona una duracion de inventario valida ({permitidas} dias).")
    return duracion

def obtener_config():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cursor.execute("INSERT OR IGNORE INTO config (clave, valor) VALUES ('whatsapp', '573147735950')")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'nombre_negocio',
        'PECHY PLAYERS'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'nombre_corto',
        'PECHY'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'eslogan',
        'Vive el cine a otro nivel'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'descripcion_negocio',
        'Entretenimiento, streaming y servicios digitales en un solo lugar.'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'titulo_navegador',
        'PECHY PLAYERS'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'texto_footer',
        'PECHY PLAYERS - Todos los derechos reservados.'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'color_principal',
        '#e50914'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'color_secundario',
        '#18191d'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'color_acento',
        '#d4af37'
    )
""")

    cursor.execute("""
    INSERT OR IGNORE INTO config (
        clave,
        valor
    )
    VALUES (
        'intensidad_fondo',
        '100'
    )
""")

        # ==========================================
    # CONFIGURACIÓN COMERCIAL
    # ==========================================

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "moneda_nombre",
            "Peso colombiano"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "moneda_simbolo",
            "$"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "separador_miles",
            "."
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "dias_garantia",
            "30"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "texto_entrega",
            "Entrega inmediata"
        )
    )


        # ==========================================
    # PÁGINA DE INICIO
    # ==========================================

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_hero_activo",
            "1"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_badge",
            "🛡️ COMPRA SEGURA Y PROTEGIDA"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_titulo_superior",
            "EL MEJOR"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_titulo_destacado",
            "ENTRETENIMIENTO"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_titulo_inferior",
            "EN TUS MANOS"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_boton_catalogo",
            "Explorar catálogo →"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "inicio_boton_whatsapp",
            "💬 Comprar por WhatsApp"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "texto_disponibilidad",
            "Disponible"
        )
    )

    cursor.execute(
        """
        INSERT OR IGNORE INTO config
        (clave, valor)
        VALUES (?, ?)
        """,
        (
            "mensaje_comercial",
            "Plataformas premium al mejor precio, entrega inmediata y soporte rápido."
        )
    )
    conn.commit()

    

    cursor.execute("SELECT clave, valor FROM config")
    filas = cursor.fetchall()
    conn.close()

    return {clave: valor for clave, valor in filas}


def actualizar_config(clave, valor):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO config (clave, valor)
        VALUES (?, ?)
    """, (clave, valor))

    conn.commit()
    conn.close()

def registrar_historial(accion):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("INSERT INTO historial (accion) VALUES (?)", (accion,))

    conn.commit()
    conn.close()


def obtener_historial(limite=15, offset=0):

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        SELECT
            accion,
            datetime(fecha, 'localtime') AS fecha
        FROM historial
        ORDER BY id DESC
        LIMIT ?
        OFFSET ?
    """, (
        limite,
        offset
    ))

    filas = cursor.fetchall()

    conn.close()

    return filas

def obtener_resumen_historial():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        SELECT COUNT(*)
        FROM historial
    """)

    total_movimientos = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM historial
        WHERE DATE(
            datetime(fecha, 'localtime')
        ) = DATE(
            'now',
            'localtime'
        )
    """)

    movimientos_hoy = cursor.fetchone()[0]

    cursor.execute("""
        SELECT datetime(fecha, 'localtime')
        FROM historial
        ORDER BY id DESC
        LIMIT 1
    """)

    ultima_fila = cursor.fetchone()

    ultima_actividad = (
        ultima_fila[0]
        if ultima_fila
        else None
    )

    conn.close()

    return {
        "total_movimientos": total_movimientos,
        "movimientos_hoy": movimientos_hoy,
        "ultima_actividad": ultima_actividad
    }

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()

    for columna in [
    "oferta_precio TEXT DEFAULT ''",
    "oferta_activa INTEGER DEFAULT 0",
    "destacado INTEGER DEFAULT 0",
    "visible INTEGER DEFAULT 1",
    "estado TEXT DEFAULT 'disponible'",
    "orden INTEGER DEFAULT 999",
    "categoria TEXT DEFAULT 'Streaming'",
    "orden_categoria INTEGER DEFAULT 999",
]:
        try:
            cursor.execute(f"ALTER TABLE productos ADD COLUMN {columna}")
        except:
            pass

    cursor.execute("""
CREATE TABLE IF NOT EXISTS promociones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imagen TEXT NOT NULL,
    imagen_desktop TEXT,
    activa INTEGER DEFAULT 1,
    orden INTEGER DEFAULT 999
)
""")

    columnas_promociones = {
        fila[1]
        for fila in cursor.execute("PRAGMA table_info(promociones)").fetchall()
    }
    if "imagen_desktop" not in columnas_promociones:
        cursor.execute("ALTER TABLE promociones ADD COLUMN imagen_desktop TEXT")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS categorias (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT UNIQUE NOT NULL,

    icono TEXT DEFAULT 'folder',

    color TEXT DEFAULT '#64748b',

    visible INTEGER DEFAULT 1,

    orden INTEGER DEFAULT 999

)
""")

    cursor.execute("""
CREATE TABLE IF NOT EXISTS cartelera (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tipo TEXT NOT NULL DEFAULT 'Película',

    titulo TEXT NOT NULL,

    subtitulo TEXT DEFAULT '',

    genero TEXT DEFAULT '',

    categoria TEXT DEFAULT '',

    categoria_id INTEGER,

    descripcion TEXT DEFAULT '',

    anio INTEGER,

    fecha_estreno TEXT DEFAULT '',

    calificacion TEXT DEFAULT '',

    poster TEXT DEFAULT '',

    banner TEXT DEFAULT '',

    url TEXT DEFAULT '',

    tendencia INTEGER DEFAULT 0,

    destacado INTEGER DEFAULT 0,

    publicado INTEGER DEFAULT 1,

    orden INTEGER DEFAULT 999,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

    for columna_cartelera in [
        "tipo TEXT NOT NULL DEFAULT 'Película'",
        "subtitulo TEXT DEFAULT ''",
        "fecha_estreno TEXT DEFAULT ''",
        "categoria TEXT DEFAULT ''",
        "categoria_id INTEGER",
        "calificacion TEXT DEFAULT ''",
        "banner TEXT DEFAULT ''",
        "destacado INTEGER DEFAULT 0",
        "orden INTEGER DEFAULT 999",
        "fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    ]:
        try:
            cursor.execute(
                f"ALTER TABLE cartelera ADD COLUMN {columna_cartelera}"
            )
        except sqlite3.OperationalError:
            pass    

    cursor.execute("""
CREATE TABLE IF NOT EXISTS cartelera_categorias (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nombre TEXT NOT NULL,

    clave TEXT NOT NULL UNIQUE,

    activa INTEGER NOT NULL DEFAULT 1,

    orden INTEGER NOT NULL DEFAULT 999,

    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)
""")

    categorias_iniciales_cartelera = [
        ("Acción", "accion", 1),
        ("Drama", "drama", 2),
        ("Comedia", "comedia", 3),
        ("Terror", "terror", 4),
        ("Ciencia ficción", "ciencia ficcion", 5),
        ("Infantil", "infantil", 6),
        ("Romance", "romance", 7),
        ("Documentales", "documentales", 8),
        ("Series", "series", 9),
        ("Anime", "anime", 10),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO cartelera_categorias (
            nombre,
            clave,
            activa,
            orden
        ) VALUES (?, ?, 1, ?)
    """, categorias_iniciales_cartelera)

    categorias_por_clave = {
        _normalizar_clave_categoria_cartelera(fila["clave"]): fila["id"]
        for fila in cursor.execute("""
            SELECT id, clave
            FROM cartelera_categorias
        """).fetchall()
    }

    peliculas_sin_relacion = cursor.execute("""
        SELECT id, categoria
        FROM cartelera
        WHERE categoria_id IS NULL
          AND categoria IS NOT NULL
          AND TRIM(categoria) != ''
    """).fetchall()

    asociaciones_cartelera = []
    for pelicula in peliculas_sin_relacion:
        categoria_id = categorias_por_clave.get(
            _normalizar_clave_categoria_cartelera(pelicula["categoria"])
        )
        if categoria_id is not None:
            asociaciones_cartelera.append((categoria_id, pelicula["id"]))

    cursor.executemany("""
        UPDATE cartelera
        SET categoria_id = ?
        WHERE id = ?
          AND categoria_id IS NULL
    """, asociaciones_cartelera)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS cartelera_plataformas (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    cartelera_id INTEGER NOT NULL,

    plataforma TEXT NOT NULL,

    FOREIGN KEY(cartelera_id)
    REFERENCES cartelera(id)
    ON DELETE CASCADE

)
""")
    
    cursor.execute("""
    INSERT OR IGNORE INTO categorias (
        nombre,
        icono,
        color,
        visible,
        orden
    )
    SELECT DISTINCT
        categoria,
        'folder',
        '#64748b',
        1,
        999
    FROM productos
    WHERE categoria IS NOT NULL
      AND TRIM(categoria) != ''
""")

    # ==========================================
    # NUBE DE CUENTAS
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_clientes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nombre TEXT DEFAULT '',

            telefono TEXT DEFAULT '',

            correo TEXT DEFAULT '',

            notas TEXT DEFAULT '',

            activo INTEGER DEFAULT 1,

            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    try:
        cursor.execute("""
            ALTER TABLE nube_clientes
            ADD COLUMN telefono_normalizado TEXT
        """)
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_nube_clientes_telefono_normalizado
        ON nube_clientes(telefono_normalizado)
        WHERE telefono_normalizado IS NOT NULL
          AND telefono_normalizado != ''
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_cuentas (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            plataforma TEXT NOT NULL,

            correo TEXT NOT NULL,

            contrasena TEXT DEFAULT '',

            pin TEXT DEFAULT '',

            tipo_cuenta TEXT DEFAULT '',

            cliente_id INTEGER,

            nombre_cliente TEXT DEFAULT '',

            telefono TEXT DEFAULT '',

            fecha_entrega TEXT DEFAULT '',

            dias_cuenta INTEGER DEFAULT 0,

            fecha_vencimiento TEXT DEFAULT '',

            estado TEXT DEFAULT 'disponible',

            garantia_usada INTEGER DEFAULT 0,

            cantidad_garantias INTEGER DEFAULT 0,

            notas TEXT DEFAULT '',

            origen TEXT DEFAULT 'manual',

            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(cliente_id)
                REFERENCES nube_clientes(id)
                ON DELETE SET NULL

        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_movimientos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cuenta_id INTEGER NOT NULL,

            tipo TEXT NOT NULL,

            descripcion TEXT DEFAULT '',

            estado_anterior TEXT DEFAULT '',

            estado_nuevo TEXT DEFAULT '',

            cliente_nombre TEXT DEFAULT '',

            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(cuenta_id)
                REFERENCES nube_cuentas(id)
                ON DELETE CASCADE

        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_reemplazos (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cuenta_anterior_id INTEGER NOT NULL,

            cuenta_nueva_id INTEGER NOT NULL,

            cliente_id INTEGER,

            motivo TEXT DEFAULT '',

            dias_restantes INTEGER DEFAULT 0,

            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(cuenta_anterior_id)
                REFERENCES nube_cuentas(id)
                ON DELETE CASCADE,

            FOREIGN KEY(cuenta_nueva_id)
                REFERENCES nube_cuentas(id)
                ON DELETE CASCADE,

            FOREIGN KEY(cliente_id)
                REFERENCES nube_clientes(id)
                ON DELETE SET NULL

        )
    """)


    # ==========================================
    # NUBE — REEMPLAZOS DE PERFILES
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_reemplazos_perfiles (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            perfil_anterior_id INTEGER NOT NULL,

            perfil_nuevo_id INTEGER NOT NULL,

            cuenta_anterior_id INTEGER NOT NULL,

            cuenta_nueva_id INTEGER NOT NULL,

            nombre_cliente TEXT DEFAULT '',

            telefono TEXT DEFAULT '',

            motivo TEXT DEFAULT '',

            dias_restantes INTEGER DEFAULT 0,

            fecha_vencimiento_anterior TEXT DEFAULT '',

            pin_anterior TEXT DEFAULT '',

            pin_nuevo TEXT DEFAULT '',

            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(perfil_anterior_id)
                REFERENCES nube_perfiles(id),

            FOREIGN KEY(perfil_nuevo_id)
                REFERENCES nube_perfiles(id),

            FOREIGN KEY(cuenta_anterior_id)
                REFERENCES nube_cuentas(id),

            FOREIGN KEY(cuenta_nueva_id)
                REFERENCES nube_cuentas(id)

        )
    """)



    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_reemplazos_perfiles_anterior
        ON nube_reemplazos_perfiles(
            perfil_anterior_id
        )
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_reemplazos_perfiles_nuevo
        ON nube_reemplazos_perfiles(
            perfil_nuevo_id
        )
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_reemplazos_perfiles_cliente
        ON nube_reemplazos_perfiles(
            nombre_cliente
        )
    """)    


    # ==========================================
    # ÍNDICES PARA BÚSQUEDA RÁPIDA
    # ==========================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_cuentas_correo
        ON nube_cuentas(correo)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_cuentas_cliente
        ON nube_cuentas(nombre_cliente)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_cuentas_telefono
        ON nube_cuentas(telefono)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_cuentas_plataforma
        ON nube_cuentas(plataforma)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_cuentas_estado
        ON nube_cuentas(estado)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_movimientos_cuenta
        ON nube_movimientos(cuenta_id)
    """)



    # ==========================================
    # NUBE DE CUENTAS — PERFILES / ESPACIOS
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_perfiles (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cuenta_id INTEGER NOT NULL,

            nombre_perfil TEXT DEFAULT '',

            pin TEXT DEFAULT '',

            cliente_id INTEGER,

            nombre_cliente TEXT DEFAULT '',

            telefono TEXT DEFAULT '',

            fecha_entrega TEXT DEFAULT '',

            dias_cuenta INTEGER DEFAULT 0,

            fecha_vencimiento TEXT DEFAULT '',

            estado TEXT DEFAULT 'disponible',

            garantia_usada INTEGER DEFAULT 0,

            cantidad_garantias INTEGER DEFAULT 0,

            notas TEXT DEFAULT '',

            orden INTEGER DEFAULT 999,

            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(cuenta_id)
                REFERENCES nube_cuentas(id)
                ON DELETE CASCADE,

            FOREIGN KEY(cliente_id)
                REFERENCES nube_clientes(id)
                ON DELETE SET NULL

        )
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_perfiles_cuenta
        ON nube_perfiles(cuenta_id)
    """)

    # Evita el B-tree temporal al cargar perfiles agrupados en su orden visual.
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_perfiles_cuenta_orden_id
        ON nube_perfiles(cuenta_id, orden, id)
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_perfiles_cliente
        ON nube_perfiles(nombre_cliente)
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_perfiles_estado
        ON nube_perfiles(estado)
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_transferencias_servicios (

            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operacion_uuid TEXT NOT NULL UNIQUE,
            tipo_operacion TEXT NOT NULL,
            perfil_origen_id INTEGER NOT NULL,
            cuenta_origen_id INTEGER NOT NULL,
            cliente_id INTEGER,
            dias_disponibles INTEGER DEFAULT 0,
            dias_trasladados INTEGER DEFAULT 0,
            destino_tipo TEXT DEFAULT '',
            perfil_destino_id INTEGER,
            cuenta_destino_id INTEGER,
            motivo TEXT DEFAULT '',
            venta_origen_snapshot TEXT NOT NULL,
            destino_antes_snapshot TEXT,
            destino_despues_snapshot TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP

        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_transferencias_origen
        ON nube_transferencias_servicios(perfil_origen_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_transferencias_cliente
        ON nube_transferencias_servicios(cliente_id)
    """)

    # ==========================================
    # NUBE DE CUENTAS — COLUMNAS NUEVAS
    # ==========================================

    for columna_nube in [

        "modalidad TEXT DEFAULT 'cuenta_completa'",

        "cantidad_perfiles INTEGER DEFAULT 0",

        # Capacidad comercial de la unidad fisica. NULL conserva el inventario
        # historico sin atribuirle una duracion que nunca fue registrada.
        "duracion_unidad_dias INTEGER"

    ]:

        try:

            cursor.execute(
                f"""
                ALTER TABLE nube_cuentas
                ADD COLUMN {columna_nube}
                """
            )

        except sqlite3.OperationalError:

            pass


    # ==========================================
    # NUBE — CONTROL DE PAGOS
    # ==========================================

    for columna_pago_nube in [

        "tipo_pago TEXT DEFAULT ''",

        "valor_pin INTEGER DEFAULT 0",

        "plan_pago TEXT DEFAULT ''",

        "precio_plan_referencia INTEGER DEFAULT 0",

        "fecha_aplicacion_pin TEXT DEFAULT ''",

        "dias_estimados_pin INTEGER DEFAULT 0",

        "fecha_proximo_pago TEXT DEFAULT ''"

    ]:

        try:

            cursor.execute(
                f"""
                ALTER TABLE nube_cuentas
                ADD COLUMN {columna_pago_nube}
                """
            )

        except sqlite3.OperationalError:

            pass

    for columna_archivo_nube in [
        "fecha_archivada TEXT DEFAULT ''",
        "motivo_archivo TEXT DEFAULT ''"
    ]:
        try:
            cursor.execute(
                f"ALTER TABLE nube_cuentas ADD COLUMN {columna_archivo_nube}"
            )
        except sqlite3.OperationalError:
            pass




    # ==========================================
    # NUBE — HISTORIAL DE PAGOS PIN
    # ==========================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_pagos_pin (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            cuenta_id INTEGER NOT NULL,

            valor_pin INTEGER NOT NULL DEFAULT 0,

            plan TEXT DEFAULT '',

            precio_plan_referencia INTEGER DEFAULT 0,

            fecha_aplicacion TEXT NOT NULL,

            dias_estimados INTEGER DEFAULT 0,

            fecha_estimada_fin TEXT DEFAULT '',

            notas TEXT DEFAULT '',

            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(cuenta_id)
                REFERENCES nube_cuentas(id)
                ON DELETE CASCADE

        )
    """)


    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_nube_pagos_pin_cuenta
        ON nube_pagos_pin(cuenta_id)
    """)

    _asegurar_notificaciones_renovacion_nube(cursor)





    conn.commit()
    conn.close()

def obtener_productos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
SELECT
    id,
    nombre,
    imagen,
    plan,
    precio,
    oferta_precio,
    oferta_activa,
    destacado,
    visible,
    estado,
    categoria,
    orden_categoria
FROM productos
ORDER BY
    CASE
        WHEN orden IS NULL THEN 9999
        ELSE orden
    END ASC,
    destacado DESC,
    nombre ASC
""")

    filas = cursor.fetchall()
    conn.close()

    productos = {}

    for (
    id_plan,
    nombre,
    imagen,
    plan,
    precio,
    oferta_precio,
    oferta_activa,
    destacado,
    visible,
    estado,
    categoria,
    orden_categoria
) in filas:
        if nombre not in productos:
            productos[nombre] = {
    "nombre": nombre,
    "imagen": imagen,
    "destacado": destacado,
    "visible": visible,
    "estado": estado or "disponible",
    "categoria": categoria or "Streaming",
    "orden_categoria": orden_categoria,
    "planes": []
}

        productos[nombre]["planes"].append({
            "id": id_plan,
            "plan": plan,
            "precio": precio,
            "oferta_precio": oferta_precio,
            "oferta_activa": oferta_activa,
            "destacado": destacado,
            "visible": visible
        })

    return list(productos.values())

def obtener_estadisticas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(DISTINCT nombre) FROM productos")
    plataformas = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM productos")
    planes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT imagen) FROM productos")
    imagenes = cursor.fetchone()[0]

    conn.close()

    return {
        "plataformas": plataformas,
        "planes": planes,
        "imagenes": imagenes
    }
def obtener_info_sistema():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(productos)")
    columnas = cursor.fetchall()

    conn.close()

    return {
        "version": "2.0",
        "columnas": len(columnas),
        "estado": "Operativo"
    }
def obtener_promociones():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promociones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imagen TEXT NOT NULL,
            imagen_desktop TEXT,
            activa INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 999
        )
    """)

    columnas = {
        fila[1]
        for fila in cursor.execute("PRAGMA table_info(promociones)").fetchall()
    }
    if "imagen_desktop" not in columnas:
        cursor.execute("ALTER TABLE promociones ADD COLUMN imagen_desktop TEXT")
        conn.commit()

    cursor.execute("""
        SELECT id, imagen, activa, imagen_desktop
        FROM promociones
        ORDER BY orden ASC, id DESC
    """)

    filas = cursor.fetchall()
    conn.close()

    return filas

def obtener_categorias():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            nombre,
            icono,
            color,
            visible,
            orden
        FROM categorias
        ORDER BY orden ASC, nombre ASC
    """)

    categorias = cursor.fetchall()

    conn.close()

    return categorias


def obtener_categorias_cartelera(solo_activas=False):
    conn = conectar()
    cursor = conn.cursor()

    consulta = """
        SELECT
            id,
            nombre,
            clave,
            activa,
            orden,
            fecha_creacion,
            fecha_actualizacion
        FROM cartelera_categorias
    """
    if solo_activas:
        consulta += " WHERE activa = 1"
    consulta += " ORDER BY orden ASC, id ASC"

    cursor.execute(consulta)
    categorias = [dict(fila) for fila in cursor.fetchall()]
    conn.close()
    return categorias


def obtener_categoria_cartelera_por_id(categoria_id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            id,
            nombre,
            clave,
            activa,
            orden,
            fecha_creacion,
            fecha_actualizacion
        FROM cartelera_categorias
        WHERE id = ?
    """, (categoria_id,))
    fila = cursor.fetchone()
    conn.close()
    return dict(fila) if fila else None


def obtener_categoria_cartelera_por_clave(clave):
    clave_normalizada = _normalizar_clave_categoria_cartelera(clave)
    conn = conectar()
    cursor = conn.cursor()
    filas = cursor.execute("""
        SELECT
            id,
            nombre,
            clave,
            activa,
            orden,
            fecha_creacion,
            fecha_actualizacion
        FROM cartelera_categorias
    """).fetchall()
    conn.close()

    for fila in filas:
        if _normalizar_clave_categoria_cartelera(fila["clave"]) == clave_normalizada:
            return dict(fila)
    return None


def obtener_categorias_cartelera_con_conteo():
    conn = conectar()
    filas = conn.execute("""
        SELECT
            cc.id,
            cc.nombre,
            cc.clave,
            cc.activa,
            cc.orden,
            cc.fecha_creacion,
            cc.fecha_actualizacion,
            COUNT(c.id) AS cantidad_peliculas
        FROM cartelera_categorias AS cc
        LEFT JOIN cartelera AS c ON c.categoria_id = cc.id
        GROUP BY cc.id
        ORDER BY cc.orden ASC, cc.id ASC
    """).fetchall()
    conn.close()
    return [dict(fila) for fila in filas]


def _clave_desde_nombre_categoria_cartelera(nombre):
    clave = _normalizar_clave_categoria_cartelera(nombre)
    clave = re.sub(r"[^a-z0-9]+", " ", clave).strip()
    return " ".join(clave.split())


def _validar_nombre_categoria_cartelera(nombre):
    nombre = " ".join(str(nombre or "").strip().split())
    if not nombre:
        raise ValueError("Debes escribir un nombre.")
    if len(nombre) > 80:
        raise ValueError("El nombre no puede superar 80 caracteres.")
    clave = _clave_desde_nombre_categoria_cartelera(nombre)
    if not clave:
        raise ValueError("El nombre debe contener letras o números.")
    return nombre, clave


def crear_categoria_cartelera(nombre):
    nombre, clave = _validar_nombre_categoria_cartelera(nombre)
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute(
            "SELECT 1 FROM cartelera_categorias WHERE clave = ?",
            (clave,),
        ).fetchone():
            raise ValueError("Ya existe una categoría con la misma clave canónica.")
        orden = conn.execute(
            "SELECT COALESCE(MAX(orden), 0) + 1 FROM cartelera_categorias"
        ).fetchone()[0]
        cursor = conn.execute("""
            INSERT INTO cartelera_categorias
                (nombre, clave, activa, orden)
            VALUES (?, ?, 1, ?)
        """, (nombre, clave, orden))
        categoria_id = cursor.lastrowid
        conn.commit()
        return obtener_categoria_cartelera_por_id(categoria_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def renombrar_categoria_cartelera(categoria_id, nombre):
    nombre, _ = _validar_nombre_categoria_cartelera(nombre)
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        categoria = conn.execute(
            "SELECT id, clave FROM cartelera_categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        if not categoria:
            raise LookupError("La categoría no existe.")
        duplicada = conn.execute("""
            SELECT 1 FROM cartelera_categorias
            WHERE id != ? AND LOWER(TRIM(nombre)) = LOWER(TRIM(?))
        """, (categoria_id, nombre)).fetchone()
        if duplicada:
            raise ValueError("Ya existe una categoría con ese nombre.")
        conn.execute("""
            UPDATE cartelera_categorias
            SET nombre = ?, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (nombre, categoria_id))
        conn.execute("""
            UPDATE cartelera SET categoria = ? WHERE categoria_id = ?
        """, (nombre, categoria_id))
        conn.commit()
        return obtener_categoria_cartelera_por_id(categoria_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def establecer_categoria_cartelera_activa(categoria_id, activa):
    if type(activa) is not bool:
        raise ValueError("El estado debe ser verdadero o falso.")
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute("""
            UPDATE cartelera_categorias
            SET activa = ?, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if activa else 0, categoria_id))
        if cursor.rowcount != 1:
            raise LookupError("La categoría no existe.")
        conn.commit()
        return obtener_categoria_cartelera_por_id(categoria_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reordenar_categorias_cartelera(orden_ids):
    if not isinstance(orden_ids, list) or not orden_ids:
        raise ValueError("Debes enviar el orden completo de categorías.")
    if any(type(categoria_id) is not int or categoria_id <= 0 for categoria_id in orden_ids):
        raise ValueError("El orden contiene IDs inválidos.")
    if len(set(orden_ids)) != len(orden_ids):
        raise ValueError("El orden contiene IDs duplicados.")
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        ids_reales = {
            fila[0]
            for fila in conn.execute("SELECT id FROM cartelera_categorias").fetchall()
        }
        if set(orden_ids) != ids_reales:
            raise ValueError("La lista no coincide con las categorías actuales.")
        for posicion, categoria_id in enumerate(orden_ids, start=1):
            conn.execute("""
                UPDATE cartelera_categorias
                SET orden = ?, fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (posicion, categoria_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def eliminar_categoria_cartelera_si_vacia(categoria_id):
    conn = conectar()
    try:
        conn.execute("BEGIN IMMEDIATE")
        categoria = conn.execute(
            "SELECT id, nombre FROM cartelera_categorias WHERE id = ?",
            (categoria_id,),
        ).fetchone()
        if not categoria:
            raise LookupError("La categoría no existe.")
        cantidad = conn.execute(
            "SELECT COUNT(*) FROM cartelera WHERE categoria_id = ?",
            (categoria_id,),
        ).fetchone()[0]
        if cantidad:
            raise RuntimeError(
                f"No se puede eliminar: {cantidad} película"
                f"{'s dependen' if cantidad != 1 else ' depende'} de esta categoría."
            )
        conn.execute("DELETE FROM cartelera_categorias WHERE id = ?", (categoria_id,))
        categorias = conn.execute(
            "SELECT id FROM cartelera_categorias ORDER BY orden ASC, id ASC"
        ).fetchall()
        for posicion, fila in enumerate(categorias, start=1):
            conn.execute(
                "UPDATE cartelera_categorias SET orden = ? WHERE id = ?",
                (posicion, fila[0]),
            )
        conn.commit()
        return categoria["nombre"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_cartelera():

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.id,
            c.tipo,
            c.titulo,
            c.subtitulo,
            c.genero,
            c.categoria,
            c.categoria_id,
            cc.clave AS categoria_clave,
            cc.activa AS categoria_activa,
            c.descripcion,
            c.anio,
            c.poster,
            c.banner,
            c.url,
            c.tendencia,
            c.destacado,
            c.publicado,
            c.orden,
            c.fecha_creacion,

            GROUP_CONCAT(
                cp.plataforma,
                ', '
            ) AS plataformas

        FROM cartelera AS c

        LEFT JOIN cartelera_categorias AS cc
            ON cc.id = c.categoria_id

        LEFT JOIN cartelera_plataformas AS cp
            ON cp.cartelera_id = c.id

        GROUP BY c.id

        ORDER BY
            c.orden ASC,
            c.fecha_creacion DESC
    """)

    filas = cursor.fetchall()

    peliculas = [
        dict(fila)
        for fila in filas
    ]

    conn.close()

    return peliculas

# ==========================================
# NUBE DE CUENTAS — LÓGICA DE VENCIMIENTOS
# ==========================================

from datetime import datetime, timedelta


def calcular_fecha_vencimiento(
    fecha_entrega,
    dias_cuenta
):

    if not fecha_entrega:
        return ""


    try:

        fecha_base = datetime.strptime(
            fecha_entrega,
            "%Y-%m-%d"
        )

        dias = int(
            dias_cuenta or 0
        )

    except (
        ValueError,
        TypeError
    ):

        return ""


    fecha_final = (
        fecha_base +
        timedelta(days=dias)
    )


    return fecha_final.strftime(
        "%Y-%m-%d"
    )


def calcular_dias_restantes(
    fecha_vencimiento
):

    if not fecha_vencimiento:
        return 0


    try:

        fecha_final = datetime.strptime(
            fecha_vencimiento,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return 0


    hoy = datetime.now().date()


    return (
        fecha_final - hoy
    ).days


def normalizar_telefono_nube(telefono):

    digitos = re.sub(
        r"\D",
        "",
        str(telefono or "")
    )

    if (
        len(digitos) == 10 and
        digitos.startswith("3")
    ):
        return "57" + digitos

    if (
        len(digitos) == 12 and
        digitos.startswith("573")
    ):
        return digitos

    return digitos


def es_asignacion_operativa_nube(
    nombre_cliente,
    fecha_entrega,
    dias_cuenta,
    fecha_vencimiento
):

    if not (nombre_cliente or "").strip():
        return False

    try:
        dias = int(dias_cuenta or 0)
        datetime.strptime(fecha_entrega or "", "%Y-%m-%d")
        datetime.strptime(fecha_vencimiento or "", "%Y-%m-%d")
    except (ValueError, TypeError):
        return False

    return dias > 0


def _resolver_cliente_existente_por_telefono_nube(
    cursor,
    nombre_cliente,
    telefono
):

    nombre_cliente = (nombre_cliente or "").strip()
    telefono = (telefono or "").strip()
    telefono_normalizado = normalizar_telefono_nube(telefono)

    if not telefono_normalizado:
        return None

    cursor.execute(
        "SELECT id, telefono, telefono_normalizado FROM nube_clientes"
    )
    coincidencias = [
        fila for fila in cursor.fetchall()
        if (
            (fila["telefono_normalizado"] or "") == telefono_normalizado
            or (
                not fila["telefono_normalizado"] and
                normalizar_telefono_nube(fila["telefono"]) ==
                telefono_normalizado
            )
        )
    ]

    if len(coincidencias) != 1:
        return None

    cliente_id = coincidencias[0]["id"]

    cursor.execute(
        """
        UPDATE nube_clientes
        SET
            telefono_normalizado = ?,
            nombre = CASE WHEN ? != '' THEN ? ELSE nombre END,
            telefono = CASE WHEN ? != '' THEN ? ELSE telefono END,
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            telefono_normalizado,
            nombre_cliente,
            nombre_cliente,
            telefono,
            telefono,
            cliente_id
        )
    )
    return cliente_id


def _obtener_o_crear_cliente_nube(
    cursor,
    nombre_cliente,
    telefono
):

    nombre_cliente = (nombre_cliente or "").strip()
    telefono = (telefono or "").strip()
    telefono_normalizado = normalizar_telefono_nube(
        telefono
    )

    if not telefono_normalizado:
        return None

    cursor.execute(
        """
        SELECT id
        FROM nube_clientes
        WHERE telefono_normalizado = ?
        LIMIT 1
        """,
        (telefono_normalizado,)
    )
    cliente = cursor.fetchone()

    if cliente:
        cliente_id = cliente["id"]
        cursor.execute(
            """
            UPDATE nube_clientes
            SET
                nombre = CASE
                    WHEN ? != '' THEN ?
                    ELSE nombre
                END,
                telefono = CASE
                    WHEN ? != '' THEN ?
                    ELSE telefono
                END,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                nombre_cliente,
                nombre_cliente,
                telefono,
                telefono,
                cliente_id
            )
        )
        return cliente_id

    # Compatibilidad sin backfill: se adopta un cliente antiguo
    # solamente cuando el teléfono coincide y no es ambiguo.
    cursor.execute(
        """
        SELECT id, telefono
        FROM nube_clientes
        WHERE telefono_normalizado IS NULL
           OR telefono_normalizado = ''
        """
    )
    coincidencias = [
        fila
        for fila in cursor.fetchall()
        if normalizar_telefono_nube(fila["telefono"]) ==
           telefono_normalizado
    ]

    if len(coincidencias) == 1:
        cliente_id = coincidencias[0]["id"]
        cursor.execute(
            """
            UPDATE nube_clientes
            SET
                telefono_normalizado = ?,
                nombre = CASE
                    WHEN ? != '' THEN ?
                    ELSE nombre
                END,
                telefono = CASE
                    WHEN ? != '' THEN ?
                    ELSE telefono
                END,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
              AND (
                    telefono_normalizado IS NULL
                    OR telefono_normalizado = ''
              )
            """,
            (
                telefono_normalizado,
                nombre_cliente,
                nombre_cliente,
                telefono,
                telefono,
                cliente_id
            )
        )
        return cliente_id

    if len(coincidencias) > 1:
        return None

    cursor.execute(
        """
        INSERT INTO nube_clientes (
            nombre,
            telefono,
            telefono_normalizado
        )
        VALUES (?, ?, ?)
        """,
        (
            nombre_cliente,
            telefono,
            telefono_normalizado
        )
    )
    return cursor.lastrowid


def _crear_snapshot_servicio_nube(cursor, perfil_id):

    cursor.execute(
        """
        SELECT
            p.id AS perfil_id,
            p.cuenta_id,
            c.plataforma,
            c.correo,
            p.nombre_perfil,
            p.pin,
            p.cliente_id,
            p.nombre_cliente,
            p.telefono,
            p.fecha_entrega,
            p.dias_cuenta,
            p.fecha_vencimiento,
            p.estado,
            p.notas,
            p.garantia_usada,
            p.cantidad_garantias
        FROM nube_perfiles AS p
        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id
        WHERE p.id = ?
        """,
        (perfil_id,)
    )
    fila = cursor.fetchone()

    if not fila:
        return None

    snapshot = dict(fila)
    snapshot["dias_restantes"] = max(
        calcular_dias_restantes(
            snapshot.get("fecha_vencimiento")
        ),
        0
    )
    snapshot["fecha_snapshot"] = (
        datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
    )

    return json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True
    )


def _identidad_cliente_servicio_nube(cursor, perfil):
    """Devuelve una identidad segura: cliente_id o teléfono único legado."""

    if perfil["cliente_id"] is not None:
        return {"tipo": "cliente_id", "valor": perfil["cliente_id"]}

    telefono_normalizado = normalizar_telefono_nube(perfil["telefono"])
    if not telefono_normalizado:
        return None

    cursor.execute(
        "SELECT id, telefono, telefono_normalizado FROM nube_clientes"
    )
    clientes = {
        fila["id"]
        for fila in cursor.fetchall()
        if normalizar_telefono_nube(
            fila["telefono_normalizado"] or fila["telefono"]
        ) == telefono_normalizado
    }
    if len(clientes) > 1:
        return None

    return {
        "tipo": "telefono",
        "valor": telefono_normalizado,
        "cliente_id_unico": next(iter(clientes), None)
    }


def _servicio_pertenece_a_identidad_nube(cursor, perfil, identidad):
    if not identidad:
        return False

    if identidad["tipo"] == "cliente_id":
        return perfil["cliente_id"] == identidad["valor"]

    telefono_destino = normalizar_telefono_nube(perfil["telefono"])
    if telefono_destino != identidad["valor"]:
        return False

    cliente_id_unico = identidad.get("cliente_id_unico")
    return (
        perfil["cliente_id"] is None or
        perfil["cliente_id"] == cliente_id_unico
    )


def _nuevo_vencimiento_extension_nube(fecha_vencimiento, dias):
    fecha_actual = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
    base = max(fecha_actual, datetime.now().date())
    return (base + timedelta(days=dias)).strftime("%Y-%m-%d")


def _estado_destino_extension_nube(fecha_vencimiento):
    try:
        fecha = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "vencida"
    if fecha == datetime.now().date():
        return "por_vencer"
    return calcular_estado_nube(fecha_vencimiento, estado_actual="activa")


def obtener_contexto_liberacion_perfil_nube(perfil_id):

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                p.id AS perfil_id,
                p.cliente_id,
                p.nombre_cliente AS cliente,
                p.telefono,
                p.fecha_entrega,
                p.dias_cuenta,
                p.nombre_perfil AS perfil,
                p.fecha_vencimiento AS vencimiento,
                p.estado,
                c.id AS cuenta_id,
                c.plataforma,
                c.correo AS cuenta_madre
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c
                ON c.id = p.cuenta_id
            WHERE p.id = ?
            """,
            (perfil_id,)
        )
        fila = cursor.fetchone()

        if not fila:
            return None

        contexto = dict(fila)
        contexto["dias_restantes"] = max(
            calcular_dias_restantes(contexto["vencimiento"]),
            0
        )
        contexto["asignado"] = es_asignacion_operativa_nube(
            contexto["cliente"],
            contexto["fecha_entrega"],
            contexto["dias_cuenta"],
            contexto["vencimiento"]
        )
        contexto["perfiles_destino"] = []
        contexto["plataformas_destino"] = []
        contexto["servicios_activos_cliente"] = []

        if contexto["asignado"] and contexto["dias_restantes"] > 0:
            cursor.execute(
                """
                SELECT
                    p.id AS perfil_id,
                    p.cuenta_id,
                    p.nombre_perfil,
                    p.pin,
                    c.plataforma,
                    c.correo
                FROM nube_perfiles AS p
                INNER JOIN nube_cuentas AS c
                    ON c.id = p.cuenta_id
                WHERE p.estado = 'disponible'
                  AND p.id != ?
                  AND c.modalidad = 'perfiles'
                  AND COALESCE(c.estado, '') NOT IN (
                        'caida', 'papelera', 'reemplazada', 'garantia'
                  )
                ORDER BY
                    LOWER(TRIM(c.plataforma)),
                    c.id,
                    p.orden,
                    p.id
                """,
                (perfil_id,)
            )
            candidatos = [dict(fila) for fila in cursor.fetchall()]
            contexto["perfiles_destino"] = (
                _enriquecer_recomendaciones_perfiles_nube(
                    cursor,
                    candidatos,
                    contexto["vencimiento"]
                )
            )
            contexto["plataformas_destino"] = sorted(
                {
                    candidato["plataforma"]
                    for candidato in contexto["perfiles_destino"]
                    if (candidato["plataforma"] or "").strip()
                },
                key=lambda plataforma: plataforma.casefold()
            )

            identidad = _identidad_cliente_servicio_nube(cursor, contexto)
            if identidad:
                cursor.execute(
                    """
                    SELECT
                        p.id AS perfil_id,
                        p.cuenta_id,
                        p.cliente_id,
                        p.telefono,
                        p.nombre_perfil,
                        p.pin,
                        p.fecha_entrega,
                        p.dias_cuenta,
                        p.fecha_vencimiento,
                        p.estado,
                        c.plataforma,
                        c.correo,
                        c.estado AS estado_cuenta
                    FROM nube_perfiles AS p
                    INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
                    WHERE p.id != ?
                      AND COALESCE(p.estado, '') NOT IN (
                            'caida', 'reemplazada', 'papelera',
                            'disponible', 'garantia', 'vencida'
                      )
                      AND COALESCE(c.estado, '') NOT IN (
                            'caida', 'papelera', 'reemplazada', 'garantia'
                      )
                    ORDER BY LOWER(TRIM(c.plataforma)), p.id
                    """,
                    (perfil_id,)
                )
                for candidato_fila in cursor.fetchall():
                    candidato = dict(candidato_fila)
                    estado = _estado_destino_extension_nube(
                        candidato["fecha_vencimiento"]
                    )
                    if estado not in {"activa", "por_vencer"}:
                        continue
                    if not es_asignacion_operativa_nube(
                        "cliente",
                        candidato["fecha_entrega"],
                        candidato["dias_cuenta"],
                        candidato["fecha_vencimiento"]
                    ):
                        continue
                    if not _servicio_pertenece_a_identidad_nube(
                        cursor, candidato, identidad
                    ):
                        continue
                    candidato["estado"] = estado
                    candidato["nuevo_vencimiento"] = (
                        _nuevo_vencimiento_extension_nube(
                            candidato["fecha_vencimiento"],
                            contexto["dias_restantes"]
                        )
                    )
                    contexto["servicios_activos_cliente"].append(candidato)
        return contexto
    finally:
        conn.close()


def liberar_perfil_nube(
    perfil_origen_id,
    motivo="",
    operacion_uuid=""
):

    motivo = (motivo or "").strip()
    operacion_uuid = (operacion_uuid or "").strip()

    if not operacion_uuid:
        return {
            "ok": False,
            "codigo": "operacion_uuid_requerido",
            "mensaje": "La operación necesita un identificador único."
        }

    conn = conectar()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                p.id,
                p.cuenta_id,
                p.cliente_id,
                p.nombre_cliente,
                p.telefono,
                p.fecha_entrega,
                p.dias_cuenta,
                p.fecha_vencimiento,
                p.estado
            FROM nube_perfiles AS p
            WHERE p.id = ?
            """,
            (perfil_origen_id,)
        )
        origen = cursor.fetchone()

        if not origen:
            raise ValueError("No se encontró el perfil de origen.")

        if not es_asignacion_operativa_nube(
            origen["nombre_cliente"],
            origen["fecha_entrega"],
            origen["dias_cuenta"],
            origen["fecha_vencimiento"]
        ):
            raise ValueError(
                "El perfil ya está disponible o no tiene una asignación real."
            )

        cliente_id_esperado = origen["cliente_id"]
        if cliente_id_esperado is None and origen["telefono"]:
            cliente_id_esperado = (
                _resolver_cliente_existente_por_telefono_nube(
                    cursor,
                    origen["nombre_cliente"],
                    origen["telefono"]
                )
            )
            if cliente_id_esperado is not None:
                cursor.execute(
                    """
                    UPDATE nube_perfiles
                    SET cliente_id = ?
                    WHERE id = ? AND cliente_id IS NULL
                    """,
                    (cliente_id_esperado, perfil_origen_id)
                )
        estado_esperado = origen["estado"] or ""
        dias_restantes = max(
            calcular_dias_restantes(origen["fecha_vencimiento"]),
            0
        )
        snapshot = _crear_snapshot_servicio_nube(
            cursor,
            perfil_origen_id
        )

        if not snapshot:
            raise ValueError("No se pudo crear el snapshot del servicio.")

        cursor.execute(
            """
            INSERT INTO nube_transferencias_servicios (
                operacion_uuid,
                tipo_operacion,
                perfil_origen_id,
                cuenta_origen_id,
                cliente_id,
                dias_disponibles,
                dias_trasladados,
                destino_tipo,
                perfil_destino_id,
                cuenta_destino_id,
                motivo,
                venta_origen_snapshot
            )
            VALUES (?, 'liberar', ?, ?, ?, ?, 0, '', NULL, NULL, ?, ?)
            """,
            (
                operacion_uuid,
                perfil_origen_id,
                origen["cuenta_id"],
                cliente_id_esperado,
                dias_restantes,
                motivo,
                snapshot
            )
        )

        cursor.execute(
            """
            UPDATE nube_perfiles
            SET
                cliente_id = NULL,
                nombre_cliente = '',
                telefono = '',
                fecha_entrega = '',
                dias_cuenta = 0,
                fecha_vencimiento = '',
                estado = 'disponible',
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
              AND (
                    cliente_id = ?
                    OR (cliente_id IS NULL AND ? IS NULL)
              )
              AND COALESCE(estado, '') = ?
            """,
            (
                perfil_origen_id,
                cliente_id_esperado,
                cliente_id_esperado,
                estado_esperado
            )
        )

        if cursor.rowcount != 1:
            raise RuntimeError(
                "El perfil cambió durante la operación; no fue liberado."
            )

        cursor.execute(
            """
            INSERT INTO nube_movimientos (
                cuenta_id,
                tipo,
                descripcion,
                estado_anterior,
                estado_nuevo,
                cliente_nombre
            )
            VALUES (?, 'liberacion_perfil', ?, ?, 'disponible', ?)
            """,
            (
                origen["cuenta_id"],
                "Perfil liberado sin trasladar días"
                + (f". Motivo: {motivo}" if motivo else ""),
                estado_esperado,
                origen["nombre_cliente"] or ""
            )
        )

        conn.commit()
        return {
            "ok": True,
            "mensaje": "Perfil liberado correctamente.",
            "perfil_id": perfil_origen_id,
            "dias_restantes": dias_restantes,
            "estado": "disponible"
        }

    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "operacion_uuid" in str(error).lower():
            return {
                "ok": False,
                "codigo": "operacion_duplicada",
                "mensaje": "Esta liberación ya fue procesada."
            }
        return {
            "ok": False,
            "codigo": "error_integridad",
            "mensaje": "No se pudo guardar la liberación."
        }
    except (ValueError, RuntimeError) as error:
        conn.rollback()
        return {
            "ok": False,
            "codigo": "origen_no_valido",
            "mensaje": str(error)
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def liberar_o_trasladar_perfil_nube(
    perfil_origen_id,
    accion="liberar",
    perfil_destino_id=None,
    dias_trasladar=None,
    motivo="",
    operacion_uuid=""
):

    if accion == "liberar":
        return liberar_perfil_nube(
            perfil_origen_id=perfil_origen_id,
            motivo=motivo,
            operacion_uuid=operacion_uuid
        )

    if accion == "sumar_activo":
        return _sumar_dias_servicio_activo_nube(
            perfil_origen_id=perfil_origen_id,
            perfil_destino_id=perfil_destino_id,
            dias_trasladar=dias_trasladar,
            motivo=motivo,
            operacion_uuid=operacion_uuid
        )

    if accion != "trasladar_nuevo":
        return {
            "ok": False,
            "codigo": "accion_no_valida",
            "mensaje": "La acción solicitada no es válida."
        }

    motivo = (motivo or "").strip()
    operacion_uuid = (operacion_uuid or "").strip()

    try:
        perfil_origen_id = int(perfil_origen_id)
        perfil_destino_id = int(perfil_destino_id)
        dias_trasladar = int(dias_trasladar)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "codigo": "datos_no_validos",
            "mensaje": "Selecciona un destino y una cantidad de días válidos."
        }

    if not operacion_uuid:
        return {
            "ok": False,
            "codigo": "operacion_uuid_requerido",
            "mensaje": "La operación necesita un identificador único."
        }

    if (
        perfil_origen_id <= 0 or
        perfil_destino_id <= 0 or
        perfil_origen_id == perfil_destino_id
    ):
        return {
            "ok": False,
            "codigo": "destino_no_valido",
            "mensaje": "Selecciona un perfil de destino diferente y válido."
        }

    conn = conectar()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT
                p.id,
                p.cuenta_id,
                p.cliente_id,
                p.nombre_cliente,
                p.telefono,
                p.fecha_entrega,
                p.dias_cuenta,
                p.fecha_vencimiento,
                p.estado,
                p.nombre_perfil,
                c.plataforma
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
            WHERE p.id = ?
            """,
            (perfil_origen_id,)
        )
        origen = cursor.fetchone()

        if not origen or not es_asignacion_operativa_nube(
            origen["nombre_cliente"],
            origen["fecha_entrega"],
            origen["dias_cuenta"],
            origen["fecha_vencimiento"]
        ):
            raise ValueError(
                "El perfil de origen ya está disponible o no tiene una asignación real."
            )

        dias_restantes = max(
            calcular_dias_restantes(origen["fecha_vencimiento"]),
            0
        )
        if dias_trasladar < 1 or dias_trasladar > dias_restantes:
            raise ValueError(
                f"Los días a trasladar deben estar entre 1 y {dias_restantes}."
            )

        cliente_id = origen["cliente_id"]
        if cliente_id is None and origen["telefono"]:
            cliente_id = _obtener_o_crear_cliente_nube(
                cursor,
                origen["nombre_cliente"],
                origen["telefono"]
            )
            if cliente_id is not None:
                cursor.execute(
                    """
                    UPDATE nube_perfiles
                    SET cliente_id = ?
                    WHERE id = ? AND cliente_id IS NULL
                    """,
                    (cliente_id, perfil_origen_id)
                )

        cursor.execute(
            """
            SELECT
                p.id,
                p.cuenta_id,
                p.estado,
                p.nombre_perfil,
                p.pin,
                c.plataforma,
                c.modalidad,
                c.estado AS estado_cuenta
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
            WHERE p.id = ?
            """,
            (perfil_destino_id,)
        )
        destino = cursor.fetchone()

        if not destino:
            raise ValueError("No se encontró el perfil de destino.")
        if destino["estado"] != "disponible":
            raise ValueError("El perfil de destino ya no está disponible.")
        if destino["modalidad"] != "perfiles" or (
            destino["estado_cuenta"] or ""
        ) in {"caida", "papelera", "reemplazada", "garantia"}:
            raise ValueError("La cuenta madre de destino ya no es utilizable.")

        snapshot_origen = _crear_snapshot_servicio_nube(
            cursor,
            perfil_origen_id
        )
        snapshot_destino_antes = _crear_snapshot_servicio_nube(
            cursor,
            perfil_destino_id
        )
        if not snapshot_origen or not snapshot_destino_antes:
            raise RuntimeError("No se pudieron crear los snapshots previos.")

        fecha_entrega = datetime.now().date().strftime("%Y-%m-%d")
        fecha_vencimiento = calcular_fecha_vencimiento(
            fecha_entrega,
            dias_trasladar
        )
        estado_destino = calcular_estado_nube(
            fecha_vencimiento,
            estado_actual="activa"
        )

        cursor.execute(
            """
            UPDATE nube_perfiles
            SET
                cliente_id = ?,
                nombre_cliente = ?,
                telefono = ?,
                fecha_entrega = ?,
                dias_cuenta = ?,
                fecha_vencimiento = ?,
                estado = ?,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
              AND estado = 'disponible'
            """,
            (
                cliente_id,
                origen["nombre_cliente"],
                origen["telefono"],
                fecha_entrega,
                dias_trasladar,
                fecha_vencimiento,
                estado_destino,
                perfil_destino_id
            )
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                "El perfil de destino cambió durante la operación."
            )

        snapshot_destino_despues = _crear_snapshot_servicio_nube(
            cursor,
            perfil_destino_id
        )
        if not snapshot_destino_despues:
            raise RuntimeError("No se pudo crear el snapshot final del destino.")

        cursor.execute(
            """
            INSERT INTO nube_transferencias_servicios (
                operacion_uuid,
                tipo_operacion,
                perfil_origen_id,
                cuenta_origen_id,
                cliente_id,
                dias_disponibles,
                dias_trasladados,
                destino_tipo,
                perfil_destino_id,
                cuenta_destino_id,
                motivo,
                venta_origen_snapshot,
                destino_antes_snapshot,
                destino_despues_snapshot
            )
            VALUES (?, 'trasladar_nuevo', ?, ?, ?, ?, ?, 'perfil', ?, ?, ?, ?, ?, ?)
            """,
            (
                operacion_uuid,
                perfil_origen_id,
                origen["cuenta_id"],
                cliente_id,
                dias_restantes,
                dias_trasladar,
                perfil_destino_id,
                destino["cuenta_id"],
                motivo,
                snapshot_origen,
                snapshot_destino_antes,
                snapshot_destino_despues
            )
        )

        cursor.execute(
            """
            UPDATE nube_perfiles
            SET
                cliente_id = NULL,
                nombre_cliente = '',
                telefono = '',
                fecha_entrega = '',
                dias_cuenta = 0,
                fecha_vencimiento = '',
                estado = 'disponible',
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
              AND COALESCE(estado, '') = ?
              AND (
                    cliente_id = ?
                    OR (cliente_id IS NULL AND ? IS NULL)
              )
            """,
            (
                perfil_origen_id,
                origen["estado"] or "",
                cliente_id,
                cliente_id
            )
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                "El perfil de origen cambió durante la operación."
            )

        descripcion = (
            f"{origen['plataforma']} · {origen['nombre_perfil']} trasladado a "
            f"{destino['plataforma']} · {destino['nombre_perfil']} "
            f"con {dias_trasladar} días"
        )
        if motivo:
            descripcion += f" · Motivo: {motivo}"

        cursor.executemany(
            """
            INSERT INTO nube_movimientos (
                cuenta_id,
                tipo,
                descripcion,
                estado_anterior,
                estado_nuevo,
                cliente_nombre
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    origen["cuenta_id"],
                    "traslado_servicio_origen",
                    descripcion,
                    origen["estado"] or "",
                    "disponible",
                    origen["nombre_cliente"] or ""
                ),
                (
                    destino["cuenta_id"],
                    "traslado_servicio_destino",
                    descripcion,
                    "disponible",
                    estado_destino,
                    origen["nombre_cliente"] or ""
                )
            ]
        )

        datos_entrega = _obtener_datos_entrega_perfil_nube(
            cursor,
            perfil_destino_id
        )
        datos_entrega.update({
            "plataforma_origen": origen["plataforma"] or "",
            "plataforma_destino": destino["plataforma"] or "",
            "dias_trasladados": dias_trasladar
        })

        conn.commit()
        return {
            "ok": True,
            "mensaje": "Servicio cambiado correctamente.",
            "perfil_origen_id": perfil_origen_id,
            "perfil_destino_id": perfil_destino_id,
            "dias_disponibles": dias_restantes,
            "dias_trasladados": dias_trasladar,
            "fecha_vencimiento": fecha_vencimiento,
            "estado": estado_destino,
            "datos_entrega": datos_entrega
        }

    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "operacion_uuid" in str(error).lower():
            return {
                "ok": False,
                "codigo": "operacion_duplicada",
                "mensaje": "Esta operación ya fue procesada."
            }
        return {
            "ok": False,
            "codigo": "error_integridad",
            "mensaje": "No se pudo guardar el cambio de servicio."
        }
    except (ValueError, RuntimeError) as error:
        conn.rollback()
        return {
            "ok": False,
            "codigo": "transferencia_no_valida",
            "mensaje": str(error)
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def registrar_no_renovacion_perfil_nube(perfil_id, operacion_uuid=""):
    """Cierra una venta no renovada y conserva su snapshot en el historial."""
    try:
        perfil_id = int(perfil_id)
    except (TypeError, ValueError):
        return {"ok": False, "codigo": "perfil_invalido",
                "mensaje": "No se pudo identificar el perfil."}
    operacion_uuid = (operacion_uuid or "").strip()
    if perfil_id <= 0 or not operacion_uuid:
        return {"ok": False, "codigo": "datos_invalidos",
                "mensaje": "La operación no es válida."}

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("""
            SELECT id, cuenta_id, cliente_id, nombre_cliente, telefono,
                   fecha_entrega, dias_cuenta, fecha_vencimiento, estado
            FROM nube_perfiles WHERE id=?
        """, (perfil_id,))
        perfil = cursor.fetchone()
        if not perfil:
            raise ValueError("No se encontró el perfil.")
        estado = (perfil["estado"] or "").strip().lower()
        asignado = es_asignacion_operativa_nube(
            perfil["nombre_cliente"], perfil["fecha_entrega"],
            perfil["dias_cuenta"], perfil["fecha_vencimiento"]
        )
        if estado == "disponible" and not asignado:
            conn.rollback()
            return {"ok": True, "duplicado": True, "perfil_id": perfil_id,
                    "estado": "disponible",
                    "mensaje": "La no renovación ya fue procesada."}
        if estado in {"reemplazada", "papelera", "garantia", "caida"}:
            raise ValueError("El estado actual del perfil no permite marcar no renovación.")
        if not asignado:
            raise ValueError("El perfil no tiene una asignación operativa real.")

        snapshot = _crear_snapshot_servicio_nube(cursor, perfil_id)
        if not snapshot:
            raise RuntimeError("No se pudo crear el snapshot previo del servicio.")
        dias_restantes = max(calcular_dias_restantes(perfil["fecha_vencimiento"]), 0)
        cursor.execute("""
            INSERT INTO nube_transferencias_servicios (
                operacion_uuid, tipo_operacion, perfil_origen_id,
                cuenta_origen_id, cliente_id, dias_disponibles,
                dias_trasladados, destino_tipo, perfil_destino_id,
                cuenta_destino_id, motivo, venta_origen_snapshot
            ) VALUES (?, 'no_renovo', ?, ?, ?, ?, 0, '', NULL, NULL,
                      'Cliente no renovó el servicio', ?)
        """, (operacion_uuid, perfil_id, perfil["cuenta_id"],
              perfil["cliente_id"], dias_restantes, snapshot))
        cursor.execute("""
            UPDATE nube_perfiles SET cliente_id=NULL, nombre_cliente='',
                telefono='', fecha_entrega='', dias_cuenta=0,
                fecha_vencimiento='', estado='disponible',
                fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=? AND COALESCE(estado, '')=?
        """, (perfil_id, perfil["estado"] or ""))
        if cursor.rowcount != 1:
            raise RuntimeError("El perfil cambió durante la operación.")
        cursor.execute("""
            INSERT INTO nube_movimientos (
                cuenta_id, tipo, descripcion, estado_anterior,
                estado_nuevo, cliente_nombre
            ) VALUES (?, 'servicio_no_renovado', ?, ?, 'disponible', ?)
        """, (perfil["cuenta_id"],
              "Servicio no renovado; el perfil volvió a estar disponible",
              perfil["estado"] or "", perfil["nombre_cliente"] or ""))
        conn.commit()
        return {"ok": True, "duplicado": False, "perfil_id": perfil_id,
                "estado": "disponible",
                "mensaje": "Servicio marcado como no renovado."}
    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "operacion_uuid" in str(error).lower() or "unique" in str(error).lower():
            return {"ok": True, "duplicado": True, "perfil_id": perfil_id,
                    "mensaje": "La no renovación ya fue procesada."}
        raise
    except (ValueError, RuntimeError) as error:
        conn.rollback()
        return {"ok": False, "codigo": "perfil_no_elegible", "mensaje": str(error)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sumar_dias_servicio_activo_nube(
    perfil_origen_id,
    perfil_destino_id,
    dias_trasladar,
    motivo="",
    operacion_uuid=""
):
    motivo = (motivo or "").strip()
    operacion_uuid = (operacion_uuid or "").strip()
    try:
        perfil_origen_id = int(perfil_origen_id)
        perfil_destino_id = int(perfil_destino_id)
        dias_trasladar = int(dias_trasladar)
    except (TypeError, ValueError):
        return {"ok": False, "codigo": "datos_no_validos",
                "mensaje": "Selecciona un destino y una cantidad de días válidos."}

    if not operacion_uuid:
        return {"ok": False, "codigo": "operacion_uuid_requerido",
                "mensaje": "La operación necesita un identificador único."}
    if perfil_origen_id <= 0 or perfil_destino_id <= 0 or perfil_origen_id == perfil_destino_id:
        return {"ok": False, "codigo": "destino_no_valido",
                "mensaje": "Selecciona un servicio activo de destino diferente."}

    conn = conectar()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT 1 FROM nube_transferencias_servicios WHERE operacion_uuid = ?",
            (operacion_uuid,)
        )
        if cursor.fetchone():
            raise sqlite3.IntegrityError("operacion_uuid UNIQUE")
        cursor.execute(
            """
            SELECT p.*, c.plataforma
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
            WHERE p.id = ?
            """, (perfil_origen_id,)
        )
        origen = cursor.fetchone()
        if not origen or not es_asignacion_operativa_nube(
            origen["nombre_cliente"], origen["fecha_entrega"],
            origen["dias_cuenta"], origen["fecha_vencimiento"]
        ):
            raise ValueError("El perfil de origen ya no tiene una asignación válida.")

        identidad = _identidad_cliente_servicio_nube(cursor, origen)
        if not identidad:
            raise ValueError("No se pudo identificar al cliente de forma inequívoca.")
        dias_restantes = max(calcular_dias_restantes(origen["fecha_vencimiento"]), 0)
        if dias_trasladar < 1 or dias_trasladar > dias_restantes:
            raise ValueError(
                f"Los días a trasladar deben estar entre 1 y {dias_restantes}."
            )

        cursor.execute(
            """
            SELECT p.*, c.plataforma, c.correo,
                   c.contrasena, c.estado AS estado_cuenta
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
            WHERE p.id = ?
            """, (perfil_destino_id,)
        )
        destino = cursor.fetchone()
        if not destino:
            raise ValueError("No se encontró el servicio activo de destino.")
        if not _servicio_pertenece_a_identidad_nube(cursor, destino, identidad):
            raise ValueError("El servicio de destino no pertenece al mismo cliente.")
        if (destino["estado"] or "") in {
            "caida", "reemplazada", "papelera", "disponible", "garantia", "vencida"
        }:
            raise ValueError("El servicio de destino no está activo.")
        estado_calculado = _estado_destino_extension_nube(
            destino["fecha_vencimiento"]
        )
        if estado_calculado not in {"activa", "por_vencer"}:
            raise ValueError("El servicio de destino no está activo.")
        if (destino["estado_cuenta"] or "") in {
            "caida", "papelera", "reemplazada", "garantia"
        }:
            raise ValueError("La cuenta madre de destino no es utilizable.")
        if not es_asignacion_operativa_nube(
            destino["nombre_cliente"], destino["fecha_entrega"],
            destino["dias_cuenta"], destino["fecha_vencimiento"]
        ):
            raise ValueError("El servicio de destino no tiene una asignación válida.")

        snapshot_origen = _crear_snapshot_servicio_nube(cursor, perfil_origen_id)
        snapshot_destino_antes = _crear_snapshot_servicio_nube(cursor, perfil_destino_id)
        if not snapshot_origen or not snapshot_destino_antes:
            raise RuntimeError("No se pudieron crear los snapshots previos.")

        nuevo_vencimiento = _nuevo_vencimiento_extension_nube(
            destino["fecha_vencimiento"], dias_trasladar
        )
        nuevo_estado = calcular_estado_nube(nuevo_vencimiento, estado_actual="activa")
        cursor.execute(
            """
            UPDATE nube_perfiles
            SET fecha_vencimiento = ?, estado = ?,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ? AND fecha_vencimiento = ? AND COALESCE(estado, '') = ?
            """,
            (nuevo_vencimiento, nuevo_estado, perfil_destino_id,
             destino["fecha_vencimiento"], destino["estado"] or "")
        )
        if cursor.rowcount != 1:
            raise RuntimeError("El servicio de destino cambió durante la operación.")
        snapshot_destino_despues = _crear_snapshot_servicio_nube(cursor, perfil_destino_id)
        if not snapshot_destino_despues:
            raise RuntimeError("No se pudo crear el snapshot final del destino.")

        cliente_id_historial = (
            identidad["valor"] if identidad["tipo"] == "cliente_id"
            else identidad.get("cliente_id_unico")
        )
        cursor.execute(
            """
            INSERT INTO nube_transferencias_servicios (
                operacion_uuid, tipo_operacion, perfil_origen_id,
                cuenta_origen_id, cliente_id, dias_disponibles,
                dias_trasladados, destino_tipo, perfil_destino_id,
                cuenta_destino_id, motivo, venta_origen_snapshot,
                destino_antes_snapshot, destino_despues_snapshot
            ) VALUES (?, 'sumar_activo', ?, ?, ?, ?, ?, 'perfil', ?, ?, ?, ?, ?, ?)
            """,
            (operacion_uuid, perfil_origen_id, origen["cuenta_id"],
             cliente_id_historial, dias_restantes, dias_trasladar,
             perfil_destino_id, destino["cuenta_id"], motivo,
             snapshot_origen, snapshot_destino_antes, snapshot_destino_despues)
        )

        cursor.execute(
            """
            UPDATE nube_perfiles
            SET cliente_id = NULL, nombre_cliente = '', telefono = '',
                fecha_entrega = '', dias_cuenta = 0, fecha_vencimiento = '',
                estado = 'disponible', fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ? AND COALESCE(estado, '') = ?
              AND COALESCE(fecha_vencimiento, '') = ?
            """,
            (perfil_origen_id, origen["estado"] or "", origen["fecha_vencimiento"] or "")
        )
        if cursor.rowcount != 1:
            raise RuntimeError("El perfil de origen cambió durante la operación.")

        descripcion = (
            f"{dias_trasladar} días de {origen['plataforma']} · "
            f"{origen['nombre_perfil']} sumados a {destino['plataforma']} · "
            f"{destino['nombre_perfil']}"
        ) + (f" · Motivo: {motivo}" if motivo else "")
        cursor.executemany(
            """
            INSERT INTO nube_movimientos (
                cuenta_id, tipo, descripcion, estado_anterior,
                estado_nuevo, cliente_nombre
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (origen["cuenta_id"], "traslado_dias_origen", descripcion,
                 origen["estado"] or "", "disponible", origen["nombre_cliente"] or ""),
                (destino["cuenta_id"], "suma_dias_destino", descripcion,
                 destino["estado"] or "", nuevo_estado, destino["nombre_cliente"] or "")
            ]
        )
        datos_entrega = _obtener_datos_entrega_perfil_nube(cursor, perfil_destino_id)
        datos_entrega.update({
            "plataforma_origen": origen["plataforma"] or "",
            "plataforma_destino": destino["plataforma"] or "",
            "dias_trasladados": dias_trasladar,
            "vencimiento_anterior": destino["fecha_vencimiento"] or "",
            "nuevo_vencimiento": nuevo_vencimiento
        })
        conn.commit()
        return {
            "ok": True, "mensaje": "Días trasladados correctamente.",
            "perfil_origen_id": perfil_origen_id,
            "perfil_destino_id": perfil_destino_id,
            "dias_disponibles": dias_restantes,
            "dias_trasladados": dias_trasladar,
            "fecha_vencimiento": nuevo_vencimiento,
            "estado": nuevo_estado, "datos_entrega": datos_entrega
        }
    except sqlite3.IntegrityError as error:
        conn.rollback()
        if "operacion_uuid" in str(error).lower():
            return {"ok": False, "codigo": "operacion_duplicada",
                    "mensaje": "Esta operación ya fue procesada."}
        return {"ok": False, "codigo": "error_integridad",
                "mensaje": "No se pudo guardar el traslado de días."}
    except (ValueError, RuntimeError) as error:
        conn.rollback()
        return {"ok": False, "codigo": "transferencia_no_valida", "mensaje": str(error)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def calcular_estado_nube(
    fecha_vencimiento,
    estado_actual="disponible"
):

    estados_manuales = {
        "disponible",
        "caida",
        "garantia",
        "reemplazada",
        "papelera"
    }


    if estado_actual in estados_manuales:

        return estado_actual


    dias_restantes = (
        calcular_dias_restantes(
            fecha_vencimiento
        )
    )


    if dias_restantes <= 0:

        return "vencida"


    if dias_restantes <= 3:

        return "por_vencer"


    return "activa"


def calcular_estado_efectivo_cuenta_nube(
    fecha_vencimiento,
    estado_actual="disponible",
    modalidad="cuenta_completa",
    perfiles_disponibles=0,
    perfiles_ocupados=0
):

    estado_actual = estado_actual or "disponible"

    if estado_actual in {
        "caida",
        "papelera",
        "reemplazada"
    }:
        return estado_actual

    if modalidad == "perfiles":

        if perfiles_disponibles > 0:
            return "disponible"

        if perfiles_ocupados > 0:
            return "activa"

    if estado_actual in {
        "activa",
        "por_vencer",
        "vencida"
    }:
        return calcular_estado_nube(
            fecha_vencimiento,
            estado_actual=estado_actual
        )

    return estado_actual

# ==========================================
# NUBE DE CUENTAS — CREAR CUENTA
# ==========================================

def crear_cuenta_nube(
    plataforma,
    correo,
    contrasena="",
    pin="",
    tipo_cuenta="",
    nombre_cliente="",
    telefono="",
    fecha_entrega="",
    dias_cuenta=0,
    estado="disponible",
    notas="",
    origen="manual",
    modalidad="cuenta_completa",
    cantidad_perfiles=0,
    tipo_pago="",
    valor_pin=0,
    plan_pago="",
    precio_plan_referencia=0,
    fecha_aplicacion_pin="",
    pines_perfiles=None,
    duracion_unidad_dias=None
):

    conn = conectar()
    cursor = conn.cursor()


    # ==========================================
    # LIMPIAR DATOS GENERALES
    # ==========================================

    plataforma = (
        plataforma or ""
    ).strip()

    correo = (
        correo or ""
    ).strip()

    contrasena = (
        contrasena or ""
    ).strip()

    pin = (
        pin or ""
    ).strip()

    tipo_cuenta = (
        tipo_cuenta or ""
    ).strip()

    nombre_cliente = (
        nombre_cliente or ""
    ).strip()

    telefono = (
        telefono or ""
    ).strip()

    fecha_entrega = (
        fecha_entrega or ""
    ).strip()

    notas = (
        notas or ""
    ).strip()

    origen = (
        origen or "manual"
    ).strip()

    modalidad = (
        modalidad or
        "cuenta_completa"
    ).strip()

    tipo_pago = (
        tipo_pago or ""
    ).strip().lower()

    plan_pago = (
        plan_pago or ""
    ).strip()

    fecha_aplicacion_pin = (
        fecha_aplicacion_pin or ""
    ).strip()


    # ==========================================
    # CONVERTIR NÚMEROS
    # ==========================================

    try:

        dias_cuenta = int(
            dias_cuenta or 0
        )

    except (
        ValueError,
        TypeError
    ):

        dias_cuenta = 0


    try:

        cantidad_perfiles = int(
            cantidad_perfiles or 0
        )

    except (
        ValueError,
        TypeError
    ):

        cantidad_perfiles = 0

    try:
        duracion_unidad_dias = validar_duracion_unidad_inventario(
            plataforma, modalidad, duracion_unidad_dias, cursor=cursor
        )
    except ValueError:
        conn.close()
        raise


    if cantidad_perfiles < 0:
        cantidad_perfiles = 0


    try:

        valor_pin = int(
            valor_pin or 0
        )

    except (
        ValueError,
        TypeError
    ):

        valor_pin = 0


    try:

        precio_plan_referencia = int(
            precio_plan_referencia or 0
        )

    except (
        ValueError,
        TypeError
    ):

        precio_plan_referencia = 0


    # ==========================================
    # VENCIMIENTO DEL CLIENTE / SERVICIO
    # ==========================================

    fecha_vencimiento = ""


    if (
        fecha_entrega and
        dias_cuenta > 0
    ):

        fecha_vencimiento = (
            calcular_fecha_vencimiento(
                fecha_entrega,
                dias_cuenta
            )
        )


    if (
        nombre_cliente or
        telefono or
        fecha_entrega
    ):

        estado = calcular_estado_nube(
            fecha_vencimiento,
            estado_actual="activa"
        )

    else:

        estado = "disponible"


    # ==========================================
    # CONTROL DE PAGO PIN
    # ==========================================

    dias_estimados_pin = 0
    fecha_proximo_pago = ""


    if tipo_pago == "pin":

        dias_estimados_pin = (
            calcular_dias_pin_nube(
                valor_pin,
                precio_plan_referencia
            )
        )


        fecha_proximo_pago = (
            calcular_fecha_pago_pin_nube(
                fecha_aplicacion_pin,
                dias_estimados_pin
            )
        )


    elif tipo_pago == "autopagable":

        valor_pin = 0
        plan_pago = ""
        precio_plan_referencia = 0
        fecha_aplicacion_pin = ""
        dias_estimados_pin = 0
        fecha_proximo_pago = ""


    else:

        tipo_pago = ""
        valor_pin = 0
        plan_pago = ""
        precio_plan_referencia = 0
        fecha_aplicacion_pin = ""
        dias_estimados_pin = 0
        fecha_proximo_pago = ""


    # ==========================================
    # GUARDAR CUENTA MADRE
    # ==========================================

    cursor.execute(
        """
        INSERT INTO nube_cuentas (

            plataforma,
            correo,
            contrasena,
            pin,
            tipo_cuenta,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            notas,
            origen,
            modalidad,
            cantidad_perfiles,
            tipo_pago,
            valor_pin,
            plan_pago,
            precio_plan_referencia,
            fecha_aplicacion_pin,
            dias_estimados_pin,
            fecha_proximo_pago
            ,duracion_unidad_dias

        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            plataforma,
            correo,
            contrasena,
            pin,
            tipo_cuenta,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            notas,
            origen,
            modalidad,
            cantidad_perfiles,
            tipo_pago,
            valor_pin,
            plan_pago,
            precio_plan_referencia,
            fecha_aplicacion_pin,
            dias_estimados_pin,
            fecha_proximo_pago,
            duracion_unidad_dias
        )
    )


    cuenta_id = cursor.lastrowid


    # ==========================================
    # HISTORIAL GENERAL
    # ==========================================

    cursor.execute(
        """
        INSERT INTO nube_movimientos (

            cuenta_id,
            tipo,
            descripcion,
            estado_nuevo,
            cliente_nombre

        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            cuenta_id,
            "creacion",
            "Cuenta creada en la Nube",
            estado,
            nombre_cliente
        )
    )


    # ==========================================
    # HISTORIAL DEL PRIMER PIN
    # ==========================================

    if (
        tipo_pago == "pin" and
        valor_pin > 0 and
        fecha_aplicacion_pin
    ):

        cursor.execute(
            """
            INSERT INTO nube_pagos_pin (

                cuenta_id,
                valor_pin,
                plan,
                precio_plan_referencia,
                fecha_aplicacion,
                dias_estimados,
                fecha_estimada_fin

            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cuenta_id,
                valor_pin,
                plan_pago,
                precio_plan_referencia,
                fecha_aplicacion_pin,
                dias_estimados_pin,
                fecha_proximo_pago
            )
        )


    conn.commit()
    conn.close()


    # ==========================================
    # GENERAR PERFILES
    # ==========================================

    if (
        modalidad == "perfiles" and
        cantidad_perfiles > 0
    ):

        generar_perfiles_nube(
            cuenta_id,
            cantidad_perfiles,
            pines_perfiles
        )


    return cuenta_id


def asignar_cuenta_completa_nube(
    cuenta_id,
    nombre_cliente="",
    telefono="",
    fecha_entrega="",
    dias_cuenta=0,
    notas=""
):
    conn = conectar()
    cursor = conn.cursor()

    nombre_cliente = (nombre_cliente or "").strip()
    telefono = (telefono or "").strip()
    fecha_entrega = (fecha_entrega or "").strip()
    notas = (notas or "").strip()

    try:
        cuenta_id = int(cuenta_id)
        dias_cuenta = int(dias_cuenta or 0)
    except (TypeError, ValueError):
        conn.close()
        return {"ok": False, "mensaje": "Datos inválidos para asignar la cuenta."}

    if not nombre_cliente or not fecha_entrega or dias_cuenta <= 0:
        conn.close()
        return {"ok": False, "mensaje": "Cliente, entrega y días son obligatorios."}

    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor.execute(
            """
            SELECT id, plataforma, correo, contrasena, pin, modalidad, estado,
                   nombre_cliente, fecha_entrega, dias_cuenta, fecha_vencimiento
            FROM nube_cuentas
            WHERE id = ?
            """,
            (cuenta_id,)
        )
        cuenta = cursor.fetchone()

        if not cuenta:
            conn.rollback()
            return {"ok": False, "mensaje": "La cuenta no existe."}

        if (cuenta["modalidad"] or "cuenta_completa") == "perfiles":
            conn.rollback()
            return {"ok": False, "mensaje": "Esta acción solo aplica a cuentas completas."}

        if cuenta["estado"] in {"caida", "papelera", "reemplazada"}:
            conn.rollback()
            return {"ok": False, "mensaje": "La cuenta no puede asignarse en su estado actual."}

        ya_asignada = es_asignacion_operativa_nube(
            cuenta["nombre_cliente"],
            cuenta["fecha_entrega"],
            cuenta["dias_cuenta"],
            cuenta["fecha_vencimiento"]
        )
        if ya_asignada:
            conn.rollback()
            return {"ok": False, "mensaje": "La cuenta ya tiene una asignación operativa."}

        cliente_id = _obtener_o_crear_cliente_nube(cursor, nombre_cliente, telefono)
        fecha_vencimiento = calcular_fecha_vencimiento(fecha_entrega, dias_cuenta)
        estado = calcular_estado_nube(fecha_vencimiento, estado_actual="activa")

        cursor.execute(
            """
            UPDATE nube_cuentas
            SET cliente_id = ?, nombre_cliente = ?, telefono = ?,
                fecha_entrega = ?, dias_cuenta = ?, fecha_vencimiento = ?,
                estado = ?, notas = ?, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                cliente_id, nombre_cliente, telefono, fecha_entrega,
                dias_cuenta, fecha_vencimiento, estado, notas, cuenta_id
            )
        )

        cursor.execute(
            """
            INSERT INTO nube_movimientos (
                cuenta_id, tipo, descripcion, estado_anterior, estado_nuevo,
                cliente_nombre
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cuenta_id,
                "asignacion_cuenta_completa",
                "Cuenta completa asignada a cliente",
                cuenta["estado"] or "disponible",
                estado,
                nombre_cliente
            )
        )

        conn.commit()
        return {
            "ok": True,
            "cuenta_id": cuenta_id,
            "estado": estado,
            "fecha_vencimiento": fecha_vencimiento,
            "datos_entrega": {
                "plataforma": cuenta["plataforma"] or "",
                "correo": cuenta["correo"] or "",
                "contrasena": cuenta["contrasena"] or "",
                "pin": cuenta["pin"] or "",
                "cliente": nombre_cliente,
                "telefono": telefono,
                "fecha_vencimiento": fecha_vencimiento
            }
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def crear_cuentas_nube_lote(
    plataforma,
    modalidad,
    tipo_pago,
    plan_pago,
    cantidad_perfiles,
    credenciales,
    valor_pin=0,
    precio_plan_referencia=0,
    fecha_aplicacion_pin="",
    duracion_unidad_dias=None
):
    conn = conectar()
    cursor = conn.cursor()

    plataforma = (plataforma or "").strip()
    modalidad = (modalidad or "cuenta_completa").strip()
    tipo_pago = (tipo_pago or "").strip().lower()
    plan_pago = (plan_pago or "").strip()
    fecha_aplicacion_pin = (fecha_aplicacion_pin or "").strip()

    try:
        cantidad_perfiles = int(cantidad_perfiles or 0)
        valor_pin = int(valor_pin or 0)
        precio_plan_referencia = int(precio_plan_referencia or 0)
    except (TypeError, ValueError):
        conn.close()
        return {"ok": False, "mensaje": "Configuración numérica inválida."}

    if not plataforma:
        conn.close()
        return {"ok": False, "mensaje": "Selecciona una plataforma."}

    if modalidad not in {"perfiles", "cuenta_completa"}:
        conn.close()
        return {"ok": False, "mensaje": "Modalidad inválida."}

    try:
        duracion_unidad_dias = validar_duracion_unidad_inventario(
            plataforma, modalidad, duracion_unidad_dias, cursor=cursor
        )
    except ValueError as error:
        conn.close()
        return {"ok": False, "mensaje": str(error)}

    if modalidad == "perfiles" and not (1 <= cantidad_perfiles <= 10):
        conn.close()
        return {"ok": False, "mensaje": "La cantidad de perfiles debe estar entre 1 y 10."}

    if not credenciales:
        conn.close()
        return {"ok": False, "mensaje": "No hay credenciales válidas para crear."}

    if tipo_pago == "pin" and (
        valor_pin <= 0 or
        not plan_pago or
        precio_plan_referencia <= 0 or
        not fecha_aplicacion_pin
    ):
        conn.close()
        return {
            "ok": False,
            "mensaje": "Para carga PIN debes indicar valor, plan, precio mensual y fecha de aplicación."
        }

    correos = [item["correo"] for item in credenciales]
    placeholders = ",".join("?" for _ in correos)
    cursor.execute(
        f"SELECT LOWER(correo) AS correo FROM nube_cuentas WHERE LOWER(correo) IN ({placeholders})",
        tuple(correo.lower() for correo in correos)
    )
    duplicados = {fila["correo"] for fila in cursor.fetchall()}
    if duplicados:
        conn.close()
        return {
            "ok": False,
            "mensaje": "Hay correos duplicados en la base.",
            "duplicados": sorted(duplicados)
        }

    dias_estimados_pin = 0
    fecha_proximo_pago = ""
    if tipo_pago == "pin":
        dias_estimados_pin = calcular_dias_pin_nube(valor_pin, precio_plan_referencia)
        fecha_proximo_pago = calcular_fecha_pago_pin_nube(fecha_aplicacion_pin, dias_estimados_pin)
    elif tipo_pago != "autopagable":
        tipo_pago = ""
        valor_pin = 0
        plan_pago = ""
        precio_plan_referencia = 0
        fecha_aplicacion_pin = ""

    creadas = []

    try:
        conn.execute("BEGIN IMMEDIATE")
        for item in credenciales:
            tipo_cuenta = "perfil" if modalidad == "perfiles" else "cuenta_completa"
            pin = item.get("pin", "")
            cursor.execute(
                """
                INSERT INTO nube_cuentas (
                    plataforma, correo, contrasena, pin, tipo_cuenta,
                    estado, origen, modalidad, cantidad_perfiles, tipo_pago,
                    valor_pin, plan_pago, precio_plan_referencia,
                    fecha_aplicacion_pin, dias_estimados_pin, fecha_proximo_pago,
                    duracion_unidad_dias
                )
                VALUES (?, ?, ?, ?, ?, 'disponible', 'carga_rapida', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plataforma, item["correo"], item.get("contrasena", ""), pin,
                    tipo_cuenta, modalidad,
                    cantidad_perfiles if modalidad == "perfiles" else 0,
                    tipo_pago, valor_pin, plan_pago, precio_plan_referencia,
                    fecha_aplicacion_pin, dias_estimados_pin, fecha_proximo_pago,
                    duracion_unidad_dias
                )
            )
            cuenta_id = cursor.lastrowid
            creadas.append(cuenta_id)
            cursor.execute(
                """
                INSERT INTO nube_movimientos (
                    cuenta_id, tipo, descripcion, estado_nuevo, cliente_nombre
                )
                VALUES (?, 'creacion', 'Cuenta creada por carga rápida', 'disponible', '')
                """,
                (cuenta_id,)
            )

            if modalidad == "perfiles":
                for numero in range(1, cantidad_perfiles + 1):
                    cursor.execute(
                        """
                        INSERT INTO nube_perfiles (
                            cuenta_id, nombre_perfil, pin, estado, orden
                        )
                        VALUES (?, ?, '', 'disponible', ?)
                        """,
                        (cuenta_id, f"Perfil {numero}", numero)
                    )

        conn.commit()
        return {"ok": True, "creadas": creadas, "total": len(creadas)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==========================================
# NUBE DE CUENTAS — PREPARAR REGISTRO
# ==========================================

def preparar_cuenta_nube(fila):

    cuenta = dict(fila)


    fecha_vencimiento = (
        cuenta.get(
            "fecha_vencimiento"
        ) or ""
    )


    estado_actual = (
        cuenta.get(
            "estado"
        ) or "disponible"
    )


    dias_restantes = 0


    if fecha_vencimiento:

        dias_restantes = (
            calcular_dias_restantes(
                fecha_vencimiento
            )
        )


    estado_calculado = (
        calcular_estado_efectivo_cuenta_nube(
            fecha_vencimiento=fecha_vencimiento,
            estado_actual=estado_actual,
            modalidad=cuenta.get(
                "modalidad"
            ) or "cuenta_completa"
        )
    )


    cuenta[
        "dias_restantes"
    ] = dias_restantes

    cuenta[
        "estado_calculado"
    ] = estado_calculado


    return cuenta

# ==========================================
# NUBE DE CUENTAS — OBTENER CUENTAS
# ==========================================

def obtener_cuentas_nube(limite=25, offset=0, cuenta_id=None):

    conn = conectar()
    cursor = conn.cursor()

    filtro_cuenta = " AND id = ?" if cuenta_id is not None else ""
    parametros = ([cuenta_id] if cuenta_id is not None else []) + [limite, offset]
    cursor.execute(
        f"""
        SELECT

            id,
            plataforma,
            correo,
            contrasena,
            pin,
            tipo_cuenta,
            cliente_id,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            garantia_usada,
            cantidad_garantias,
                        notas,
            origen,

            modalidad,
            cantidad_perfiles,

            tipo_pago,
            valor_pin,
            plan_pago,
            precio_plan_referencia,
            fecha_aplicacion_pin,
            dias_estimados_pin,
            fecha_proximo_pago,

            fecha_creacion,
            fecha_actualizacion

        FROM nube_cuentas

        WHERE COALESCE(estado, '') != 'papelera'{filtro_cuenta}

        ORDER BY id DESC

        LIMIT ?
        OFFSET ?
        """,
        parametros
    )


    filas = cursor.fetchall()

    cursor.execute(
        f"""
        WITH pagina AS (
            SELECT id, modalidad
            FROM nube_cuentas
            WHERE COALESCE(estado, '') != 'papelera'{filtro_cuenta}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        )
        SELECT
            p.id, p.cuenta_id, p.nombre_perfil, p.pin, p.cliente_id,
            p.nombre_cliente, p.telefono, p.fecha_entrega, p.dias_cuenta,
            p.fecha_vencimiento, p.estado, p.garantia_usada,
            p.cantidad_garantias, p.notas, p.orden, p.fecha_creacion,
            p.fecha_actualizacion
        FROM nube_perfiles AS p
        WHERE p.cuenta_id IN (
            SELECT id FROM pagina WHERE modalidad = 'perfiles'
        )
        ORDER BY p.cuenta_id ASC, p.orden ASC, p.id ASC
        """,
        parametros
    )
    perfiles_por_cuenta = defaultdict(list)
    for fila_perfil in cursor.fetchall():
        perfil = preparar_perfil_nube(fila_perfil)
        perfiles_por_cuenta[perfil["cuenta_id"]].append(perfil)

    ids_pagina = [int(fila["id"]) for fila in filas]
    notificaciones_activas = set()
    if ids_pagina:
        placeholders = ",".join("?" for _ in ids_pagina)
        try:
            cursor.execute(f"""
                SELECT servicio_tipo, servicio_id, cuenta_id,
                       fecha_vencimiento_ciclo
                FROM nube_notificacion_servicios
                WHERE estado = 'pendiente_corte'
                  AND cuenta_id IN ({placeholders})
            """, ids_pagina)
            notificaciones_activas = {
                (item["servicio_tipo"], int(item["servicio_id"]),
                 int(item["cuenta_id"]), item["fecha_vencimiento_ciclo"] or "")
                for item in cursor.fetchall()
            }
        except sqlite3.OperationalError:
            notificaciones_activas = set()

    conn.close()

    cuentas = []


    for fila in filas:

        cuenta = preparar_cuenta_nube(
            fila
        )


        # ==========================================
        # PERFILES DE LA CUENTA MADRE
        # ==========================================

        if (
            cuenta.get("modalidad") ==
            "perfiles"
        ):

            cuenta["perfiles"] = perfiles_por_cuenta.get(cuenta["id"], [])

            for perfil in cuenta["perfiles"]:
                perfil["asignacion_operativa"] = es_asignacion_operativa_nube(
                    perfil.get("nombre_cliente"), perfil.get("fecha_entrega"),
                    perfil.get("dias_cuenta"), perfil.get("fecha_vencimiento")
                ) and (perfil.get("estado") or "").lower() not in {
                    "disponible", "papelera", "reemplazada", "garantia", "caida"
                } and (cuenta.get("estado") or "").lower() not in {"papelera", "reemplazada", "caida"}
                perfil["notificacion_activa"] = (
                    "perfil", int(perfil["id"]), int(cuenta["id"]),
                    perfil.get("fecha_vencimiento") or ""
                ) in notificaciones_activas
                perfil["estado_visual"] = (
                    "notificada" if perfil.get("estado_calculado") == "vencida"
                    and perfil["notificacion_activa"] else perfil.get("estado_calculado")
                )

        else:

            cuenta["perfiles"] = []

        cuenta["asignacion_operativa"] = (
            cuenta.get("modalidad") != "perfiles" and
            es_asignacion_operativa_nube(
                cuenta.get("nombre_cliente"), cuenta.get("fecha_entrega"),
                cuenta.get("dias_cuenta"), cuenta.get("fecha_vencimiento")
            )
        ) and (cuenta.get("estado") or "").lower() not in {
            "disponible", "papelera", "reemplazada", "garantia", "caida"
        }
        cuenta["notificacion_activa"] = (
            "cuenta_completa", int(cuenta["id"]), int(cuenta["id"]),
            cuenta.get("fecha_vencimiento") or ""
        ) in notificaciones_activas


        cuenta[
            "perfiles_totales"
        ] = len(
            cuenta["perfiles"]
        )


        cuenta[
            "perfiles_disponibles"
        ] = sum(
            1
            for perfil
            in cuenta["perfiles"]
            if perfil.get(
                "estado_calculado"
            ) == "disponible"
        )


        cuenta[
            "perfiles_ocupados"
        ] = (
            cuenta[
                "perfiles_totales"
            ]
            -
            cuenta[
                "perfiles_disponibles"
            ]
        )


        cuenta["estado_calculado"] = (
            calcular_estado_efectivo_cuenta_nube(
                fecha_vencimiento=cuenta.get(
                    "fecha_vencimiento"
                ) or "",
                estado_actual=cuenta.get(
                    "estado"
                ) or "disponible",
                modalidad=cuenta.get(
                    "modalidad"
                ) or "cuenta_completa",
                perfiles_disponibles=cuenta[
                    "perfiles_disponibles"
                ],
                perfiles_ocupados=cuenta[
                    "perfiles_ocupados"
                ]
            )
        )
        cuenta["estado_visual"] = (
            "notificada" if cuenta.get("estado_calculado") == "vencida"
            and cuenta["notificacion_activa"] else cuenta.get("estado_calculado")
        )


        cuentas.append(
            cuenta
        )


    return cuentas

# ==========================================
# NUBE DE CUENTAS — ESTADÍSTICAS
# ==========================================

def obtener_estadisticas_nube():
    cuentas = obtener_cuentas_nube(limite=1000000, offset=0)
    resumen = {
        "total": 0,
        "activas": 0,
        "vendidas": 0,
        "por_vencer": 0,
        "vencidas": 0,
        "notificadas": 0,
        "disponibles": 0,
        "caidas": 0,
        "papelera": 0,
        "garantia": 0,
        "reemplazadas": 0
        ,"cuentas_madre_disponibles": 0
        ,"perfiles_disponibles": 0
        ,"cuentas_completas_disponibles": 0
    }


    for cuenta in cuentas:
        if cuenta.get("modalidad") == "perfiles":
            servicios = cuenta.get("perfiles") or []
            resumen["total"] += len(servicios)
            disponibles = sum(
                perfil.get("estado_calculado") == "disponible"
                and not perfil.get("asignacion_operativa")
                and cuenta.get("estado_calculado") != "caida"
                for perfil in servicios
            )
            resumen["perfiles_disponibles"] += disponibles
            if disponibles:
                resumen["cuentas_madre_disponibles"] += 1
        else:
            servicios = [cuenta]
            resumen["total"] += 1
            if cuenta.get("estado_calculado") == "disponible" and not cuenta.get("asignacion_operativa"):
                resumen["cuentas_completas_disponibles"] += 1

        if cuenta.get("estado_calculado") == "caida":
            resumen["caidas"] += 1
        for servicio in servicios:
            if not servicio.get("asignacion_operativa"):
                continue
            resumen["vendidas"] += 1
            resumen["activas"] += 1
            if servicio.get("estado_calculado") == "por_vencer":
                resumen["por_vencer"] += 1
            if servicio.get("estado_calculado") == "vencida":
                resumen["vencidas"] += 1
            if servicio.get("notificacion_activa"):
                resumen["notificadas"] += 1

    resumen["disponibles"] = (
        resumen["perfiles_disponibles"] + resumen["cuentas_completas_disponibles"]
    )


    resumen[
        "caidas_papelera"
    ] = (
        resumen["caidas"] +
        resumen["papelera"]
    )


    return resumen


def obtener_alertas_operativas_nube():
    """Construye las alertas operativas de Nube sin mutar datos."""
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            c.id, c.plataforma, c.nombre_cliente, c.fecha_entrega,
            c.dias_cuenta, c.fecha_vencimiento, c.estado, c.modalidad,
            c.tipo_pago, c.fecha_proximo_pago,
            COUNT(p.id) AS perfiles_totales,
            COALESCE(SUM(CASE
                WHEN p.estado NOT IN ('reemplazada', 'papelera') THEN 1
                ELSE 0
            END), 0) AS perfiles_vigentes,
            COALESCE(SUM(CASE WHEN p.estado = 'disponible' THEN 1 ELSE 0 END), 0)
                AS perfiles_disponibles
        FROM nube_cuentas AS c
        LEFT JOIN nube_perfiles AS p ON p.cuenta_id = c.id
        WHERE COALESCE(c.estado, '') != 'papelera'
        GROUP BY c.id
        ORDER BY c.id
    """)
    cuentas = [dict(fila) for fila in cursor.fetchall()]

    cursor.execute("""
        SELECT
            p.id, p.cuenta_id, p.nombre_perfil, p.cliente_id,
            p.nombre_cliente, p.fecha_entrega, p.dias_cuenta,
            p.fecha_vencimiento, p.estado, c.plataforma,
            c.estado AS estado_cuenta
        FROM nube_perfiles AS p
        INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
        WHERE COALESCE(c.estado, '') != 'papelera'
        ORDER BY p.cuenta_id, p.id
    """)
    perfiles = [dict(fila) for fila in cursor.fetchall()]
    conn.close()

    alertas = []
    cuentas_caidas = set()

    def agregar(tipo, prioridad, titulo, descripcion, fecha_objetivo,
                dias_restantes, cuenta, perfil_id=None, cliente="",
                accion="gestionar_cuenta", **adicionales):
        alerta = {
            "tipo": tipo,
            "prioridad": prioridad,
            "titulo": titulo,
            "descripcion": descripcion,
            "fecha_objetivo": fecha_objetivo or "",
            "dias_restantes": dias_restantes,
            "perfil_id": perfil_id,
            "cuenta_id": cuenta["id"],
            "plataforma": cuenta.get("plataforma") or "",
            "cliente": cliente or "",
            "accion": accion
        }
        alerta.update(adicionales)
        alertas.append(alerta)

    for cuenta in cuentas:
        perfiles_totales = int(cuenta.get("perfiles_totales") or 0)
        perfiles_disponibles = int(cuenta.get("perfiles_disponibles") or 0)
        estado_efectivo = calcular_estado_efectivo_cuenta_nube(
            cuenta.get("fecha_vencimiento") or "",
            cuenta.get("estado") or "disponible",
            cuenta.get("modalidad") or "cuenta_completa",
            perfiles_disponibles,
            perfiles_totales - perfiles_disponibles
        )
        if estado_efectivo != "caida":
            continue
        cuentas_caidas.add(cuenta["id"])
        afectados = int(cuenta.get("perfiles_vigentes") or 0)
        descripcion = "La cuenta madre está marcada como caída."
        if afectados:
            descripcion += f" Afecta {afectados} perfil(es) vigente(s)."
        agregar(
            "cuenta_caida", "critica", "Cuenta madre caída", descripcion,
            "", None, cuenta, cliente=cuenta.get("nombre_cliente") or "",
            perfiles_afectados=afectados
        )

    for cuenta in cuentas:
        if cuenta["id"] in cuentas_caidas:
            continue
        estado = cuenta.get("estado") or "disponible"
        if estado in {"papelera", "reemplazada", "garantia"}:
            continue

        if (
            (cuenta.get("modalidad") or "cuenta_completa") == "cuenta_completa" and
            es_asignacion_operativa_nube(
                cuenta.get("nombre_cliente"), cuenta.get("fecha_entrega"),
                cuenta.get("dias_cuenta"), cuenta.get("fecha_vencimiento")
            )
        ):
            dias = calcular_dias_restantes(cuenta.get("fecha_vencimiento"))
            if dias < 0:
                agregar(
                    "cuenta_vencida", "critica", "Cuenta vencida",
                    "El servicio de la cuenta completa ya venció.",
                    cuenta.get("fecha_vencimiento"), dias, cuenta,
                    cliente=cuenta.get("nombre_cliente") or ""
                )
            elif dias == 0:
                agregar(
                    "cuenta_vence_hoy", "alta", "Cuenta vence hoy",
                    "El servicio de la cuenta completa vence hoy.",
                    cuenta.get("fecha_vencimiento"), dias, cuenta,
                    cliente=cuenta.get("nombre_cliente") or ""
                )
            elif dias <= 3:
                agregar(
                    "cuenta_por_vencer", "media", "Cuenta por vencer",
                    f"El servicio de la cuenta completa vence en {dias} día(s).",
                    cuenta.get("fecha_vencimiento"), dias, cuenta,
                    cliente=cuenta.get("nombre_cliente") or ""
                )

        estado_pago = calcular_estado_pago_nube(
            cuenta.get("tipo_pago"), cuenta.get("fecha_proximo_pago")
        )
        if estado_pago in {"", "autopagable", "sin_fecha"}:
            continue
        dias_pago = calcular_dias_restantes(cuenta.get("fecha_proximo_pago"))
        if dias_pago < 0:
            agregar(
                "pago_pin_pendiente", "critica", "Pago PIN pendiente",
                "La fecha estimada de pago del PIN ya pasó.",
                cuenta.get("fecha_proximo_pago"), dias_pago, cuenta,
                cliente=cuenta.get("nombre_cliente") or "",
                accion="actualizar_pago_pin"
            )
        elif dias_pago == 0:
            agregar(
                "pago_pin_vence_hoy", "alta", "Pago PIN vence hoy",
                "La fecha estimada de pago del PIN es hoy.",
                cuenta.get("fecha_proximo_pago"), dias_pago, cuenta,
                cliente=cuenta.get("nombre_cliente") or "",
                accion="actualizar_pago_pin"
            )
        elif dias_pago <= 3:
            agregar(
                "pago_pin_proximo", "media", "Pago PIN próximo",
                f"La fecha estimada de pago del PIN es en {dias_pago} día(s).",
                cuenta.get("fecha_proximo_pago"), dias_pago, cuenta,
                cliente=cuenta.get("nombre_cliente") or "",
                accion="actualizar_pago_pin"
            )

    for perfil in perfiles:
        if perfil["cuenta_id"] in cuentas_caidas:
            continue
        if (perfil.get("estado") or "disponible") in {
            "disponible", "papelera", "reemplazada", "garantia", "caida"
        }:
            continue
        if not es_asignacion_operativa_nube(
            perfil.get("nombre_cliente"), perfil.get("fecha_entrega"),
            perfil.get("dias_cuenta"), perfil.get("fecha_vencimiento")
        ):
            continue
        cuenta = {"id": perfil["cuenta_id"], "plataforma": perfil["plataforma"]}
        dias = calcular_dias_restantes(perfil.get("fecha_vencimiento"))
        nombre = perfil.get("nombre_perfil") or "Perfil"
        if dias < 0:
            agregar(
                "perfil_vencido", "critica", "Perfil vencido",
                f"{nombre} ya venció.", perfil.get("fecha_vencimiento"), dias,
                cuenta, perfil["id"], perfil.get("nombre_cliente"),
                "gestionar_perfil"
            )
        elif dias == 0:
            agregar(
                "perfil_vence_hoy", "alta", "Perfil vence hoy",
                f"{nombre} vence hoy.", perfil.get("fecha_vencimiento"), dias,
                cuenta, perfil["id"], perfil.get("nombre_cliente"),
                "gestionar_perfil"
            )
        elif dias <= 3:
            agregar(
                "perfil_por_vencer", "media", "Perfil por vencer",
                f"{nombre} vence en {dias} día(s).",
                perfil.get("fecha_vencimiento"), dias, cuenta, perfil["id"],
                perfil.get("nombre_cliente"), "gestionar_perfil"
            )

    orden_prioridad = {"critica": 0, "alta": 1, "media": 2}
    alertas.sort(key=lambda alerta: (
        orden_prioridad.get(alerta["prioridad"], 99),
        alerta["fecha_objetivo"] or "9999-12-31",
        alerta["cuenta_id"],
        alerta["perfil_id"] or 0,
        alerta["tipo"]
    ))
    return {
        "resumen": {
            "total": len(alertas),
            "criticas": sum(a["prioridad"] == "critica" for a in alertas),
            "hoy": sum(a["dias_restantes"] == 0 for a in alertas),
            "proximas": sum(
                isinstance(a["dias_restantes"], int) and
                1 <= a["dias_restantes"] <= 3
                for a in alertas
            )
        },
        "alertas": alertas
    }


def obtener_detalle_alerta_nube(cuenta_id, perfil_id=None):
    """Devuelve contexto operativo seguro, sin credenciales, para el modal."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plataforma, correo, nombre_cliente, modalidad, estado, tipo_pago,
               valor_pin, plan_pago, precio_plan_referencia,
               fecha_aplicacion_pin, dias_estimados_pin, fecha_proximo_pago
        FROM nube_cuentas WHERE id = ?
    """, (cuenta_id,))
    fila = cursor.fetchone()
    if not fila:
        conn.close()
        return None
    cuenta = dict(fila)
    cursor.execute("""
        SELECT id, nombre_perfil, estado, cliente_id, nombre_cliente,
               fecha_entrega, dias_cuenta, fecha_vencimiento
        FROM nube_perfiles WHERE cuenta_id = ? ORDER BY orden, id
    """, (cuenta_id,))
    perfiles_cuenta = [dict(item) for item in cursor.fetchall()]
    pendientes = [item for item in perfiles_cuenta if _servicio_vigente_pendiente_nube(item)]
    vencidos = [item for item in perfiles_cuenta if _servicio_vencido_nube(item)]
    resueltos = [item for item in perfiles_cuenta if
                 (item.get("estado") or "").lower() in {"reemplazada", "papelera"}]
    cuenta["perfiles_totales"] = len(perfiles_cuenta)
    cuenta["perfiles_pendientes"] = len(pendientes)
    cuenta["perfiles_resueltos"] = len(resueltos)
    cuenta["perfiles_vencidos"] = len(vencidos)
    cuenta["servicios_vigentes_pendientes"] = len(pendientes)
    cuenta["lista_para_papelera"] = not pendientes and cuenta.get("estado") == "caida"
    perfil = None
    if perfil_id:
        cursor.execute("""
            SELECT id, cuenta_id, nombre_perfil, nombre_cliente,
                   fecha_vencimiento, estado
            FROM nube_perfiles WHERE id = ? AND cuenta_id = ?
        """, (perfil_id, cuenta_id))
        fila_perfil = cursor.fetchone()
        perfil = dict(fila_perfil) if fila_perfil else None
    cursor.execute("""
        SELECT id, valor_pin, plan, precio_plan_referencia,
               fecha_aplicacion, dias_estimados, fecha_estimada_fin, notas
        FROM nube_pagos_pin WHERE cuenta_id = ?
        ORDER BY fecha_aplicacion DESC, id DESC LIMIT 12
    """, (cuenta_id,))
    historial = [dict(fila_pago) for fila_pago in cursor.fetchall()]
    conn.close()
    return {"cuenta": cuenta, "perfil": perfil, "perfiles": perfiles_cuenta,
            "perfiles_pendientes": pendientes, "historial_pin": historial}


def obtener_detalle_drawer_cuenta_nube(cuenta_id):
    try:
        cuenta_id = int(cuenta_id)
    except (TypeError, ValueError):
        return None

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, plataforma, correo, contrasena, pin, tipo_cuenta,
               nombre_cliente, telefono, fecha_entrega, dias_cuenta,
               fecha_vencimiento, estado, notas, modalidad, tipo_pago,
               valor_pin, plan_pago, fecha_creacion, fecha_actualizacion
        FROM nube_cuentas
        WHERE id = ?
    """, (cuenta_id,))
    fila_cuenta = cursor.fetchone()
    if not fila_cuenta:
        conn.close()
        return None

    cuenta = dict(fila_cuenta)
    cursor.execute("""
        SELECT id, nombre_perfil, pin, nombre_cliente, telefono,
               fecha_entrega, dias_cuenta, fecha_vencimiento, estado,
               garantia_usada, cantidad_garantias, notas, orden,
               fecha_actualizacion
        FROM nube_perfiles
        WHERE cuenta_id = ?
        ORDER BY orden, id
    """, (cuenta_id,))
    perfiles = [dict(fila) for fila in cursor.fetchall()]
    for perfil in perfiles:
        perfil["dias_restantes"] = calcular_dias_restantes(
            perfil.get("fecha_vencimiento")
        ) if perfil.get("fecha_vencimiento") else 0
        perfil["asignado"] = es_asignacion_operativa_nube(
            perfil.get("nombre_cliente"),
            perfil.get("fecha_entrega"),
            perfil.get("dias_cuenta"),
            perfil.get("fecha_vencimiento")
        )

    cursor.execute("""
        SELECT id, tipo, descripcion, estado_anterior, estado_nuevo,
               cliente_nombre, fecha
        FROM nube_movimientos
        WHERE cuenta_id = ?
        ORDER BY fecha DESC, id DESC
        LIMIT 80
    """, (cuenta_id,))
    movimientos = [dict(fila) for fila in cursor.fetchall()]

    cursor.execute("""
        SELECT id, valor_pin, plan, precio_plan_referencia,
               fecha_aplicacion, dias_estimados, fecha_estimada_fin,
               notas
        FROM nube_pagos_pin
        WHERE cuenta_id = ?
        ORDER BY fecha_aplicacion DESC, id DESC
        LIMIT 30
    """, (cuenta_id,))
    pagos_pin = [dict(fila) for fila in cursor.fetchall()]

    cursor.execute("""
        SELECT r.id, r.perfil_anterior_id, r.perfil_nuevo_id,
               r.cuenta_anterior_id, r.cuenta_nueva_id,
               r.nombre_cliente, r.telefono, r.motivo,
               r.dias_restantes, r.fecha_vencimiento_anterior,
               r.fecha,
               pa.nombre_perfil AS perfil_anterior,
               pn.nombre_perfil AS perfil_nuevo,
               ca.plataforma AS plataforma_anterior,
               cn.plataforma AS plataforma_nueva
        FROM nube_reemplazos_perfiles AS r
        LEFT JOIN nube_perfiles AS pa ON pa.id = r.perfil_anterior_id
        LEFT JOIN nube_perfiles AS pn ON pn.id = r.perfil_nuevo_id
        LEFT JOIN nube_cuentas AS ca ON ca.id = r.cuenta_anterior_id
        LEFT JOIN nube_cuentas AS cn ON cn.id = r.cuenta_nueva_id
        WHERE r.cuenta_anterior_id = ? OR r.cuenta_nueva_id = ?
        ORDER BY r.fecha DESC, r.id DESC
        LIMIT 50
    """, (cuenta_id, cuenta_id))
    reemplazos = [dict(fila) for fila in cursor.fetchall()]

    try:
        _asegurar_archivo_asignaciones_nube(cursor)
        cursor.execute("""
            SELECT id, perfil_id, tipo_origen, snapshot, fecha
            FROM nube_archivos_asignaciones
            WHERE cuenta_id = ?
            ORDER BY fecha DESC, id DESC
            LIMIT 40
        """, (cuenta_id,))
        snapshots = [dict(fila) for fila in cursor.fetchall()]
        for item in snapshots:
            item["datos"] = json.loads(item.pop("snapshot") or "{}")
    except sqlite3.Error:
        snapshots = []

    conn.close()

    garantias = []
    perfiles_afectados = set()
    for perfil in perfiles:
        if int(perfil.get("garantia_usada") or 0) or int(perfil.get("cantidad_garantias") or 0):
            perfiles_afectados.add(perfil["id"])
            garantias.append({
                "tipo": "perfil",
                "perfil_id": perfil["id"],
                "perfil": perfil.get("nombre_perfil") or f"Perfil {perfil['id']}",
                "cliente": perfil.get("nombre_cliente") or "",
                "estado": perfil.get("estado") or "",
                "cantidad": int(perfil.get("cantidad_garantias") or 0),
                "fecha": perfil.get("fecha_actualizacion") or ""
            })
    for reemplazo in reemplazos:
        perfiles_afectados.add(reemplazo.get("perfil_anterior_id"))
        garantias.append({
            "tipo": "reemplazo",
            "perfil_id": reemplazo.get("perfil_anterior_id"),
            "perfil": reemplazo.get("perfil_anterior") or "",
            "cliente": reemplazo.get("nombre_cliente") or "",
            "estado": "reemplazado",
            "destino": " · ".join(
                parte for parte in [
                    reemplazo.get("plataforma_nueva") or "",
                    reemplazo.get("perfil_nuevo") or ""
                ] if parte
            ),
            "fecha": reemplazo.get("fecha") or "",
            "motivo": reemplazo.get("motivo") or ""
        })

    return {
        "cuenta": cuenta,
        "perfiles": perfiles,
        "historial": {
            "movimientos": movimientos,
            "pagos_pin": pagos_pin,
            "reemplazos": reemplazos,
            "snapshots": snapshots
        },
        "garantias": {
            "total_perfiles": len(perfiles),
            "perfiles_afectados": len([item for item in perfiles_afectados if item]),
            "reemplazados": len(reemplazos),
            "pendientes": sum(1 for perfil in perfiles if perfil.get("estado") == "garantia"),
            "items": garantias
        }
    }


def actualizar_notas_cuenta_nube(cuenta_id, notas=""):
    try:
        cuenta_id = int(cuenta_id)
    except (TypeError, ValueError):
        return {"ok": False, "mensaje": "Cuenta inválida."}

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE nube_cuentas
        SET notas = ?, fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        ((notas or "").strip(), cuenta_id)
    )
    actualizado = cursor.rowcount == 1
    conn.commit()
    conn.close()
    if not actualizado:
        return {"ok": False, "mensaje": "Cuenta no encontrada."}
    return {"ok": True, "mensaje": "Nota guardada."}


def registrar_pago_pin_nube(cuenta_id, valor_pin, plan,
                            precio_plan_referencia, fecha_aplicacion,
                            notas=""):
    """Registra un ciclo PIN preservando historial y actualiza su proyección."""
    try:
        cuenta_id = int(cuenta_id)
        valor_pin = int(valor_pin)
        precio_plan_referencia = int(precio_plan_referencia)
        datetime.strptime(fecha_aplicacion, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError("Los datos del pago PIN no son válidos.")
    plan = (plan or "").strip()
    notas = (notas or "").strip()
    if valor_pin <= 0 or precio_plan_referencia <= 0 or not plan:
        raise ValueError("Plan, valor PIN y precio mensual son obligatorios.")
    dias = calcular_dias_pin_nube(valor_pin, precio_plan_referencia)
    proximo_pago = calcular_fecha_pago_pin_nube(fecha_aplicacion, dias)
    if not proximo_pago:
        raise ValueError("No fue posible calcular la próxima fecha de pago.")

    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT id, tipo_pago, estado, modalidad FROM nube_cuentas WHERE id = ?",
            (cuenta_id,)
        )
        cuenta = cursor.fetchone()
        if not cuenta:
            raise ValueError("La cuenta no existe.")
        if (cuenta["tipo_pago"] or "").lower() != "pin":
            raise ValueError("La cuenta no utiliza modalidad de pago PIN.")
        cursor.execute("""
            SELECT id, fecha_estimada_fin FROM nube_pagos_pin
            WHERE cuenta_id = ? AND valor_pin = ? AND plan = ?
              AND precio_plan_referencia = ? AND fecha_aplicacion = ?
            ORDER BY id DESC LIMIT 1
        """, (cuenta_id, valor_pin, plan, precio_plan_referencia, fecha_aplicacion))
        duplicado = cursor.fetchone()
        if duplicado:
            pago_id = duplicado["id"]
            proximo_pago = duplicado["fecha_estimada_fin"]
        else:
            cursor.execute("""
                INSERT INTO nube_pagos_pin (
                    cuenta_id, valor_pin, plan, precio_plan_referencia,
                    fecha_aplicacion, dias_estimados, fecha_estimada_fin, notas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cuenta_id, valor_pin, plan, precio_plan_referencia,
                  fecha_aplicacion, dias, proximo_pago, notas))
            pago_id = cursor.lastrowid
        cursor.execute("""
            UPDATE nube_cuentas SET valor_pin = ?, plan_pago = ?,
                precio_plan_referencia = ?, fecha_aplicacion_pin = ?,
                dias_estimados_pin = ?, fecha_proximo_pago = ?
            WHERE id = ?
        """, (valor_pin, plan, precio_plan_referencia, fecha_aplicacion,
              dias, proximo_pago, cuenta_id))
        cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nube_movimientos'")
        if not duplicado and cursor.fetchone():
            cursor.execute("""
                INSERT INTO nube_movimientos
                (cuenta_id, tipo, descripcion, estado_anterior, estado_nuevo)
                SELECT ?, 'pago_pin_registrado', ?, estado, estado
                FROM nube_cuentas WHERE id = ?
            """, (cuenta_id, f"Pago PIN registrado para {plan}", cuenta_id))
        estado_anterior = cuenta["estado"]
        reactivada = estado_anterior == "caida"
        restaurada_papelera = estado_anterior == "papelera"
        perfiles_liberados = 0
        if reactivada or restaurada_papelera:
            perfiles_liberados = _limpiar_y_habilitar_cuenta_nube(cursor, cuenta_id)
            cursor.execute("""
                UPDATE nube_cuentas SET estado='disponible', cliente_id=NULL,
                    nombre_cliente='', telefono='', fecha_entrega='', dias_cuenta=0,
                    fecha_vencimiento='', fecha_archivada='', motivo_archivo='',
                    fecha_actualizacion=CURRENT_TIMESTAMP
                WHERE id=? AND estado=?
            """, (cuenta_id, estado_anterior))
            if cursor.rowcount != 1:
                raise RuntimeError("La cuenta cambiÃ³ durante la reactivaciÃ³n.")
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nube_movimientos'")
            if cursor.fetchone():
                cursor.execute("""
                    INSERT INTO nube_movimientos
                    (cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo)
                    VALUES (?,?,?,?, 'disponible')
                """, (cuenta_id,
                      ('cuenta_restaurada_por_pago_pin' if restaurada_papelera else 'cuenta_reactivada_por_pago_pin'),
                      f"Cuenta {'restaurada' if restaurada_papelera else 'reactivada'} por pago PIN; {perfiles_liberados} slots disponibles",
                      estado_anterior))
        conn.commit()
        return {
            "duplicado": bool(duplicado), "pago_id": pago_id,
            "fecha_aplicacion": fecha_aplicacion, "proximo_pago": proximo_pago,
            "valor_pin": valor_pin, "plan": plan, "dias_estimados": dias,
            "cuenta_reactivada": reactivada,
            "cuenta_restaurada": restaurada_papelera,
            "perfiles_liberados": perfiles_liberados
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columnas_tabla_nube(cursor, tabla):
    try:
        cursor.execute(f"PRAGMA table_info({tabla})")
        return {fila["name"] for fila in cursor.fetchall()}
    except sqlite3.Error:
        return set()


def _asegurar_notificaciones_renovacion_nube(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_notificaciones_renovacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            telefono_normalizado TEXT DEFAULT '',
            fecha_vencimiento_ciclo TEXT NOT NULL,
            fecha_notificacion TEXT DEFAULT '',
            estado TEXT NOT NULL DEFAULT 'notificado',
            tipo TEXT NOT NULL DEFAULT 'individual',
            mensaje TEXT DEFAULT '',
            medio TEXT DEFAULT '',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nube_notificacion_servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notificacion_id INTEGER NOT NULL,
            servicio_tipo TEXT NOT NULL,
            servicio_id INTEGER NOT NULL,
            cuenta_id INTEGER NOT NULL,
            perfil_id INTEGER,
            fecha_vencimiento_ciclo TEXT NOT NULL,
            snapshot TEXT NOT NULL DEFAULT '{}',
            estado TEXT NOT NULL DEFAULT 'pendiente_corte',
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(notificacion_id)
                REFERENCES nube_notificaciones_renovacion(id)
                ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type = 'index' AND name = 'idx_nube_notif_servicio_ciclo'
    """)
    indice_ciclo = cursor.fetchone()
    sql_indice_ciclo = " ".join(str(indice_ciclo["sql"] or "").lower().split()) if indice_ciclo else ""
    if indice_ciclo and "where estado = 'pendiente_corte'" not in sql_indice_ciclo:
        cursor.execute("DROP INDEX idx_nube_notif_servicio_ciclo")
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nube_notif_servicio_ciclo
        ON nube_notificacion_servicios(
            servicio_tipo, servicio_id, fecha_vencimiento_ciclo
        )
        WHERE estado = 'pendiente_corte'
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_nube_notif_servicios_notificacion
        ON nube_notificacion_servicios(notificacion_id)
    """)


def _fecha_hoy_nube():
    return datetime.now().date()


def _parse_fecha_nube(valor):
    try:
        return datetime.strptime((valor or "").strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _servicio_expirado_operativo_nube(servicio, hoy=None):
    hoy = hoy or _fecha_hoy_nube()
    estado = (servicio.get("estado") or "").strip().lower()
    if estado in {"disponible", "papelera", "reemplazada", "garantia", "caida"}:
        return False
    if not es_asignacion_operativa_nube(
        servicio.get("nombre_cliente"), servicio.get("fecha_entrega"),
        servicio.get("dias_cuenta"), servicio.get("fecha_vencimiento")
    ):
        return False
    fecha = _parse_fecha_nube(servicio.get("fecha_vencimiento"))
    return bool(fecha and fecha <= hoy)


def _expr_tabla_columna_nube(columnas, tabla_alias, nombre, alias, defecto="''"):
    if nombre in columnas:
        return f"{tabla_alias}.{nombre} AS {alias}"
    return f"{defecto} AS {alias}"


def _leer_servicios_vencidos_reales_nube(cursor, hoy=None):
    hoy = hoy or _fecha_hoy_nube()
    servicios = []
    columnas_cuenta = _columnas_tabla_nube(cursor, "nube_cuentas")
    columnas_perfil = _columnas_tabla_nube(cursor, "nube_perfiles")
    cursor.execute(f"""
        SELECT p.id AS servicio_id, 'perfil' AS servicio_tipo,
               p.id AS perfil_id, p.cuenta_id AS cuenta_id,
               c.plataforma AS plataforma, c.correo AS correo,
               {_expr_tabla_columna_nube(columnas_perfil, 'p', 'nombre_perfil', 'nombre_perfil')},
               {_expr_tabla_columna_nube(columnas_perfil, 'p', 'pin', 'pin')},
               {_expr_tabla_columna_nube(columnas_perfil, 'p', 'cliente_id', 'cliente_id', 'NULL')},
               p.nombre_cliente AS nombre_cliente,
               {_expr_tabla_columna_nube(columnas_perfil, 'p', 'telefono', 'telefono')},
               p.fecha_entrega AS fecha_entrega,
               p.dias_cuenta AS dias_cuenta,
               p.fecha_vencimiento AS fecha_vencimiento,
               p.estado AS estado,
               c.estado AS estado_cuenta
        FROM nube_perfiles AS p
        INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
        WHERE COALESCE(c.estado, '') != 'papelera'
    """)
    for fila in cursor.fetchall():
        servicio = dict(fila)
        if (servicio.get("estado_cuenta") or "").strip().lower() in {"papelera", "reemplazada"}:
            continue
        servicio["telefono_normalizado"] = normalizar_telefono_nube(servicio.get("telefono"))
        if _servicio_expirado_operativo_nube(servicio, hoy):
            servicios.append(servicio)

    modalidad = (
        "COALESCE(c.modalidad, 'cuenta_completa') AS modalidad"
        if "modalidad" in columnas_cuenta
        else "'cuenta_completa' AS modalidad"
    )
    cursor.execute(f"""
        SELECT c.id AS servicio_id, 'cuenta_completa' AS servicio_tipo,
               NULL AS perfil_id, c.id AS cuenta_id,
               c.plataforma AS plataforma, c.correo AS correo,
               '' AS nombre_perfil,
               {_expr_tabla_columna_nube(columnas_cuenta, 'c', 'pin', 'pin')},
               {_expr_tabla_columna_nube(columnas_cuenta, 'c', 'cliente_id', 'cliente_id', 'NULL')},
               c.nombre_cliente AS nombre_cliente,
               {_expr_tabla_columna_nube(columnas_cuenta, 'c', 'telefono', 'telefono')},
               c.fecha_entrega AS fecha_entrega,
               c.dias_cuenta AS dias_cuenta,
               c.fecha_vencimiento AS fecha_vencimiento,
               c.estado AS estado,
               {modalidad}
        FROM nube_cuentas AS c
    """)
    for fila in cursor.fetchall():
        servicio = dict(fila)
        if (servicio.get("modalidad") or "cuenta_completa") == "perfiles":
            continue
        servicio["telefono_normalizado"] = normalizar_telefono_nube(servicio.get("telefono"))
        if _servicio_expirado_operativo_nube(servicio, hoy):
            servicios.append(servicio)
    return servicios


def _leer_cuenta_madre_operativa_nube(cursor, cuenta_id):
    columnas = _columnas_tabla_nube(cursor, "nube_cuentas")
    tipo_cuenta = (
        "c.tipo_cuenta AS tipo_cuenta"
        if "tipo_cuenta" in columnas
        else "'' AS tipo_cuenta"
    )
    modalidad = (
        "c.modalidad AS modalidad"
        if "modalidad" in columnas
        else "'cuenta_completa' AS modalidad"
    )
    cursor.execute(f"""
        SELECT c.id, c.plataforma, c.correo, c.contrasena, c.pin,
               {tipo_cuenta}, {modalidad}, c.estado
        FROM nube_cuentas AS c
        WHERE c.id = ?
    """, (cuenta_id,))
    fila = cursor.fetchone()
    if not fila:
        return None
    cuenta = dict(fila)
    return {
        "id": cuenta["id"],
        "plataforma": cuenta.get("plataforma") or "",
        "correo": cuenta.get("correo") or "",
        "contrasena": cuenta.get("contrasena") or "",
        "pin": cuenta.get("pin") or "",
        "tipo": cuenta.get("tipo_cuenta") or "",
        "modalidad": cuenta.get("modalidad") or "cuenta_completa",
        "estado": cuenta.get("estado") or ""
    }


def _contar_perfiles_cuenta_nube(cursor, cuenta_id):
    cursor.execute("SELECT COUNT(*) AS total FROM nube_perfiles WHERE cuenta_id = ?", (cuenta_id,))
    fila = cursor.fetchone()
    return int((fila["total"] if fila else 0) or 0)


def _identidad_unidad_renovacion_nube(servicio):
    if servicio.get("cliente_id") is not None:
        return f"cliente:{servicio.get('cliente_id')}"
    telefono = servicio.get("telefono_normalizado") or normalizar_telefono_nube(servicio.get("telefono"))
    if telefono:
        return f"telefono:{telefono}"
    nombre = (servicio.get("nombre_cliente") or "").strip().casefold()
    if nombre and servicio.get("fecha_entrega") and servicio.get("fecha_vencimiento"):
        return f"fallback:{nombre}:{servicio.get('fecha_entrega')}:{servicio.get('fecha_vencimiento')}"
    return ""


def _snapshot_notificacion_servicio_nube(servicio):
    publico = {
        "servicio_tipo": servicio.get("servicio_tipo"),
        "servicio_id": servicio.get("servicio_id"),
        "cuenta_id": servicio.get("cuenta_id"),
        "perfil_id": servicio.get("perfil_id"),
        "plataforma": servicio.get("plataforma") or "",
        "correo": servicio.get("correo") or "",
        "nombre_perfil": servicio.get("nombre_perfil") or "",
        "pin": servicio.get("pin") or "",
        "cliente_id": servicio.get("cliente_id"),
        "nombre_cliente": servicio.get("nombre_cliente") or "",
        "telefono": servicio.get("telefono") or "",
        "telefono_normalizado": servicio.get("telefono_normalizado") or "",
        "fecha_entrega": servicio.get("fecha_entrega") or "",
        "dias_cuenta": int(servicio.get("dias_cuenta") or 0),
        "fecha_vencimiento": servicio.get("fecha_vencimiento") or "",
        "estado": servicio.get("estado") or "",
        "fecha_snapshot": datetime.now().astimezone().isoformat(timespec="seconds")
    }
    return json.dumps(publico, ensure_ascii=False, sort_keys=True)


def _mensaje_renovacion_nube(unidad):
    cliente = unidad.get("cliente") or "Cliente"
    servicios = unidad.get("servicios") or []
    plataformas = [s.get("plataforma") or "Servicio" for s in servicios]
    if unidad.get("tipo") == "combo":
        lineas = "\n".join(f"- {plataforma}" for plataforma in plataformas)
        return f"Hola, {cliente}\n\nTu combo de:\n\n{lineas}\n\nha vencido.\n\nDeseas renovarlo?\n\nGracias por preferirnos.\n\nPECHY PLAYERS"
    plataforma = plataformas[0] if plataformas else "tu servicio"
    return f"Hola, {cliente}\n\nTe informamos que tu servicio de {plataforma} ha vencido.\n\nDeseas renovarlo?\n\nGracias por preferirnos.\n\nPECHY PLAYERS"


def _url_whatsapp_nube(telefono_normalizado, mensaje):
    from urllib.parse import quote
    telefono = normalizar_telefono_nube(telefono_normalizado)
    if not telefono:
        return ""
    return f"https://wa.me/{telefono}?text={quote(mensaje or '')}"


def _servicio_token_renovacion_nube(servicio):
    return f"{servicio['servicio_tipo']}:{servicio['servicio_id']}"


def _servicios_no_notificados_nube(cursor):
    _asegurar_notificaciones_renovacion_nube(cursor)
    pendientes = []
    for servicio in _leer_servicios_vencidos_reales_nube(cursor):
        cursor.execute("""
            SELECT 1 FROM nube_notificacion_servicios
            WHERE servicio_tipo = ? AND servicio_id = ?
              AND fecha_vencimiento_ciclo = ?
              AND estado = 'pendiente_corte'
            LIMIT 1
        """, (servicio["servicio_tipo"], servicio["servicio_id"], servicio["fecha_vencimiento"]))
        if not cursor.fetchone():
            pendientes.append(servicio)
    return pendientes


def _crear_unidades_renovacion_nube(servicios):
    grupos = {}
    sueltos = []
    for servicio in servicios:
        identidad = _identidad_unidad_renovacion_nube(servicio)
        if not identidad:
            sueltos.append([servicio])
            continue
        clave = (
            identidad, servicio.get("fecha_entrega") or "",
            int(servicio.get("dias_cuenta") or 0),
            servicio.get("fecha_vencimiento") or ""
        )
        grupos.setdefault(clave, []).append(servicio)
    unidades = sueltos + list(grupos.values())
    resultado = []
    for grupo in unidades:
        grupo.sort(key=lambda s: (s["plataforma"], s["servicio_tipo"], s["servicio_id"]))
        primero = grupo[0]
        tokens = ",".join(_servicio_token_renovacion_nube(s) for s in grupo)
        unidad = {
            "unidad_id": f"pendiente:{primero.get('fecha_vencimiento')}:{tokens}",
            "tipo": "combo" if len(grupo) > 1 else "individual",
            "cliente_id": primero.get("cliente_id"),
            "cliente": primero.get("nombre_cliente") or "",
            "telefono": primero.get("telefono") or "",
            "telefono_normalizado": primero.get("telefono_normalizado") or "",
            "fecha_entrega": primero.get("fecha_entrega") or "",
            "dias_cuenta": int(primero.get("dias_cuenta") or 0),
            "fecha_vencimiento": primero.get("fecha_vencimiento") or "",
            "servicios": grupo
        }
        unidad["mensaje"] = _mensaje_renovacion_nube(unidad)
        unidad["whatsapp_url"] = _url_whatsapp_nube(unidad["telefono_normalizado"], unidad["mensaje"])
        resultado.append(unidad)
    resultado.sort(key=lambda u: (u["fecha_vencimiento"], u["cliente"].casefold(), u["unidad_id"]))
    return resultado


def obtener_centro_notificaciones_renovacion_nube():
    conn = conectar()
    try:
        cursor = conn.cursor()
        _asegurar_notificaciones_renovacion_nube(cursor)
        pendientes = _crear_unidades_renovacion_nube(_servicios_no_notificados_nube(cursor))
        cursor.execute("""
            SELECT * FROM nube_notificaciones_renovacion
            ORDER BY COALESCE(fecha_notificacion, fecha_creacion) DESC, id DESC
            LIMIT 250
        """)
        notificados = []
        for fila in cursor.fetchall():
            item = dict(fila)
            cursor.execute("""
                SELECT snapshot, estado
                FROM nube_notificacion_servicios
                WHERE notificacion_id = ?
                ORDER BY id
            """, (item["id"],))
            servicios = []
            for fila_servicio in cursor.fetchall():
                snapshot = json.loads(fila_servicio["snapshot"] or "{}")
                snapshot["estado_corte"] = fila_servicio["estado"]
                servicios.append(snapshot)
            item["servicios"] = servicios
            item["cliente"] = servicios[0].get("nombre_cliente") if servicios else ""
            item["telefono"] = servicios[0].get("telefono") if servicios else ""
            item["fecha_vencimiento"] = item["fecha_vencimiento_ciclo"]
            item["whatsapp_url"] = _url_whatsapp_nube(item.get("telefono_normalizado"), item.get("mensaje"))
            notificados.append(item)
        hoy = _fecha_hoy_nube().isoformat()
        return {
            "pendientes": pendientes,
            "notificados": notificados,
            "resumen": {
                "pendientes": len(pendientes),
                "vencen_hoy": sum(u["fecha_vencimiento"] == hoy for u in pendientes),
                "notificados_hoy": sum((n.get("fecha_notificacion") or "").startswith(hoy) for n in notificados),
                "combos": sum(u["tipo"] == "combo" for u in pendientes),
                "individuales": sum(u["tipo"] == "individual" for u in pendientes)
            }
        }
    finally:
        conn.close()


def marcar_notificacion_renovacion_nube(servicios_payload, mensaje="", medio="manual"):
    solicitados = {
        (str(item.get("servicio_tipo") or ""), int(item.get("servicio_id") or 0))
        for item in (servicios_payload or [])
        if item.get("servicio_tipo") in {"perfil", "cuenta_completa"}
    }
    solicitados = {item for item in solicitados if item[1] > 0}
    if not solicitados:
        return {"ok": False, "mensaje": "Selecciona al menos un servicio vencido."}
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        _asegurar_notificaciones_renovacion_nube(cursor)
        reales = {(s["servicio_tipo"], int(s["servicio_id"])): s for s in _servicios_no_notificados_nube(cursor)}
        seleccionados = []
        for clave in solicitados:
            servicio = reales.get(clave)
            if not servicio:
                conn.rollback()
                return {"ok": False, "codigo": "servicio_no_elegible", "mensaje": "El servicio ya fue renovado, liberado o notificado."}
            seleccionados.append(servicio)
        unidad = _crear_unidades_renovacion_nube(seleccionados)[0]
        mensaje = (mensaje or "").strip() or _mensaje_renovacion_nube(unidad)
        cursor.execute("""
            INSERT INTO nube_notificaciones_renovacion (
                cliente_id, telefono_normalizado, fecha_vencimiento_ciclo,
                fecha_notificacion, estado, tipo, mensaje, medio
            ) VALUES (?, ?, ?, datetime('now','localtime'), 'notificado', ?, ?, ?)
        """, (
            seleccionados[0].get("cliente_id"),
            seleccionados[0].get("telefono_normalizado") or "",
            seleccionados[0].get("fecha_vencimiento") or "",
            "combo" if len(seleccionados) > 1 else "individual",
            mensaje, (medio or "manual").strip()
        ))
        notificacion_id = cursor.lastrowid
        for servicio in seleccionados:
            cursor.execute("""
                INSERT INTO nube_notificacion_servicios (
                    notificacion_id, servicio_tipo, servicio_id, cuenta_id,
                    perfil_id, fecha_vencimiento_ciclo, snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                notificacion_id, servicio["servicio_tipo"], servicio["servicio_id"],
                servicio["cuenta_id"], servicio.get("perfil_id"),
                servicio["fecha_vencimiento"], _snapshot_notificacion_servicio_nube(servicio)
            ))
        cursor.execute("""
            INSERT INTO nube_movimientos (cuenta_id, tipo, descripcion, cliente_nombre)
            VALUES (?, 'renovacion_notificada', ?, ?)
        """, (
            seleccionados[0]["cuenta_id"],
            f"Notificacion de renovacion registrada para {len(seleccionados)} servicio(s)",
            seleccionados[0].get("nombre_cliente") or ""
        ))
        conn.commit()
        return {"ok": True, "notificacion_id": notificacion_id}
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"ok": False, "codigo": "duplicado", "mensaje": "Este ciclo de vencimiento ya fue notificado."}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _horas_desde_nube(fecha_texto):
    if not fecha_texto:
        return 0
    try:
        fecha = datetime.fromisoformat(str(fecha_texto).replace(" ", "T"))
    except ValueError:
        return 0
    return max(int((datetime.now() - fecha).total_seconds() // 3600), 0)


def obtener_historial_cortes_nube(cursor):
    cursor.execute("""
        SELECT ns.*, n.fecha_notificacion, n.tipo AS tipo_notificacion
        FROM nube_notificacion_servicios AS ns
        INNER JOIN nube_notificaciones_renovacion AS n ON n.id = ns.notificacion_id
        WHERE ns.estado IN ('cortado', 'retirado_renovacion')
        ORDER BY ns.fecha_actualizacion DESC, ns.id DESC
        LIMIT 120
    """)
    historial = []
    for fila in cursor.fetchall():
        item = dict(fila)
        snapshot = json.loads(item.pop("snapshot") or "{}")
        snapshot.update({
            "notificacion_id": item["notificacion_id"],
            "estado_corte": item["estado"],
            "fecha_notificacion": item["fecha_notificacion"],
            "fecha_actualizacion": item["fecha_actualizacion"],
            "tipo_notificacion": item["tipo_notificacion"] or "individual"
        })
        historial.append(snapshot)
    cursor.execute("""
        SELECT m.cuenta_id, m.tipo, m.descripcion, m.fecha,
               c.plataforma, c.correo
        FROM nube_movimientos AS m
        LEFT JOIN nube_cuentas AS c ON c.id = m.cuenta_id
        WHERE m.tipo IN (
            'credenciales_actualizadas_corte',
            'pin_perfil_actualizado_corte'
        )
        ORDER BY m.fecha DESC, m.id DESC
        LIMIT 80
    """)
    for fila in cursor.fetchall():
        item = dict(fila)
        historial.append({
            "cuenta_id": item.get("cuenta_id"),
            "plataforma": item.get("plataforma") or "Cuenta madre",
            "correo": item.get("correo") or "",
            "servicio_tipo": "evento",
            "nombre_perfil": "",
            "nombre_cliente": "",
            "telefono": "",
            "telefono_normalizado": "",
            "estado_corte": item.get("tipo") or "evento",
            "tipo_evento": item.get("tipo") or "evento",
            "descripcion": item.get("descripcion") or "Evento operativo",
            "fecha_actualizacion": item.get("fecha") or "",
            "tipo_notificacion": "operativo"
        })
    historial.sort(key=lambda item: item.get("fecha_actualizacion") or "", reverse=True)
    historial = historial[:120]
    return historial


def obtener_cortes_nube():
    conn = conectar()
    try:
        cursor = conn.cursor()
        _asegurar_notificaciones_renovacion_nube(cursor)
        reales = {
            (s["servicio_tipo"], int(s["servicio_id"]), s["fecha_vencimiento"]): s
            for s in _leer_servicios_vencidos_reales_nube(cursor)
        }
        cursor.execute("""
            SELECT ns.*, n.fecha_notificacion, n.medio, n.tipo AS tipo_notificacion
            FROM nube_notificacion_servicios AS ns
            INNER JOIN nube_notificaciones_renovacion AS n ON n.id = ns.notificacion_id
            WHERE ns.estado = 'pendiente_corte'
            ORDER BY n.fecha_notificacion ASC, ns.id ASC
        """)
        por_cuenta = {}
        cuentas_madre = {}
        retirados = 0
        for fila in cursor.fetchall():
            item = dict(fila)
            clave = (item["servicio_tipo"], int(item["servicio_id"]), item["fecha_vencimiento_ciclo"])
            real = reales.get(clave)
            if not real:
                retirados += 1
                cursor.execute("""
                    UPDATE nube_notificacion_servicios
                    SET estado = 'retirado_renovacion',
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE id = ? AND estado = 'pendiente_corte'
                """, (item["id"],))
                continue
            cuenta_madre = cuentas_madre.get(real["cuenta_id"])
            if cuenta_madre is None:
                cuenta_madre = _leer_cuenta_madre_operativa_nube(cursor, real["cuenta_id"]) or {}
                cuenta_madre["perfiles_totales"] = _contar_perfiles_cuenta_nube(cursor, real["cuenta_id"])
                cuentas_madre[real["cuenta_id"]] = cuenta_madre
            real["cuenta_madre"] = cuenta_madre
            real["notificacion_id"] = item["notificacion_id"]
            real["fecha_notificacion"] = item["fecha_notificacion"] or ""
            real["medio"] = item["medio"] or ""
            real["tipo_notificacion"] = item["tipo_notificacion"] or "individual"
            grupo = por_cuenta.setdefault(real["cuenta_id"], {
                "cuenta_id": real["cuenta_id"],
                "grupo_id": f"cuenta:{real['cuenta_id']}",
                "tipo": "individual",
                "fecha_notificacion": real["fecha_notificacion"],
                "medio": real["medio"],
                "cliente": real.get("nombre_cliente") or "",
                "telefono": real.get("telefono") or "",
                "telefono_normalizado": real.get("telefono_normalizado") or "",
                "fecha_vencimiento": real.get("fecha_vencimiento") or "",
                "cuenta_madre": cuenta_madre,
                "perfiles_totales": cuenta_madre.get("perfiles_totales", 0),
                "servicios": []
            })
            grupo["servicios"].append(real)
            if real["fecha_notificacion"] and (
                not grupo["fecha_notificacion"] or real["fecha_notificacion"] < grupo["fecha_notificacion"]
            ):
                grupo["fecha_notificacion"] = real["fecha_notificacion"]
            if real.get("fecha_vencimiento") and (
                not grupo["fecha_vencimiento"] or real["fecha_vencimiento"] < grupo["fecha_vencimiento"]
            ):
                grupo["fecha_vencimiento"] = real["fecha_vencimiento"]
            if real.get("tipo_notificacion") == "combo":
                grupo["tipo"] = "combo"
        pendientes = []
        for grupo in por_cuenta.values():
            grupo["pendientes_count"] = len(grupo["servicios"])
            grupo["vigentes_count"] = max(int(grupo.get("perfiles_totales") or 0) - grupo["pendientes_count"], 0)
            if grupo["pendientes_count"] > 1 and grupo["tipo"] != "combo":
                grupo["tipo"] = "individual"
            pendientes.append(grupo)
        pendientes.sort(key=lambda g: (g["fecha_notificacion"], (g["cuenta_madre"].get("correo") or "").casefold(), g["cuenta_id"]))
        hoy = _fecha_hoy_nube().isoformat()
        servicios_pendientes = sum(len(g["servicios"]) for g in pendientes)
        if retirados:
            conn.commit()
        return {
            "pendientes": pendientes,
            "historial": obtener_historial_cortes_nube(cursor),
            "resumen": {
                "cuentas_pendientes": len(pendientes),
                "servicios_pendientes": servicios_pendientes,
                "pendientes": len(pendientes),
                "notificados_hoy": sum(g["fecha_notificacion"].startswith(hoy) for g in pendientes),
                "mas_de_x_horas": sum(_horas_desde_nube(g["fecha_notificacion"]) >= 8 for g in pendientes),
                "combos": sum(1 for g in pendientes for s in g["servicios"] if s.get("tipo_notificacion") == "combo"),
                "individuales": sum(1 for g in pendientes for s in g["servicios"] if s.get("tipo_notificacion") != "combo"),
                "servicios_individuales": servicios_pendientes
            },
            "retirados_por_renovacion": retirados
        }
    finally:
        conn.close()


def actualizar_credenciales_cuenta_corte_nube(cuenta_id, correo=None, contrasena=None, pin=None):
    try:
        cuenta_id = int(cuenta_id or 0)
    except (TypeError, ValueError):
        cuenta_id = 0
    correo = (correo or "").strip()
    contrasena = (contrasena or "").strip()
    pin_recibido = pin is not None
    pin = (pin or "").strip()
    if cuenta_id <= 0:
        return {"ok": False, "mensaje": "Cuenta invalida."}
    if not correo:
        return {"ok": False, "mensaje": "El correo no puede estar vacio."}
    if not contrasena:
        return {"ok": False, "mensaje": "La contrasena no puede estar vacia."}
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("""
            SELECT id, correo, contrasena, pin
            FROM nube_cuentas
            WHERE id = ?
        """, (cuenta_id,))
        actual = cursor.fetchone()
        if not actual:
            conn.rollback()
            return {"ok": False, "mensaje": "La cuenta madre no existe."}
        pin_final = pin if pin_recibido else (actual["pin"] or "")
        cursor.execute("""
            UPDATE nube_cuentas
            SET correo = ?, contrasena = ?, pin = ?,
                fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (correo, contrasena, pin_final, cuenta_id))
        if cursor.rowcount != 1:
            raise RuntimeError("La cuenta cambio durante la actualizacion de credenciales.")
        cursor.execute("""
            INSERT INTO nube_movimientos (
                cuenta_id, tipo, descripcion, estado_anterior,
                estado_nuevo, cliente_nombre
            ) VALUES (?, 'credenciales_actualizadas_corte', ?, '', '', '')
        """, (
            cuenta_id,
            "Credenciales de cuenta madre actualizadas desde Cortes"
        ))
        cursor.execute("""
            SELECT id, correo, contrasena, pin
            FROM nube_cuentas
            WHERE id = ?
        """, (cuenta_id,))
        persistida = dict(cursor.fetchone())
        conn.commit()
        return {
            "ok": True,
            "mensaje": "Datos de la cuenta actualizados.",
            "cuenta": persistida
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def actualizar_pin_perfil_corte_nube(cuenta_id, perfil_id, pin=None):
    try:
        cuenta_id = int(cuenta_id or 0)
        perfil_id = int(perfil_id or 0)
    except (TypeError, ValueError):
        return {"ok": False, "mensaje": "Perfil invalido."}
    pin = (pin or "").strip()
    if cuenta_id <= 0 or perfil_id <= 0:
        return {"ok": False, "mensaje": "Perfil invalido."}
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("""
            SELECT id, cuenta_id, nombre_perfil
            FROM nube_perfiles
            WHERE id = ?
        """, (perfil_id,))
        perfil = cursor.fetchone()
        if not perfil or int(perfil["cuenta_id"] or 0) != cuenta_id:
            conn.rollback()
            return {"ok": False, "mensaje": "El perfil no pertenece a esta cuenta madre."}
        cursor.execute("""
            UPDATE nube_perfiles
            SET pin = ?, fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ? AND cuenta_id = ?
        """, (pin, perfil_id, cuenta_id))
        if cursor.rowcount != 1:
            raise RuntimeError("El perfil cambio durante la actualizacion del PIN.")
        cursor.execute("""
            INSERT INTO nube_movimientos (
                cuenta_id, tipo, descripcion, estado_anterior,
                estado_nuevo, cliente_nombre
            ) VALUES (?, 'pin_perfil_actualizado_corte', ?, '', '', '')
        """, (
            cuenta_id,
            f"PIN de perfil actualizado desde Cortes ({perfil['nombre_perfil'] or 'Perfil'})"
        ))
        cursor.execute("""
            SELECT id, cuenta_id, pin
            FROM nube_perfiles
            WHERE id = ? AND cuenta_id = ?
        """, (perfil_id, cuenta_id))
        persistido = dict(cursor.fetchone())
        conn.commit()
        return {"ok": True, "mensaje": "PIN del perfil actualizado.", "perfil": persistido}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _limpiar_servicio_cortado_nube(cursor, servicio):
    if servicio["servicio_tipo"] == "perfil":
        cursor.execute("""
            UPDATE nube_perfiles
            SET cliente_id = NULL, nombre_cliente = '', telefono = '',
                fecha_entrega = '', dias_cuenta = 0, fecha_vencimiento = '',
                estado = 'disponible', fecha_actualizacion = CURRENT_TIMESTAMP
            WHERE id = ? AND fecha_vencimiento = ?
        """, (servicio["servicio_id"], servicio["fecha_vencimiento"]))
        return cursor.rowcount
    cursor.execute("""
        UPDATE nube_cuentas
        SET cliente_id = NULL, nombre_cliente = '', telefono = '',
            fecha_entrega = '', dias_cuenta = 0, fecha_vencimiento = '',
            estado = 'disponible', fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = ? AND fecha_vencimiento = ?
    """, (servicio["servicio_id"], servicio["fecha_vencimiento"]))
    return cursor.rowcount


def cortar_servicios_nube(servicios_payload, motivo="", actor_id=None):
    solicitados = {}
    for item in (servicios_payload or []):
        servicio_tipo = str(item.get("servicio_tipo") or "")
        if servicio_tipo not in {"perfil", "cuenta_completa"}:
            continue
        try:
            servicio_id = int(item.get("servicio_id") or 0)
            cuenta_id = int(item.get("cuenta_id") or 0)
        except (TypeError, ValueError):
            continue
        if servicio_id > 0:
            solicitados[(servicio_tipo, servicio_id)] = cuenta_id
    if not solicitados:
        return {"ok": False, "mensaje": "Selecciona al menos un servicio para cortar."}
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        _asegurar_notificaciones_renovacion_nube(cursor)
        reales = {(s["servicio_tipo"], int(s["servicio_id"])): s for s in _leer_servicios_vencidos_reales_nube(cursor)}
        cortados = 0
        retirados = 0
        omitidos = []
        for clave, cuenta_id_payload in solicitados.items():
            servicio = reales.get(clave)
            if not servicio:
                cursor.execute("""
                    UPDATE nube_notificacion_servicios
                    SET estado = 'retirado_renovacion',
                        fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE servicio_tipo = ? AND servicio_id = ?
                      AND estado = 'pendiente_corte'
                """, clave)
                retirados += cursor.rowcount
                omitidos.append({"servicio_tipo": clave[0], "servicio_id": clave[1], "codigo": "servicio_renovado"})
                continue
            if cuenta_id_payload and int(servicio["cuenta_id"] or 0) != cuenta_id_payload:
                conn.rollback()
                return {"ok": False, "mensaje": "El servicio no pertenece a esta cuenta madre."}
            cursor.execute("""
                SELECT id FROM nube_notificacion_servicios
                WHERE servicio_tipo = ? AND servicio_id = ?
                  AND fecha_vencimiento_ciclo = ?
                  AND estado = 'pendiente_corte'
            """, (servicio["servicio_tipo"], servicio["servicio_id"], servicio["fecha_vencimiento"]))
            fila_notificada = cursor.fetchone()
            if not fila_notificada:
                conn.rollback()
                return {"ok": False, "mensaje": "El servicio no tiene una notificacion pendiente de corte."}
            snapshot = _snapshot_notificacion_servicio_nube(servicio)
            if _limpiar_servicio_cortado_nube(cursor, servicio) != 1:
                raise RuntimeError("El servicio cambio durante el corte.")
            # Import local para evitar el ciclo database <-> reseller_accounts.
            import reseller_accounts
            reseller_accounts.registrar_corte_purchase_reseller(
                cursor=cursor,
                cuenta_id=servicio["cuenta_id"],
                perfil_id=(servicio["servicio_id"] if servicio["servicio_tipo"] == "perfil" else None),
                motivo=motivo,
                actor_id=actor_id,
            )
            cursor.execute("""
                UPDATE nube_notificacion_servicios
                SET snapshot = ?, estado = 'cortado',
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (snapshot, fila_notificada["id"]))
            cursor.execute("""
                INSERT INTO nube_movimientos (
                    cuenta_id, tipo, descripcion, estado_anterior,
                    estado_nuevo, cliente_nombre
                ) VALUES (?, 'servicio_cortado', ?, ?, 'disponible', ?)
            """, (
                servicio["cuenta_id"],
                "Servicio cortado manualmente desde Cortes" + (f". Motivo: {(motivo or '').strip()}" if (motivo or "").strip() else ""),
                servicio.get("estado") or "",
                servicio.get("nombre_cliente") or ""
            ))
            cortados += 1
        conn.commit()
        if cortados:
            mensaje = f"{cortados} servicio(s) cortado(s)."
            if retirados:
                mensaje += f" {retirados} retirado(s) porque ya no eran elegibles."
            return {"ok": True, "cortados": cortados, "retirados": retirados, "omitidos": omitidos, "mensaje": mensaje}
        return {
            "ok": False,
            "codigo": "sin_elegibles",
            "cortados": 0,
            "retirados": retirados,
            "omitidos": omitidos,
            "mensaje": "Ningun servicio seguia pendiente de corte."
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _servicio_vigente_pendiente_nube(servicio):
    estado = (servicio.get("estado") or "").strip().lower()
    if estado in {"reemplazada", "papelera"}:
        return False
    if not es_asignacion_operativa_nube(
        servicio.get("nombre_cliente"), servicio.get("fecha_entrega"),
        servicio.get("dias_cuenta"), servicio.get("fecha_vencimiento")
    ):
        return False
    return calcular_dias_restantes(servicio.get("fecha_vencimiento")) >= 0


def _servicio_vencido_nube(servicio):
    return es_asignacion_operativa_nube(
        servicio.get("nombre_cliente"), servicio.get("fecha_entrega"),
        servicio.get("dias_cuenta"), servicio.get("fecha_vencimiento")
    ) and calcular_dias_restantes(servicio.get("fecha_vencimiento")) < 0


def _asegurar_archivo_asignaciones_nube(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS nube_archivos_asignaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cuenta_id INTEGER NOT NULL,
        perfil_id INTEGER, tipo_origen TEXT NOT NULL DEFAULT 'perfil',
        snapshot TEXT NOT NULL, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")


def _limpiar_y_habilitar_cuenta_nube(cursor, cuenta_id, estado_perfiles="disponible"):
    cursor.execute("""UPDATE nube_perfiles SET cliente_id=NULL,nombre_cliente='',
        telefono='',fecha_entrega='',dias_cuenta=0,fecha_vencimiento='',estado=?,
        fecha_actualizacion=CURRENT_TIMESTAMP WHERE cuenta_id=?""",
        (estado_perfiles, cuenta_id))
    return cursor.rowcount


def _resumen_papelera_cuenta(cursor, cuenta_id):
    cursor.execute("""
        SELECT id, nombre_perfil, estado, cliente_id, nombre_cliente,
               fecha_entrega, dias_cuenta, fecha_vencimiento
        FROM nube_perfiles WHERE cuenta_id = ? ORDER BY orden, id
    """, (cuenta_id,))
    perfiles = [dict(fila) for fila in cursor.fetchall()]
    pendientes = [p for p in perfiles if _servicio_vigente_pendiente_nube(p)]
    return perfiles, pendientes


def mover_cuenta_papelera_nube(cuenta_id, motivo=""):
    """Archiva una madre caída sólo cuando no quedan servicios por resolver."""
    try:
        cuenta_id = int(cuenta_id)
    except (TypeError, ValueError):
        return {"ok": False, "codigo": "cuenta_invalida", "mensaje": "Cuenta inválida."}
    conn = conectar()
    try:
        cursor = conn.cursor(); cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("""SELECT id, estado, modalidad, nombre_cliente,
            fecha_entrega, dias_cuenta, fecha_vencimiento
            FROM nube_cuentas WHERE id = ?""", (cuenta_id,))
        cuenta = cursor.fetchone()
        if not cuenta:
            raise ValueError("La cuenta no existe.")
        if cuenta["estado"] == "papelera":
            conn.rollback(); return {"ok": True, "duplicado": True, "estado": "papelera"}
        if cuenta["estado"] != "caida":
            raise ValueError("Sólo una cuenta caída puede moverse a Papelera.")
        perfiles, pendientes = _resumen_papelera_cuenta(cursor, cuenta_id)
        cuenta_dict = dict(cuenta)
        if (cuenta["modalidad"] or "cuenta_completa") == "cuenta_completa" and _servicio_vigente_pendiente_nube(cuenta_dict):
            pendientes.append({"id": None, "nombre_perfil": "Cuenta completa"})
        if pendientes:
            cantidad = len(pendientes)
            raise ValueError(f"Falta {cantidad} servicio vigente por resolver." if cantidad == 1 else f"Faltan {cantidad} servicios vigentes por resolver.")
        _asegurar_archivo_asignaciones_nube(cursor)
        for perfil in perfiles:
            if es_asignacion_operativa_nube(perfil.get("nombre_cliente"), perfil.get("fecha_entrega"), perfil.get("dias_cuenta"), perfil.get("fecha_vencimiento")):
                snapshot = _crear_snapshot_servicio_nube(cursor, perfil["id"])
                cursor.execute("""INSERT INTO nube_archivos_asignaciones
                    (cuenta_id,perfil_id,tipo_origen,snapshot) VALUES (?,?,'perfil',?)""",
                    (cuenta_id, perfil["id"], snapshot))
        if (cuenta["modalidad"] or "cuenta_completa") == "cuenta_completa" and es_asignacion_operativa_nube(
            cuenta["nombre_cliente"], cuenta["fecha_entrega"], cuenta["dias_cuenta"], cuenta["fecha_vencimiento"]):
            cursor.execute("""INSERT INTO nube_archivos_asignaciones
                (cuenta_id,perfil_id,tipo_origen,snapshot) VALUES (?,NULL,'cuenta_completa',?)""",
                (cuenta_id, json.dumps(cuenta_dict, ensure_ascii=False, sort_keys=True)))
        _limpiar_y_habilitar_cuenta_nube(cursor, cuenta_id, "papelera")
        cursor.execute("""UPDATE nube_cuentas SET estado='papelera',
            fecha_archivada=datetime('now','localtime'), motivo_archivo=?,
            cliente_id=NULL,nombre_cliente='',telefono='',fecha_entrega='',
            dias_cuenta=0,fecha_vencimiento='',
            fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=? AND estado='caida'""",
            ((motivo or "").strip(), cuenta_id))
        if cursor.rowcount != 1:
            raise RuntimeError("La cuenta cambió durante la operación.")
        cursor.execute("""INSERT INTO nube_movimientos
            (cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo)
            VALUES (?,'cuenta_movida_papelera',?,'caida','papelera')""",
            (cuenta_id, "Cuenta archivada" + (f". Motivo: {motivo.strip()}" if motivo.strip() else "")))
        conn.commit()
        return {"ok": True, "duplicado": False, "estado": "papelera",
                "perfiles": len(perfiles)}
    except (ValueError, RuntimeError) as error:
        conn.rollback(); return {"ok": False, "codigo": "no_elegible", "mensaje": str(error)}
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()


def obtener_cuentas_papelera_nube():
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("""SELECT c.id,c.plataforma,c.correo,c.estado,c.modalidad,c.tipo_pago,
        c.valor_pin,c.plan_pago,c.fecha_aplicacion_pin,c.fecha_proximo_pago,
        c.fecha_archivada,c.motivo_archivo,COUNT(p.id) perfiles_totales,
        (SELECT tipo FROM nube_movimientos m WHERE m.cuenta_id=c.id ORDER BY m.id DESC LIMIT 1) ultimo_movimiento
        FROM nube_cuentas c LEFT JOIN nube_perfiles p ON p.cuenta_id=c.id
        WHERE c.estado='papelera' GROUP BY c.id ORDER BY c.fecha_archivada DESC,c.id DESC""")
    cuentas = [dict(fila) for fila in cursor.fetchall()]; conn.close(); return cuentas


def obtener_detalle_papelera_nube(cuenta_id):
    conn = conectar(); cursor = conn.cursor()
    cursor.execute("""SELECT id,plataforma,correo,estado,modalidad,tipo_pago,valor_pin,
        plan_pago,precio_plan_referencia,fecha_aplicacion_pin,fecha_proximo_pago,
        fecha_archivada,motivo_archivo FROM nube_cuentas WHERE id=? AND estado='papelera'""", (cuenta_id,))
    fila = cursor.fetchone()
    if not fila: conn.close(); return None
    cuenta = dict(fila); perfiles, _ = _resumen_papelera_cuenta(cursor, cuenta_id)
    cursor.execute("""SELECT id,tipo,descripcion,estado_anterior,estado_nuevo,cliente_nombre,fecha
        FROM nube_movimientos WHERE cuenta_id=? ORDER BY id DESC LIMIT 50""", (cuenta_id,))
    movimientos = [dict(x) for x in cursor.fetchall()]
    cursor.execute("""SELECT id,valor_pin,plan,precio_plan_referencia,fecha_aplicacion,
        dias_estimados,fecha_estimada_fin,notas FROM nube_pagos_pin WHERE cuenta_id=?
        ORDER BY id DESC LIMIT 20""", (cuenta_id,))
    pagos = [dict(x) for x in cursor.fetchall()]
    _asegurar_archivo_asignaciones_nube(cursor)
    cursor.execute("""SELECT id,perfil_id,tipo_origen,snapshot,fecha
        FROM nube_archivos_asignaciones WHERE cuenta_id=? ORDER BY id DESC""", (cuenta_id,))
    snapshots = [dict(x) for x in cursor.fetchall()]
    for item in snapshots:
        item["datos"] = json.loads(item.pop("snapshot"))
    conn.close()
    return {"cuenta": cuenta, "perfiles": perfiles, "movimientos": movimientos,
            "historial_pin": pagos, "snapshots": snapshots}


def restaurar_cuenta_papelera_nube(cuenta_id):
    """Reactiva la madre y libera sus slots sin reactivar asignaciones antiguas."""
    try: cuenta_id = int(cuenta_id)
    except (TypeError, ValueError): return {"ok": False, "mensaje": "Cuenta inválida."}
    conn = conectar()
    try:
        cursor = conn.cursor(); cursor.execute("BEGIN IMMEDIATE")
        cursor.execute("SELECT id,estado,modalidad FROM nube_cuentas WHERE id=?", (cuenta_id,))
        cuenta = cursor.fetchone()
        if not cuenta: raise ValueError("La cuenta no existe.")
        if cuenta["estado"] != "papelera":
            conn.rollback(); return {"ok": True, "duplicado": True, "estado": cuenta["estado"]}
        perfiles, pendientes = _resumen_papelera_cuenta(cursor, cuenta_id)
        if cuenta["modalidad"] == "perfiles":
            _limpiar_y_habilitar_cuenta_nube(cursor, cuenta_id)
        cursor.execute("""UPDATE nube_cuentas SET estado='disponible',fecha_archivada='',
            motivo_archivo='',cliente_id=NULL,nombre_cliente='',telefono='',fecha_entrega='',
            dias_cuenta=0,fecha_vencimiento='',fecha_actualizacion=CURRENT_TIMESTAMP
            WHERE id=? AND estado='papelera'""", (cuenta_id,))
        cursor.execute("""INSERT INTO nube_movimientos
            (cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo)
            VALUES (?,'cuenta_restaurada','Cuenta restaurada sin reactivar clientes anteriores','papelera','disponible')""", (cuenta_id,))
        conn.commit(); return {"ok": True, "duplicado": False, "estado": "disponible", "perfiles": len(perfiles)}
    except ValueError as error:
        conn.rollback(); return {"ok": False, "mensaje": str(error)}
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

# ==========================================
# NUBE DE CUENTAS — BUSCADOR UNIVERSAL
# ==========================================

def buscar_cuentas_nube(
    termino="",
    plataforma="",
    tipo_cuenta="",
    estado="",
    limite=25,
    offset=0
):

    conn = conectar()
    cursor = conn.cursor()


    termino = (
        termino or ""
    ).strip()

    plataforma = (
        plataforma or ""
    ).strip()

    tipo_cuenta = (
        tipo_cuenta or ""
    ).strip()

    estado = (
        estado or ""
    ).strip()


    condiciones = ["COALESCE(estado, '') != 'papelera'"]

    parametros = []


    # ==========================================
    # BÚSQUEDA GENERAL
    # ==========================================

    if termino:

        like = f"%{termino}%"

        condiciones.append(
            """
            (
                correo LIKE ?
                OR contrasena LIKE ?
                OR pin LIKE ?
                OR nombre_cliente LIKE ?
                OR telefono LIKE ?
                OR plataforma LIKE ?
                OR tipo_cuenta LIKE ?
                OR notas LIKE ?
            )
            """
        )

        parametros.extend([
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like
        ])


    # ==========================================
    # FILTRO PLATAFORMA
    # ==========================================

    if plataforma:

        condiciones.append(
            "plataforma = ?"
        )

        parametros.append(
            plataforma
        )


    # ==========================================
    # FILTRO TIPO DE CUENTA
    # ==========================================

    if tipo_cuenta:

        condiciones.append(
            "tipo_cuenta = ?"
        )

        parametros.append(
            tipo_cuenta
        )


    # ==========================================
    # FILTRO ESTADO
    # ==========================================

    if estado:

        condiciones.append(
            "estado = ?"
        )

        parametros.append(
            estado
        )


    where_sql = ""


    if condiciones:

        where_sql = (
            "WHERE " +
            " AND ".join(
                condiciones
            )
        )


    consulta = f"""
        SELECT

            id,
            plataforma,
            correo,
            contrasena,
            pin,
            tipo_cuenta,
            cliente_id,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            garantia_usada,
            cantidad_garantias,
            notas,
            origen,
            fecha_creacion,
            fecha_actualizacion

        FROM nube_cuentas

        {where_sql}

        ORDER BY id DESC

        LIMIT ?
        OFFSET ?
    """


    parametros.extend([
        limite,
        offset
    ])


    cursor.execute(
        consulta,
        parametros
    )


    filas = cursor.fetchall()

    conn.close()


    return [
        preparar_cuenta_nube(
            fila
        )
        for fila in filas
    ]

# ==========================================
# NUBE DE CUENTAS — PLATAFORMAS DINÁMICAS
# ==========================================

def obtener_plataformas_nube():

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute("""
        SELECT DISTINCT
            TRIM(plataforma) AS plataforma
        FROM nube_cuentas
        WHERE plataforma IS NOT NULL
          AND TRIM(plataforma) != ''
          AND COALESCE(estado, '') != 'papelera'
        ORDER BY plataforma ASC
    """)


    filas = cursor.fetchall()

    conn.close()


    return [
        fila["plataforma"]
        for fila in filas
    ]


# ==========================================
# NUBE DE CUENTAS — TIPOS DINÁMICOS
# ==========================================

def obtener_tipos_cuenta_nube():

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute("""
        SELECT DISTINCT
            TRIM(tipo_cuenta) AS tipo_cuenta
        FROM nube_cuentas
        WHERE tipo_cuenta IS NOT NULL
          AND TRIM(tipo_cuenta) != ''
          AND COALESCE(estado, '') != 'papelera'
        ORDER BY tipo_cuenta ASC
    """)


    filas = cursor.fetchall()

    conn.close()


    etiquetas = {}
    for fila in filas:
        valor = (fila["tipo_cuenta"] or "").strip()
        clave = re.sub(r"[^a-z0-9]+", "_", valor.lower()).strip("_")
        if clave in {"cuenta_completa", "cuenta_completas", "completa", "completas"}:
            etiquetas["cuenta_completa"] = "Cuenta completa"
        elif clave in {"perfil", "perfiles"}:
            etiquetas["perfiles"] = "Perfiles"
        elif clave in {"perfil_extra", "miembro_extra"}:
            etiquetas["perfil_extra"] = "Perfil Extra"
        elif clave == "plan_estandar":
            etiquetas["plan_estandar"] = "Plan estándar"
        elif valor:
            etiquetas[clave] = valor

    return [
        etiquetas[clave]
        for clave in sorted(etiquetas)
    ]


# ==========================================
# NUBE DE CUENTAS — GENERAR PERFILES
# ==========================================

def generar_perfiles_nube(
    cuenta_id,
    cantidad,
    pines_perfiles=None
):

    conn = conectar()
    cursor = conn.cursor()


    try:

        cantidad = int(
            cantidad or 0
        )

    except (
        ValueError,
        TypeError
    ):

        cantidad = 0


    if cantidad <= 0:

        conn.close()

        return 0


    # ==========================================
    # NORMALIZAR LISTA DE PINES
    # ==========================================

    if not isinstance(
        pines_perfiles,
        (list, tuple)
    ):

        pines_perfiles = []


    pines_limpios = [
        str(pin or "").strip()
        for pin in pines_perfiles
    ]


    # ==========================================
    # SABER CUÁNTOS PERFILES YA EXISTEN
    # ==========================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM nube_perfiles
        WHERE cuenta_id = ?
        """,
        (
            cuenta_id,
        )
    )


    existentes = (
        cursor.fetchone()[0]
    )


    creados = 0


    # ==========================================
    # CREAR PERFILES NUEVOS
    # ==========================================

    for numero in range(
        existentes + 1,
        cantidad + 1
    ):

        indice_pin = (
            numero - 1
        )


        pin_perfil = ""


        if (
            indice_pin <
            len(pines_limpios)
        ):

            pin_perfil = (
                pines_limpios[
                    indice_pin
                ]
            )


        cursor.execute(
            """
            INSERT INTO nube_perfiles (

                cuenta_id,
                nombre_perfil,
                pin,
                estado,
                orden

            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cuenta_id,
                f"Perfil {numero}",
                pin_perfil,
                "disponible",
                numero
            )
        )


        creados += 1


    # ==========================================
    # ACTUALIZAR CUENTA MADRE
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_cuentas

        SET
            modalidad = ?,
            cantidad_perfiles = ?,
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            "perfiles",
            cantidad,
            cuenta_id
        )
    )


    conn.commit()
    conn.close()


    return creados


# ==========================================
# NUBE DE CUENTAS — OBTENER PERFILES
# ==========================================

def preparar_perfil_nube(fila):
    """Conserva en un solo lugar los campos calculados de un perfil."""
    perfil = dict(fila)
    fecha_vencimiento = perfil.get("fecha_vencimiento") or ""
    estado_actual = perfil.get("estado") or "disponible"
    dias_restantes = calcular_dias_restantes(fecha_vencimiento) if fecha_vencimiento else 0
    if estado_actual in {"activa", "por_vencer", "vencida"}:
        estado_calculado = calcular_estado_nube(fecha_vencimiento, estado_actual)
    else:
        estado_calculado = estado_actual
    perfil["dias_restantes"] = dias_restantes
    perfil["estado_calculado"] = estado_calculado
    return perfil


def obtener_perfiles_nube(
    cuenta_id
):

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT

            id,
            cuenta_id,
            nombre_perfil,
            pin,
            cliente_id,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            garantia_usada,
            cantidad_garantias,
            notas,
            orden,
            fecha_creacion,
            fecha_actualizacion

        FROM nube_perfiles

        WHERE cuenta_id = ?

        ORDER BY
            orden ASC,
            id ASC
        """,
        (
            cuenta_id,
        )
    )


    filas = cursor.fetchall()

    conn.close()


    return [preparar_perfil_nube(fila) for fila in filas]

# ==========================================
# NUBE — CALCULAR DÍAS DE UN PIN
# ==========================================

def calcular_dias_pin_nube(
    valor_pin,
    precio_plan
):

    try:

        valor_pin = int(
            valor_pin or 0
        )

        precio_plan = int(
            precio_plan or 0
        )

    except (
        ValueError,
        TypeError
    ):

        return 0


    if (
        valor_pin <= 0 or
        precio_plan <= 0
    ):

        return 0


    dias_estimados = int(
        (
            valor_pin /
            precio_plan
        ) * 30
    )


    return max(
        dias_estimados,
        1
    )


# ==========================================
# NUBE — FECHA ESTIMADA DE PRÓXIMO PAGO
# ==========================================

def calcular_fecha_pago_pin_nube(
    fecha_aplicacion,
    dias_estimados
):

    if not fecha_aplicacion:

        return ""


    try:

        fecha = datetime.strptime(
            fecha_aplicacion,
            "%Y-%m-%d"
        )

        dias = int(
            dias_estimados or 0
        )

    except (
        ValueError,
        TypeError
    ):

        return ""


    if dias <= 0:

        return ""


    fecha_final = (
        fecha +
        timedelta(days=dias)
    )


    return fecha_final.strftime(
        "%Y-%m-%d"
    )


# ==========================================
# NUBE — ESTADO DE PAGO
# ==========================================

def calcular_estado_pago_nube(
    tipo_pago,
    fecha_proximo_pago=""
):

    tipo_pago = (
        tipo_pago or ""
    ).strip().lower()


    if tipo_pago == "autopagable":

        return "autopagable"


    if tipo_pago != "pin":

        return ""


    if not fecha_proximo_pago:

        return "sin_fecha"


    try:

        fecha_pago = datetime.strptime(
            fecha_proximo_pago,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return "sin_fecha"


    hoy = datetime.now().date()

    dias_restantes = (
        fecha_pago - hoy
    ).days


    if dias_restantes <= 0:

        return "pago_pendiente"


    if dias_restantes == 1:

        return "actualizar_pago"


    return "al_dia"


# ==========================================
# NUBE — ACTUALIZAR / ASIGNAR PERFIL
# ==========================================

def _obtener_datos_entrega_perfil_nube(cursor, perfil_id):

    cursor.execute(
        """
        SELECT
            c.plataforma,
            c.correo,
            c.contrasena,
            p.nombre_perfil,
            p.pin,
            p.nombre_cliente AS cliente,
            p.telefono,
            p.fecha_vencimiento
        FROM nube_perfiles AS p
        INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
        WHERE p.id = ?
        """,
        (perfil_id,)
    )

    fila = cursor.fetchone()
    if not fila:
        return None

    return {
        "plataforma": fila["plataforma"] or "",
        "correo": fila["correo"] or "",
        "contrasena": fila["contrasena"] or "",
        "nombre_perfil": fila["nombre_perfil"] or "",
        "pin": fila["pin"] or "",
        "cliente": fila["cliente"] or "",
        "telefono": fila["telefono"] or "",
        "fecha_vencimiento": fila["fecha_vencimiento"] or ""
    }


def actualizar_perfil_nube(
    perfil_id,
    pin="",
    nombre_cliente="",
    telefono="",
    fecha_entrega="",
    dias_cuenta=0,
    notas=""
):

    conn = conectar()
    cursor = conn.cursor()


    # ==========================================
    # LIMPIAR DATOS
    # ==========================================

    pin = (
        pin or ""
    ).strip()

    nombre_cliente = (
        nombre_cliente or ""
    ).strip()

    telefono = (
        telefono or ""
    ).strip()

    fecha_entrega = (
        fecha_entrega or ""
    ).strip()

    notas = (
        notas or ""
    ).strip()


    try:

        dias_cuenta = int(
            dias_cuenta or 0
        )

    except (
        ValueError,
        TypeError
    ):

        dias_cuenta = 0


    if dias_cuenta < 0:

        dias_cuenta = 0

    conn.execute("BEGIN IMMEDIATE")


    # ==========================================
    # ESTADO DE LA CUENTA MADRE
    # ==========================================

    cursor.execute(
        """
        SELECT
            c.estado AS estado_cuenta,
            p.estado AS estado_perfil,
            p.cliente_id AS cliente_id_actual,
            p.nombre_cliente AS nombre_cliente_actual,
            p.fecha_entrega AS fecha_entrega_actual,
            p.dias_cuenta AS dias_cuenta_actual,
            p.fecha_vencimiento AS fecha_vencimiento_actual

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE p.id = ?
        """,
        (
            perfil_id,
        )
    )


    fila_cuenta = cursor.fetchone()


    estado_cuenta = (
        fila_cuenta["estado_cuenta"]
        if fila_cuenta
        else ""
    ) or ""


    estado_perfil = (
        fila_cuenta["estado_perfil"]
        if fila_cuenta
        else ""
    ) or ""

    cliente_id_actual = (
        fila_cuenta["cliente_id_actual"]
        if fila_cuenta
        else None
    )

    asignacion_operativa_actual = bool(
        fila_cuenta and es_asignacion_operativa_nube(
            fila_cuenta["nombre_cliente_actual"],
            fila_cuenta["fecha_entrega_actual"],
            fila_cuenta["dias_cuenta_actual"],
            fila_cuenta["fecha_vencimiento_actual"]
        )
    )


    if estado_perfil in {
        "reemplazada",
        "papelera"
    }:

        conn.close()
        return False



    # ==========================================
    # SABER SI EL PERFIL ESTÁ ASIGNADO
    # ==========================================

    perfil_asignado = bool(
        nombre_cliente and
        fecha_entrega and
        dias_cuenta > 0
    )

    if asignacion_operativa_actual and not perfil_asignado:
        conn.rollback()
        conn.close()
        return {
            "ok": False,
            "codigo": "liberacion_requerida",
            "mensaje": (
                "Un perfil vendido no puede desasignarse desde Guardar perfil. "
                "Usa ‘Cambiar / liberar servicio’."
            )
        }

    cliente_id = None

    if perfil_asignado:
        cliente_id = _obtener_o_crear_cliente_nube(
            cursor,
            nombre_cliente,
            telefono
        )

        if cliente_id is None and fila_cuenta:
            cliente_id = fila_cuenta["cliente_id_actual"]


    # ==========================================
    # CALCULAR VENCIMIENTO Y ESTADO
    # ==========================================

    fecha_vencimiento = ""


    if perfil_asignado:

        fecha_vencimiento = (
            calcular_fecha_vencimiento(
                fecha_entrega,
                dias_cuenta
            )
        )


        # ==========================================
        # SI LA MADRE ESTÁ CAÍDA,
        # EL PERFIL NO PUEDE REVIVIR
        # ==========================================

        if estado_cuenta == "caida":

            estado = "caida"

        else:

            estado = calcular_estado_nube(
                fecha_vencimiento,
                estado_actual="activa"
            )


    else:

        # ==========================================
        # INCLUSO UN PERFIL SIN CLIENTE
        # SIGUE CAÍDO SI LA MADRE ESTÁ CAÍDA
        # ==========================================

        if estado_cuenta == "caida":

            estado = "caida"

        else:

            estado = "disponible"


        fecha_entrega = ""
        dias_cuenta = 0
        fecha_vencimiento = ""

        fecha_entrega = ""

        dias_cuenta = 0

        fecha_vencimiento = ""


    # ==========================================
    # ACTUALIZAR PERFIL
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_perfiles

        SET
            pin = ?,
            cliente_id = ?,
            nombre_cliente = ?,
            telefono = ?,
            fecha_entrega = ?,
            dias_cuenta = ?,
            fecha_vencimiento = ?,
            estado = ?,
            notas = ?,
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            pin,
            cliente_id,
            nombre_cliente,
            telefono,
            fecha_entrega,
            dias_cuenta,
            fecha_vencimiento,
            estado,
            notas,
            perfil_id
        )
    )


    actualizado = (
        cursor.rowcount > 0
    )


    datos_entrega = (
        _obtener_datos_entrega_perfil_nube(cursor, perfil_id)
        if actualizado and perfil_asignado
        else None
    )

    conn.commit()
    conn.close()

    if not actualizado:
        return False

    return {
        "ok": True,
        "estado": estado,
        "fecha_vencimiento": fecha_vencimiento,
        "datos_entrega": datos_entrega
    }

# ==========================================
# NUBE — RENOVAR PERFIL
# ==========================================

def renovar_perfil_nube(
    perfil_id,
    dias_renovacion
):

    conn = conectar()
    cursor = conn.cursor()


    try:

        perfil_id = int(
            perfil_id
        )

        dias_renovacion = int(
            dias_renovacion
        )

    except (
        ValueError,
        TypeError
    ):

        conn.close()

        return False


    if (
        perfil_id <= 0 or
        dias_renovacion <= 0
    ):

        conn.close()
        return False


    # ==========================================
    # BUSCAR PERFIL
    # ==========================================

    cursor.execute(
        """
        SELECT
            fecha_vencimiento,
            estado,
            nombre_cliente

        FROM nube_perfiles

        WHERE id = ?
        """,
        (
            perfil_id,
        )
    )


    perfil = cursor.fetchone()


    if not perfil:

        conn.close()

        return False


    # No renovamos perfiles libres
    if (
        not perfil["nombre_cliente"] or
        perfil["estado"] in {
            "disponible",
            "caida",
            "reemplazada",
            "papelera"
        }
    ):

        conn.close()

        return False


    hoy = datetime.now().date()


    fecha_actual = None


    if perfil["fecha_vencimiento"]:

        try:

            fecha_actual = datetime.strptime(
                perfil["fecha_vencimiento"],
                "%Y-%m-%d"
            ).date()

        except ValueError:

            fecha_actual = None


    # ==========================================
    # DEFINIR DESDE DÓNDE RENOVAMOS
    # ==========================================

    if (
        fecha_actual and
        fecha_actual > hoy
    ):

        fecha_base = fecha_actual

    else:

        fecha_base = hoy


    nueva_fecha = (
        fecha_base +
        timedelta(
            days=dias_renovacion
        )
    )


    nueva_fecha_texto = (
        nueva_fecha.strftime(
            "%Y-%m-%d"
        )
    )


    nuevo_estado = calcular_estado_nube(
        nueva_fecha_texto,
        estado_actual="activa"
    )


    # ==========================================
    # ACTUALIZAR PERFIL
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_perfiles

        SET
            fecha_vencimiento = ?,
            estado = ?,
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            nueva_fecha_texto,
            nuevo_estado,
            perfil_id
        )
    )


    actualizado = (
        cursor.rowcount > 0
    )

    datos_entrega = (
        _obtener_datos_entrega_perfil_nube(cursor, perfil_id)
        if actualizado
        else None
    )

    conn.commit()
    conn.close()


    if not actualizado:

        return False


    return {
        "ok": True,
        "fecha_vencimiento": nueva_fecha_texto,
        "estado": nuevo_estado,
        "datos_entrega": datos_entrega
}


# ==========================================
# NUBE — MARCAR PERFIL COMO CAÍDO
# ==========================================

def marcar_perfil_caido_nube(
    perfil_id,
    motivo=""
):

    conn = conectar()
    cursor = conn.cursor()


    try:

        perfil_id = int(
            perfil_id
        )

    except (
        ValueError,
        TypeError
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje": "Perfil inválido."
        }


    motivo = (
        motivo or ""
    ).strip()


    # ==========================================
    # BUSCAR PERFIL Y CUENTA MADRE
    # ==========================================

    cursor.execute(
        """
        SELECT
            p.id,
            p.cuenta_id,
            p.nombre_perfil,
            p.nombre_cliente,
            p.estado,
            p.fecha_vencimiento,

            c.plataforma,
            c.correo,
            c.estado AS estado_cuenta

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE p.id = ?
        """,
        (
            perfil_id,
        )
    )


    perfil = cursor.fetchone()


    if not perfil:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil no existe."
        }


    estado_anterior = (
        perfil["estado"] or
        "disponible"
    )


    # ==========================================
    # NO PERMITIR CAER HISTÓRICOS
    # ==========================================

    if estado_anterior in {
        "reemplazada",
        "papelera"
    }:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "Este perfil ya pertenece al historial y no puede marcarse como caído."
        }


    # ==========================================
    # DÍAS QUE LE QUEDABAN AL PERFIL SELECCIONADO
    # ==========================================

    dias_restantes = 0


    if perfil["fecha_vencimiento"]:

        dias_restantes = max(
            calcular_dias_restantes(
                perfil["fecha_vencimiento"]
            ),
            0
        )


    cuenta_id = perfil[
        "cuenta_id"
    ]


    # ==========================================
    # CONTAR PERFILES AFECTADOS
    # ==========================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM nube_perfiles

        WHERE
            cuenta_id = ?

            AND estado NOT IN (
                'reemplazada',
                'papelera'
            )
        """,
        (
            cuenta_id,
        )
    )


    perfiles_afectados = (
        cursor.fetchone()[0]
    )


    # ==========================================
    # MARCAR TODA LA CUENTA MADRE COMO CAÍDA
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_cuentas

        SET
            estado = 'caida',
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            cuenta_id,
        )
    )


    # ==========================================
    # MARCAR TODOS LOS PERFILES VIGENTES
    # DE ESA CUENTA COMO CAÍDOS
    #
    # NO TOCAMOS:
    # - reemplazada
    # - papelera
    #
    # porque son historial.
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_perfiles

        SET
            estado = 'caida',
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE
            cuenta_id = ?

            AND estado NOT IN (
                'reemplazada',
                'papelera'
            )
        """,
        (
            cuenta_id,
        )
    )


    # ==========================================
    # REGISTRAR MOVIMIENTO
    # ==========================================

    descripcion = (
        f"Cuenta madre {perfil['plataforma']} "
        f"marcada como caída desde "
        f"{perfil['nombre_perfil']} · "
        f"{perfiles_afectados} perfiles afectados"
    )


    if motivo:

        descripcion += (
            f" · Motivo: {motivo}"
        )


    cursor.execute(
        """
        INSERT INTO nube_movimientos (

            cuenta_id,
            tipo,
            descripcion,
            estado_anterior,
            estado_nuevo,
            cliente_nombre

        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            cuenta_id,

            "cuenta_caida",

            descripcion,

            perfil[
                "estado_cuenta"
            ] or "disponible",

            "caida",

            perfil[
                "nombre_cliente"
            ] or ""
        )
    )


    conn.commit()
    conn.close()


    return {
        "ok": True,

        "mensaje":
            f"Cuenta marcada como caída. "
            f"{perfiles_afectados} perfiles afectados.",

        "estado":
            "caida",

        "dias_restantes":
            dias_restantes,

        "cuenta_id":
            cuenta_id,

        "perfiles_afectados":
            perfiles_afectados
    }


# ==========================================
# NUBE — REEMPLAZAR PERFIL CAÍDO
# ==========================================

def reemplazar_perfil_nube(
    perfil_anterior_id,
    perfil_nuevo_id,
    motivo=""
):

    conn = conectar()
    cursor = conn.cursor()


    try:

        perfil_anterior_id = int(
            perfil_anterior_id
        )

        perfil_nuevo_id = int(
            perfil_nuevo_id
        )

    except (
        ValueError,
        TypeError
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje": "Perfiles inválidos."
        }


    if (
        perfil_anterior_id <= 0 or
        perfil_nuevo_id <= 0
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje": "No se pudo identificar uno de los perfiles."
        }


    if (
        perfil_anterior_id ==
        perfil_nuevo_id
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil de reemplazo debe ser diferente al perfil caído."
        }


    motivo = (
        motivo or ""
    ).strip()


    # Bloquea escritores concurrentes durante toda la
    # validacion y transferencia del reemplazo.
    conn.execute("BEGIN IMMEDIATE")


    # ==========================================
    # BUSCAR PERFIL ANTERIOR
    # ==========================================

    cursor.execute(
        """
        SELECT
            p.id,
            p.cuenta_id,
            p.nombre_perfil,
            p.pin,
            p.nombre_cliente,
            p.telefono,
            p.fecha_entrega,
            p.dias_cuenta,
            p.fecha_vencimiento,
            p.estado,
            p.cantidad_garantias,
            p.notas,
            c.plataforma

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE p.id = ?
        """,
        (
            perfil_anterior_id,
        )
    )


    perfil_anterior = (
        cursor.fetchone()
    )


    if not perfil_anterior:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "No se encontró el perfil caído."
        }


    if (
        perfil_anterior["estado"] !=
        "caida"
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "Solo se pueden reemplazar perfiles marcados como caída."
        }


    if not perfil_anterior[
        "nombre_cliente"
    ]:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil caído no tiene un cliente asignado."
        }


    # ==========================================
    # BUSCAR PERFIL NUEVO
    # ==========================================

    cursor.execute(
        """
        SELECT
            p.id,
            p.cuenta_id,
            p.nombre_perfil,
            p.pin,
            p.estado,
            c.plataforma,
            c.estado AS estado_cuenta,
            c.modalidad

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE p.id = ?
        """,
        (
            perfil_nuevo_id,
        )
    )


    perfil_nuevo = (
        cursor.fetchone()
    )


    if not perfil_nuevo:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "No se encontró el perfil de reemplazo."
        }


    if (
        perfil_nuevo["estado"] !=
        "disponible"
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil de reemplazo ya está ocupado o no está disponible."
        }


    if (
        perfil_nuevo["cuenta_id"] ==
        perfil_anterior["cuenta_id"] or
        (
            perfil_nuevo["plataforma"] or ""
        ).strip().lower() !=
        (
            perfil_anterior["plataforma"] or ""
        ).strip().lower() or
        perfil_nuevo["modalidad"] !=
        "perfiles" or
        perfil_nuevo["estado_cuenta"] in {
            "caida",
            "reemplazada",
            "papelera",
            "garantia"
        }
    ):

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "La cuenta destino ya no es elegible para el reemplazo."
        }


    # ==========================================
    # CALCULAR DÍAS PENDIENTES
    # ==========================================

    dias_restantes = 0


    if perfil_anterior[
        "fecha_vencimiento"
    ]:

        dias_restantes = max(
            calcular_dias_restantes(
                perfil_anterior[
                    "fecha_vencimiento"
                ]
            ),
            0
        )


    if dias_restantes <= 0:

        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil caído ya no tiene días pendientes para trasladar."
        }


    # ==========================================
    # NUEVA FECHA DE ENTREGA / VENCIMIENTO
    # ==========================================

    hoy = datetime.now().date()


    nueva_fecha_entrega = (
        hoy.strftime(
            "%Y-%m-%d"
        )
    )


    # La garantia conserva literalmente el vencimiento
    # original; no se recalcula para acomodarlo al destino.
    nueva_fecha_vencimiento = (
        perfil_anterior[
            "fecha_vencimiento"
        ] or ""
    )


    # ==========================================
    # ACTIVAR PERFIL NUEVO
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_perfiles

        SET
            nombre_cliente = ?,
            telefono = ?,
            fecha_entrega = ?,
            dias_cuenta = ?,
            fecha_vencimiento = ?,
            estado = 'activa',
            garantia_usada = 1,
            cantidad_garantias =
                COALESCE(cantidad_garantias, 0) + 1,
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE
            id = ?
            AND estado = 'disponible'
        """,
        (
            perfil_anterior[
                "nombre_cliente"
            ],

            perfil_anterior[
                "telefono"
            ],

            nueva_fecha_entrega,

            dias_restantes,

            nueva_fecha_vencimiento,

            perfil_nuevo_id
        )
    )


    if cursor.rowcount != 1:

        conn.rollback()
        conn.close()

        return {
            "ok": False,
            "mensaje":
                "El perfil destino acaba de dejar de estar disponible."
        }


    # ==========================================
    # MARCAR PERFIL VIEJO COMO REEMPLAZADO
    # ==========================================

    cursor.execute(
        """
        UPDATE nube_perfiles

        SET
            estado = 'reemplazada',
            garantia_usada = 1,
            cantidad_garantias =
                COALESCE(cantidad_garantias, 0) + 1,
            fecha_actualizacion = CURRENT_TIMESTAMP

        WHERE id = ?
        """,
        (
            perfil_anterior_id,
        )
    )


    # ==========================================
    # GUARDAR RELACIÓN DEL REEMPLAZO
    # ==========================================

    cursor.execute(
        """
        INSERT INTO nube_reemplazos_perfiles (

            perfil_anterior_id,
            perfil_nuevo_id,

            cuenta_anterior_id,
            cuenta_nueva_id,

            nombre_cliente,
            telefono,

            motivo,

            dias_restantes,

            fecha_vencimiento_anterior,

            pin_anterior,
            pin_nuevo

        )
        VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        """,
        (
            perfil_anterior_id,
            perfil_nuevo_id,

            perfil_anterior[
                "cuenta_id"
            ],

            perfil_nuevo[
                "cuenta_id"
            ],

            perfil_anterior[
                "nombre_cliente"
            ],

            perfil_anterior[
                "telefono"
            ],

            motivo,

            dias_restantes,

            perfil_anterior[
                "fecha_vencimiento"
            ] or "",

            perfil_anterior[
                "pin"
            ] or "",

            perfil_nuevo[
                "pin"
            ] or ""
        )
    )


    # ==========================================
    # MOVIMIENTO EN HISTORIAL
    # ==========================================

    descripcion = (
        f"{perfil_anterior['nombre_perfil']} "
        f"reemplazado por "
        f"{perfil_nuevo['nombre_perfil']} "
        f"con {dias_restantes} días pendientes"
    )


    if motivo:

        descripcion += (
            f" · Motivo: {motivo}"
        )


    cursor.execute(
        """
        INSERT INTO nube_movimientos (

            cuenta_id,
            tipo,
            descripcion,

            estado_anterior,
            estado_nuevo,

            cliente_nombre

        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            perfil_anterior[
                "cuenta_id"
            ],

            "reemplazo_perfil",

            descripcion,

            "caida",

            "reemplazada",

            perfil_anterior[
                "nombre_cliente"
            ]
        )
    )


    datos_entrega = _obtener_datos_entrega_perfil_nube(
        cursor,
        perfil_nuevo_id
    )

    conn.commit()
    conn.close()


    return {
        "ok": True,

        "mensaje":
            "Perfil reemplazado correctamente.",

        "perfil_anterior_id":
            perfil_anterior_id,

        "perfil_nuevo_id":
            perfil_nuevo_id,

        "dias_restantes":
            dias_restantes,

        "fecha_vencimiento":
            nueva_fecha_vencimiento,

        "cliente":
            perfil_anterior[
                "nombre_cliente"
            ],

        "datos_entrega":
            datos_entrega
    }


    # ==========================================
# NUBE — PERFILES DISPONIBLES PARA REEMPLAZO
# ==========================================

def _mediana_fechas_nube(fechas):

    fechas_ordenadas = sorted(fechas)

    if not fechas_ordenadas:
        return None

    # Para una cantidad par usamos la mediana inferior:
    # mantiene una fecha real y evita introducir medios días.
    indice = (len(fechas_ordenadas) - 1) // 2

    return fechas_ordenadas[indice]


def _nivel_recomendacion_nube(diferencia_dias):

    if diferencia_dias is None:
        return "cuenta_nueva"
    if diferencia_dias <= 1:
        return "excelente"
    if diferencia_dias <= 3:
        return "muy_buena"
    if diferencia_dias <= 7:
        return "buena"
    if diferencia_dias <= 15:
        return "aceptable"

    return "lejana"


def _enriquecer_recomendaciones_perfiles_nube(
    cursor,
    candidatos,
    fecha_cliente_texto
):

    try:
        fecha_cliente = datetime.strptime(
            (fecha_cliente_texto or "").strip(),
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return []

    cuentas_ids = sorted({
        candidato["cuenta_id"]
        for candidato in candidatos
    })
    resumen_cuentas = {}

    for cuenta_id in cuentas_ids:
        cursor.execute(
            """
            SELECT estado, nombre_cliente, fecha_vencimiento
            FROM nube_perfiles
            WHERE cuenta_id = ?
            """,
            (cuenta_id,)
        )
        fechas_ocupadas = []
        disponibles = 0

        for perfil in cursor.fetchall():
            estado_perfil = (perfil["estado"] or "").strip()
            if estado_perfil == "disponible":
                disponibles += 1
                continue
            if not (perfil["nombre_cliente"] or "").strip() or not (
                perfil["fecha_vencimiento"]
            ):
                continue

            estado_calculado = estado_perfil
            if estado_perfil in {"activa", "por_vencer", "vencida"}:
                estado_calculado = calcular_estado_nube(
                    perfil["fecha_vencimiento"],
                    estado_actual=estado_perfil
                )
            if estado_calculado not in {"activa", "por_vencer"}:
                continue
            try:
                fechas_ocupadas.append(
                    datetime.strptime(
                        perfil["fecha_vencimiento"],
                        "%Y-%m-%d"
                    ).date()
                )
            except ValueError:
                continue

        fecha_referencia = _mediana_fechas_nube(fechas_ocupadas)
        diferencia = (
            abs((fecha_cliente - fecha_referencia).days)
            if fecha_referencia
            else None
        )
        resumen_cuentas[cuenta_id] = {
            "fecha_referencia_cuenta": (
                fecha_referencia.strftime("%Y-%m-%d")
                if fecha_referencia
                else ""
            ),
            "diferencia_dias": diferencia,
            "cantidad_perfiles_ocupados": len(fechas_ocupadas),
            "cantidad_perfiles_disponibles": disponibles,
            "nivel_recomendacion": _nivel_recomendacion_nube(diferencia)
        }

    for candidato in candidatos:
        candidato.update(resumen_cuentas[candidato["cuenta_id"]])
        candidato["fecha_vencimiento_cliente"] = fecha_cliente_texto

    candidatos.sort(
        key=lambda candidato: (
            candidato["diferencia_dias"] is None,
            candidato["diferencia_dias"]
            if candidato["diferencia_dias"] is not None
            else 999999,
            candidato["cuenta_id"],
            candidato["perfil_id"]
        )
    )
    return candidatos


def obtener_perfiles_disponibles_reemplazo(
    perfil_anterior_id
):

    conn = conectar()
    cursor = conn.cursor()

    try:
        perfil_anterior_id = int(perfil_anterior_id)
    except (ValueError, TypeError):
        conn.close()
        return []

    cursor.execute(
        """
        SELECT
            p.id,
            p.cuenta_id,
            p.fecha_vencimiento,
            c.plataforma

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE p.id = ?
        """,
        (perfil_anterior_id,)
    )

    perfil_anterior = cursor.fetchone()

    if not perfil_anterior:
        conn.close()
        return []

    plataforma = (
        perfil_anterior["plataforma"] or ""
    ).strip()
    fecha_cliente_texto = (
        perfil_anterior["fecha_vencimiento"] or ""
    ).strip()

    try:
        fecha_cliente = datetime.strptime(
            fecha_cliente_texto,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        conn.close()
        return []

    cursor.execute(
        """
        SELECT
            p.id AS perfil_id,
            p.cuenta_id,
            p.nombre_perfil,
            p.pin,
            c.plataforma,
            c.correo

        FROM nube_perfiles AS p

        INNER JOIN nube_cuentas AS c
            ON c.id = p.cuenta_id

        WHERE
            p.estado = 'disponible'
            AND p.id != ?
            AND p.cuenta_id != ?
            AND c.modalidad = 'perfiles'
            AND c.estado NOT IN (
                'caida',
                'reemplazada',
                'papelera',
                'garantia'
            )
            AND LOWER(TRIM(c.plataforma)) =
                LOWER(TRIM(?))

        ORDER BY
            c.id ASC,
            p.orden ASC,
            p.id ASC
        """,
        (
            perfil_anterior_id,
            perfil_anterior["cuenta_id"],
            plataforma
        )
    )

    candidatos = [
        dict(fila)
        for fila in cursor.fetchall()
    ]
    candidatos = _enriquecer_recomendaciones_perfiles_nube(
        cursor,
        candidatos,
        fecha_cliente_texto
    )
    conn.close()
    return candidatos


# ==========================================
# NUBE — HISTORIAL COMPLETO DEL PERFIL
# ==========================================

def _leer_snapshot_historial_perfil_nube(valor):
    if not valor:
        return {}
    try:
        snapshot = json.loads(valor)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return snapshot if isinstance(snapshot, dict) else {}


def _datos_publicos_snapshot_perfil_nube(snapshot):
    if not snapshot:
        return {}
    return {
        "perfil_id": snapshot.get("perfil_id"),
        "cuenta_id": snapshot.get("cuenta_id"),
        "plataforma": snapshot.get("plataforma") or "",
        "nombre_perfil": snapshot.get("nombre_perfil") or "",
        "cliente": snapshot.get("nombre_cliente") or "",
        "telefono": snapshot.get("telefono") or "",
        "fecha_entrega": snapshot.get("fecha_entrega") or "",
        "dias": int(snapshot.get("dias_cuenta") or 0),
        "dias_restantes": int(snapshot.get("dias_restantes") or 0),
        "fecha_vencimiento": snapshot.get("fecha_vencimiento") or "",
        "estado": snapshot.get("estado") or ""
    }


def _crear_evento_historial_perfil_nube(
    clave, tipo, fecha, titulo, descripcion, datos,
    origen, icono, nivel="normal"
):
    return {
        "id": clave,
        "tipo": tipo,
        "fecha": fecha or "",
        "titulo": titulo,
        "descripcion": descripcion or "",
        "datos": datos or {},
        "origen": origen,
        "icono": icono,
        "nivel": nivel
    }


def obtener_historial_completo_perfil_nube(perfil_id):
    try:
        perfil_id = int(perfil_id)
    except (TypeError, ValueError):
        return None
    if perfil_id <= 0:
        return None

    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT p.id AS perfil_id, p.cuenta_id, p.nombre_perfil,
                   p.nombre_cliente, p.telefono, p.fecha_entrega,
                   p.dias_cuenta, p.fecha_vencimiento, p.estado,
                   p.fecha_creacion, p.fecha_actualizacion, c.plataforma
            FROM nube_perfiles AS p
            INNER JOIN nube_cuentas AS c ON c.id = p.cuenta_id
            WHERE p.id = ?
            """,
            (perfil_id,)
        )
        fila_perfil = cursor.fetchone()
        if not fila_perfil:
            return None

        perfil = {
            "perfil_id": fila_perfil["perfil_id"],
            "nombre_perfil": fila_perfil["nombre_perfil"] or "",
            "plataforma": fila_perfil["plataforma"] or "",
            "cuenta_id": fila_perfil["cuenta_id"],
            "cuenta_madre": f"Cuenta #{fila_perfil['cuenta_id']}",
            "estado": fila_perfil["estado"] or "disponible"
        }
        eventos = []
        claves = set()
        asignaciones = set()

        def agregar(evento):
            if evento and evento["id"] not in claves:
                claves.add(evento["id"])
                eventos.append(evento)

        def agregar_asignacion(snapshot, origen, clave_base):
            if int(snapshot.get("perfil_id") or 0) != perfil_id:
                return
            datos = _datos_publicos_snapshot_perfil_nube(snapshot)
            if not (datos["cliente"] and datos["fecha_entrega"] and datos["dias"] > 0):
                return
            clave_asignacion = (
                perfil_id,
                snapshot.get("cliente_id"),
                datos["cliente"].strip().casefold(),
                datos["fecha_entrega"],
                datos["fecha_vencimiento"]
            )
            if clave_asignacion in asignaciones:
                return
            asignaciones.add(clave_asignacion)
            agregar(_crear_evento_historial_perfil_nube(
                f"asignacion:{clave_base}", "venta", datos["fecha_entrega"],
                "Venta realizada",
                f"Perfil asignado a {datos['cliente']} por {datos['dias']} días.",
                datos, origen, "user-check"
            ))

        cursor.execute(
            """
            SELECT * FROM nube_transferencias_servicios
            WHERE perfil_origen_id = ? OR perfil_destino_id = ?
            ORDER BY fecha DESC, id DESC
            """,
            (perfil_id, perfil_id)
        )
        for transferencia in cursor.fetchall():
            snapshot_origen = _leer_snapshot_historial_perfil_nube(
                transferencia["venta_origen_snapshot"]
            )
            snapshot_antes = _leer_snapshot_historial_perfil_nube(
                transferencia["destino_antes_snapshot"]
            )
            snapshot_despues = _leer_snapshot_historial_perfil_nube(
                transferencia["destino_despues_snapshot"]
            )
            agregar_asignacion(
                snapshot_origen,
                "nube_transferencias_servicios.venta_origen_snapshot",
                f"transferencia:{transferencia['id']}:origen"
            )
            rol = (
                "origen" if transferencia["perfil_origen_id"] == perfil_id
                else "destino"
            )
            datos = {
                "operacion_uuid": transferencia["operacion_uuid"],
                "rol_perfil": rol,
                "dias_disponibles": transferencia["dias_disponibles"] or 0,
                "dias_trasladados": transferencia["dias_trasladados"] or 0,
                "motivo": transferencia["motivo"] or "",
                "origen": _datos_publicos_snapshot_perfil_nube(snapshot_origen),
                "destino_antes": _datos_publicos_snapshot_perfil_nube(snapshot_antes),
                "destino_despues": _datos_publicos_snapshot_perfil_nube(snapshot_despues)
            }
            operacion = transferencia["tipo_operacion"]
            if operacion == "no_renovo":
                tipo, titulo = "no_renovo", "Servicio no renovado"
                descripcion = "El cliente no renovó y el perfil volvió a estar disponible."
                icono, nivel = "user-minus", "advertencia"
            elif operacion == "liberar":
                tipo, titulo = "liberacion", "Perfil liberado"
                descripcion = "El perfil fue liberado sin trasladar días."
                icono, nivel = "unlock", "advertencia"
            elif operacion == "sumar_activo":
                tipo, titulo = "traslado_servicio_activo", "Días trasladados a servicio activo"
                descripcion = f"Se trasladaron {datos['dias_trasladados']} días a un servicio activo."
                icono, nivel = "calendar-plus", "positivo"
            else:
                tipo, titulo = "traslado_nuevo_servicio", "Traslado a nuevo servicio"
                descripcion = f"Se trasladaron {datos['dias_trasladados']} días a un nuevo perfil."
                icono, nivel = "arrow-right-left", "positivo"
            agregar(_crear_evento_historial_perfil_nube(
                f"transferencia:{transferencia['id']}:{rol}", tipo,
                transferencia["fecha"], titulo, descripcion, datos,
                "nube_transferencias_servicios", icono, nivel
            ))

        cursor.execute(
            """
            SELECT r.*, pa.nombre_perfil AS perfil_anterior,
                   pn.nombre_perfil AS perfil_nuevo,
                   ca.plataforma AS plataforma_anterior,
                   cn.plataforma AS plataforma_nueva
            FROM nube_reemplazos_perfiles AS r
            INNER JOIN nube_perfiles AS pa ON pa.id = r.perfil_anterior_id
            INNER JOIN nube_perfiles AS pn ON pn.id = r.perfil_nuevo_id
            INNER JOIN nube_cuentas AS ca ON ca.id = r.cuenta_anterior_id
            INNER JOIN nube_cuentas AS cn ON cn.id = r.cuenta_nueva_id
            WHERE r.perfil_anterior_id = ? OR r.perfil_nuevo_id = ?
            ORDER BY r.fecha DESC, r.id DESC
            """,
            (perfil_id, perfil_id)
        )
        for reemplazo in cursor.fetchall():
            rol = "origen" if reemplazo["perfil_anterior_id"] == perfil_id else "destino"
            datos = {
                "rol_perfil": rol,
                "perfil_origen_id": reemplazo["perfil_anterior_id"],
                "perfil_origen": reemplazo["perfil_anterior"] or "",
                "plataforma_origen": reemplazo["plataforma_anterior"] or "",
                "perfil_destino_id": reemplazo["perfil_nuevo_id"],
                "perfil_destino": reemplazo["perfil_nuevo"] or "",
                "plataforma_destino": reemplazo["plataforma_nueva"] or "",
                "cliente": reemplazo["nombre_cliente"] or "",
                "telefono": reemplazo["telefono"] or "",
                "motivo": reemplazo["motivo"] or "",
                "dias_restantes": reemplazo["dias_restantes"] or 0,
                "vencimiento_preservado": reemplazo["fecha_vencimiento_anterior"] or ""
            }
            agregar(_crear_evento_historial_perfil_nube(
                f"reemplazo:{reemplazo['id']}:{rol}", "reemplazo",
                reemplazo["fecha"], "Perfil reemplazado",
                f"{datos['perfil_origen']} fue reemplazado por {datos['perfil_destino']}.",
                datos, "nube_reemplazos_perfiles", "repeat-2", "advertencia"
            ))

        cursor.execute(
            """
            SELECT * FROM nube_movimientos
            WHERE cuenta_id = ?
              AND tipo IN ('creacion', 'cuenta_caida', 'perfil_caido')
            ORDER BY fecha DESC, id DESC
            """,
            (fila_perfil["cuenta_id"],)
        )
        for movimiento in cursor.fetchall():
            if (
                movimiento["tipo"] == "perfil_caido" and
                (fila_perfil["nombre_perfil"] or "").casefold()
                not in (movimiento["descripcion"] or "").casefold()
            ):
                continue
            if movimiento["tipo"] == "creacion":
                tipo, titulo, icono, nivel = (
                    "creacion_cuenta", "Cuenta madre creada", "cloud", "normal"
                )
            else:
                tipo, titulo, icono, nivel = (
                    "caida", "Servicio marcado como caído", "triangle-alert", "critico"
                )
            agregar(_crear_evento_historial_perfil_nube(
                f"movimiento:{movimiento['id']}", tipo, movimiento["fecha"],
                titulo, movimiento["descripcion"] or "",
                {
                    "cliente": movimiento["cliente_nombre"] or "",
                    "estado_anterior": movimiento["estado_anterior"] or "",
                    "estado_nuevo": movimiento["estado_nuevo"] or ""
                },
                "nube_movimientos", icono, nivel
            ))

        agregar_asignacion(
            {
                "perfil_id": perfil_id,
                "cuenta_id": fila_perfil["cuenta_id"],
                "plataforma": fila_perfil["plataforma"],
                "nombre_perfil": fila_perfil["nombre_perfil"],
                "nombre_cliente": fila_perfil["nombre_cliente"],
                "telefono": fila_perfil["telefono"],
                "fecha_entrega": fila_perfil["fecha_entrega"],
                "dias_cuenta": fila_perfil["dias_cuenta"],
                "fecha_vencimiento": fila_perfil["fecha_vencimiento"],
                "estado": fila_perfil["estado"]
            },
            "nube_perfiles", "actual"
        )
        eventos.sort(
            key=lambda evento: (evento["fecha"] or "", evento["id"]),
            reverse=True
        )
        return {"perfil": perfil, "eventos": eventos}
    finally:
        conn.close()
