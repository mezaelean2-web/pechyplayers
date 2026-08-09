import sqlite3

DB = "pechy.db"

def conectar():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")

    return conn

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
    activa INTEGER DEFAULT 1,
    orden INTEGER DEFAULT 999
)
""")

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

    # ==========================================
    # NUBE DE CUENTAS — COLUMNAS NUEVAS
    # ==========================================

    for columna_nube in [

        "modalidad TEXT DEFAULT 'cuenta_completa'",

        "cantidad_perfiles INTEGER DEFAULT 0"

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
        SELECT id, imagen, activa
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
    pines_perfiles=None
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

        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
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
            fecha_proximo_pago
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


    estados_automaticos = {
        "activa",
        "por_vencer",
        "vencida"
    }


    if estado_actual in estados_automaticos:

        estado_calculado = (
            calcular_estado_nube(
                fecha_vencimiento,
                estado_actual=estado_actual
            )
        )

    else:

        estado_calculado = (
            estado_actual
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

def obtener_cuentas_nube(
    limite=25,
    offset=0
):

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute(
        """
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

        ORDER BY id DESC

        LIMIT ?
        OFFSET ?
        """,
        (
            limite,
            offset
        )
    )


    filas = cursor.fetchall()

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

            cuenta["perfiles"] = (
                obtener_perfiles_nube(
                    cuenta["id"]
                )
            )

        else:

            cuenta["perfiles"] = []


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


        cuentas.append(
            cuenta
        )


    return cuentas

# ==========================================
# NUBE DE CUENTAS — ESTADÍSTICAS
# ==========================================

def obtener_estadisticas_nube():

    conn = conectar()
    cursor = conn.cursor()


    cursor.execute("""
        SELECT
            id,
            fecha_vencimiento,
            estado
        FROM nube_cuentas
    """)


    filas = cursor.fetchall()

    conn.close()


    resumen = {
        "total": 0,
        "activas": 0,
        "por_vencer": 0,
        "vencidas": 0,
        "disponibles": 0,
        "caidas": 0,
        "papelera": 0,
        "garantia": 0,
        "reemplazadas": 0
    }


    for fila in filas:

        resumen["total"] += 1


        estado_actual = (
            fila["estado"] or
            "disponible"
        )


        fecha_vencimiento = (
            fila["fecha_vencimiento"] or
            ""
        )


        if estado_actual in {
            "activa",
            "por_vencer",
            "vencida"
        }:

            estado = calcular_estado_nube(
                fecha_vencimiento,
                estado_actual=estado_actual
            )

        else:

            estado = estado_actual


        if estado == "activa":

            resumen["activas"] += 1


        elif estado == "por_vencer":

            resumen["por_vencer"] += 1


        elif estado == "vencida":

            resumen["vencidas"] += 1


        elif estado == "disponible":

            resumen["disponibles"] += 1


        elif estado == "caida":

            resumen["caidas"] += 1


        elif estado == "papelera":

            resumen["papelera"] += 1


        elif estado == "garantia":

            resumen["garantia"] += 1


        elif estado == "reemplazada":

            resumen["reemplazadas"] += 1


    resumen[
        "caidas_papelera"
    ] = (
        resumen["caidas"] +
        resumen["papelera"]
    )


    return resumen

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


    condiciones = []

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
        ORDER BY tipo_cuenta ASC
    """)


    filas = cursor.fetchall()

    conn.close()


    return [
        fila["tipo_cuenta"]
        for fila in filas
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


    perfiles = []


    for fila in filas:

        perfil = dict(
            fila
        )


        fecha_vencimiento = (
            perfil.get(
                "fecha_vencimiento"
            ) or ""
        )


        estado_actual = (
            perfil.get(
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


        if estado_actual in {
            "activa",
            "por_vencer",
            "vencida"
        }:

            estado_calculado = (
                calcular_estado_nube(
                    fecha_vencimiento,
                    estado_actual
                )
            )

        else:

            estado_calculado = (
                estado_actual
            )


        perfil[
            "dias_restantes"
        ] = dias_restantes

        perfil[
            "estado_calculado"
        ] = estado_calculado


        perfiles.append(
            perfil
        )


    return perfiles

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



    # ==========================================
    # ESTADO DE LA CUENTA MADRE
    # ==========================================

    cursor.execute(
        """
        SELECT
            c.estado AS estado_cuenta,
            p.estado AS estado_perfil

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


    conn.commit()
    conn.close()


    return actualizado

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


    conn.commit()
    conn.close()


    if not actualizado:

        return False


    return {
        "ok": True,
        "fecha_vencimiento": nueva_fecha_texto,
        "estado": nuevo_estado
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
            ]
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
    cuentas_ids = sorted({
        candidato["cuenta_id"]
        for candidato in candidatos
    })
    resumen_cuentas = {}

    for cuenta_id in cuentas_ids:

        cursor.execute(
            """
            SELECT
                estado,
                nombre_cliente,
                fecha_vencimiento

            FROM nube_perfiles

            WHERE cuenta_id = ?
            """,
            (cuenta_id,)
        )

        fechas_ocupadas = []
        disponibles = 0

        for perfil in cursor.fetchall():

            estado_perfil = (
                perfil["estado"] or ""
            ).strip()

            if estado_perfil == "disponible":
                disponibles += 1
                continue

            if (
                not (
                    perfil["nombre_cliente"] or ""
                ).strip() or
                not perfil["fecha_vencimiento"]
            ):
                continue

            estado_calculado = estado_perfil

            if estado_perfil in {
                "activa",
                "por_vencer",
                "vencida"
            }:
                estado_calculado = calcular_estado_nube(
                    perfil["fecha_vencimiento"],
                    estado_actual=estado_perfil
                )

            if estado_calculado not in {
                "activa",
                "por_vencer"
            }:
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

        fecha_referencia = _mediana_fechas_nube(
            fechas_ocupadas
        )
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
            "cantidad_perfiles_ocupados": len(
                fechas_ocupadas
            ),
            "cantidad_perfiles_disponibles": disponibles,
            "nivel_recomendacion": (
                _nivel_recomendacion_nube(diferencia)
            )
        }

    conn.close()

    for candidato in candidatos:
        candidato.update(
            resumen_cuentas[candidato["cuenta_id"]]
        )
        candidato["fecha_vencimiento_cliente"] = (
            fecha_cliente_texto
        )

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
