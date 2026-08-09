from flask import Flask, render_template, request, redirect, session, flash, send_file, jsonify
import sqlite3
from flask_compress import Compress
import os
import re
from io import BytesIO
from openpyxl import Workbook
from werkzeug.utils import secure_filename
from PIL import Image
from database import conectar, obtener_productos, obtener_estadisticas, obtener_info_sistema, inicializar_db, obtener_config, actualizar_config, registrar_historial, obtener_historial, obtener_promociones, obtener_categorias, obtener_cartelera, obtener_historial, obtener_resumen_historial, obtener_cuentas_nube, obtener_estadisticas_nube, obtener_plataformas_nube, obtener_tipos_cuenta_nube, crear_cuenta_nube, actualizar_perfil_nube, renovar_perfil_nube, marcar_perfil_caido_nube, obtener_perfiles_disponibles_reemplazo, reemplazar_perfil_nube, obtener_contexto_liberacion_perfil_nube, liberar_o_trasladar_perfil_nube
from datetime import timedelta
from collections import defaultdict
from collections import OrderedDict
from database import obtener_historial
from datetime import datetime

app = Flask(__name__)
Compress(app)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30
app.secret_key = os.environ.get("SECRET_KEY", "clave-temporal-local")
app.permanent_session_lifetime = timedelta(minutes=30)

UPLOAD_FOLDER = "static/img/platforms"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CARTELERA_FOLDER = "static/img/cartelera"
os.makedirs(CARTELERA_FOLDER, exist_ok=True)

def guardar_imagen_optimizada(imagen_file):

    nombre = os.path.splitext(
        secure_filename(imagen_file.filename)
    )[0] + ".webp"

    ruta = os.path.join(
        UPLOAD_FOLDER,
        nombre
    )

    imagen = Image.open(imagen_file)

    if imagen.mode != "RGB":
        imagen = imagen.convert("RGB")

    ancho_maximo = 600

    if imagen.width > ancho_maximo:

        alto = int(
            imagen.height *
            ancho_maximo /
            imagen.width
        )

        imagen = imagen.resize(
            (ancho_maximo, alto),
            Image.LANCZOS
        )

    imagen.save(
        ruta,
        "WEBP",
        quality=80,
        optimize=True
    )

    return nombre

PROMO_FOLDER = "static/img/promociones"
os.makedirs(PROMO_FOLDER, exist_ok=True)

def guardar_poster_cartelera(imagen_file):

    nombre = os.path.splitext(
        secure_filename(imagen_file.filename)
    )[0] + ".webp"

    ruta = os.path.join(
        CARTELERA_FOLDER,
        nombre
    )

    imagen = Image.open(imagen_file)

    if imagen.mode != "RGB":
        imagen = imagen.convert("RGB")

    ancho_maximo = 800

    if imagen.width > ancho_maximo:

        alto = int(
            imagen.height *
            ancho_maximo /
            imagen.width
        )

        imagen = imagen.resize(
            (ancho_maximo, alto),
            Image.LANCZOS
        )

    imagen.save(
        ruta,
        "WEBP",
        quality=85,
        optimize=True
    )

    return nombre

@app.route("/")
def inicio():

    # Todos los productos visibles continúan disponibles
    # para el catálogo principal.
    productos = [
        producto
        for producto in obtener_productos()
        if producto.get("visible", 1) == 1
    ]

    categorias_db = obtener_categorias()

    categorias_visibles = {
        categoria["nombre"]
        for categoria in categorias_db
        if categoria["visible"] == 1
    }

    productos_por_categoria = {}

    for producto in productos:

        categoria = producto.get("categoria") or "Sin categoría"

        if categoria.strip().lower() == "sin categoría":
           continue

        if categoria not in categorias_visibles:
           continue

        productos_por_categoria.setdefault(categoria, []).append(producto)

    categorias = {}

    for categoria in categorias_db:

        nombre = categoria["nombre"]

        if nombre in productos_por_categoria:
            categorias[nombre] = productos_por_categoria[nombre]

    for nombre_categoria in categorias:
        categorias[nombre_categoria].sort(
            key=lambda producto: (
                producto.get("orden_categoria", 999),
                producto.get("nombre", "").lower()
            )
        )

        config = obtener_config()

    promociones = [
        promo
        for promo in obtener_promociones()
        if promo[2] == 1
    ]

    peliculas = [
        pelicula
        for pelicula in obtener_cartelera()
        if pelicula.get("publicado", 0) == 1
    ]

    peliculas_por_categoria = OrderedDict()

    for pelicula in peliculas:

        categoria = (
            pelicula.get("categoria") or "Otros"
        ).strip()

        if categoria not in peliculas_por_categoria:

            peliculas_por_categoria[categoria] = []

        peliculas_por_categoria[categoria].append(
            pelicula
        )
        peliculas_ordenadas = []

    for categoria in peliculas_por_categoria:

        peliculas_ordenadas.extend(
        peliculas_por_categoria[categoria]
    )

        


    return render_template(
        "index.html",
        productos=productos,
        categorias=categorias,
        config=config,
        promociones=promociones,
        peliculas=peliculas_ordenadas,
        peliculas_por_categoria=peliculas_por_categoria
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
        "admin/dashboard.html",
        productos=productos,
        stats=stats,
        config=config,
        historial=historial,
        promociones=promociones
    )


@app.route("/admin/historial")
def admin_historial():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    historial = obtener_historial()

    resumen = obtener_resumen_historial()

    return render_template(
        "admin/historial.html",
        historial=historial,
        total_movimientos=resumen[
            "total_movimientos"
        ],
        movimientos_hoy=resumen[
            "movimientos_hoy"
        ],
        ultima_actividad=resumen[
            "ultima_actividad"
        ]
    )

@app.route("/admin/historial/cargar-mas")
def cargar_mas_historial():

    if not session.get("admin"):
        return {
            "ok": False,
            "mensaje": "No autorizado"
        }, 401

    try:
        offset = int(
            request.args.get(
                "offset",
                0
            )
        )

    except ValueError:
        offset = 0

    registros = obtener_historial(
        limite=15,
        offset=offset
    )

    return {
        "ok": True,
        "registros": [
            {
                "accion": registro["accion"],
                "fecha": registro["fecha"]
            }
            for registro in registros
        ]
    }

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

@app.route("/admin/productos")
def admin_productos():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    productos = obtener_productos()
    categorias = obtener_categorias()

    return render_template(
        "admin/productos.html",
        productos=productos,
        categorias=categorias
    )

@app.route("/admin/configuracion")
def admin_configuracion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    config = obtener_config()

    return render_template(
        "admin/configuracion.html",
        config=config
    )



@app.route("/admin/nube-cuentas")
def admin_nube_cuentas():

    if not session.get("admin"):

        return redirect(
            "/pechy-panel-seguro"
        )


    cuentas = obtener_cuentas_nube(
        limite=25,
        offset=0
    )

    estadisticas = (
        obtener_estadisticas_nube()
    )

    plataformas = (
        obtener_plataformas_nube()
    )

    tipos_cuenta = (
        obtener_tipos_cuenta_nube()
    )


    return render_template(
        "admin/nube_cuentas.html",
        cuentas=cuentas,
        estadisticas=estadisticas,
        plataformas=plataformas,
        tipos_cuenta=tipos_cuenta
    )


@app.route(
    "/admin/nube-cuentas/nueva",
    methods=["POST"]
)
def crear_nueva_cuenta_nube():

    if not session.get("admin"):

        return redirect(
            "/pechy-panel-seguro"
        )


    # ==========================================
    # DATOS GENERALES
    # ==========================================

    plataforma = request.form.get(
        "plataforma",
        ""
    ).strip()

    correo = request.form.get(
        "correo",
        ""
    ).strip()

    contrasena = request.form.get(
        "contrasena",
        ""
    ).strip()

    pin = request.form.get(
        "pin",
        ""
    ).strip()

    tipo_cuenta = request.form.get(
        "tipo_cuenta",
        ""
    ).strip()

    nombre_cliente = request.form.get(
        "nombre_cliente",
        ""
    ).strip()

    telefono = request.form.get(
        "telefono",
        ""
    ).strip()

    fecha_entrega = request.form.get(
        "fecha_entrega",
        ""
    ).strip()

    dias_cuenta = request.form.get(
        "dias_cuenta",
        "0"
    ).strip()

    notas = request.form.get(
        "notas",
        ""
    ).strip()


    # ==========================================
    # PERFILES
    # ==========================================

    cantidad_perfiles = request.form.get(
        "cantidad_perfiles",
        "0"
    ).strip()







    # ==========================================
    # CONTROL DE PAGO
    # ==========================================

    tipo_pago = request.form.get(
        "tipo_pago",
        ""
    ).strip().lower()

    valor_pin = request.form.get(
        "valor_pin",
        "0"
    ).strip()

    plan_pago = request.form.get(
        "plan_pago",
        ""
    ).strip()

    precio_plan_referencia = request.form.get(
        "precio_plan_referencia",
        "0"
    ).strip()

    fecha_aplicacion_pin = request.form.get(
        "fecha_aplicacion_pin",
        ""
    ).strip()


    # ==========================================
    # VALIDACIONES BÁSICAS
    # ==========================================

    if not plataforma:

        flash(
            "Debes indicar la plataforma."
        )

        return redirect(
            "/admin/nube-cuentas"
        )


    if not correo:

        flash(
            "Debes indicar el correo de la cuenta."
        )

        return redirect(
            "/admin/nube-cuentas"
        )


    # ==========================================
    # TIPO / MODALIDAD
    # ==========================================

    tipos_validos = {
        "cuenta_completa",
        "perfil",
        "plan_estandar"
    }


    if tipo_cuenta not in tipos_validos:

        flash(
            "Selecciona un tipo de cuenta válido."
        )

        return redirect(
            "/admin/nube-cuentas"
        )


    if tipo_cuenta == "perfil":

        modalidad = "perfiles"

    else:

        modalidad = "cuenta_completa"


    # ==========================================
    # CONVERTIR NÚMEROS
    # ==========================================

    try:

        dias_cuenta = int(
            dias_cuenta or 0
        )

    except ValueError:

        dias_cuenta = 0


    if dias_cuenta < 0:

        dias_cuenta = 0


    try:

        cantidad_perfiles = int(
            cantidad_perfiles or 0
        )

    except ValueError:

        cantidad_perfiles = 0


    if modalidad == "perfiles":

        if (
            cantidad_perfiles < 1 or
            cantidad_perfiles > 10
        ):

            flash(
                "La cantidad de perfiles debe estar entre 1 y 10."
            )

            return redirect(
                "/admin/nube-cuentas"
            )

    else:

        cantidad_perfiles = 0


    # ==========================================
    # PINES INDIVIDUALES DE LOS PERFILES
    # ==========================================

    pines_perfiles = []


    if modalidad == "perfiles":

        for numero in range(
            1,
            cantidad_perfiles + 1
        ):

            pin_perfil = request.form.get(
                f"pin_perfil_{numero}",
                ""
            ).strip()


            pines_perfiles.append(
                pin_perfil
            )


    try:

        valor_pin = int(
            re.sub(
            r"\D",
            "",
            str(valor_pin or "0")
            ) or 0
        )

    except (
        ValueError,
        TypeError
    ):

        valor_pin = 0


    try:

        precio_plan_referencia = int(
            re.sub(
                r"\D",
                "",
                str(
                    precio_plan_referencia or "0"
                )
            ) or 0
        )

    except (
        ValueError,
        TypeError
    ):

        precio_plan_referencia = 0


    # ==========================================
    # VALIDACIÓN DEL TIPO DE PAGO
    # ==========================================

    if tipo_pago not in {
        "",
        "autopagable",
        "pin"
    }:

        tipo_pago = ""


    if tipo_pago == "pin":

        if valor_pin <= 0:

            flash(
                "Debes indicar el valor del PIN."
            )

            return redirect(
                "/admin/nube-cuentas"
            )


        if not plan_pago:

            flash(
                "Debes indicar el plan para calcular el PIN."
            )

            return redirect(
                "/admin/nube-cuentas"
            )


        if precio_plan_referencia <= 0:

            flash(
                "Debes indicar el precio mensual del plan."
            )

            return redirect(
                "/admin/nube-cuentas"
            )


        if not fecha_aplicacion_pin:

            flash(
                "Debes indicar la fecha en que aplicaste el PIN."
            )

            return redirect(
                "/admin/nube-cuentas"
            )


    # ==========================================
    # CREAR CUENTA
    # ==========================================

    crear_cuenta_nube(

        plataforma=plataforma,

        correo=correo,

        contrasena=contrasena,

        pin=pin,

        tipo_cuenta=tipo_cuenta,

        nombre_cliente=nombre_cliente,

        telefono=telefono,

        fecha_entrega=fecha_entrega,

        dias_cuenta=dias_cuenta,

        notas=notas,

        origen="manual",

        modalidad=modalidad,

        cantidad_perfiles=cantidad_perfiles,

        tipo_pago=tipo_pago,

        valor_pin=valor_pin,

        plan_pago=plan_pago,

        precio_plan_referencia=precio_plan_referencia,

        fecha_aplicacion_pin=fecha_aplicacion_pin,

        pines_perfiles=pines_perfiles
    )


    flash(
        "Cuenta agregada a la Nube correctamente ☁️"
    )


    return redirect(
        "/admin/nube-cuentas"
    )


@app.route(
    "/admin/nube-cuentas/perfil/guardar",
    methods=["POST"]
)
def guardar_perfil_nube():

    es_ajax = (
        request.headers.get("X-Requested-With") ==
        "XMLHttpRequest"
    )

    if not session.get("admin"):

        if es_ajax:
            return jsonify({
                "ok": False,
                "mensaje": "No autorizado"
            }), 401

        return redirect(
            "/pechy-panel-seguro"
        )


    perfil_id = request.form.get(
        "perfil_id",
        ""
    ).strip()

    pin = request.form.get(
        "pin",
        ""
    ).strip()

    nombre_cliente = request.form.get(
        "nombre_cliente",
        ""
    ).strip()

    telefono = request.form.get(
        "telefono",
        ""
    ).strip()

    fecha_entrega = request.form.get(
        "fecha_entrega",
        ""
    ).strip()

    dias_cuenta = request.form.get(
        "dias_cuenta",
        "0"
    ).strip()

    notas = request.form.get(
        "notas",
        ""
    ).strip()


    try:

        perfil_id = int(
            perfil_id
        )

    except ValueError:

        if es_ajax:
            return jsonify({
                "ok": False,
                "mensaje": "No se pudo identificar el perfil."
            }), 400

        flash(
            "No se pudo identificar el perfil."
        )

        return redirect(
            "/admin/nube-cuentas"
        )


    try:

        dias_cuenta = int(
            dias_cuenta or 0
        )

    except ValueError:

        dias_cuenta = 0


    actualizado = actualizar_perfil_nube(

        perfil_id=perfil_id,

        pin=pin,

        nombre_cliente=nombre_cliente,

        telefono=telefono,

        fecha_entrega=fecha_entrega,

        dias_cuenta=dias_cuenta,

        notas=notas
    )


    if actualizado and actualizado.get("ok") and es_ajax:

        return jsonify({
            "ok": True,
            "mensaje": "Perfil actualizado correctamente.",
            "fecha_vencimiento": actualizado[
                "fecha_vencimiento"
            ],
            "estado": actualizado["estado"],
            "datos_entrega": actualizado[
                "datos_entrega"
            ]
        })

    if actualizado and not actualizado.get("ok") and es_ajax:

        return jsonify(actualizado), 409

    if not actualizado and es_ajax:

        return jsonify({
            "ok": False,
            "mensaje": "No se encontró el perfil."
        }), 404

    if actualizado and actualizado.get("ok"):

        flash(
            "Perfil actualizado correctamente ✅"
        )

    else:

        flash(
            "No se encontró el perfil."
        )


    return redirect(
        "/admin/nube-cuentas"
    )


@app.route(
    "/admin/nube-cuentas/perfil/<int:perfil_id>/liberacion",
    methods=["GET"]
)
def obtener_contexto_liberacion_perfil_nube_route(perfil_id):

    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    contexto = obtener_contexto_liberacion_perfil_nube(perfil_id)

    if not contexto:
        return jsonify({
            "ok": False,
            "mensaje": "No se encontró el perfil."
        }), 404

    if not contexto["asignado"]:
        return jsonify({
            "ok": False,
            "mensaje": "El perfil no tiene una asignación real para liberar."
        }), 409

    return jsonify({"ok": True, **contexto})


@app.route(
    "/admin/nube-cuentas/perfil/liberar-trasladar",
    methods=["POST"]
)
def liberar_trasladar_perfil_nube_route():

    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    datos = request.get_json(silent=True) or {}

    accion = datos.get("accion")
    if accion not in {"liberar", "trasladar_nuevo", "sumar_activo"}:
        return jsonify({
            "ok": False,
            "mensaje": "La acción solicitada no es válida."
        }), 400

    if accion == "sumar_activo" and datos.get("destino_tipo") != "perfil":
        return jsonify({
            "ok": False,
            "mensaje": "El destino activo debe ser un perfil."
        }), 400

    try:
        perfil_origen_id = int(datos.get("perfil_origen_id", 0))
    except (TypeError, ValueError):
        perfil_origen_id = 0

    if perfil_origen_id <= 0:
        return jsonify({
            "ok": False,
            "mensaje": "No se pudo identificar el perfil de origen."
        }), 400

    resultado = liberar_o_trasladar_perfil_nube(
        perfil_origen_id=perfil_origen_id,
        accion=accion,
        perfil_destino_id=datos.get("destino_id", datos.get("perfil_destino_id")),
        dias_trasladar=datos.get("dias_trasladar"),
        motivo=datos.get("motivo", ""),
        operacion_uuid=datos.get("operacion_uuid", "")
    )

    return jsonify(resultado), (200 if resultado["ok"] else 409)



# ==========================================
# NUBE — RENOVAR PERFIL
# ==========================================

@app.route(
    "/admin/nube-cuentas/perfil/renovar",
    methods=["POST"]
)
def renovar_perfil_nube_route():

    if not session.get("admin"):

        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401


    datos = request.get_json(
        silent=True
    ) or {}


    perfil_id = datos.get(
        "perfil_id",
        0
    )

    dias = datos.get(
        "dias",
        0
    )


    try:

        perfil_id = int(
            perfil_id
        )

        dias = int(
            dias
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "ok": False,
            "mensaje": "Datos inválidos."
        }), 400


    if (
        perfil_id <= 0 or
        dias <= 0
    ):

        return jsonify({
            "ok": False,
            "mensaje": "Debes indicar un perfil y días válidos."
        }), 400


    actualizado = renovar_perfil_nube(
        perfil_id,
        dias
    )


    if not actualizado:

        return jsonify({
            "ok": False,
            "mensaje": "No se pudo renovar el perfil."
        }), 400


    return jsonify({
    "ok": True,

    "mensaje":
        f"Perfil renovado por {dias} días.",

    "fecha_vencimiento":
        actualizado[
            "fecha_vencimiento"
        ],

    "estado":
        actualizado[
            "estado"
        ],

    "datos_entrega":
        actualizado[
            "datos_entrega"
        ]
})

# ==========================================
# NUBE — MARCAR PERFIL COMO CAÍDO
# ==========================================

@app.route(
    "/admin/nube-cuentas/perfil/caido",
    methods=["POST"]
)
def marcar_perfil_caido_nube_route():

    if not session.get("admin"):

        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401


    datos = request.get_json(
        silent=True
    ) or {}


    perfil_id = datos.get(
        "perfil_id",
        0
    )


    motivo = (
        datos.get(
            "motivo",
            ""
        ) or ""
    ).strip()


    try:

        perfil_id = int(
            perfil_id
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "ok": False,
            "mensaje": "Perfil inválido."
        }), 400


    if perfil_id <= 0:

        return jsonify({
            "ok": False,
            "mensaje": "No se pudo identificar el perfil."
        }), 400


    resultado = marcar_perfil_caido_nube(
        perfil_id=perfil_id,
        motivo=motivo
    )


    if not resultado.get(
        "ok"
    ):

        return jsonify(
            resultado
        ), 400


    return jsonify(
        resultado
    )


# ==========================================
# NUBE — OPCIONES DE REEMPLAZO
# ==========================================

@app.route(
    "/admin/nube-cuentas/perfil/<int:perfil_id>/reemplazos",
    methods=["GET"]
)
def obtener_reemplazos_perfil_nube_route(perfil_id):

    if not session.get("admin"):

        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401


    perfiles = (
        obtener_perfiles_disponibles_reemplazo(
            perfil_id
        )
    )


    return jsonify({
        "ok": True,
        "perfiles": perfiles,
        "total": len(perfiles)
    })


# ==========================================
# NUBE — CONFIRMAR REEMPLAZO DE PERFIL
# ==========================================

@app.route(
    "/admin/nube-cuentas/perfil/reemplazar",
    methods=["POST"]
)
def reemplazar_perfil_nube_route():

    if not session.get("admin"):

        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401


    datos = request.get_json(
        silent=True
    ) or {}


    perfil_anterior_id = datos.get(
        "perfil_anterior_id",
        0
    )


    perfil_nuevo_id = datos.get(
        "perfil_nuevo_id",
        0
    )


    motivo = (
        datos.get(
            "motivo",
            ""
        ) or ""
    ).strip()


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

        return jsonify({
            "ok": False,
            "mensaje":
                "No se pudieron identificar los perfiles."
        }), 400


    if (
        perfil_anterior_id <= 0 or
        perfil_nuevo_id <= 0
    ):

        return jsonify({
            "ok": False,
            "mensaje":
                "Selecciona un perfil de reemplazo válido."
        }), 400


    resultado = reemplazar_perfil_nube(
        perfil_anterior_id=
            perfil_anterior_id,

        perfil_nuevo_id=
            perfil_nuevo_id,

        motivo=
            motivo
    )


    if not resultado.get(
        "ok"
    ):

        return jsonify(
            resultado
        ), 400


    return jsonify(
        resultado
    )


@app.route("/admin/organizacion")
def admin_organizacion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    productos = obtener_productos()
    categorias_db = obtener_categorias()

    productos_por_categoria = defaultdict(list)

    for producto in productos:
        categoria = producto["categoria"] or "Sin categoría"
        productos_por_categoria[categoria].append(producto)

        for nombre_categoria in productos_por_categoria:
            productos_por_categoria[nombre_categoria].sort(
                key=lambda producto: (
                    producto.get("orden_categoria")
                    if producto.get("orden_categoria") is not None
                    else 9999,
                    producto.get("nombre", "").lower()
        )
    )

    categorias = {}

    for categoria in categorias_db:

        nombre_categoria = categoria["nombre"]

        categorias[nombre_categoria] = productos_por_categoria.get(
            nombre_categoria,
            []
        )

    if (
         "Sin categoría" in productos_por_categoria
         and "Sin categoría" not in categorias
    ):
         categorias["Sin categoría"] = productos_por_categoria["Sin categoría"]

    estilos_categorias = {}

    for categoria in categorias_db:
        estilos_categorias[categoria["nombre"]] = {
            "icono": categoria["icono"],
            "color": categoria["color"],
            "visible": categoria["visible"],
            "orden": categoria["orden"],
            "clase": "",
        }
    productos_sin_categoria = productos_por_categoria.get(
    "Sin categoría",
    []
)
        
    return render_template(
    "admin/organizacion.html",
    categorias=dict(categorias),
    estilos_categorias=estilos_categorias,
    productos_sin_categoria=productos_sin_categoria
)

@app.route("/admin/cartelera")
def admin_cartelera():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    peliculas = obtener_cartelera()
    productos = obtener_productos()

    plataformas = []
    nombres_agregados = set()

    for producto in productos:

        nombre = producto.get("nombre", "").strip()

        if not nombre:
            continue

        clave_nombre = nombre.lower()

        if clave_nombre in nombres_agregados:
            continue

        nombres_agregados.add(clave_nombre)

        plataformas.append({
            "nombre": nombre,
            "imagen": producto.get("imagen", "")
        })

    plataformas.sort(
        key=lambda plataforma:
        plataforma["nombre"].lower()
    )

    return render_template(
        "admin/cartelera.html",
        peliculas=peliculas,
        plataformas=plataformas
    )

@app.route("/admin/cartelera/guardar", methods=["POST"])
def guardar_cartelera():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    tipo = request.form.get("tipo", "").strip()
    titulo = request.form.get("titulo", "").strip()
    genero = request.form.get("genero", "").strip()
    categoria = request.form.get("categoria", "").strip()
    anio = request.form.get("anio", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    url = request.form.get("url", "").strip()
    print("URL RECIBIDA:", url)

    pelicula_id = request.form.get("pelicula_id", "").strip()

    tendencia = 1 if request.form.get("tendencia") else 0
    destacado = 1 if request.form.get("destacado") else 0
    publicado = 1 if request.form.get("publicado") else 0

    plataformas = request.form.getlist("plataformas")
    poster = request.files.get("poster")
    banner = request.files.get("banner")

    if not titulo:
        flash("Debes escribir el título de la película ❌")
        return redirect("/admin/cartelera")

    if not plataformas:
        flash("Selecciona al menos una plataforma ❌")
        return redirect("/admin/cartelera")

    nombre_poster = ""
    nombre_banner = ""

    if poster and poster.filename:
        nombre_poster = guardar_poster_cartelera(poster)

    if banner and banner.filename:
        nombre_banner = guardar_poster_cartelera(banner)

        print("PLATAFORMAS:", plataformas)

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute("PRAGMA table_info(cartelera)")
    print(cursor.fetchall())

    try:
        cursor.execute("""
            ALTER TABLE cartelera
            ADD COLUMN url TEXT DEFAULT '';
        """)
        conexion.commit()
        print("✅ Columna URL creada.")
    except Exception as e:
        print(e)

    try:

        print("CATEGORIA:", categoria)

        if pelicula_id:

            cursor.execute(
                """
                SELECT poster, banner
                FROM cartelera
                WHERE id = ?
                """,
                (pelicula_id,)
            )

            pelicula_actual = cursor.fetchone()

            if not pelicula_actual:
                raise ValueError(
                    "La película que intentas editar no existe."
                )

            poster_actual = pelicula_actual[0] or ""
            banner_actual = pelicula_actual[1] or ""

            if nombre_poster:
                poster_final = nombre_poster
            else:
                poster_final = poster_actual

            if nombre_banner:
                banner_final = nombre_banner
            else:
                banner_final = banner_actual

            cursor.execute(
                """
                UPDATE cartelera
                SET
                    tipo = ?,
                    titulo = ?,
                    genero = ?,
                    categoria = ?,
                    descripcion = ?,
                    anio = ?,
                    url = ?,
                    poster = ?,
                    banner = ?,
                    tendencia = ?,
                    destacado = ?,
                    publicado = ?
                WHERE id = ?
                """,
                (
                    tipo,
                    titulo,
                    genero,
                    categoria,
                    descripcion,
                    int(anio) if anio else None,
                    url,
                    poster_final,
                    banner_final,
                    tendencia,
                    destacado,
                    publicado,
                    pelicula_id
                )
            )

            cursor.execute(
                """
                DELETE FROM cartelera_plataformas
                WHERE cartelera_id = ?
                """,
                (pelicula_id,)
            )

            for plataforma in plataformas:

                cursor.execute(
                    """
                    INSERT INTO cartelera_plataformas (
                        cartelera_id,
                        plataforma
                    )
                    VALUES (?, ?)
                    """,
                    (
                        pelicula_id,
                        plataforma
                    )
                )

            mensaje_exito = "Película actualizada correctamente 🎬✅"

        else:

            cursor.execute(
                """
                INSERT INTO cartelera (
                    tipo,
                    titulo,
                    genero,
                    categoria,
                    descripcion,
                    anio,
                    url,
                    poster,
                    banner,
                    tendencia,
                    destacado,
                    publicado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tipo,
                    titulo,
                    genero,
                    categoria,
                    descripcion,
                    int(anio) if anio else None,
                    url,
                    nombre_poster,
                    nombre_banner,
                    tendencia,
                    destacado,
                    publicado
                )
            )

            cartelera_id = cursor.lastrowid

            for plataforma in plataformas:

                cursor.execute(
                    """
                    INSERT INTO cartelera_plataformas (
                        cartelera_id,
                        plataforma
                    )
                    VALUES (?, ?)
                    """,
                    (
                        cartelera_id,
                        plataforma
                    )
                )

            mensaje_exito = "Película guardada correctamente 🎬✅"

        conexion.commit()

        flash(mensaje_exito)

    except Exception as error:

        conexion.rollback()

        flash(f"No se pudo guardar la película: {error}")

    finally:

        conexion.close()

    return redirect("/admin/cartelera")
    

@app.route("/admin/cartelera/eliminar/<int:pelicula_id>", methods=["POST"])
def eliminar_cartelera(pelicula_id):

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            """
            SELECT poster
            FROM cartelera
            WHERE id = ?
            """,
            (pelicula_id,)
        )

        pelicula = cursor.fetchone()

        if not pelicula:

            flash("La película no existe ❌")

            return redirect("/admin/cartelera")

        poster = pelicula[0]

        cursor.execute(
            """
            DELETE FROM cartelera_plataformas
            WHERE cartelera_id = ?
            """,
            (pelicula_id,)
        )

        cursor.execute(
            """
            DELETE FROM cartelera
            WHERE id = ?
            """,
            (pelicula_id,)
        )

        conexion.commit()

        if poster:

            ruta = os.path.join(
                CARTELERA_FOLDER,
                poster
            )

            if os.path.exists(ruta):
                os.remove(ruta)

        flash("Película eliminada correctamente 🗑️")

    except Exception as error:

        conexion.rollback()

        flash(f"No se pudo eliminar: {error}")

    finally:

        conexion.close()

    return redirect("/admin/cartelera")


@app.route("/admin/organizacion/guardar-orden", methods=["POST"])
def guardar_orden_categorias():

    if not session.get("admin"):
        return {"ok": False}, 401

    datos = request.get_json()

    orden = datos.get("orden", [])

    conexion = conectar()
    cursor = conexion.cursor()

    for posicion, categoria in enumerate(orden, start=1):

        cursor.execute(
    """
    UPDATE categorias
    SET orden = ?
    WHERE nombre = ?
    """,
    (posicion, categoria)
)

    conexion.commit()
    conexion.close()

    return {"ok": True}

@app.route("/admin/organizacion/eliminar-categoria", methods=["POST"])
def eliminar_categoria():

    if not session.get("admin"):
        return {
            "ok": False,
            "mensaje": "No autorizado"
        }, 401

    datos = request.get_json(silent=True) or {}
    categoria = datos.get("categoria", "").strip()

    if not categoria:
        return {
            "ok": False,
            "mensaje": "No se recibió la categoría"
        }, 400

    if categoria.lower() == "sin categoría":
        return {
            "ok": False,
            "mensaje": "La categoría Sin categoría no se puede eliminar"
        }, 400

    conexion = conectar()
    cursor = conexion.cursor()

    cursor.execute(
        """
        UPDATE productos
        SET categoria = ?
        WHERE categoria = ?
        """,
        ("Sin categoría", categoria)
    )

    cursor.execute(
    """
    DELETE FROM categorias
    WHERE nombre = ?
    """,
    (categoria,)
)

    productos_movidos = cursor.rowcount

    conexion.commit()
    conexion.close()

    return {
        "ok": True,
        "mensaje": "Categoría eliminada correctamente",
        "productos_movidos": productos_movidos
    }

@app.route("/admin/cartelera/guardar-orden", methods=["POST"])
def guardar_orden_cartelera():

    if not session.get("admin"):
        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401

    datos = request.get_json(silent=True) or {}

    orden_peliculas = datos.get("orden", [])

    if not orden_peliculas:
        return jsonify({
            "ok": False,
            "mensaje": "No se recibió el orden"
        }), 400

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        for posicion, pelicula_id in enumerate(
            orden_peliculas,
            start=1
        ):

            cursor.execute(
                """
                UPDATE cartelera
                SET orden = ?
                WHERE id = ?
                """,
                (
                    posicion,
                    pelicula_id
                )
            )

        conexion.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Orden guardado correctamente"
        })

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:

        conexion.close()


@app.route("/admin/organizacion/editar-categoria", methods=["POST"])
def editar_categoria():

    datos = request.get_json() or {}

    categoria_original = datos.get(
        "categoria_original", ""
    ).strip()

    nuevo_nombre = datos.get(
        "nombre", ""
    ).strip()

    nuevo_icono = datos.get(
        "icono", "folder"
    ).strip()

    nuevo_color = datos.get(
        "color", "#64748b"
    ).strip()

    visible = 1 if datos.get("visible") else 0

    if not categoria_original or not nuevo_nombre:
        return jsonify({
            "ok": False,
            "mensaje": "El nombre de la categoría es obligatorio."
        }), 400

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            """
            UPDATE productos
            SET categoria = ?
            WHERE categoria = ?
            """,
            (
                nuevo_nombre,
                categoria_original
            )
        )

        cursor.execute(
            """
            UPDATE categorias
            SET
                nombre = ?,
                icono = ?,
                color = ?,
                visible = ?
            WHERE nombre = ?
            """,
            (
                nuevo_nombre,
                nuevo_icono,
                nuevo_color,
                visible,
                categoria_original
            )
        )

        if cursor.rowcount == 0:

            cursor.execute(
                """
                INSERT INTO categorias (
                    nombre,
                    icono,
                    color,
                    visible,
                    orden
                )
                VALUES (?, ?, ?, ?, 999)
                """,
                (
                    nuevo_nombre,
                    nuevo_icono,
                    nuevo_color,
                    visible
                )
            )

        conexion.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Categoría actualizada correctamente."
        })

    except sqlite3.IntegrityError:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": "Ya existe una categoría con ese nombre."
        }), 400

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:
        conexion.close()

@app.route("/admin/organizacion/crear-categoria", methods=["POST"])
def crear_categoria():

    if not session.get("admin"):
        return jsonify({
            "ok": False,
            "mensaje": "No autorizado."
        }), 401

    datos = request.get_json() or {}

    nombre = datos.get("nombre", "").strip()
    icono = datos.get("icono", "folder").strip()
    color = datos.get("color", "#64748b").strip()
    visible = 1 if datos.get("visible") else 0

    if not nombre:
        return jsonify({
            "ok": False,
            "mensaje": "Debes escribir un nombre."
        }), 400

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            "SELECT 1 FROM categorias WHERE LOWER(nombre)=LOWER(?)",
            (nombre,)
        )

        if cursor.fetchone():
            return jsonify({
                "ok": False,
                "mensaje": "Ya existe una categoría con ese nombre."
            }), 400

        cursor.execute(
            """
            SELECT COALESCE(MAX(orden),0)+1
            FROM categorias
            """
        )

        siguiente_orden = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO categorias
            (
                nombre,
                icono,
                color,
                visible,
                orden
            )
            VALUES
            (?, ?, ?, ?, ?)
            """,
            (
                nombre,
                icono,
                color,
                visible,
                siguiente_orden
            )
        )

        conexion.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Categoría creada correctamente."
        })

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:

        conexion.close()
        
@app.route("/admin/organizacion/toggle-visible", methods=["POST"])
def toggle_visible_categoria():

    datos = request.get_json() or {}

    categoria = datos.get("categoria", "").strip()
    visible = 1 if datos.get("visible") else 0

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            """
            UPDATE categorias
            SET visible = ?
            WHERE nombre = ?
            """,
            (
                visible,
                categoria
            )
        )

        conexion.commit()

        return jsonify({
            "ok": True
        })

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:

        conexion.close()

@app.route("/admin/promociones")
def admin_promociones():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    promociones = obtener_promociones()

    return render_template(
        "admin/promociones.html",
        promociones=promociones
    )


@app.route("/guardar-orden-promociones", methods=["POST"])
def guardar_orden_promociones():

    if not session.get("admin"):
        return {
            "ok": False,
            "mensaje": "No autorizado"
        }, 401

    datos = request.get_json(silent=True)

    if not datos:
        return {
            "ok": False,
            "mensaje": "No se recibió información"
        }, 400

    orden_promociones = datos.get("orden", [])

    if not isinstance(orden_promociones, list):
        return {
            "ok": False,
            "mensaje": "Formato inválido"
        }, 400

    conn = conectar()
    cursor = conn.cursor()

    try:

        for posicion, promo_id in enumerate(
            orden_promociones,
            start=1
        ):

            cursor.execute("""
                UPDATE promociones
                SET orden = ?
                WHERE id = ?
            """, (
                posicion,
                promo_id
            ))

        conn.commit()

    except Exception as error:

        conn.rollback()

        return {
            "ok": False,
            "mensaje": str(error)
        }, 500

    finally:

        conn.close()

    return {
        "ok": True,
        "mensaje": "Orden guardado correctamente"
    }




@app.route("/agregar-producto", methods=["POST"])
def agregar_producto():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form["nombre"]
    plan = request.form["plan"]
    precio = request.form["precio"]
    categoria = request.form.get("categoria", "").strip()

    if not categoria:
       categoria = "Sin categoría"
    imagen_file = request.files["imagen"]

    filename = guardar_imagen_optimizada(imagen_file)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO productos
    (nombre, imagen, plan, precio, categoria)
    VALUES (?, ?, ?, ?, ?)
""", (
    nombre,
    filename,
    plan,
    precio,
    categoria
))
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
        filename = guardar_imagen_optimizada(imagen_file)

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

@app.route("/actualizar-categoria", methods=["POST"])
def actualizar_categoria():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form["nombre"]
    categoria = request.form["categoria"]

    categorias_db = obtener_categorias()

    categorias_validas = {
        categoria["nombre"]
        for categoria in categorias_db
    }

    if categoria not in categorias_validas:
        flash("Categoría no válida ❌")
        return redirect("/admin#productos")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE productos
        SET categoria = ?
        WHERE nombre = ?
        """,
        (categoria, nombre)
    )

    conn.commit()
    conn.close()

    registrar_historial(
        f"Categoría de {nombre} actualizada a {categoria}"
    )

    flash("Categoría actualizada correctamente ✅")

    return redirect("/admin#productos")

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

@app.route("/actualizar-estado", methods=["POST"])
def actualizar_estado():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    nombre = request.form.get("nombre", "").strip()

    estado = (
        "disponible"
        if request.form.get("disponible") == "on"
        else "agotado"
    )

    if not nombre:
        flash("No se pudo actualizar el producto ❌")
        return redirect("/admin/productos")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE productos
        SET estado = ?
        WHERE nombre = ?
        """,
        (estado, nombre)
    )

    conn.commit()
    conn.close()

    if estado == "disponible":
        registrar_historial(
            f"{nombre} fue marcado como disponible"
        )
        flash(f"{nombre} ahora está disponible 🟢")
    else:
        registrar_historial(
            f"{nombre} fue marcado como agotado"
        )
        flash(f"{nombre} ahora está agotado 🔴")

    return redirect("/admin/productos")

@app.route("/actualizar-config", methods=["POST"])
def actualizar_configuracion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    tipo_configuracion = request.form.get(
        "tipo_configuracion",
        ""
    )

    # ==========================================
    # IDENTIDAD DEL NEGOCIO
    # ==========================================

    if tipo_configuracion == "identidad":

        nombre_negocio = request.form.get(
            "nombre_negocio",
            ""
        ).strip()

        nombre_corto = request.form.get(
            "nombre_corto",
            ""
        ).strip()

        eslogan = request.form.get(
            "eslogan",
            ""
        ).strip()

        descripcion_negocio = request.form.get(
            "descripcion_negocio",
            ""
        ).strip()

        titulo_navegador = request.form.get(
            "titulo_navegador",
            ""
        ).strip()

        texto_footer = request.form.get(
            "texto_footer",
            ""
        ).strip()

        if not nombre_negocio:

            flash(
                "El nombre del negocio es obligatorio."
            )

            return redirect(
                "/admin/configuracion"
            )

        actualizar_config(
            "nombre_negocio",
            nombre_negocio
        )

        actualizar_config(
            "nombre_corto",
            nombre_corto
        )

        actualizar_config(
            "eslogan",
            eslogan
        )

        actualizar_config(
            "descripcion_negocio",
            descripcion_negocio
        )

        actualizar_config(
            "titulo_navegador",
            titulo_navegador
        )

        actualizar_config(
            "texto_footer",
            texto_footer
        )

        flash(
            "Identidad del negocio guardada correctamente ✨"
        )

        return redirect(
            "/admin/configuracion"
        )
    


        # ==========================================
    # PÁGINA DE INICIO
    # ==========================================

    if tipo_configuracion == "inicio":

        inicio_hero_activo = (
            "1"
            if request.form.get("inicio_hero_activo")
            else "0"
        )

        inicio_badge = request.form.get(
            "inicio_badge",
            ""
        ).strip()

        inicio_titulo_superior = request.form.get(
            "inicio_titulo_superior",
            ""
        ).strip()

        inicio_titulo_destacado = request.form.get(
            "inicio_titulo_destacado",
            ""
        ).strip()

        inicio_titulo_inferior = request.form.get(
            "inicio_titulo_inferior",
            ""
        ).strip()

        inicio_boton_catalogo = request.form.get(
            "inicio_boton_catalogo",
            ""
        ).strip()

        inicio_boton_whatsapp = request.form.get(
            "inicio_boton_whatsapp",
            ""
        ).strip()


        if not inicio_badge:

            flash(
                "Debes ingresar la insignia del hero."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not inicio_titulo_superior:

            flash(
                "Debes ingresar la primera línea del título."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not inicio_titulo_destacado:

            flash(
                "Debes ingresar la línea destacada."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not inicio_titulo_inferior:

            flash(
                "Debes ingresar la última línea del título."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not inicio_boton_catalogo:

            flash(
                "Debes ingresar el texto del botón de catálogo."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not inicio_boton_whatsapp:

            flash(
                "Debes ingresar el texto del botón de WhatsApp."
            )

            return redirect(
                "/admin/configuracion"
            )


        actualizar_config(
            "inicio_hero_activo",
            inicio_hero_activo
        )

        actualizar_config(
            "inicio_badge",
            inicio_badge
        )

        actualizar_config(
            "inicio_titulo_superior",
            inicio_titulo_superior
        )

        actualizar_config(
            "inicio_titulo_destacado",
            inicio_titulo_destacado
        )

        actualizar_config(
            "inicio_titulo_inferior",
            inicio_titulo_inferior
        )

        actualizar_config(
            "inicio_boton_catalogo",
            inicio_boton_catalogo
        )

        actualizar_config(
            "inicio_boton_whatsapp",
            inicio_boton_whatsapp
        )


        flash(
            "Configuración de inicio guardada correctamente 🏠"
        )

        return redirect(
            "/admin/configuracion"
        )

    # ==========================================
    # WHATSAPP
    # ==========================================

     # ==========================================
    # COLORES Y APARIENCIA
    # ==========================================

    if tipo_configuracion == "apariencia":

        color_principal = request.form.get(
            "color_principal",
            ""
        ).strip().upper()

        color_secundario = request.form.get(
            "color_secundario",
            ""
        ).strip().upper()

        color_acento = request.form.get(
            "color_acento",
            ""
        ).strip().upper()

        intensidad_fondo = request.form.get(
            "intensidad_fondo",
            "100"
        ).strip()


        

        patron_color = re.compile(
            r"^#[0-9A-F]{6}$"
        )


        colores = [
            color_principal,
            color_secundario,
            color_acento
        ]


        if not all(
            patron_color.match(color)
            for color in colores
        ):

            flash(
                "Uno de los colores no tiene un formato válido."
            )

            return redirect(
                "/admin/configuracion"
            )


        try:

            intensidad_numero = int(
                intensidad_fondo
            )

        except ValueError:

            intensidad_numero = 100


        intensidad_numero = max(
            60,
            min(
                intensidad_numero,
                100
            )
        )


        actualizar_config(
            "color_principal",
            color_principal
        )

        actualizar_config(
            "color_secundario",
            color_secundario
        )

        actualizar_config(
            "color_acento",
            color_acento
        )

        actualizar_config(
            "intensidad_fondo",
            str(intensidad_numero)
        )


        flash(
            "Apariencia guardada correctamente 🎨"
        )

        return redirect(
            "/admin/configuracion"
        )


        # ==========================================
    # CONFIGURACIÓN COMERCIAL
    # ==========================================

    if tipo_configuracion == "comercial":

        moneda_nombre = request.form.get(
            "moneda_nombre",
            ""
        ).strip()

        moneda_simbolo = request.form.get(
            "moneda_simbolo",
            ""
        ).strip()

        separador_miles = request.form.get(
            "separador_miles",
            "."
        )

        dias_garantia = request.form.get(
            "dias_garantia",
            "30"
        ).strip()

        texto_entrega = request.form.get(
            "texto_entrega",
            ""
        ).strip()

        texto_disponibilidad = request.form.get(
            "texto_disponibilidad",
            ""
        ).strip()

        mensaje_comercial = request.form.get(
            "mensaje_comercial",
            ""
        ).strip()


        # Campos obligatorios

        if not moneda_nombre:

            flash(
                "Debes ingresar el nombre de la moneda."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not moneda_simbolo:

            flash(
                "Debes ingresar el símbolo de la moneda."
            )

            return redirect(
                "/admin/configuracion"
            )


        if separador_miles not in [
            ".",
            ",",
            " "
        ]:

            flash(
                "El separador de miles seleccionado no es válido."
            )

            return redirect(
                "/admin/configuracion"
            )


        try:

            dias_garantia_numero = int(
                dias_garantia
            )

        except ValueError:

            flash(
                "Los días de garantía deben ser un número válido."
            )

            return redirect(
                "/admin/configuracion"
            )


        if (
            dias_garantia_numero < 0 or
            dias_garantia_numero > 365
        ):

            flash(
                "La garantía debe estar entre 0 y 365 días."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not texto_entrega:

            flash(
                "Debes ingresar el texto de entrega."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not texto_disponibilidad:

            flash(
                "Debes ingresar el texto de disponibilidad."
            )

            return redirect(
                "/admin/configuracion"
            )


        if not mensaje_comercial:

            flash(
                "Debes ingresar el mensaje comercial."
            )

            return redirect(
                "/admin/configuracion"
            )


        if len(mensaje_comercial) > 220:

            flash(
                "El mensaje comercial no puede superar los 220 caracteres."
            )

            return redirect(
                "/admin/configuracion"
            )


        # Guardar configuración

        actualizar_config(
            "moneda_nombre",
            moneda_nombre
        )

        actualizar_config(
            "moneda_simbolo",
            moneda_simbolo
        )

        actualizar_config(
            "separador_miles",
            separador_miles
        )

        actualizar_config(
            "dias_garantia",
            str(dias_garantia_numero)
        )

        actualizar_config(
            "texto_entrega",
            texto_entrega
        )

        actualizar_config(
            "texto_disponibilidad",
            texto_disponibilidad
        )

        actualizar_config(
            "mensaje_comercial",
            mensaje_comercial
        )


        flash(
            "Configuración comercial guardada correctamente 💼"
        )

        return redirect(
            "/admin/configuracion"
        )

    if tipo_configuracion == "whatsapp":

        whatsapp = request.form.get(
            "whatsapp",
            ""
        ).strip()

        if not whatsapp:

            flash(
                "Debes ingresar un número de WhatsApp."
            )

            return redirect(
                "/admin/configuracion"
            )

        actualizar_config(
            "whatsapp",
            whatsapp
        )

        flash(
            "WhatsApp actualizado correctamente 📲"
        )

        return redirect(
            "/admin/configuracion"
        )

    flash(
        "No se reconoció la configuración enviada."
    )

    return redirect(
        "/admin/configuracion"
    )

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
        SELECT
imagen,
plan,
precio,
oferta_precio,
oferta_activa,
destacado,
visible,
categoria
        FROM productos
        WHERE nombre = ?
    """, (nombre,))

    planes = cursor.fetchall()

    for (
    imagen,
    plan,
    precio,
    oferta_precio,
    oferta_activa,
    destacado,
    visible,
    categoria
) in planes:
        cursor.execute("""
            INSERT INTO productos
(
    nombre,
    imagen,
    plan,
    precio,
    oferta_precio,
    oferta_activa,
    destacado,
    visible,
    categoria
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ((
    nuevo_nombre,
    imagen,
    plan,
    precio,
    oferta_precio,
    oferta_activa,
    destacado,
    visible,
    categoria
)))

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


@app.route("/guardar-orden-categoria", methods=["POST"])
def guardar_orden_categoria():
    if not session.get("admin"):
        return {"ok": False, "mensaje": "No autorizado"}, 401

    data = request.get_json(silent=True) or {}

    print("=" * 50)
    print(data)

    categoria = data.get("categoria")
    orden_productos = data.get("orden", [])

    if not categoria:
        return {"ok": False, "mensaje": "Falta la categoría"}, 400

    conn = conectar()
    cursor = conn.cursor()

    for posicion, nombre in enumerate(orden_productos, start=1):

        cursor.execute(
           """
           UPDATE productos
           SET orden_categoria = ?
           WHERE nombre = ? AND categoria = ?
           """,
           (posicion, nombre, categoria)
    )

    print(nombre, cursor.rowcount)

    conn.commit()
    conn.close()

    return {"ok": True}

@app.route(
    "/admin/organizacion/agregar-productos",
    methods=["POST"]
)
def agregar_productos_categoria():

    if not session.get("admin"):
        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401

    datos = request.get_json(silent=True) or {}

    categoria = datos.get("categoria", "").strip()
    productos = datos.get("productos", [])

    if not categoria:
        return jsonify({
            "ok": False,
            "mensaje": "Falta la categoría"
        }), 400

    if not productos:
        return jsonify({
            "ok": False,
            "mensaje": "Selecciona al menos un producto"
        }), 400

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        for nombre in productos:

            cursor.execute(
                """
                UPDATE productos
                SET categoria = ?,
                    orden_categoria = 9999
                WHERE nombre = ?
                  AND (
                      categoria IS NULL
                      OR categoria = ''
                      OR categoria = 'Sin categoría'
                  )
                """,
                (
                    categoria,
                    nombre
                )
            )

        conexion.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Productos agregados correctamente"
        })

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:

        conexion.close()

@app.route(
    "/admin/organizacion/mover-producto",
    methods=["POST"]
)
def mover_producto_categoria():

    if not session.get("admin"):
        return jsonify({
            "ok": False,
            "mensaje": "No autorizado"
        }), 401

    datos = request.get_json(silent=True) or {}

    producto = datos.get("producto", "").strip()
    categoria_destino = datos.get("categoria_destino", "").strip()

    if not producto or not categoria_destino:
        return jsonify({
            "ok": False,
            "mensaje": "Faltan datos para mover el producto"
        }), 400

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            """
            UPDATE productos
            SET categoria = ?,
                orden_categoria = 9999
            WHERE nombre = ?
            """,
            (
                categoria_destino,
                producto
            )
        )

        if cursor.rowcount == 0:
            conexion.rollback()

            return jsonify({
                "ok": False,
                "mensaje": "No se encontró el producto"
            }), 404

        conexion.commit()

        return jsonify({
            "ok": True,
            "mensaje": "Producto movido correctamente"
        })

    except Exception as error:

        conexion.rollback()

        return jsonify({
            "ok": False,
            "mensaje": str(error)
        }), 500

    finally:

        conexion.close()
        
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
    return redirect("/admin/promociones")

@app.route("/actualizar-promocion", methods=["POST"])
def actualizar_promocion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    promo_id = request.form.get("id")

    if not promo_id:
        flash("No se recibió la promoción seleccionada.")
        return redirect("/admin/promociones")

    activa = 1 if request.form.get("activa") == "on" else 0

    imagen_file = request.files.get("imagen")

    conn = conectar()
    cursor = conn.cursor()

    if imagen_file and imagen_file.filename:

        filename = secure_filename(imagen_file.filename)

        imagen_path = os.path.join(
            PROMO_FOLDER,
            filename
        )

        imagen_file.save(imagen_path)

        cursor.execute("""
            UPDATE promociones
            SET imagen = ?, activa = ?
            WHERE id = ?
        """, (
            filename,
            activa,
            promo_id
        ))

    else:

        cursor.execute("""
            UPDATE promociones
            SET activa = ?
            WHERE id = ?
        """, (
            activa,
            promo_id
        ))

    conn.commit()
    conn.close()

    flash("Promoción actualizada correctamente 🔥")

    return redirect("/admin/promociones")

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
    return redirect("/admin/promociones")

@app.route("/reparar-cartelera")
def reparar_cartelera():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    conexion = conectar()
    cursor = conexion.cursor()

    try:

        cursor.execute(
            "DROP TABLE IF EXISTS cartelera_plataformas"
        )

        cursor.execute(
            "DROP TABLE IF EXISTS cartelera"
        )

        conexion.commit()
        conexion.close()

        inicializar_db()

        flash("Tablas de cartelera reparadas correctamente 🛠️✅")

    except Exception as error:

        conexion.rollback()
        conexion.close()

        flash(f"No se pudo reparar la cartelera: {error}")

    return redirect("/admin/cartelera")

print("="*60)
print(os.getcwd())
print("="*60)

if __name__ == "__main__":
    inicializar_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
