from flask import Flask, render_template, request, redirect, session, flash, send_file
import os
from io import BytesIO
from openpyxl import Workbook
from werkzeug.utils import secure_filename
from database import conectar, obtener_productos, obtener_estadisticas, obtener_info_sistema, inicializar_db, obtener_config, actualizar_config, registrar_historial, obtener_historial, obtener_promociones
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-temporal-local")
app.permanent_session_lifetime = timedelta(minutes=30)

UPLOAD_FOLDER = "static/img/platforms"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROMO_FOLDER = "static/img/promociones"
os.makedirs(PROMO_FOLDER, exist_ok=True)

@app.route("/")
def inicio():
    productos = [p for p in obtener_productos() if p.get("visible", 1) == 1]
    config = obtener_config()
    promociones = [
    promo for promo in obtener_promociones()
    if promo[2] == 1
]

    return render_template(
        "index.html",
        productos=productos,
        config=config,
        promociones=promociones
    )

@app.route("/pechy-panel-seguro", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        admin_usuario = os.environ.get("ADMIN_USER", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD", "pechy123")

        if usuario == admin_usuario and password == admin_password:
            session.permanent = True
            session["admin"] = True
            return redirect("/admin")

        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

@app.route("/login")
def login_bloqueado():
    return redirect("/")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/pechy-panel-seguro")

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    productos = obtener_productos()
    stats = obtener_estadisticas()
    config = obtener_config()
    historial = obtener_historial()
    promociones = obtener_promociones()

    return render_template(
    "admin.html",
    productos=productos,
    stats=stats,
    config=config,
    historial=historial,
    promociones=promociones
)

@app.route("/actualizar-precio", methods=["POST"])
def actualizar_precio():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    id_plan = request.form["id"]
    precio = request.form["precio"]

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET precio = ? WHERE id = ?", (precio, id_plan))
    conn.commit()
    conn.close()

    flash("Precio actualizado correctamente ✅")

    return redirect("/admin")

@app.route("/agregar-producto", methods=["POST"])
def agregar_producto():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

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
    
    flash("Producto agregado correctamente ✅")

    return redirect("/admin")

@app.route("/eliminar-plan", methods=["POST"])
def eliminar_plan():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    id_plan = request.form["id"]

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = ?", (id_plan,))
    conn.commit()
    conn.close()
    
    flash("Plan eliminado correctamente 🗑️")

    return redirect("/admin")

@app.route("/editar-producto", methods=["POST"])
def editar_producto():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

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

    flash("Producto actualizado correctamente ✏️")

    return redirect("/admin")

@app.route("/actualizar-oferta", methods=["POST"])
def actualizar_oferta():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    id_plan = request.form["id"]
    oferta_precio = request.form["oferta_precio"]
    oferta_activa = 1 if request.form.get("oferta_activa") == "on" else 0

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE productos
        SET oferta_precio = ?, oferta_activa = ?
        WHERE id = ?
    """, (oferta_precio, oferta_activa, id_plan))

    conn.commit()
    conn.close()

    flash("Oferta guardada correctamente 🔥")

    return redirect("/admin")

@app.route("/actualizar-destacado", methods=["POST"])
def actualizar_destacado():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form["nombre"]
    destacado = 1 if request.form.get("destacado") == "on" else 0

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE productos SET destacado = ? WHERE nombre = ?",
        (destacado, nombre)
    )
    conn.commit()
    conn.close()

    flash("Destacado actualizado correctamente ⭐")

    return redirect("/admin")

@app.route("/actualizar-visible", methods=["POST"])
def actualizar_visible():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form["nombre"]
    visible = 1 if request.form.get("visible") == "on" else 0

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE productos SET visible = ? WHERE nombre = ?",
        (visible, nombre)
    )
    conn.commit()
    conn.close()

    flash("Visibilidad actualizada correctamente 👁️")

    return redirect("/admin")

@app.route("/actualizar-config", methods=["POST"])
def actualizar_configuracion():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    whatsapp = request.form["whatsapp"]
    actualizar_config("whatsapp", whatsapp)

    flash("Configuración guardada correctamente ⚙️")

    return redirect("/admin")

@app.route("/descargar-respaldo")
def descargar_respaldo():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre, imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible
        FROM productos
    """)
    productos = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Productos"

    ws.append([
        "Nombre",
        "Imagen",
        "Plan",
        "Precio",
        "Precio Oferta",
        "Oferta Activa",
        "Destacado",
        "Visible"
    ])

    for fila in productos:
        ws.append(fila)

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)

    flash("Respaldo en Excel descargado correctamente 📥")

    return send_file(
        archivo,
        as_attachment=True,
        download_name="respaldo_pechy_players.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/duplicar-producto", methods=["POST"])
def duplicar_producto():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form["nombre"]
    nuevo_nombre = nombre + " (Copia)"

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible
        FROM productos
        WHERE nombre = ?
    """, (nombre,))

    planes = cursor.fetchall()

    for imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible in planes:
        cursor.execute("""
            INSERT INTO productos
            (nombre, imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (nuevo_nombre, imagen, plan, precio, oferta_precio, oferta_activa, destacado, visible))

    conn.commit()
    conn.close()

    flash("Producto duplicado correctamente 📄")
    return redirect("/admin")

@app.route("/guardar-orden", methods=["POST"])
def guardar_orden():
    if not session.get("admin"):
        return {"ok": False}, 401

    data = request.get_json()
    orden_productos = data.get("orden", [])

    conn = conectar()
    cursor = conn.cursor()

    for posicion, nombre in enumerate(orden_productos, start=1):
        cursor.execute(
            "UPDATE productos SET orden = ? WHERE nombre = ?",
            (posicion, nombre)
        )

    conn.commit()
    conn.close()

    return {"ok": True}

@app.route("/actualizar-db")
def actualizar_db():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    inicializar_db()

    flash("Base de datos actualizada correctamente 🛠")

    return redirect("/admin")

@app.route("/agregar-promocion", methods=["POST"])
def agregar_promocion():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    imagen_file = request.files["imagen"]
    activa = 1 if request.form.get("activa") == "on" else 0

    filename = secure_filename(imagen_file.filename)
    imagen_path = os.path.join(PROMO_FOLDER, filename)
    imagen_file.save(imagen_path)

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO promociones (imagen, activa)
        VALUES (?, ?)
    """, (filename, activa))

    conn.commit()
    conn.close()

    flash("Promoción agregada correctamente 🔥")
    return redirect("/admin#promociones")

@app.route("/actualizar-promocion", methods=["POST"])
def actualizar_promocion():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    promo_id = request.form["id"]
    activa = 1 if request.form.get("activa") == "on" else 0

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE promociones SET activa = ? WHERE id = ?",
        (activa, promo_id)
    )
    conn.commit()
    conn.close()

    flash("Promoción actualizada correctamente 🔥")
    return redirect("/admin#promociones")


@app.route("/eliminar-promocion", methods=["POST"])
def eliminar_promocion():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    promo_id = request.form["id"]

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT imagen FROM promociones WHERE id = ?",
        (promo_id,)
    )
    fila = cursor.fetchone()

    cursor.execute(
        "DELETE FROM promociones WHERE id = ?",
        (promo_id,)
    )

    conn.commit()
    conn.close()

    if fila:
        ruta_imagen = os.path.join(PROMO_FOLDER, fila[0])

        if os.path.exists(ruta_imagen):
            os.remove(ruta_imagen)

    flash("Promoción eliminada correctamente 🗑️")
    return redirect("/admin#promociones")

if __name__ == "__main__":
    inicializar_db()
    app.run(host="0.0.0.0", port=5000, debug=True)