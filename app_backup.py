from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "pechy_players_seguro_2026"

DB = "pechy.db"

UPLOAD_FOLDER = "static/img/platforms"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

productos_iniciales = [
    ("Netflix", "netflix.jpg", "Cuenta completa", "45 MIL"),
    ("Netflix", "netflix.jpg", "Perfil", "15 MIL"),
    ("Disney Premium", "disney.jpg", "Cuenta completa", "35 MIL"),
    ("Disney Premium", "disney.jpg", "Perfil", "15 MIL"),
    ("Disney Estándar", "disney-standard.jpg", "Cuenta completa", "25 MIL"),
    ("Disney Estándar", "disney-standard.jpg", "Perfil", "12 MIL"),
    ("Max Premium", "max.jpg", "Cuenta completa", "30 MIL"),
    ("Max Premium", "max.jpg", "Perfil", "12 MIL"),
    ("Prime Video", "prime.jpg", "Cuenta completa", "25 MIL"),
    ("Prime Video", "prime.jpg", "Perfil", "12 MIL"),
    ("Paramount+", "paramount.jpg", "Cuenta completa", "25 MIL"),
    ("Paramount+", "paramount.jpg", "Perfil", "15 MIL"),
    ("YouTube Premium", "youtube.jpg", "1 mes", "18 MIL"),
    ("YouTube Premium", "youtube.jpg", "3 meses", "54 MIL"),
    ("ViX Premium", "vix.jpg", "Cuenta completa", "10 MIL"),
    ("IPTV Premium", "iptv.jpg", "Cuenta completa", "45 MIL"),
    ("IPTV Premium", "iptv.jpg", "Perfil", "30 MIL"),
    ("Plex", "plex.jpg", "Cuenta completa", "35 MIL"),
    ("Plex", "plex.jpg", "Perfil", "12 MIL"),
    ("DIRECTV GO + WIN+", "directv.jpg", "Perfil", "50 MIL"),
    ("Spotify Premium", "spotify.jpg", "1 mes", "15 MIL"),
    ("Spotify Premium", "spotify.jpg", "3 meses", "45 MIL"),
    ("Jellyfin", "jellyfin.jpg", "Cuenta completa", "45 MIL"),
    ("Jellyfin", "jellyfin.jpg", "Perfil", "30 MIL"),
]

def conectar():
    return sqlite3.connect(DB)

def crear_db():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            imagen TEXT NOT NULL,
            plan TEXT NOT NULL,
            precio TEXT NOT NULL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM productos")
    total = cursor.fetchone()[0]

    if total == 0:
        cursor.executemany("""
            INSERT INTO productos (nombre, imagen, plan, precio)
            VALUES (?, ?, ?, ?)
        """, productos_iniciales)

    conn.commit()
    conn.close()

def obtener_productos():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, imagen, plan, precio FROM productos")
    filas = cursor.fetchall()
    conn.close()

    productos = {}

    for id_plan, nombre, imagen, plan, precio in filas:
        if nombre not in productos:
            productos[nombre] = {
                "nombre": nombre,
                "imagen": imagen,
                "planes": []
            }

        productos[nombre]["planes"].append({
            "id": id_plan,
            "plan": plan,
            "precio": precio
        })

    return list(productos.values())

@app.route("/")
def inicio():
    productos = obtener_productos()
    return render_template("index.html", productos=productos)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        if usuario == "admin" and password == "pechy123":
            session["admin"] = True
            return redirect("/admin")

        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/login")

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

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/login")

    productos = obtener_productos()
    stats = obtener_estadisticas()

    return render_template("admin.html", productos=productos, stats=stats)

@app.route("/actualizar-precio", methods=["POST"])
def actualizar_precio():
    if not session.get("admin"):
        return redirect("/login")

    id_plan = request.form["id"]
    precio = request.form["precio"]

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET precio = ? WHERE id = ?", (precio, id_plan))
    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/agregar-producto", methods=["POST"])
def agregar_producto():
    if not session.get("admin"):
        return redirect("/login")

    nombre = request.form["nombre"]
    plan = request.form["plan"]
    precio = request.form["precio"]
    imagen_file = request.files["imagen"]

    filename = secure_filename(imagen_file.filename)
    imagen_path = os.path.join(UPLOAD_FOLDER, filename)
    imagen_file.save(imagen_path)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO productos (nombre, imagen, plan, precio)
        VALUES (?, ?, ?, ?)
    """, (nombre, filename, plan, precio))

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/eliminar-plan", methods=["POST"])
def eliminar_plan():
    if not session.get("admin"):
        return redirect("/login")

    id_plan = request.form["id"]

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id_plan,))
    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/editar-producto", methods=["POST"])
def editar_producto():
    if not session.get("admin"):
        return redirect("/login")

    nombre_actual = request.form["nombre_actual"]
    nuevo_nombre = request.form["nuevo_nombre"]
    imagen_file = request.files.get("imagen")

    conn = conectar()
    cursor = conn.cursor()

    if imagen_file and imagen_file.filename != "":
        filename = secure_filename(imagen_file.filename)
        imagen_path = os.path.join(UPLOAD_FOLDER, filename)
        imagen_file.save(imagen_path)

        cursor.execute(
            "UPDATE productos SET nombre = ?, imagen = ? WHERE nombre = ?",
            (nuevo_nombre, filename, nombre_actual)
        )
    else:
        cursor.execute(
            "UPDATE productos SET nombre = ? WHERE nombre = ?",
            (nuevo_nombre, nombre_actual)
        )

    conn.commit()
    conn.close()

    return redirect("/admin")

if __name__ == "__main__":
    crear_db()
    app.run(debug=True)