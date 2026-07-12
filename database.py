import sqlite3

DB = "pechy.db"

def conectar():
    return sqlite3.connect(DB)

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


def obtener_historial():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT accion, fecha FROM historial ORDER BY id DESC LIMIT 15")
    filas = cursor.fetchall()

    conn.close()
    return filas

def inicializar_db():
    conn = conectar()
    cursor = conn.cursor()

    for columna in [
        "oferta_precio TEXT DEFAULT ''",
        "oferta_activa INTEGER DEFAULT 0",
        "destacado INTEGER DEFAULT 0",
        "visible INTEGER DEFAULT 1"
        "orden INTEGER DEFAULT 999",
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
    
    conn.commit()
    conn.close()

def obtener_productos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nombre, imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible
        FROM productos
        ORDER BY orden ASC, destacado DESC, nombre ASC
    """)

    filas = cursor.fetchall()
    conn.close()

    productos = {}

    for id_plan, nombre, imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible in filas:
        if nombre not in productos:
            productos[nombre] = {
                "nombre": nombre,
                "imagen": imagen,
                "destacado": destacado,
                "visible": visible,
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