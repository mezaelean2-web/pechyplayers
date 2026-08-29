from flask import Flask, render_template, request, redirect, session, flash, send_file, jsonify, url_for
import sqlite3
import hashlib
from flask_compress import Compress
import json
import os
import re
import secrets
import time
from pathlib import Path
from itsdangerous import BadSignature, URLSafeTimedSerializer
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

from io import BytesIO
from openpyxl import Workbook
from werkzeug.utils import secure_filename
from PIL import Image
from configuracion_centro import (MODULOS as MODULOS_CONFIGURACION, estado_general as estado_configuracion,
    obtener_modulo as obtener_modulo_configuracion, guardar_borrador as guardar_borrador_configuracion,
    restaurar_modulo as restaurar_modulo_configuracion, restaurar_todo as restaurar_todo_configuracion,
    publicar as publicar_configuracion, configuracion_efectiva, auditoria as auditoria_configuracion)
import database
import resellers
import wallets
import bold_recharges
import reseller_accounts
import customer_cart
import customer_orders
import customer_bold_payments
import customer_fulfillment_rules
import customer_fulfillment
import customer_delivery_access
import customer_order_email
import customer_order_recovery
import reseller_mailbox
import reseller_mailbox_persistence
import mail_center
import managed_secret_store
from mail_provider_factory import build_mail_provider
from mailbox_bindings import MailboxBindingResolver
from pilot_private_email_gate import PilotPrivateEmailGate
from pilot_message_adapter import build_pilot_message_registry
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import PrivateEmailMailProvider
from database import conectar, obtener_productos, obtener_estadisticas, obtener_info_sistema, inicializar_db, obtener_config, actualizar_config, registrar_historial, obtener_historial, obtener_promociones, obtener_categorias, obtener_categorias_cartelera, obtener_categoria_cartelera_por_id, obtener_cartelera, obtener_historial, obtener_resumen_historial, obtener_cuentas_nube, obtener_estadisticas_nube, obtener_plataformas_nube, obtener_tipos_cuenta_nube, crear_cuenta_nube, actualizar_perfil_nube, renovar_perfil_nube, marcar_perfil_caido_nube, obtener_perfiles_disponibles_reemplazo, reemplazar_perfil_nube, obtener_contexto_liberacion_perfil_nube, liberar_o_trasladar_perfil_nube, registrar_no_renovacion_perfil_nube, obtener_historial_completo_perfil_nube, obtener_alertas_operativas_nube, obtener_detalle_alerta_nube, registrar_pago_pin_nube, mover_cuenta_papelera_nube, obtener_cuentas_papelera_nube, obtener_detalle_papelera_nube, restaurar_cuenta_papelera_nube, asignar_cuenta_completa_nube, crear_cuentas_nube_lote, obtener_detalle_drawer_cuenta_nube, actualizar_notas_cuenta_nube
from datetime import timedelta
from collections import defaultdict
from collections import OrderedDict
from database import obtener_historial
from datetime import datetime

app = Flask(__name__)
Compress(app)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 30


def _configured_secret_key():
    configured = os.environ.get("SECRET_KEY", "").strip()
    environments = {
        os.environ.get("APP_ENV", "").strip().lower(),
        os.environ.get("FLASK_ENV", "").strip().lower(),
        os.environ.get("BOLD_ENV", "").strip().lower(),
    }
    production = "production" in environments
    testing = os.environ.get("PECHY_TESTING", "").strip() == "1"
    if production and not testing and not configured:
        raise RuntimeError("SECRET_KEY debe configurarse para iniciar en producción.")
    return configured or "clave-temporal-local"


app.secret_key = _configured_secret_key()
app.permanent_session_lifetime = timedelta(minutes=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
def _config_bool_explicita(valor):
    """Solo activa una capacidad sensible ante un valor afirmativo inequivoco."""
    if valor is True or valor == 1:
        return True
    if isinstance(valor, str):
        return valor.strip().lower() in {"true", "1", "yes", "on"}
    return False


app.config["RESELLER_PURCHASES_ENABLED"] = _config_bool_explicita(
    os.environ.get("RESELLER_PURCHASES_ENABLED"))


def _serializador_preview_carrito():
    return URLSafeTimedSerializer(app.secret_key, salt="reseller-cart-commercial-preview-v1")


def _snapshot_preview_carrito(revendedor_id, preview):
    return {
        "v": 1, "revendedor_id": int(revendedor_id),
        "cart_intent_id": str(preview.get("cart_intent_id") or ""),
        "total": preview["total"],
        "lineas": [{
            "plan_id": linea["plan_id"],
            "cantidad_unidades": linea["cantidad_unidades"],
            "cantidad_periodos": linea["cantidad_periodos"],
            "precio_unitario": linea["precio_unitario"],
            "subtotal": linea["precio_total"],
            "tipo_unidad": linea["tipo_unidad"],
            "duracion_base_dias": linea["duracion_base_dias"],
        } for linea in sorted(
            preview["lineas"], key=lambda x: (x["plan_id"], x["cantidad_periodos"]))],
    }

_intentos_login_reseller = {}
_LOGIN_RESELLER_MAX_INTENTOS = 5
_LOGIN_RESELLER_VENTANA = 15 * 60

# Gate temporal 5B.4A: construir transporte no abre red; solo el piloto exacto puede usarlo.
fake_mail_provider = build_mail_provider(environ={"MAIL_PROVIDER_MODE": "fake"})
try:
    _pilot_credentials = ProviderCredentialResolver()
    _pilot_private_email_provider = PrivateEmailMailProvider(
        PrivateEmailIMAPTransport(_pilot_credentials),
        build_pilot_message_registry(_pilot_credentials))
except Exception:
    _pilot_private_email_provider = None
reseller_mailbox_service = reseller_mailbox.ResellerMailboxService(
    fake_mail_provider, reseller_mailbox_persistence.SQLiteMailboxRepository(),
    binding_resolver=MailboxBindingResolver(),
    private_email_provider=_pilot_private_email_provider,
    private_email_gate=PilotPrivateEmailGate(),action_catalog=mail_center)

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

FORMATOS_PROMOCION = {"PNG", "JPEG", "WEBP"}


def guardar_imagen_promocion(imagen_file):
    if not imagen_file or not imagen_file.filename:
        return None
    try:
        imagen = Image.open(imagen_file.stream)
        imagen.verify()
        formato = (imagen.format or "").upper()
    except Exception as error:
        raise ValueError("El archivo de promoción no es una imagen válida.") from error
    if formato not in FORMATOS_PROMOCION:
        raise ValueError("Formato no permitido. Usa PNG, JPG o WEBP.")

    imagen_file.stream.seek(0)
    imagen = Image.open(imagen_file.stream)
    if imagen.width > 6000 or imagen.height > 6000:
        raise ValueError("La imagen supera las dimensiones máximas permitidas.")
    if imagen.mode not in {"RGB", "RGBA"}:
        imagen = imagen.convert("RGBA" if "A" in imagen.getbands() else "RGB")
    if imagen.width > 2400:
        alto = round(imagen.height * 2400 / imagen.width)
        imagen = imagen.resize((2400, alto), Image.LANCZOS)

    nombre = f"promo_{secrets.token_hex(16)}.webp"
    imagen.save(os.path.join(PROMO_FOLDER, nombre), "WEBP", quality=88, optimize=True)
    return nombre


def eliminar_imagen_promocion_si_huerfana(nombre, excluir_id=None):
    nombre = os.path.basename(nombre or "")
    if not nombre:
        return
    conn = conectar()
    cursor = conn.cursor()
    consulta = """
        SELECT 1 FROM promociones
        WHERE (imagen = ? OR imagen_desktop = ?)
    """
    parametros = [nombre, nombre]
    if excluir_id is not None:
        consulta += " AND id != ?"
        parametros.append(excluir_id)
    existe = cursor.execute(consulta, parametros).fetchone()
    conn.close()
    if existe:
        return
    ruta = os.path.abspath(os.path.join(PROMO_FOLDER, nombre))
    carpeta = os.path.abspath(PROMO_FOLDER)
    if os.path.commonpath([ruta, carpeta]) == carpeta and os.path.isfile(ruta):
        os.remove(ruta)


def resolver_variantes_promociones(promociones):
    resueltas = []
    for promo in promociones:
        mobile = os.path.basename(promo[1] or "")
        desktop = os.path.basename(promo[3] or "")
        mobile_valida = mobile and os.path.isfile(os.path.join(PROMO_FOLDER, mobile))
        desktop_valida = desktop and os.path.isfile(os.path.join(PROMO_FOLDER, desktop))
        if not mobile_valida and not desktop_valida:
            continue
        mobile_efectiva = mobile if mobile_valida else desktop
        desktop_efectiva = desktop if desktop_valida else mobile_efectiva
        resueltas.append((promo[0], mobile_efectiva, promo[2], desktop_efectiva))
    return resueltas

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

    config = configuracion_efectiva()
    revendedor_actual = _revendedor_sesion_actual()
    if not revendedor_actual and session.get("reseller_auth_error"):
        return redirect("/revendedores/login")

    # Todos los productos visibles continúan disponibles
    # para el catálogo principal.
    productos = [
        producto
        for producto in obtener_productos()
        if producto.get("visible", 1) == 1
    ]
    for producto in productos:
        producto["imagen"] = producto.get("imagen") or "producto.jpg"

    categorias_db = obtener_categorias()

    categorias_visibles = {
        categoria["nombre"]
        for categoria in categorias_db
        if categoria["visible"] == 1
    }

    if revendedor_actual and request.path == "/revendedores/productos":
        productos = [
            producto for producto in productos
            if (producto.get("categoria") or "Sin categoría") in categorias_visibles
            and (producto.get("categoria") or "Sin categoría").strip().lower()
                != "sin categoría"
        ]

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

    promociones = [
        promo
        for promo in resolver_variantes_promociones(obtener_promociones())
        if promo[2] == 1
    ]

    if revendedor_actual:
        revendedor_actual["saldo_wallet"] = wallets.obtener_saldo(revendedor_actual["id"])
        revendedor_actual["saldo_wallet_cop"] = wallets.formato_cop(revendedor_actual["saldo_wallet"])
        plan_ids = [plan["id"] for producto in productos for plan in producto["planes"]]
        precios_reseller = resellers.resolver_precios_revendedor(
            revendedor_actual["id"], plan_ids
        )
        for producto in productos:
            for plan in producto["planes"]:
                plan["precio_reseller"] = precios_reseller.get(
                    plan["id"],
                    {"precio": None, "origen": "sin_precio_reseller", "precio_base": None}
                )
                precio_privado = plan["precio_reseller"].get("precio")
                plan["precio_reseller_cop"] = (
                    wallets.formato_cop(precio_privado)
                    if precio_privado is not None else None
                )

    peliculas = [
        pelicula
        for pelicula in obtener_cartelera()
        if (
            pelicula.get("publicado", 0) == 1
            and pelicula.get("categoria_activa") == 1
            and pelicula.get("categoria_clave")
        )
    ]

    categorias_cartelera = obtener_categorias_cartelera(solo_activas=True)

    peliculas_por_categoria = OrderedDict()
    peliculas_ordenadas = []

    for pelicula in peliculas:

        categoria = (
            pelicula.get("categoria_clave")
        ).strip()

        if categoria not in peliculas_por_categoria:

            peliculas_por_categoria[categoria] = []

        peliculas_por_categoria[categoria].append(
            pelicula
        )

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
        peliculas_por_categoria=peliculas_por_categoria,
        categorias_cartelera=categorias_cartelera,
        revendedor_actual=revendedor_actual,
        csrf_customer_checkout_token=_csrf_customer_checkout_token()
    )


def _csrf_reseller_token():
    token = session.get("csrf_reseller")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_reseller"] = token
    return token


def _validar_csrf_reseller():
    recibido = request.form.get("csrf_token", "") or request.headers.get("X-CSRF-Token", "")
    esperado = session.get("csrf_reseller", "")
    return bool(recibido and esperado and secrets.compare_digest(recibido, esperado))


def _csrf_admin_token():
    token = session.get("csrf_admin")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_admin"] = token
    return token


def _csrf_customer_checkout_token():
    token = session.get("csrf_customer_checkout")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_customer_checkout"] = token
    return token


def _validar_csrf_customer_checkout():
    recibido = request.headers.get("X-CSRF-Token", "")
    esperado = session.get("csrf_customer_checkout", "")
    return bool(recibido and esperado and secrets.compare_digest(recibido, esperado))


def _customer_checkout_session_hash():
    token = session.get("customer_checkout_guest_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["customer_checkout_guest_token"] = token
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _customer_delivery_telemetry_context():
    guest_hash = _customer_checkout_session_hash()
    fingerprint = customer_delivery_access.session_fingerprint(guest_hash, app.secret_key)
    return guest_hash, fingerprint


def _customer_order_access(public_order_id, guest_hash):
    try:
        return customer_delivery_access.lookup_owned_order(public_order_id, guest_hash), False
    except customer_delivery_access.CustomerOrderLookupNotFound:
        order_id = customer_order_recovery.authorized_order_id(session, public_order_id)
        if order_id is None:
            raise
        return customer_delivery_access.lookup_recovered_order(public_order_id, order_id), True


def _record_customer_delivery_event(order_id, event_type, source, http_status, safe_code, fingerprint):
    try:
        customer_delivery_access.record_event(
            order_id=order_id, event_type=event_type, source=source,
            http_status=http_status, safe_code=safe_code,
            session_fingerprint_value=fingerprint)
    except Exception:
        # La telemetria nunca debe bloquear pagos, consultas ni entregas.
        pass


def _customer_delivery_secure_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Vary"] = "Cookie"
    return response


def _validar_csrf_admin():
    recibido = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    esperado = session.get("csrf_admin", "")
    return bool(recibido and esperado and secrets.compare_digest(recibido, esperado))


def _limpiar_sesion_reseller():
    for clave in (
        "reseller_id", "reseller_auth_version", "csrf_reseller",
        "reseller_auth_error",
    ):
        session.pop(clave, None)


def _invalidar_sesion_reseller(motivo="sesion"):
    _limpiar_sesion_reseller()
    session["reseller_auth_error"] = motivo


@app.after_request
def _evitar_cache_privado_reseller(respuesta):
    if request.path == "/revendedores" or request.path.startswith("/revendedores/"):
        if "Cache-Control" not in respuesta.headers:
            respuesta.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
        if "Pragma" not in respuesta.headers:
            respuesta.headers["Pragma"] = "no-cache"
        if "Expires" not in respuesta.headers:
            respuesta.headers["Expires"] = "0"
    return respuesta


def _revendedor_sesion_actual():
    reseller_id = session.get("reseller_id")
    version = session.get("reseller_auth_version")
    if not reseller_id or version is None:
        if reseller_id or version is not None:
            _invalidar_sesion_reseller()
        return None
    try:
        revendedor = resellers.obtener_revendedor(int(reseller_id))
    except (TypeError, ValueError, sqlite3.OperationalError):
        revendedor = None
    if not revendedor:
        _invalidar_sesion_reseller()
        return None
    if revendedor["estado"] != "activo":
        _invalidar_sesion_reseller("bloqueado")
        return None
    try:
        version_valida = int(revendedor.get("auth_version") or 1) == int(version)
    except (TypeError, ValueError):
        version_valida = False
    if not version_valida:
        _invalidar_sesion_reseller()
        return None
    return revendedor


def _login_reseller_limitado(correo):
    ahora = time.monotonic()
    clave = (request.remote_addr or "local", str(correo or "").strip().lower())
    intentos = [instante for instante in _intentos_login_reseller.get(clave, []) if ahora - instante < _LOGIN_RESELLER_VENTANA]
    _intentos_login_reseller[clave] = intentos
    return len(intentos) >= _LOGIN_RESELLER_MAX_INTENTOS, clave


def _catalogo_reseller(revendedor_id, incluir_sin_precio=False):
    """Construye el catálogo privado sin usar el precio público como respaldo."""
    categorias_visibles = {
        categoria["nombre"]
        for categoria in obtener_categorias()
        if categoria["visible"] == 1
    }
    candidatos = [
        producto for producto in obtener_productos()
        if producto.get("visible", 1) == 1
        and (incluir_sin_precio or
             (producto.get("estado") or "disponible").strip().lower() == "disponible")
        and (producto.get("categoria") or "Sin categoría").strip().lower() != "sin categoría"
        and (producto.get("categoria") or "Sin categoría") in categorias_visibles
    ]
    plan_ids = [plan["id"] for producto in candidatos for plan in producto["planes"]]
    precios = resellers.resolver_precios_revendedor(revendedor_id, plan_ids)
    catalogo = []
    for producto in candidatos:
        planes = []
        for plan in producto["planes"]:
            precio = precios.get(plan["id"], {})
            if precio.get("precio") is None and not incluir_sin_precio:
                continue
            variante = dict(plan)
            variante["precio_reseller"] = precio or {
                "precio": None, "origen": "sin_precio_reseller", "precio_base": None
            }
            variante["precio_reseller_cop"] = (
                wallets.formato_cop(precio["precio"])
                if precio.get("precio") is not None else None
            )
            planes.append(variante)
        if planes:
            item = dict(producto)
            item["imagen"] = item.get("imagen") or "producto.jpg"
            item["planes"] = planes
            importes = [plan["precio_reseller"]["precio"] for plan in planes
                        if plan["precio_reseller"].get("precio") is not None]
            item["precio_desde"] = min(importes) if importes else None
            item["precio_desde_cop"] = (wallets.formato_cop(item["precio_desde"])
                                         if item["precio_desde"] is not None else None)
            catalogo.append(item)
    return catalogo


def _resumen_privado_reseller(revendedor_id):
    resumen = wallets.obtener_resumen_dashboard(revendedor_id)
    resumen["saldo_cop"] = wallets.formato_cop(resumen["saldo"])
    resumen["total_recargado_cop"] = wallets.formato_cop(resumen["total_recargado"])
    return resumen


def _resumen_billetera_reseller(revendedor_id):
    resumen = _resumen_privado_reseller(revendedor_id)
    _, _, movimientos = wallets.obtener_control_saldo(revendedor_id, limite=100)
    salidas = [item for item in movimientos if item["tipo"] in wallets.TIPOS_DEBITO]
    total_utilizado = sum(int(item["monto"]) for item in salidas)
    resumen.update({
        "movimientos": movimientos,
        "cantidad_movimientos": len(movimientos),
        "cantidad_recargas": sum(1 for item in movimientos if item["tipo"] == "recharge"),
        "total_utilizado": total_utilizado,
        "total_utilizado_cop": wallets.formato_cop(total_utilizado),
        "cantidad_salidas": len(salidas),
    })
    return resumen


@app.route("/revendedores")
def dashboard_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    resumen = _resumen_privado_reseller(revendedor["id"])
    catalogo = _catalogo_reseller(revendedor["id"])
    resumen["productos_disponibles"] = len(catalogo)
    return render_template(
        "resellers/dashboard.html",
        revendedor=revendedor,
        resumen=resumen,
        productos_destacados=catalogo[:1],
        csrf_token=_csrf_reseller_token(),
        seccion_activa="inicio",
    )


@app.route("/revendedores/productos")
def productos_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    # Esta ruta reutiliza literalmente la vista, datos y assets públicos.
    # ``inicio`` ya cambia los precios al detectar la sesión reseller.
    _csrf_reseller_token()
    return inicio()


@app.get("/revendedores/productos/planes/<int:plan_id>/compra")
def preview_compra_producto_revendedor(plan_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "codigo": "sesion_requerida", "mensaje": "Debes iniciar sesión."}), 401
    try:
        try:
            periodos = int(request.args.get("cantidad_periodos", 1))
            unidades = int(request.args.get("cantidad_unidades", 1))
        except (TypeError, ValueError) as error:
            raise reseller_accounts.ResellerPurchaseError(
                "solicitud_invalida", "Las cantidades no son válidas.") from error
        preview = reseller_accounts.previsualizar_compra_plan(
            revendedor["id"], plan_id, periodos, unidades)
    except reseller_accounts.ResellerPurchaseError as error:
        estado = 404 if error.codigo == "plan_inexistente" else 400
        return jsonify({"ok": False, "codigo": error.codigo, "mensaje": error.mensaje}), estado
    return jsonify({"ok": True, "preview": preview})


@app.post("/revendedores/productos/carrito/preview")
def preview_carrito_producto_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "codigo": "sesion_requerida", "mensaje": "Debes iniciar sesión."}), 401
    if not _validar_csrf_reseller():
        return jsonify({"ok": False, "codigo": "csrf_invalido", "mensaje": "Token CSRF no válido."}), 403
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) - {"lineas", "cart_intent_id"}:
        return jsonify({"ok": False, "codigo": "payload_invalido",
                        "mensaje": "La solicitud contiene datos no permitidos."}), 400
    try:
        preview = reseller_accounts.previsualizar_carrito_reseller(
            revendedor["id"], datos.get("lineas"), datos.get("cart_intent_id"))
    except reseller_accounts.ResellerPurchaseError as error:
        estado = 404 if error.codigo == "plan_inexistente" else 400
        return jsonify({"ok": False, "codigo": error.codigo, "mensaje": error.mensaje}), estado
    preview["preview_token"] = _serializador_preview_carrito().dumps(
        _snapshot_preview_carrito(revendedor["id"], preview))
    return jsonify({"ok": True, "preview": preview})


@app.post("/revendedores/productos/carrito/comprar")
def comprar_carrito_producto_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "codigo": "sesion_requerida", "mensaje": "Debes iniciar sesión."}), 401
    if not _validar_csrf_reseller():
        return jsonify({"ok": False, "codigo": "csrf_invalido", "mensaje": "Token CSRF no válido."}), 403
    if not _config_bool_explicita(app.config.get("RESELLER_PURCHASES_ENABLED")):
        return jsonify({"ok": False, "codigo": "purchases_disabled",
                        "mensaje": "Las compras reseller no están habilitadas."}), 409
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) != {"items", "cart_intent_id", "preview_token"}:
        return jsonify({"ok": False, "codigo": "payload_invalido",
                        "mensaje": "La solicitud contiene datos no permitidos."}), 400
    try:
        snapshot = _serializador_preview_carrito().loads(datos.get("preview_token") or "")
        if (snapshot.get("v") != 1 or snapshot.get("revendedor_id") != revendedor["id"]):
            raise BadSignature("preview ajeno o incompatible")
    except (BadSignature, AttributeError, TypeError):
        return jsonify({"ok": False, "codigo": "cart_changed",
                        "mensaje": "El carrito debe revalidarse antes de comprar."}), 409
    try:
        pedido = reseller_accounts.comprar_carrito_reseller(
            revendedor["id"], datos.get("cart_intent_id"), datos.get("items"),
            preview_snapshot=snapshot)
    except reseller_accounts.ResellerPurchaseError as error:
        estados = {"plan_inexistente": 404, "reseller_inexistente": 404,
                   "saldo_insuficiente": 409, "inventario_agotado": 409,
                   "idempotencia_incompatible": 409, "price_changed": 409,
                   "cart_changed": 409}
        cuerpo = {"ok": False, "codigo": error.codigo, "mensaje": error.mensaje}
        if getattr(error, "detalles", None):
            cuerpo.update(error.detalles)
        return jsonify(cuerpo), estados.get(error.codigo, 400)
    except Exception:
        app.logger.exception("Fallo seguro al comprar carrito reseller")
        return jsonify({"ok": False, "codigo": "error_interno",
                        "mensaje": "No fue posible completar el pedido. Tu carrito sigue intacto."}), 500
    return jsonify({"ok": True, "pedido": pedido})


@app.get("/revendedores/pedidos/<int:order_id>/entrega")
def entrega_pedido_revendedor(order_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "codigo": "sesion_requerida",
                        "mensaje": "Debes iniciar sesión."}), 401
    entrega = reseller_accounts.obtener_entrega_pedido_reseller(order_id, revendedor["id"])
    if entrega is None:
        return jsonify({"ok": False, "codigo": "pedido_inexistente",
                        "mensaje": "Pedido no encontrado."}), 404
    respuesta = jsonify({"ok": True, **entrega})
    respuesta.headers["Cache-Control"] = "no-store, private"
    respuesta.headers["Pragma"] = "no-cache"
    return respuesta


@app.post("/revendedores/productos/planes/<int:plan_id>/comprar")
def comprar_producto_revendedor_bloqueado(plan_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "codigo": "sesion_requerida", "mensaje": "Debes iniciar sesión."}), 401
    if not _validar_csrf_reseller():
        return jsonify({"ok": False, "codigo": "csrf_invalido", "mensaje": "Token CSRF no válido."}), 403
    datos = request.get_json(silent=True) or {}
    permitidos = {"lineas", "cart_intent_id", "idempotency_key", "cantidad_periodos"}
    if not isinstance(datos, dict) or set(datos) - permitidos:
        return jsonify({"ok": False, "codigo": "payload_invalido",
                        "mensaje": "La solicitud contiene datos no permitidos."}), 400
    # Guard de Fase 4A: deliberadamente no existe llamada al motor de compra.
    # Incluso una activación accidental no alcanza el motor hasta que Fase 4B
    # sustituya explícitamente este contrato seguro.
    if app.config.get("RESELLER_PURCHASES_ENABLED"):
        return jsonify({"ok": False, "codigo": "purchases_not_implemented",
                        "mensaje": "Las compras reseller aún no están habilitadas."}), 503
    return jsonify({"ok": False, "codigo": "purchases_disabled",
                    "mensaje": "Las compras reseller estarán disponibles próximamente."}), 409


@app.route("/revendedores/mis-cuentas")
def mis_cuentas_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    estado, tipo, busqueda, producto = (request.args.get("estado", "todas"),
                              request.args.get("tipo", "todas"), request.args.get("q", ""),
                              request.args.get("producto", ""))
    todas = reseller_accounts.listar_mis_cuentas(revendedor["id"])
    return render_template(
        "resellers/mis_cuentas.html", revendedor=revendedor,
        cuentas=reseller_accounts.listar_mis_cuentas(
            revendedor["id"], estado, tipo, busqueda, producto),
        productos=sorted({item["producto"] for item in todas if item.get("producto")}, key=str.casefold),
        metricas=reseller_accounts.resumen_mis_cuentas(revendedor["id"]),
        resumen=_resumen_privado_reseller(revendedor["id"]),
        filtros={"estado": estado, "tipo": tipo, "q": busqueda, "producto": producto},
        csrf_token=_csrf_reseller_token(), seccion_activa="mis_cuentas")


def _reseller_mailbox_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Vary"] = "Cookie"
    return response


@app.get("/revendedores/buzon")
def buzon_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    return render_template(
        "resellers/buzon.html", revendedor=revendedor,
        resumen=_resumen_privado_reseller(revendedor["id"]),
        mail_actions=mail_center.available_actions_for_reseller(revendedor["id"]),
        csrf_token=_csrf_reseller_token(), seccion_activa="buzon")


@app.post("/revendedores/buzon/solicitudes")
def solicitar_mensaje_buzon_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return _reseller_mailbox_response(
            {"ok": False, "status": "unavailable",
             "message": "No hay mensajes disponibles para esta cuenta."}, 401)
    if not _validar_csrf_reseller():
        return _reseller_mailbox_response(
            {"ok": False, "status": "unavailable",
             "message": "No hay mensajes disponibles para esta cuenta."}, 403)
    data = request.get_json(silent=True)
    expected={"email","action_id"} if reseller_mailbox_service.action_catalog is not None else {"email"}
    valid_payload=isinstance(data,dict) and set(data)==expected
    email = data.get("email") if valid_payload else None
    action_id = data.get("action_id") if valid_payload and "action_id" in data else None
    return _reseller_mailbox_response(
        reseller_mailbox_service.request_message(revendedor["id"], email, action_id))


@app.get("/revendedores/buzon/solicitudes/<request_id>")
def estado_mensaje_buzon_revendedor(request_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return _reseller_mailbox_response(
            {"ok": False, "status": "unavailable",
             "message": "No hay mensajes disponibles para esta cuenta."}, 401)
    return _reseller_mailbox_response(
        reseller_mailbox_service.poll_request(revendedor["id"], request_id))


@app.get("/revendedores/buzon/mensajes/<delivery_id>")
def leer_mensaje_buzon_revendedor(delivery_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return _reseller_mailbox_response(
            {"ok": False, "status": "unavailable",
             "message": "No hay mensajes disponibles para esta cuenta."}, 401)
    return _reseller_mailbox_response(
        reseller_mailbox_service.read_delivery(revendedor["id"], delivery_id))


@app.route("/revendedores/mis-cuentas/<int:purchase_id>")
def detalle_mi_cuenta_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    detalle = reseller_accounts.obtener_detalle_mi_cuenta(purchase_id, revendedor["id"])
    if not detalle:
        return jsonify({"ok": False, "error": "Adquisición no encontrada."}), 404
    return jsonify({"ok": True, "detalle": detalle})


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/credenciales")
def credenciales_mi_cuenta_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    resultado = reseller_accounts.obtener_credenciales_autorizadas(purchase_id, revendedor["id"])
    if resultado is None:
        return jsonify({"ok": False, "error": "Adquisición no encontrada."}), 404
    return jsonify({"ok": True, **resultado})


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/disponibilidad")
def disponibilidad_mi_cuenta_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    resultado = reseller_accounts.consultar_disponibilidad_recuperacion(
        revendedor["id"], purchase_id)
    if resultado is None:
        return jsonify({"ok": False, "error": "Adquisición no encontrada."}), 404
    estado = 409 if resultado["code"] == "NOT_CUT" else 200
    return jsonify({"ok": estado == 200, **resultado}), estado


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/recuperacion")
def previsualizar_recuperacion_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    try:
        cantidad = request.args.get("cantidad_periodos", "1")
        if not str(cantidad).isdigit():
            raise reseller_accounts.ResellerPurchaseError(
                "cantidad_periodos_invalida", "La cantidad de períodos no es válida.")
        resultado = reseller_accounts.previsualizar_recovery(
            purchase_id, revendedor["id"], int(cantidad))
        return jsonify({"ok": True, **resultado})
    except reseller_accounts.ResellerPurchaseError as error:
        return _respuesta_error_operacion_reseller(error)


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/recuperar", methods=["POST"])
def recuperar_mi_cuenta_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    if not _validar_csrf_revendedores():
        return jsonify({"ok": False, "error": "Solicitud de seguridad inválida."}), 403
    datos = request.get_json(silent=True) or {}
    try:
        cantidad = datos.get("cantidad_periodos")
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            raise reseller_accounts.ResellerPurchaseError(
                "cantidad_periodos_invalida", "La cantidad de períodos debe ser un entero.")
        resultado = reseller_accounts.recuperar_purchase_reseller(
            revendedor["id"], purchase_id, cantidad, datos.get("idempotency_key"))
        return jsonify({"ok": True, "mensaje": "Servicio recuperado correctamente.",
                        "precio_total_cop": wallets.formato_cop(resultado["precio_total"]),
                        **resultado})
    except reseller_accounts.ResellerPurchaseError as error:
        return _respuesta_error_operacion_reseller(error)


def _respuesta_error_operacion_reseller(error):
    codigo = getattr(error, "codigo", "solicitud_invalida")
    estado = 404 if codigo == "purchase_inexistente" else 409
    if codigo in {"solicitud_invalida", "cantidad_periodos_invalida", "cantidad_periodos_excedida",
                  "idempotencia_invalida"}:
        estado = 400
    return jsonify({"ok": False, "codigo": codigo, "error": str(error)}), estado


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/renovacion")
def previsualizar_renovacion_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    try:
        cantidad = int(request.args.get("cantidad_periodos", 1))
        return jsonify({"ok": True, **reseller_accounts.previsualizar_renovacion(
            purchase_id, revendedor["id"], cantidad)})
    except (ValueError, TypeError, reseller_accounts.ResellerPurchaseError) as error:
        if not isinstance(error, reseller_accounts.ResellerPurchaseError):
            error = reseller_accounts.ResellerPurchaseError("cantidad_periodos_invalida", "La cantidad de períodos no es válida.")
        return _respuesta_error_operacion_reseller(error)


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/renovar", methods=["POST"])
def renovar_mi_cuenta_revendedor(purchase_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    if not _validar_csrf_revendedores():
        return jsonify({"ok": False, "error": "Solicitud de seguridad inválida."}), 403
    datos = request.get_json(silent=True) or {}
    try:
        cantidad = datos.get("cantidad_periodos")
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            raise reseller_accounts.ResellerPurchaseError("cantidad_periodos_invalida", "La cantidad de períodos debe ser un entero.")
        resultado = reseller_accounts.renovar_purchase_reseller(
            revendedor["id"], purchase_id, cantidad, datos.get("idempotency_key"))
        return jsonify({"ok": True, "mensaje": "Renovación realizada correctamente.", **resultado})
    except reseller_accounts.ResellerPurchaseError as error:
        return _respuesta_error_operacion_reseller(error)


def _cambiar_no_renovar_http(purchase_id, marcado):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    if not _validar_csrf_revendedores():
        return jsonify({"ok": False, "error": "Solicitud de seguridad inválida."}), 403
    try:
        resultado = reseller_accounts.cambiar_no_renovar(
            purchase_id, revendedor["id"], marcado)
        mensaje = "El servicio se marcÃ³ como No renovar." if marcado else "El servicio volverÃ¡ a estar disponible para renovar."
        return jsonify({"mensaje": mensaje, **resultado})
    except reseller_accounts.ResellerPurchaseError as error:
        return _respuesta_error_operacion_reseller(error)


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/no-renovar", methods=["POST"])
def no_renovar_mi_cuenta_revendedor(purchase_id):
    return _cambiar_no_renovar_http(purchase_id, True)


@app.route("/revendedores/mis-cuentas/<int:purchase_id>/seguir-renovando", methods=["POST"])
def seguir_renovando_mi_cuenta_revendedor(purchase_id):
    return _cambiar_no_renovar_http(purchase_id, False)


@app.route("/revendedores/recargar")
def recargar_revendedor():
    if not _revendedor_sesion_actual():
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    return redirect("/revendedores/billetera#recargar")


@app.route("/revendedores/movimientos")
def movimientos_revendedor():
    if not _revendedor_sesion_actual():
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    return redirect("/revendedores/billetera#movimientos")


@app.route("/revendedores/billetera")
def billetera_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    resumen = _resumen_billetera_reseller(revendedor["id"])
    movimientos = resumen["movimientos"]
    return render_template(
        "resellers/billetera.html", revendedor=revendedor, resumen=resumen,
        movimientos=movimientos, tipos_ingreso=wallets.TIPOS_CREDITO,
        csrf_token=_csrf_reseller_token(), seccion_activa="billetera",
    )


@app.route("/revendedores/registro", methods=["GET", "POST"])
def registro_revendedor():
    resellers.inicializar_revendedores()
    if _revendedor_sesion_actual():
        return redirect("/revendedores")
    error = None
    if request.method == "POST":
        if not _validar_csrf_reseller():
            error = "La sesión del formulario expiró. Intenta nuevamente."
        elif request.form.get("password", "") != request.form.get("confirmar_password", ""):
            error = "Las contraseñas no coinciden."
        else:
            try:
                reseller_id = resellers.crear_revendedor(
                    request.form.get("nombre"), request.form.get("correo"),
                    request.form.get("telefono"), request.form.get("negocio"),
                    request.form.get("password"), actor="autorregistro",
                    tipo_actividad="registro_publico"
                )
                revendedor = resellers.obtener_revendedor(reseller_id)
                session["reseller_id"] = reseller_id
                session["reseller_auth_version"] = revendedor["auth_version"]
                session.permanent = True
                return redirect("/revendedores")
            except ValueError as exc:
                error = str(exc)
    return render_template("resellers/registro.html", error=error, csrf_token=_csrf_reseller_token())


@app.route("/revendedores/login", methods=["GET", "POST"])
def login_revendedor():
    resellers.inicializar_revendedores()
    if _revendedor_sesion_actual():
        return redirect("/revendedores")
    motivo_sesion = session.pop("reseller_auth_error", None)
    error = (
        "Tu cuenta se encuentra temporalmente bloqueada."
        if motivo_sesion == "bloqueado"
        else "Tu sesión ha finalizado. Inicia sesión nuevamente."
        if motivo_sesion
        else None
    )
    if request.method == "POST":
        if not _validar_csrf_reseller():
            error = "La sesión del formulario expiró. Intenta nuevamente."
        else:
            limitado, clave_limite = _login_reseller_limitado(request.form.get("correo"))
            if limitado:
                error = "Demasiados intentos. Espera unos minutos antes de volver a intentar."
            else:
                resultado = resellers.autenticar_revendedor(
                    request.form.get("correo"), request.form.get("password")
                )
                if resultado["ok"]:
                    _intentos_login_reseller.pop(clave_limite, None)
                    session["reseller_id"] = resultado["id"]
                    session["reseller_auth_version"] = resultado["auth_version"]
                    session.permanent = True
                    return redirect("/revendedores")
                _intentos_login_reseller.setdefault(clave_limite, []).append(time.monotonic())
                error = (
                    "Tu cuenta se encuentra temporalmente bloqueada."
                    if resultado.get("codigo") == "bloqueado"
                    else "Correo o contraseña incorrectos."
                )
    return render_template("resellers/login.html", error=error, csrf_token=_csrf_reseller_token())


@app.route("/revendedores/logout", methods=["POST"])
def logout_revendedor():
    if not _validar_csrf_reseller():
        return "Solicitud no válida", 403
    _limpiar_sesion_reseller()
    return redirect("/revendedores/login")


@app.route("/revendedores/cuenta", methods=["GET", "POST"])
def cuenta_revendedor():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        session.setdefault("reseller_auth_error", "sesion")
        return redirect("/revendedores/login")
    error = None
    exito = None
    if request.method == "POST":
        if not _validar_csrf_reseller():
            error = "La sesión del formulario expiró. Intenta nuevamente."
        else:
            accion = request.form.get("accion")
            try:
                if accion == "perfil":
                    resellers.actualizar_perfil_propio(
                        revendedor["id"], request.form.get("nombre"),
                        request.form.get("negocio"), request.form.get("telefono")
                    )
                    exito = "Información actualizada."
                elif accion == "password":
                    nueva = request.form.get("password_nueva", "")
                    if nueva != request.form.get("confirmar_password", ""):
                        raise ValueError("Las contraseñas nuevas no coinciden.")
                    version = resellers.cambiar_password_propia(
                        revendedor["id"], request.form.get("password_actual"), nueva
                    )
                    session["reseller_auth_version"] = version
                    exito = "Contraseña actualizada. Las demás sesiones quedaron invalidadas."
                else:
                    error = "Acción no válida."
            except (ValueError, LookupError) as exc:
                error = str(exc)
            revendedor = _revendedor_sesion_actual()
    resumen = _resumen_billetera_reseller(revendedor["id"])
    return render_template(
        "resellers/cuenta.html", revendedor=revendedor, error=error,
        exito=exito, csrf_token=_csrf_reseller_token(),
        resumen=resumen, seccion_activa="cuenta"
    )


@app.route("/revendedores/recargas", methods=["POST"])
def crear_recarga_reseller():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "Debes iniciar sesión."}), 401
    if not _validar_csrf_reseller():
        return jsonify({"ok": False, "error": "Token CSRF no válido."}), 403
    datos = request.get_json(silent=True) or request.form
    retorno = os.environ.get("BOLD_REDIRECTION_URL", "").strip()
    try:
        checkout = bold_recharges.create_intent(revendedor["id"], datos.get("monto"), retorno)
    except (ValueError, LookupError) as error:
        return jsonify({"ok": False, "error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"ok": False, "error": str(error)}), 503
    return jsonify({"ok": True, "checkout": checkout}), 201


@app.route("/revendedores/recargas/resultado")
def resultado_recarga_reseller():
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return redirect("/revendedores/login")
    order_id = request.args.get("bold-order-id", "")
    intent = bold_recharges.get_intent(order_id, revendedor["id"]) if order_id else None
    return render_template("resellers/recarga_resultado.html", intent=intent, order_id=order_id)


@app.route("/revendedores/recargas/<order_id>/estado")
def estado_recarga_reseller(order_id):
    revendedor = _revendedor_sesion_actual()
    if not revendedor:
        return jsonify({"ok": False, "error": "No autorizado."}), 401
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", order_id):
        return jsonify({"ok": False, "error": "Referencia no válida."}), 400
    intent = bold_recharges.get_intent(order_id, revendedor["id"])
    if not intent:
        return jsonify({"ok": False, "error": "Recarga no encontrada."}), 404
    return jsonify({"ok": True, "order_id": intent["order_id"], "estado": intent["estado"],
        "monto": intent["monto"], "monto_cop": wallets.formato_cop(intent["monto"]),
        "saldo": intent["saldo"], "saldo_cop": wallets.formato_cop(intent["saldo"])})


@app.route("/webhooks/bold", methods=["POST"])
def webhook_bold():
    started_at = time.perf_counter()
    raw_body = request.get_data(cache=True, parse_form_data=False)
    signature = request.headers.get("X-Bold-Signature", "")
    try:
        if not bold_recharges.valid_signature(raw_body, signature):
            response = (jsonify({"ok": False, "error": "Solicitud no válida."}), 400)
        elif not request.is_json:
            response = (jsonify({"ok": False, "error": "Solicitud no válida."}), 415)
        else:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
                data = payload.get("data") if isinstance(payload, dict) else None
                metadata = data.get("metadata") if isinstance(data, dict) else None
                reference = metadata.get("reference") if isinstance(metadata, dict) else None
                if isinstance(reference, str) and reference.startswith("CUST-"):
                    result = customer_bold_payments.process_webhook(payload)
                else:
                    result = bold_recharges.process_webhook(payload)
                response = (jsonify({"ok": True, **result}), 200)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                response = (jsonify({"ok": False, "error": "Payload inválido."}), 400)
    except Exception:
        app.logger.exception("Error interno procesando webhook Bold")
        response = (jsonify({"ok": False, "error": "No se pudo procesar el evento."}), 500)
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    app.logger.info("Webhook Bold procesado status=%s duration_ms=%.2f", response[1], elapsed_ms)
    return response

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

    return redirect("/admin/productos#productos")

@app.route("/admin/productos")
def admin_productos():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    resellers.inicializar_revendedores()
    productos = obtener_productos()
    categorias = obtener_categorias()

    return render_template(
        "admin/productos.html",
        productos=productos,
        categorias=categorias,
        csrf_token=_csrf_revendedores_token()
    )


def _mail_center_admin_actor():
    return str(session.get("admin_usuario") or "admin")[:80]


def _mail_center_secret_store():
    return managed_secret_store.SQLiteEncryptedSecretStore.from_environment()


@app.get("/admin/centro-correo")
def admin_centro_correo():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    mail_center.initialize_schema()
    return render_template("admin/centro_correo.html",
        mailboxes=mail_center.list_mailboxes(), actions=mail_center.list_actions(),
        plataformas=reseller_accounts.listar_plataformas_inventario(),
        extractor_types=sorted(mail_center.EXTRACTOR_TYPES), csrf_token=_csrf_admin_token(),
        secret_storage_requires_decision=True)


def _mail_center_json(payload,status=200):
    response=jsonify(payload); response.status_code=status
    response.headers["Cache-Control"]="no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    return response


@app.post("/admin/centro-correo/api/buzones")
def admin_crear_buzon_correo():
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    data=request.get_json(silent=True)
    allowed={"display_name","provider","host","port","tls_mode","username","password","folder_key","enabled"}
    if not isinstance(data,dict) or set(data)!=allowed:
        return _mail_center_json({"ok":False,"error":"invalid_mailbox_configuration"},400)
    try:
        mailbox_id=mail_center.save_managed_mailbox(data if isinstance(data,dict) else {},
            _mail_center_secret_store(),actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True,"mailbox_id":mailbox_id})
    except managed_secret_store.SecretStoreError:
        return _mail_center_json({"ok":False,"error":"secret_store_unavailable"},503)
    except mail_center.MailCenterError:
        return _mail_center_json({"ok":False,"error":"invalid_mailbox_configuration"},400)


@app.put("/admin/centro-correo/api/buzones/<int:mailbox_id>")
def admin_editar_buzon_correo(mailbox_id):
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    data=request.get_json(silent=True)
    allowed={"display_name","provider","host","port","tls_mode","folder_key","enabled"}
    if not isinstance(data,dict) or set(data)!=allowed:
        return _mail_center_json({"ok":False,"error":"invalid_mailbox_configuration"},400)
    try:
        mail_center.update_mailbox_configuration(mailbox_id,data,
                                                 actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True,"mailbox_id":mailbox_id})
    except mail_center.MailCenterError:
        return _mail_center_json({"ok":False,"error":"invalid_mailbox_configuration"},400)


@app.post("/admin/centro-correo/api/buzones/<int:mailbox_id>/probar")
def admin_probar_buzon_correo(mailbox_id):
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    resolver=ProviderCredentialResolver()
    result=mail_center.test_mailbox_connection(mailbox_id,resolver,
        lambda value:PrivateEmailIMAPTransport(value),actor=_mail_center_admin_actor())
    return _mail_center_json(result,200 if result.get("ok") else 400)


@app.post("/admin/centro-correo/api/buzones/probar-credencial")
def admin_probar_credencial_buzon_correo():
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    result=mail_center.test_unsaved_credentials(request.get_json(silent=True) or {},
        lambda resolver:PrivateEmailIMAPTransport(resolver))
    return _mail_center_json(result,200 if result.get("ok") else 400)


@app.post("/admin/centro-correo/api/buzones/<int:mailbox_id>/credencial")
def admin_rotar_credencial_buzon_correo(mailbox_id):
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    data=request.get_json(silent=True) or {}
    if set(data)!={"username","password"}:
        return _mail_center_json({"ok":False,"error":"invalid_credential"},400)
    try:
        mail_center.rotate_mailbox_credential(mailbox_id,data["username"],data["password"],
            _mail_center_secret_store(),actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True,"mailbox_id":mailbox_id,"credential_configured":True})
    except (mail_center.MailCenterError,managed_secret_store.SecretStoreError):
        return _mail_center_json({"ok":False,"error":"credential_update_failed"},400)


@app.delete("/admin/centro-correo/api/buzones/<int:mailbox_id>")
def admin_eliminar_buzon_correo(mailbox_id):
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    try:
        mail_center.delete_managed_mailbox(mailbox_id,_mail_center_secret_store(),
                                           actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True})
    except (mail_center.MailCenterError,managed_secret_store.SecretStoreError):
        return _mail_center_json({"ok":False,"error":"mailbox_delete_denied"},409)


@app.post("/admin/centro-correo/api/acciones")
def admin_crear_accion_correo():
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    try:
        action_id=mail_center.save_action(request.get_json(silent=True) or {},
                                          actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True,"action_id":action_id})
    except mail_center.MailCenterError:
        return _mail_center_json({"ok":False,"error":"invalid_action_configuration"},400)


@app.put("/admin/centro-correo/api/acciones/<int:action_id>")
def admin_editar_accion_correo(action_id):
    if not session.get("admin"):
        return _mail_center_json({"ok":False,"error":"unauthorized"},401)
    if not _validar_csrf_admin():
        return _mail_center_json({"ok":False,"error":"invalid_csrf"},403)
    try:
        mail_center.save_action(request.get_json(silent=True) or {},action_id=action_id,
                                actor=_mail_center_admin_actor())
        return _mail_center_json({"ok":True,"action_id":action_id})
    except mail_center.MailCenterError:
        return _mail_center_json({"ok":False,"error":"invalid_action_configuration"},400)


@app.route("/admin/productos/descuentos-carrito", methods=["POST"])
def crear_regla_descuento_carrito_admin():
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"minimum_eligible_services", "discount_bps", "active"}:
        return _error_revendedores("Payload de regla no válido.")
    try:
        rule_id = customer_cart.save_discount_rule(
            None, data["minimum_eligible_services"], data["discount_bps"], data["active"]
        )
    except sqlite3.IntegrityError:
        return _error_revendedores("Ya existe una regla para ese mínimo.", 409)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True, "id": rule_id}), 201


@app.route("/admin/productos/descuentos-carrito/<int:rule_id>", methods=["PUT", "DELETE"])
def regla_descuento_carrito_admin(rule_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    try:
        if request.method == "DELETE":
            customer_cart.delete_discount_rule(rule_id)
        else:
            data = request.get_json(silent=True)
            if not isinstance(data, dict) or set(data) != {"minimum_eligible_services", "discount_bps", "active"}:
                return _error_revendedores("Payload de regla no válido.")
            customer_cart.save_discount_rule(
                rule_id, data["minimum_eligible_services"], data["discount_bps"], data["active"]
            )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except sqlite3.IntegrityError:
        return _error_revendedores("Ya existe una regla para ese mínimo.", 409)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True})


@app.route("/admin/productos/<int:plan_id>/descuento-carrito", methods=["PATCH"])
def elegibilidad_descuento_carrito_admin(plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"eligible", "discount_bps"}:
        return _error_revendedores("Payload de elegibilidad no válido.")
    try:
        customer_cart.set_plan_discount_configuration(plan_id, data["eligible"], data["discount_bps"])
    except LookupError as error:
        return _error_revendedores(error, 404)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True})


@app.route("/compras/carrito/preview", methods=["POST"])
def preview_carrito_publico():
    if request.content_length is not None and request.content_length > 4096:
        return jsonify({"ok": False, "code": "payload_too_large", "message": "El carrito supera el tamaño permitido."}), 413
    if not request.is_json:
        return jsonify({"ok": False, "code": "invalid_json", "message": "Se requiere JSON válido."}), 415
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "code": "invalid_json", "message": "El JSON no es válido."}), 400
    try:
        result = customer_cart.calculate_cart(payload)
    except customer_cart.CartValidationError as error:
        return jsonify({"ok": False, "code": error.code, "message": str(error)}), 400
    except Exception:
        app.logger.exception("Error controlado al calcular preview del carrito público")
        return jsonify({"ok": False, "code": "preview_unavailable", "message": "No pudimos calcular el carrito."}), 500
    return jsonify({"ok": True, "preview": result})


@app.route("/compras/pedidos", methods=["POST"])
def crear_pedido_cliente_publico():
    if request.content_length is not None and request.content_length > 8192:
        return jsonify({"ok": False, "code": "payload_too_large", "message": "La solicitud supera el tamaño permitido."}), 413
    if not request.is_json:
        return jsonify({"ok": False, "code": "invalid_json", "message": "Se requiere JSON válido."}), 415
    if not _validar_csrf_customer_checkout():
        return jsonify({"ok": False, "code": "invalid_csrf", "message": "La sesión de compra venció. Recarga la página e inténtalo nuevamente."}), 403
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"ok": False, "code": "invalid_json", "message": "El JSON no es válido."}), 400
    try:
        order, created = customer_orders.create_order(payload, guest_session_hash=_customer_checkout_session_hash())
    except (customer_orders.OrderValidationError, customer_cart.CartValidationError) as error:
        return jsonify({"ok": False, "code": getattr(error, "code", "invalid_order"), "message": str(error)}), getattr(error, "status", 400)
    except Exception:
        app.logger.exception("Error controlado al crear pedido público")
        return jsonify({"ok": False, "code": "order_unavailable", "message": "No pudimos preparar el pedido. Inténtalo nuevamente."}), 500
    public_order = {key: value for key, value in order.items() if key != "customer"}
    return jsonify({"ok": True, "created": created, "order": public_order}), 201 if created else 200


@app.route("/compras/checkout-profile", methods=["GET"])
def perfil_checkout_cliente_publico():
    if not _validar_csrf_customer_checkout():
        return jsonify({"ok": False, "code": "invalid_csrf", "message": "La sesión de compra venció."}), 403
    customer = customer_orders.get_checkout_customer(_customer_checkout_session_hash())
    response = jsonify({"ok": True, "customer": customer})
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.route("/compras/pedidos/cancelar-actual", methods=["POST"])
def cancelar_pedido_cliente_actual():
    if not _validar_csrf_customer_checkout():
        return jsonify({"ok": False, "code": "invalid_csrf", "message": "La sesión de compra venció."}), 403
    if not request.is_json or request.get_json(silent=True) != {}:
        return jsonify({"ok": False, "code": "invalid_payload", "message": "La solicitud de cancelación no es válida."}), 400
    try:
        result = customer_orders.cancel_current_order(_customer_checkout_session_hash())
    except customer_orders.OrderValidationError as error:
        return jsonify({"ok": False, "code": error.code, "message": str(error)}), error.status
    if result["result"] in {"ownership_mismatch", "not_cancellable"}:
        return jsonify({"ok": False, "code": "order_not_cancellable", "message": "El pedido actual no puede cancelarse automáticamente."}), 409
    return jsonify({"ok": True, "result": result["result"]})


@app.route("/compras/pedidos/<public_order_id>/pago/bold", methods=["POST"])
def iniciar_pago_bold_cliente(public_order_id):
    if not _validar_csrf_customer_checkout():
        return jsonify({"ok": False, "code": "invalid_csrf", "message": "La sesión de compra venció."}), 403
    if not request.is_json or request.get_json(silent=True) != {}:
        return jsonify({"ok": False, "code": "invalid_payload", "message": "La solicitud de pago no es válida."}), 400
    redirection_url = os.environ.get("BOLD_CUSTOMER_REDIRECTION_URL", "").strip()
    if not redirection_url:
        redirection_url = url_for("resultado_pago_bold_cliente", order=public_order_id, _external=True)
    try:
        result = customer_bold_payments.create_or_reuse_checkout(
            public_order_id, _customer_checkout_session_hash(), redirection_url)
    except customer_bold_payments.CustomerPaymentError as error:
        return jsonify({"ok": False, "code": error.reason, "message": str(error)}), error.status
    except RuntimeError as error:
        return jsonify({"ok": False, "code": "bold_unavailable", "message": str(error)}), 503
    response = jsonify({"ok": True, **result})
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.route("/compras/pago/resultado")
def resultado_pago_bold_cliente():
    public_order_id = request.args.get("order", "")
    response = app.make_response(render_template(
        "customer_payment_result.html", public_order_id=public_order_id,
        csrf_token=_csrf_customer_checkout_token()))
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.route("/compras/pedidos/<public_order_id>/estado")
def estado_pago_cliente(public_order_id):
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    if not _validar_csrf_customer_checkout():
        _record_customer_delivery_event(None, "delivery_request_denied", "server", 403, "invalid_csrf", fingerprint)
        return jsonify({"ok": False, "code": "invalid_csrf", "message": "La sesión de compra venció."}), 403
    try:
        access, recovered = _customer_order_access(public_order_id, guest_hash)
        if recovered:
            result = {"order_id": access["public_order_id"],
                      "status": access["payment_status"], "payment_status": access["payment_status"],
                      "fulfillment_status": access["state"],
                      "fulfilled": access["delivery_available"]}
        else:
            result = customer_bold_payments.get_status(
                public_order_id, guest_hash, reconcile=True)
    except (customer_bold_payments.CustomerPaymentError,
            customer_delivery_access.CustomerOrderLookupNotFound) as error:
        status = getattr(error, "status", 404)
        reason = getattr(error, "reason", "order_not_found")
        _record_customer_delivery_event(None, "delivery_request_denied", "server", status, "order_not_found", fingerprint)
        return jsonify({"ok": False, "code": reason, "message": "Pedido no encontrado."}), status
    order_id = access["internal_id"]
    _record_customer_delivery_event(order_id, "delivery_status_checked", "server", 200, result["status"], fingerprint)
    if result["fulfilled"]:
        _record_customer_delivery_event(order_id, "delivery_fulfilled_observed", "server", 200, "fulfilled", fingerprint)
    response = jsonify({"ok": True, **result})
    response.headers["Cache-Control"] = "no-store, private"
    return response


@app.route("/compras/pedidos/consultar", methods=["POST"])
def consultar_pedido_cliente():
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    if not _validar_csrf_customer_checkout():
        _record_customer_delivery_event(None, "delivery_request_denied", "server", 404, "not_found", fingerprint)
        return _customer_delivery_secure_response(
            {"ok": False, "code": "not_found", "message": "No encontramos un pedido disponible para esta sesión."}, 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"public_order_id"}:
        _record_customer_delivery_event(None, "delivery_request_denied", "server", 404, "not_found", fingerprint)
        return _customer_delivery_secure_response(
            {"ok": False, "code": "not_found", "message": "No encontramos un pedido disponible para esta sesión."}, 404)
    try:
        result = customer_delivery_access.lookup_owned_order(data["public_order_id"], guest_hash)
    except customer_delivery_access.CustomerOrderLookupNotFound:
        recovery = customer_order_recovery.prepare_recovery(data["public_order_id"])
        recovery_id = secrets.token_urlsafe(24)
        session[customer_order_recovery.RECOVERY_SESSION_KEY] = {
            "id": recovery_id, "public_order_id": str(data["public_order_id"] or "").strip(),
            "expires": time.time() + 600,
        }
        order_id = recovery["order"]["id"] if recovery["order"] else None
        safe_code = "recovery_required" if order_id else "recovery_not_found"
        _record_customer_delivery_event(order_id, "delivery_request_denied", "server", 200, safe_code, fingerprint)
        return _customer_delivery_secure_response({
            "ok": True, "recovery_required": True, "recovery_id": recovery_id,
            "channels": recovery["channels"],
            "message": "Verifica tu identidad para continuar. Si el pedido es válido, enviaremos el código al canal seleccionado.",
        })
    _record_customer_delivery_event(result["internal_id"], "delivery_status_checked", "server", 200, result["state"], fingerprint)
    if result["delivery_available"]:
        _record_customer_delivery_event(result["internal_id"], "delivery_fulfilled_observed", "server", 200, "fulfilled", fingerprint)
    public_result = {key: result[key] for key in (
        "public_order_id", "state", "payment_status", "delivery_available", "message")}
    public_result["delivery_url"] = url_for("resultado_pago_bold_cliente", order=result["public_order_id"])
    return _customer_delivery_secure_response({"ok": True, "order": public_result})


def _customer_recovery_context(recovery_id):
    context = session.get(customer_order_recovery.RECOVERY_SESSION_KEY)
    if (not isinstance(context, dict) or not isinstance(recovery_id, str)
            or not secrets.compare_digest(context.get("id", ""), recovery_id)
            or float(context.get("expires", 0)) <= time.time()):
        return None
    return context


@app.post("/compras/pedidos/recuperacion/otp/solicitar")
def solicitar_otp_pedido_cliente():
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    if not _validar_csrf_customer_checkout():
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_request"}, 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"recovery_id", "channel"}:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_request"}, 400)
    context = _customer_recovery_context(data["recovery_id"])
    if context is None:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_request"}, 400)
    requester = customer_order_recovery.requester_fingerprint(
        fingerprint, request.remote_addr, app.secret_key)
    result = customer_order_recovery.request_order_otp(
        context["public_order_id"], data["channel"], requester, app.secret_key)
    retry_after = int(result.get("retry_after", customer_order_recovery.OTP_RESEND_COOLDOWN_SECONDS))
    return _customer_delivery_secure_response({
        "ok": True, "accepted": True, "retry_after": retry_after,
        "message": "Si el pedido y el canal son válidos, el código será enviado.",
    }, 202)


@app.post("/compras/pedidos/recuperacion/otp/verificar")
def verificar_otp_pedido_cliente():
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    if not _validar_csrf_customer_checkout():
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_code"}, 400)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"recovery_id", "code"}:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_code"}, 400)
    context = _customer_recovery_context(data["recovery_id"])
    if context is None:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_code"}, 400)
    requester = customer_order_recovery.requester_fingerprint(
        fingerprint, request.remote_addr, app.secret_key)
    result = customer_order_recovery.verify_order_otp(
        context["public_order_id"], data["code"], requester, app.secret_key)
    if not result["verified"]:
        return _customer_delivery_secure_response({
            "ok": False, "code": "invalid_code",
            "message": "El código no es válido, venció o alcanzó el límite de intentos.",
        }, 400)
    customer_order_recovery.authorize_order_access(
        session, result["public_order_id"], result["order_id"])
    access = customer_delivery_access.lookup_recovered_order(
        result["public_order_id"], result["order_id"])
    public_result = {key: access[key] for key in (
        "public_order_id", "state", "payment_status", "delivery_available", "message")}
    public_result["delivery_url"] = url_for(
        "resultado_pago_bold_cliente", order=access["public_order_id"])
    session.pop(customer_order_recovery.RECOVERY_SESSION_KEY, None)
    return _customer_delivery_secure_response({"ok": True, "verified": True, "order": public_result})


@app.route("/compras/pedidos/<public_order_id>/telemetria-entrega", methods=["POST"])
def telemetria_entrega_cliente(public_order_id):
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    if not _validar_csrf_customer_checkout():
        return _customer_delivery_secure_response({"ok": False, "code": "not_found"}, 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"event", "safe_code"}:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_event"}, 400)
    try:
        event_type, safe_code = customer_delivery_access.validate_client_event(
            data["event"], data["safe_code"])
        order, _ = _customer_order_access(public_order_id, guest_hash)
    except customer_delivery_access.CustomerOrderLookupNotFound:
        _record_customer_delivery_event(None, "delivery_request_denied", "server", 404, "not_found", fingerprint)
        return _customer_delivery_secure_response({"ok": False, "code": "not_found"}, 404)
    except ValueError:
        return _customer_delivery_secure_response({"ok": False, "code": "invalid_event"}, 400)
    _record_customer_delivery_event(order["internal_id"], event_type, "client", 204, safe_code, fingerprint)
    return _customer_delivery_secure_response({}, 204)


@app.route("/compras/pedidos/<public_order_id>/entrega")
def entrega_pedido_cliente(public_order_id):
    guest_hash, fingerprint = _customer_delivery_telemetry_context()
    order_id = None
    recovered = False
    try:
        access, recovered = _customer_order_access(public_order_id, guest_hash)
        order_id = access["internal_id"]
    except customer_delivery_access.CustomerOrderLookupNotFound:
        pass
    _record_customer_delivery_event(order_id, "delivery_request_started", "server", None, "started", fingerprint)
    if not _validar_csrf_customer_checkout():
        _record_customer_delivery_event(None, "delivery_request_denied", "server", 404, "not_found", fingerprint)
        return _customer_delivery_secure_response({"ok":False,"code":"not_found","message":"Pedido no encontrado."},404)
    try:
        delivery=customer_fulfillment.get_customer_delivery(
            public_order_id,guest_hash,
            authorized_order_id=order_id if recovered else None)
    except customer_fulfillment.CustomerDeliveryNotFound:
        _record_customer_delivery_event(order_id, "delivery_request_denied", "server", 404, "not_found", fingerprint)
        return _customer_delivery_secure_response({"ok":False,"code":"not_found","message":"Pedido no encontrado."},404)
    except Exception:
        _record_customer_delivery_event(order_id, "delivery_request_failed", "server", 500, "internal_error", fingerprint)
        return _customer_delivery_secure_response({"ok":False,"code":"delivery_unavailable","message":"No pudimos abrir la entrega segura."},500)
    _record_customer_delivery_event(order_id, "delivery_request_success", "server", 200, "fulfilled", fingerprint)
    return _customer_delivery_secure_response({"ok":True,"delivery":delivery})


@app.route("/admin/pedidos-clientes")
def admin_pedidos_clientes():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    filtro = request.args.get("estado", "pending")
    if filtro not in {"pending", "paid", "cancelled", "expired", "all"}:
        filtro = "pending"
    pedidos = customer_orders.list_orders_admin(filtro)
    for pedido in pedidos:
        pedido["fulfillment"] = customer_fulfillment.get_admin(pedido["internal_id"])
    return render_template("admin/pedidos_clientes.html", pedidos=pedidos, filtro=filtro)


@app.route("/admin/pedidos-clientes/<public_order_id>")
def admin_pedido_cliente_detalle(public_order_id):
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    pedido = customer_orders.get_order_admin(public_order_id)
    if pedido is None:
        return render_template("admin/pedido_cliente_detalle.html", pedido=None), 404
    return render_template("admin/pedido_cliente_detalle.html", pedido=pedido,
                           pago=customer_bold_payments.get_payment_admin(pedido["internal_id"]),
                           fulfillment=customer_fulfillment.get_admin(pedido["internal_id"]),
                           notificacion=customer_order_email.get_admin(pedido["internal_id"]))


@app.route("/admin/reglas-inventario-reseller")
def admin_reglas_inventario_reseller():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    reseller_accounts.inicializar_esquema()
    return render_template(
        "admin/reglas_inventario_reseller.html",
        reglas=reseller_accounts.listar_reglas_inventario_admin(),
        plataformas=reseller_accounts.listar_plataformas_inventario(),
        csrf_token=_csrf_revendedores_token(),
    )


@app.route("/admin/reglas-inventario-reseller/<int:plan_id>", methods=["POST"])
def guardar_regla_inventario_reseller_admin(plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or request.form
    plataformas = reseller_accounts.listar_plataformas_inventario()
    plataforma = str(datos.get("plataforma") or "").strip()
    plataforma_real = next((p for p in plataformas if p.casefold() == plataforma.casefold()), None)
    if not plataforma_real:
        return _error_revendedores("La plataforma no existe en el inventario.")
    activo = datos.get("activo") in (True, 1, "1", "true", "on", "activo")
    try:
        regla = reseller_accounts.guardar_regla_inventario_plan(
            plan_id, plataforma_real, datos.get("tipo_unidad"),
            datos.get("duracion_dias"), activo,
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except (TypeError, ValueError) as error:
        return _error_revendedores(error)
    registrar_historial(f"Regla reseller del plan #{plan_id} actualizada por {_actor_admin()}")
    return jsonify({"ok": True, "regla": regla})


@app.route("/admin/reglas-fulfillment-clientes")
def admin_reglas_fulfillment_clientes():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    customer_fulfillment_rules.initialize_schema()
    return render_template(
        "admin/reglas_fulfillment_clientes.html",
        reglas=customer_fulfillment_rules.listar_reglas_admin(),
        plataformas=customer_fulfillment_rules.listar_plataformas_inventario(),
        csrf_token=_csrf_admin_token(),
    )


@app.route("/admin/reglas-fulfillment-clientes/<int:plan_id>", methods=["POST"])
def guardar_regla_fulfillment_cliente_admin(plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_admin():
        return _error_revendedores("Token CSRF no valido.", 403)
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) != {
            "plataforma", "tipo_unidad", "duracion_dias", "activo"}:
        return _error_revendedores("Payload de regla no valido.")
    try:
        regla = customer_fulfillment_rules.guardar_regla(
            plan_id, datos["plataforma"], datos["tipo_unidad"],
            datos["duracion_dias"], datos["activo"])
    except LookupError as error:
        return _error_revendedores(error, 404)
    except (TypeError, ValueError) as error:
        return _error_revendedores(error)
    registrar_historial(f"Regla cliente del plan #{plan_id} actualizada por {_actor_admin()}")
    return jsonify({"ok": True, "regla": regla})


@app.route("/admin/reglas-fulfillment-clientes/<int:plan_id>/copiar-reseller", methods=["POST"])
def copiar_regla_reseller_a_cliente_admin(plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_admin():
        return _error_revendedores("Token CSRF no valido.", 403)
    if not request.is_json or request.get_json(silent=True) != {}:
        return _error_revendedores("La copia no acepta valores de inventario desde el navegador.")
    try:
        regla = customer_fulfillment_rules.copiar_desde_reseller(plan_id)
    except LookupError as error:
        return _error_revendedores(error, 404)
    except (TypeError, ValueError) as error:
        return _error_revendedores(error)
    registrar_historial(f"Regla reseller copiada como regla cliente inactiva para plan #{plan_id} por {_actor_admin()}")
    return jsonify({"ok": True, "regla": regla})


def _obtener_producto_por_plan(id_plan):
    """Resuelve el grupo histórico de producto desde un ID real de plan."""
    conn = conectar()
    try:
        columnas_producto = {fila[1] for fila in conn.execute("PRAGMA table_info(productos)")}
        elegibilidad_sql = (
            "p.participa_descuento_carrito"
            if "participa_descuento_carrito" in columnas_producto else "0"
        )
        descuento_bps_sql = (
            "p.descuento_carrito_bps"
            if "descuento_carrito_bps" in columnas_producto else "0"
        )
        filas = conn.execute(
            f"""
            SELECT p.id, p.nombre, p.imagen, p.plan, p.precio, p.oferta_precio,
                   oferta_activa, destacado, visible, estado, categoria,
                   orden_categoria, {elegibilidad_sql} AS participa_descuento_carrito,
                   {descuento_bps_sql} AS descuento_carrito_bps,
                   g.precio AS precio_reseller_general,
                   g.activo AS precio_reseller_activo
            FROM productos AS p
            LEFT JOIN precios_revendedor_generales AS g ON g.plan_id = p.id
            WHERE p.nombre = (
                SELECT nombre FROM productos WHERE id = ? LIMIT 1
            )
            ORDER BY p.id ASC
            """,
            (id_plan,)
        ).fetchall()
    finally:
        conn.close()

    if not filas:
        return None

    primera = filas[0]
    return {
        "nombre": primera["nombre"],
        "imagen": primera["imagen"],
        "destacado": primera["destacado"],
        "visible": primera["visible"],
        "estado": primera["estado"] or "disponible",
        "categoria": primera["categoria"] or "Streaming",
        "orden_categoria": primera["orden_categoria"],
        "planes": [
            {
                "id": fila["id"],
                "plan": fila["plan"],
                "precio": fila["precio"],
                "precio_reseller_general": fila["precio_reseller_general"] if fila["precio_reseller_activo"] else None,
                "oferta_precio": fila["oferta_precio"],
                "oferta_activa": fila["oferta_activa"],
                "destacado": fila["destacado"],
                "visible": fila["visible"]
                ,"participa_descuento_carrito": fila["participa_descuento_carrito"]
                ,"descuento_carrito_bps": fila["descuento_carrito_bps"]
            }
            for fila in filas
        ]
    }


@app.route("/admin/productos/<int:id_plan>/control")
def admin_producto_control(id_plan):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    resellers.inicializar_revendedores()
    producto = _obtener_producto_por_plan(id_plan)
    if producto is None:
        return jsonify({"ok": False, "mensaje": "Producto no encontrado"}), 404

    return render_template(
        "admin/_producto_control.html",
        producto=producto,
        categorias=obtener_categorias(),
        csrf_token=_csrf_revendedores_token()
    )


def _csrf_revendedores_token():
    token = session.get("csrf_revendedores")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_revendedores"] = token
    return token


def _validar_csrf_revendedores():
    recibido = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    esperado = session.get("csrf_revendedores", "")
    return bool(recibido and esperado and secrets.compare_digest(recibido, esperado))


def _actor_admin():
    return str(session.get("admin_usuario") or "admin")[:80]


def _error_revendedores(error, codigo=400):
    return jsonify({"ok": False, "mensaje": str(error)}), codigo


@app.route("/admin/revendedores")
def admin_revendedores():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    resellers.inicializar_revendedores()
    return render_template(
        "admin/revendedores.html",
        revendedores=resellers.listar_revendedores(),
        resumen=resellers.resumen_revendedores(),
        csrf_token=_csrf_revendedores_token()
    )


@app.route("/admin/revendedores", methods=["POST"])
def crear_revendedor_admin():
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or request.form
    try:
        revendedor_id = resellers.crear_revendedor(
            datos.get("nombre"), datos.get("correo"), datos.get("telefono"),
            datos.get("negocio"), datos.get("password"), _actor_admin()
        )
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True, "revendedor_id": revendedor_id}), 201


@app.route("/admin/revendedores/<int:revendedor_id>/control")
def admin_revendedor_control(revendedor_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    resellers.inicializar_revendedores()
    revendedor = resellers.obtener_revendedor(revendedor_id)
    if not revendedor:
        return _error_revendedores("Revendedor no encontrado", 404)
    return render_template(
        "admin/_revendedor_control.html",
        revendedor=revendedor,
        planes=resellers.obtener_planes_revendedor(revendedor_id),
        actividad=resellers.obtener_actividad_revendedor(revendedor_id),
        csrf_token=_csrf_revendedores_token()
    )


@app.route("/admin/revendedores/<int:revendedor_id>", methods=["PATCH"])
def actualizar_revendedor_admin(revendedor_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or {}
    try:
        revendedor = resellers.actualizar_revendedor(
            revendedor_id, datos.get("nombre"), datos.get("negocio"),
            datos.get("correo"), datos.get("telefono"), _actor_admin()
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True, "revendedor": revendedor})


@app.route("/admin/revendedores/<int:revendedor_id>/estado", methods=["POST"])
def estado_revendedor_admin(revendedor_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or {}
    try:
        cambiado = resellers.cambiar_estado_revendedor(
            revendedor_id, datos.get("estado", ""), _actor_admin()
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True, "cambiado": cambiado})


@app.route("/admin/revendedores/<int:revendedor_id>/password", methods=["POST"])
def password_revendedor_admin(revendedor_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or {}
    try:
        resellers.cambiar_password_revendedor(
            revendedor_id, datos.get("password"), _actor_admin()
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True})


@app.route("/admin/revendedores/precios/generales/<int:plan_id>", methods=["PUT"])
def precio_general_revendedor_admin(plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or {}
    try:
        resellers.guardar_precio_general(plan_id, datos.get("precio"), _actor_admin())
    except (TypeError, ValueError):
        return _error_revendedores("El precio reseller general no es válido.")
    except LookupError as error:
        return _error_revendedores(error, 404)
    return jsonify({"ok": True})


@app.route("/admin/revendedores/<int:revendedor_id>/precios/<int:plan_id>", methods=["PUT", "DELETE"])
def precio_personalizado_revendedor_admin(revendedor_id, plan_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    try:
        if request.method == "DELETE":
            eliminado = resellers.restaurar_precio_general(
                revendedor_id, plan_id, _actor_admin()
            )
            return jsonify({"ok": True, "eliminado": eliminado})
        datos = request.get_json(silent=True) or {}
        resellers.guardar_precio_personalizado(
            revendedor_id, plan_id, datos.get("precio"),
            datos.get("oferta_activa") is True, datos.get("oferta_precio"),
            datos.get("oferta_inicio"), datos.get("oferta_fin"), _actor_admin()
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except (TypeError, ValueError) as error:
        return _error_revendedores(error)
    return jsonify({"ok": True})


@app.route("/admin/saldos")
def admin_saldos():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    resellers.inicializar_revendedores()
    resumen = wallets.resumen_saldos()
    return render_template(
        "admin/saldos.html",
        saldos=wallets.listar_saldos(),
        resumen=resumen,
        formato_cop=wallets.formato_cop,
        csrf_token=_csrf_revendedores_token()
    )


@app.route("/admin/saldos/<int:revendedor_id>/control")
def admin_saldo_control(revendedor_id):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    resellers.inicializar_revendedores()
    try:
        revendedor, wallet, movimientos = wallets.obtener_control_saldo(revendedor_id)
    except LookupError as error:
        return _error_revendedores(error, 404)
    return render_template(
        "admin/_saldo_control.html", revendedor=revendedor, wallet=wallet,
        movimientos=movimientos, formato_cop=wallets.formato_cop
    )


def _movimiento_manual_admin(revendedor_id, tipo):
    if not session.get("admin"):
        return _error_revendedores("No autorizado", 401)
    if not _validar_csrf_revendedores():
        return _error_revendedores("Token CSRF no válido.", 403)
    datos = request.get_json(silent=True) or {}
    try:
        movimiento = wallets.apply_wallet_transaction(
            revendedor_id, tipo, datos.get("monto"), datos.get("motivo"),
            origen="admin_manual", actor=_actor_admin()
        )
    except LookupError as error:
        return _error_revendedores(error, 404)
    except ValueError as error:
        return _error_revendedores(error)
    return jsonify({"ok": True, "movimiento": movimiento})


@app.route("/admin/saldos/<int:revendedor_id>/credito", methods=["POST"])
def admin_saldo_credito(revendedor_id):
    return _movimiento_manual_admin(revendedor_id, "manual_credit")


@app.route("/admin/saldos/<int:revendedor_id>/debito", methods=["POST"])
def admin_saldo_debito(revendedor_id):
    return _movimiento_manual_admin(revendedor_id, "manual_debit")

@app.route("/admin/configuracion")
def admin_configuracion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    config = obtener_config()
    centro = estado_configuracion(_tenant_configuracion())

    return render_template(
        "admin/configuracion.html",
        config=config,
        centro_configuracion=centro
    )


def _usuario_configuracion():
    return str(session.get("admin_usuario") or "admin")[:80]


def _tenant_configuracion():
    tenant = str(session.get("tenant_id") or "default")[:80]
    return tenant if re.fullmatch(r"[A-Za-z0-9_-]+", tenant) else "default"


@app.route("/admin/configuracion/api", methods=["GET"])
def configuracion_api_estado():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    return jsonify({"ok": True, **estado_configuracion(_tenant_configuracion())})


@app.route("/admin/configuracion/api/<modulo>", methods=["GET", "PATCH"])
def configuracion_api_modulo(modulo):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    if modulo not in MODULOS_CONFIGURACION:
        return jsonify({"ok": False, "mensaje": "Módulo desconocido."}), 404
    try:
        if request.method == "PATCH":
            datos = (request.get_json(silent=True) or {}).get("datos", {})
            resultado = guardar_borrador_configuracion(modulo, datos, tenant=_tenant_configuracion(), usuario=_usuario_configuracion())
        else:
            resultado = obtener_modulo_configuracion(modulo, _tenant_configuracion())
        return jsonify({"ok": True, **resultado})
    except ValueError as error:
        return jsonify({"ok": False, "mensaje": str(error)}), 400


@app.route("/admin/configuracion/api/<modulo>/restaurar", methods=["POST"])
def configuracion_api_restaurar_modulo(modulo):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    if modulo not in MODULOS_CONFIGURACION:
        return jsonify({"ok": False, "mensaje": "Módulo desconocido."}), 404
    resultado = restaurar_modulo_configuracion(modulo, tenant=_tenant_configuracion(), usuario=_usuario_configuracion())
    return jsonify({"ok": True, **resultado})


@app.route("/admin/configuracion/api/restaurar-todo", methods=["POST"])
def configuracion_api_restaurar_todo():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    confirmacion = (request.get_json(silent=True) or {}).get("confirmacion")
    if confirmacion != "RESTAURAR TODO":
        return jsonify({"ok": False, "mensaje": "Confirmación inválida."}), 400
    restaurar_todo_configuracion(tenant=_tenant_configuracion(), usuario=_usuario_configuracion())
    return jsonify({"ok": True, **estado_configuracion(_tenant_configuracion())})


@app.route("/admin/configuracion/api/publicar", methods=["POST"])
def configuracion_api_publicar():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    publicar_configuracion(tenant=_tenant_configuracion(), usuario=_usuario_configuracion())
    return jsonify({"ok": True, **estado_configuracion(_tenant_configuracion())})


@app.route("/admin/configuracion/api/auditoria", methods=["GET"])
def configuracion_api_auditoria():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    return jsonify({"ok": True, "eventos": auditoria_configuracion(tenant=_tenant_configuracion(),
        modulo=request.args.get("modulo", ""), accion=request.args.get("accion", "")
    )})


@app.route("/admin/configuracion/preview")
def configuracion_preview():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template("admin/configuracion_preview.html", config=configuracion_efectiva(tenant=_tenant_configuracion(), borrador=True))


@app.route("/admin/configuracion/api/upload", methods=["POST"])
def configuracion_api_upload():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        return jsonify({"ok": False, "mensaje": "Selecciona una imagen."}), 400
    if request.content_length and request.content_length > 3 * 1024 * 1024:
        return jsonify({"ok": False, "mensaje": "La imagen supera 3 MB."}), 413
    try:
        imagen = Image.open(archivo.stream); imagen.verify()
        formato = (imagen.format or "").upper()
    except Exception:
        return jsonify({"ok": False, "mensaje": "El archivo no es una imagen válida."}), 400
    extensiones = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "ICO": ".ico"}
    if formato not in extensiones:
        return jsonify({"ok": False, "mensaje": "Formato no permitido."}), 400
    archivo.stream.seek(0); imagen = Image.open(archivo.stream)
    if imagen.width > 4000 or imagen.height > 4000:
        return jsonify({"ok": False, "mensaje": "Dimensiones máximas: 4000 × 4000."}), 400
    import secrets
    tenant = _tenant_configuracion()
    carpeta = os.path.join(app.static_folder, "uploads", "configuracion", tenant)
    os.makedirs(carpeta, exist_ok=True)
    nombre = secrets.token_hex(16) + extensiones[formato]
    imagen.save(os.path.join(carpeta, nombre), formato=formato)
    return jsonify({"ok": True, "url": f"/static/uploads/configuracion/{tenant}/{nombre}"})



@app.route("/admin/nube-cuentas")
def admin_nube_cuentas():

    if not session.get("admin"):

        return redirect(
            "/pechy-panel-seguro"
        )


    cuentas = obtener_cuentas_nube(
        limite=1000,
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
        tipos_cuenta=tipos_cuenta,
        politicas_duracion_inventario=reseller_accounts.listar_politicas_duracion_inventario(),
        csrf_token=_csrf_admin_token()
    )


@app.route("/admin/nube-cuentas/plataformas/renombrar", methods=["POST"])
def renombrar_plataforma_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    if not _validar_csrf_admin():
        return jsonify({"ok": False, "mensaje": "Solicitud de seguridad invÃ¡lida."}), 403
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) != {"nombre_actual", "nombre_nuevo"}:
        return jsonify({"ok": False, "mensaje": "La solicitud contiene datos no permitidos."}), 400
    try:
        resultado = database.renombrar_plataforma_nube(
            datos.get("nombre_actual"), datos.get("nombre_nuevo")
        )
    except database.RenombrarPlataformaNubeError as error:
        estado = 404 if error.codigo == "plataforma_no_encontrada" else (
            409 if error.codigo in {
                "plataforma_existente", "referencia_desconocida", "esquema_incompleto"
            } else 400
        )
        return jsonify({"ok": False, "codigo": error.codigo, "mensaje": str(error)}), estado
    except (sqlite3.IntegrityError, RuntimeError):
        app.logger.exception("Renombre de plataforma Nube bloqueado de forma segura")
        return jsonify({
            "ok": False,
            "codigo": "conflicto_integridad",
            "mensaje": "No se pudo renombrar la plataforma sin comprometer sus referencias.",
        }), 409
    return jsonify(resultado)


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

    duracion_unidad_dias = request.form.get("duracion_unidad_dias", "").strip()


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

    try:
        duracion_unidad_dias = database.validar_duracion_unidad_inventario(
            plataforma, modalidad, duracion_unidad_dias
        )
    except ValueError as error:
        flash(str(error))
        return redirect("/admin/nube-cuentas")

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
        ,duracion_unidad_dias=duracion_unidad_dias
    )


    flash(
        "Cuenta agregada a la Nube correctamente ☁️"
    )


    return redirect(
        "/admin/nube-cuentas"
    )


@app.route("/admin/nube-cuentas/alertas", methods=["GET"])
def obtener_alertas_operativas_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    resultado = obtener_alertas_operativas_nube()
    return jsonify({"ok": True, **resultado})


@app.route("/admin/nube-alertas")
def admin_nube_alertas():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template("admin/nube_alertas.html")


@app.route("/admin/nube-notificaciones")
def admin_nube_notificaciones():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template("admin/nube_notificaciones.html")


@app.route("/admin/nube-notificaciones/datos", methods=["GET"])
def datos_nube_notificaciones_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    return jsonify({
        "ok": True,
        **database.obtener_centro_notificaciones_renovacion_nube()
    })


@app.route("/admin/nube-notificaciones/notificar", methods=["POST"])
def marcar_nube_notificacion_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    resultado = database.marcar_notificacion_renovacion_nube(
        datos.get("servicios") or [],
        datos.get("mensaje", ""),
        datos.get("medio", "manual")
    )
    return jsonify(resultado), (200 if resultado.get("ok") else 409)


@app.route("/admin/nube-cortes")
def admin_nube_cortes():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template("admin/nube_cortes.html", csrf_token=_csrf_admin_token())


@app.route("/admin/nube-cortes/datos", methods=["GET"])
def datos_nube_cortes_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    return jsonify({"ok": True, **database.obtener_cortes_nube()})


@app.route("/admin/nube-cortes/cortar", methods=["POST"])
def cortar_nube_cortes_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    if not _validar_csrf_admin():
        return jsonify({"ok": False, "mensaje": "Solicitud de seguridad inválida."}), 403
    datos = request.get_json(silent=True) or {}
    resultado = database.cortar_servicios_nube(
        datos.get("servicios") or [],
        datos.get("motivo", ""),
        actor_id=session.get("admin_id")
    )
    return jsonify(resultado), (200 if resultado.get("ok") else 409)


@app.route("/admin/nube-cortes/cuenta/credenciales", methods=["POST"])
def actualizar_credenciales_nube_cortes_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    resultado = database.actualizar_credenciales_cuenta_corte_nube(
        datos.get("cuenta_id"),
        datos.get("correo"),
        datos.get("contrasena"),
        datos.get("pin")
    )
    return jsonify(resultado), (200 if resultado.get("ok") else 400)


@app.route("/admin/nube-cortes/perfil/pin", methods=["POST"])
def actualizar_pin_perfil_nube_cortes_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    resultado = database.actualizar_pin_perfil_corte_nube(
        datos.get("cuenta_id"),
        datos.get("perfil_id"),
        datos.get("pin")
    )
    return jsonify(resultado), (200 if resultado.get("ok") else 400)


@app.route("/admin/nube-papelera")
def admin_nube_papelera():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template("admin/nube_papelera.html")


@app.route("/admin/nube-papelera/cuentas", methods=["GET"])
def listar_nube_papelera_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    respuesta = jsonify({"ok": True, "cuentas": obtener_cuentas_papelera_nube()})
    respuesta.headers["Cache-Control"] = "no-store, max-age=0"
    return respuesta


@app.route("/admin/nube-papelera/<int:cuenta_id>", methods=["GET"])
def detalle_nube_papelera_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    detalle = obtener_detalle_papelera_nube(cuenta_id)
    if not detalle:
        return jsonify({"ok": False, "mensaje": "Cuenta archivada no encontrada"}), 404
    return jsonify({"ok": True, **detalle})


@app.route("/admin/nube-cuentas/<int:cuenta_id>/papelera", methods=["POST"])
def mover_nube_papelera_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    resultado = mover_cuenta_papelera_nube(cuenta_id, (request.get_json(silent=True) or {}).get("motivo", ""))
    return jsonify(resultado), (200 if resultado.get("ok") else 409)


@app.route("/admin/nube-papelera/<int:cuenta_id>/restaurar", methods=["POST"])
def restaurar_nube_papelera_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    resultado = restaurar_cuenta_papelera_nube(cuenta_id)
    return jsonify(resultado), (200 if resultado.get("ok") else 409)


@app.route("/admin/nube-cuentas/alertas/detalle", methods=["GET"])
def obtener_detalle_alerta_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    try:
        cuenta_id = int(request.args.get("cuenta_id", ""))
        perfil_raw = request.args.get("perfil_id", "").strip()
        perfil_id = int(perfil_raw) if perfil_raw else None
    except ValueError:
        return jsonify({"ok": False, "mensaje": "Identificador inválido"}), 400
    detalle = obtener_detalle_alerta_nube(cuenta_id, perfil_id)
    if not detalle:
        return jsonify({"ok": False, "mensaje": "Cuenta no encontrada"}), 404
    return jsonify({"ok": True, **detalle})


@app.route("/admin/nube-cuentas/<int:cuenta_id>/drawer", methods=["GET"])
def obtener_detalle_drawer_nube_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    detalle = obtener_detalle_drawer_cuenta_nube(cuenta_id)
    if not detalle:
        return jsonify({"ok": False, "mensaje": "Cuenta no encontrada"}), 404
    return jsonify({"ok": True, **detalle})


@app.route("/admin/nube-cuentas/<int:cuenta_id>/resumen", methods=["GET"])
def obtener_resumen_cuenta_nube_route(cuenta_id):
    """Devuelve solamente las filas renderizadas de una cuenta y sus perfiles."""
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    cuentas = obtener_cuentas_nube(limite=1, offset=0, cuenta_id=cuenta_id)
    if not cuentas:
        return jsonify({"ok": False, "mensaje": "Cuenta no encontrada"}), 404
    pagina = render_template(
        "admin/nube_cuentas.html",
        cuentas=cuentas,
        estadisticas=defaultdict(int),
        plataformas=[],
        tipos_cuenta=[]
    )
    cuerpo = re.search(r"<tbody>(.*?)</tbody>", pagina, flags=re.DOTALL)
    if not cuerpo:
        return jsonify({"ok": False, "mensaje": "No se pudo renderizar la cuenta"}), 500
    return jsonify({"ok": True, "cuenta_id": cuenta_id, "html": cuerpo.group(1).strip()})


@app.route("/admin/nube-cuentas/<int:cuenta_id>/notas", methods=["POST"])
def actualizar_notas_cuenta_nube_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    resultado = actualizar_notas_cuenta_nube(cuenta_id, datos.get("notas", ""))
    return jsonify(resultado), (200 if resultado.get("ok") else 404)


@app.route("/admin/nube-cuentas/<int:cuenta_id>/edicion", methods=["GET"])
def contexto_edicion_cuenta_nube_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    contexto = database.obtener_contexto_edicion_cuenta_nube(cuenta_id)
    if not contexto:
        return jsonify({"ok": False, "mensaje": "Cuenta no encontrada"}), 404
    return jsonify({"ok": True, **contexto})


@app.route("/admin/nube-cuentas/<int:cuenta_id>/edicion", methods=["POST"])
def guardar_edicion_cuenta_nube_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    if not _validar_csrf_admin():
        return jsonify({"ok": False, "mensaje": "Solicitud de seguridad inválida."}), 403
    datos = request.get_json(silent=True)
    permitidos = {"plataforma", "correo", "contrasena", "pin", "modalidad",
                  "duracion_unidad_dias", "cantidad_perfiles", "confirmar_cambio_modalidad"}
    if not isinstance(datos, dict) or set(datos) - permitidos:
        return jsonify({"ok": False, "mensaje": "La solicitud contiene datos no permitidos."}), 400
    try:
        resultado = database.actualizar_cuenta_nube_admin(
            cuenta_id, datos, bool(datos.get("confirmar_cambio_modalidad"))
        )
    except (sqlite3.IntegrityError, RuntimeError):
        app.logger.exception("Edición de cuenta Nube bloqueada de forma segura")
        return jsonify({"ok": False, "codigo": "conflicto_integridad",
                        "mensaje": "La cuenta cambió o tiene relaciones que impiden esta edición."}), 409
    if resultado.get("ok"):
        return jsonify(resultado)
    estado = 404 if resultado.get("codigo") == "no_encontrada" else (
        409 if resultado.get("codigo") in {"historial_comercial", "confirmacion_requerida", "perfiles_con_actividad"} else 400
    )
    return jsonify(resultado), estado


@app.route("/admin/nube-cuentas/<int:cuenta_id>/eliminar", methods=["POST"])
def eliminar_cuenta_nube_route(cuenta_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    if not _validar_csrf_admin():
        return jsonify({"ok": False, "mensaje": "Solicitud de seguridad inválida."}), 403
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or set(datos) - {"confirmacion"}:
        return jsonify({"ok": False, "mensaje": "La solicitud contiene datos no permitidos."}), 400
    try:
        resultado = database.eliminar_cuenta_nube_descartable(cuenta_id, datos.get("confirmacion") is True)
    except (sqlite3.IntegrityError, RuntimeError):
        app.logger.exception("Eliminación de cuenta Nube bloqueada de forma segura")
        return jsonify({"ok": False, "codigo": "conflicto_integridad",
                        "mensaje": "La cuenta cambió o conserva referencias que impiden eliminarla."}), 409
    if resultado.get("ok"):
        return jsonify(resultado)
    if resultado.get("codigo") == "no_encontrada":
        return jsonify(resultado), 404
    return jsonify(resultado), 409


@app.route("/admin/nube-cuentas/pagos-pin", methods=["POST"])
def registrar_pago_pin_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    try:
        resultado = registrar_pago_pin_nube(
            datos.get("cuenta_id"), datos.get("valor_pin"), datos.get("plan"),
            datos.get("precio_plan_referencia"), datos.get("fecha_aplicacion"),
            datos.get("notas", "")
        )
    except ValueError as error:
        return jsonify({"ok": False, "mensaje": str(error)}), 400
    except sqlite3.Error:
        return jsonify({"ok": False, "mensaje": "No se pudo registrar el pago."}), 500
    return jsonify({
        "ok": True,
        "pago_registrado": not resultado.get("duplicado", False),
        "cuenta_restaurada": resultado.get("cuenta_restaurada", False),
        "estado": "disponible" if (
            resultado.get("cuenta_restaurada") or resultado.get("cuenta_reactivada")
        ) else None,
        "pago": resultado
    })


@app.route("/admin/nube-cuentas/asignar-cuenta", methods=["POST"])
def asignar_cuenta_completa_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    datos = request.get_json(silent=True) or {}
    try:
        resultado = asignar_cuenta_completa_nube(
            cuenta_id=datos.get("cuenta_id"),
            nombre_cliente=datos.get("nombre_cliente", ""),
            telefono=datos.get("telefono", ""),
            fecha_entrega=datos.get("fecha_entrega", ""),
            dias_cuenta=datos.get("dias_cuenta", 0),
            notas=datos.get("notas", "")
        )
    except sqlite3.Error:
        return jsonify({"ok": False, "mensaje": "No se pudo asignar la cuenta."}), 500

    return jsonify(resultado), (200 if resultado.get("ok") else 409)


@app.route("/admin/nube-cuentas/carga-rapida", methods=["POST"])
def carga_rapida_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    datos = request.get_json(silent=True) or {}
    credenciales = datos.get("credenciales") or []
    if not isinstance(credenciales, list):
        return jsonify({"ok": False, "mensaje": "Credenciales inválidas."}), 400

    try:
        resultado = crear_cuentas_nube_lote(
            plataforma=datos.get("plataforma", ""),
            modalidad=datos.get("modalidad", "cuenta_completa"),
            tipo_pago=datos.get("tipo_pago", ""),
            plan_pago=datos.get("plan_pago", ""),
            cantidad_perfiles=datos.get("cantidad_perfiles", 0),
            credenciales=credenciales,
            valor_pin=int(re.sub(r"\D", "", str(datos.get("valor_pin", "0"))) or 0),
            precio_plan_referencia=int(re.sub(r"\D", "", str(datos.get("precio_plan_referencia", "0"))) or 0),
            fecha_aplicacion_pin=datos.get("fecha_aplicacion_pin", "")
            ,duracion_unidad_dias=datos.get("duracion_unidad_dias")
        )
    except sqlite3.Error:
        return jsonify({"ok": False, "mensaje": "No se pudo completar la carga rápida."}), 500

    return jsonify(resultado), (200 if resultado.get("ok") else 409)


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
    "/admin/nube-cuentas/perfil/<int:perfil_id>/historial",
    methods=["GET"]
)
def obtener_historial_completo_perfil_nube_route(perfil_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401

    historial = obtener_historial_completo_perfil_nube(perfil_id)
    if not historial:
        return jsonify({
            "ok": False,
            "mensaje": "No se encontró el perfil."
        }), 404

    return jsonify({"ok": True, **historial})


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


@app.route("/admin/nube-cuentas/perfil/no-renovo", methods=["POST"])
def registrar_no_renovacion_perfil_nube_route():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado"}), 401
    datos = request.get_json(silent=True) or {}
    resultado = registrar_no_renovacion_perfil_nube(
        datos.get("perfil_id"), datos.get("operacion_uuid", "")
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
    categorias_cartelera = obtener_categorias_cartelera(solo_activas=True)
    categorias_ids = {
        categoria["id"]
        for categoria in categorias_cartelera
    }
    for pelicula in peliculas:
        categoria_id_actual = pelicula.get("categoria_id")
        if not categoria_id_actual or categoria_id_actual in categorias_ids:
            continue
        categoria_actual = obtener_categoria_cartelera_por_id(
            categoria_id_actual
        )
        if categoria_actual:
            categorias_cartelera.append(categoria_actual)
            categorias_ids.add(categoria_id_actual)
    categorias_cartelera.sort(
        key=lambda categoria: (categoria["orden"], categoria["id"])
    )
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
        plataformas=plataformas,
        categorias_cartelera=categorias_cartelera
    )


@app.route("/admin/cartelera/categorias")
def admin_cartelera_categorias():
    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    return render_template(
        "admin/cartelera_categorias.html",
        categorias_cartelera=database.obtener_categorias_cartelera_con_conteo(),
    )


def _error_categoria_cartelera(error):
    if isinstance(error, LookupError):
        return jsonify({"ok": False, "mensaje": str(error)}), 404
    if isinstance(error, RuntimeError):
        return jsonify({"ok": False, "mensaje": str(error)}), 409
    if isinstance(error, (ValueError, sqlite3.IntegrityError)):
        mensaje = str(error) if isinstance(error, ValueError) else (
            "Ya existe una categoría con la misma clave canónica."
        )
        return jsonify({"ok": False, "mensaje": mensaje}), 400
    return jsonify({"ok": False, "mensaje": "No se pudo completar la operación."}), 500


@app.route("/admin/cartelera/categorias", methods=["POST"])
def crear_categoria_cartelera_admin():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    datos = request.get_json(silent=True) or {}
    try:
        categoria = database.crear_categoria_cartelera(datos.get("nombre"))
        return jsonify({"ok": True, "categoria": categoria}), 201
    except Exception as error:
        return _error_categoria_cartelera(error)


@app.route("/admin/cartelera/categorias/<int:categoria_id>", methods=["PATCH"])
def renombrar_categoria_cartelera_admin(categoria_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    datos = request.get_json(silent=True) or {}
    try:
        categoria = database.renombrar_categoria_cartelera(
            categoria_id, datos.get("nombre")
        )
        return jsonify({"ok": True, "categoria": categoria})
    except Exception as error:
        return _error_categoria_cartelera(error)


@app.route(
    "/admin/cartelera/categorias/<int:categoria_id>/estado",
    methods=["PATCH"],
)
def estado_categoria_cartelera_admin(categoria_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    datos = request.get_json(silent=True) or {}
    try:
        categoria = database.establecer_categoria_cartelera_activa(
            categoria_id, datos.get("activa")
        )
        return jsonify({"ok": True, "categoria": categoria})
    except Exception as error:
        return _error_categoria_cartelera(error)


@app.route("/admin/cartelera/categorias/orden", methods=["PUT"])
def ordenar_categorias_cartelera_admin():
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    datos = request.get_json(silent=True) or {}
    try:
        database.reordenar_categorias_cartelera(datos.get("orden"))
        return jsonify({"ok": True, "mensaje": "Orden guardado."})
    except Exception as error:
        return _error_categoria_cartelera(error)


@app.route(
    "/admin/cartelera/categorias/<int:categoria_id>",
    methods=["DELETE"],
)
def eliminar_categoria_cartelera_admin(categoria_id):
    if not session.get("admin"):
        return jsonify({"ok": False, "mensaje": "No autorizado."}), 401
    try:
        nombre = database.eliminar_categoria_cartelera_si_vacia(categoria_id)
        return jsonify({"ok": True, "mensaje": f"Categoría {nombre} eliminada."})
    except Exception as error:
        return _error_categoria_cartelera(error)

@app.route("/admin/cartelera/guardar", methods=["POST"])
def guardar_cartelera():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")

    tipo = request.form.get("tipo", "").strip()
    titulo = request.form.get("titulo", "").strip()
    genero = request.form.get("genero", "").strip()
    categoria_id_recibida = request.form.get("categoria_id", "").strip()
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

    try:
        categoria_id = int(categoria_id_recibida)
    except (TypeError, ValueError):
        flash("Selecciona una categoría válida ❌")
        return redirect("/admin/cartelera")

    categoria_seleccionada = obtener_categoria_cartelera_por_id(categoria_id)
    if not categoria_seleccionada:
        flash("La categoría seleccionada no existe ❌")
        return redirect("/admin/cartelera")

    if not categoria_seleccionada["activa"]:
        if not pelicula_id:
            flash("La categoría seleccionada está inactiva ❌")
            return redirect("/admin/cartelera")

        conexion_validacion = conectar()
        pelicula_validacion = conexion_validacion.execute(
            "SELECT categoria_id FROM cartelera WHERE id = ?",
            (pelicula_id,)
        ).fetchone()
        conexion_validacion.close()

        if (
            not pelicula_validacion
            or pelicula_validacion["categoria_id"] != categoria_id
        ):
            flash("La categoría seleccionada está inactiva ❌")
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

        print("CATEGORIA:", categoria_seleccionada["nombre"])

        if pelicula_id:

            cursor.execute(
                """
                SELECT poster, banner, categoria_id
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
            categoria_id_actual = pelicula_actual[2]

            if (
                not categoria_seleccionada["activa"]
                and categoria_id != categoria_id_actual
            ):
                raise ValueError(
                    "La categoría seleccionada está inactiva."
                )

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
                    categoria_id = ?,
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
                    categoria_seleccionada["nombre"],
                    categoria_id,
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

            if not categoria_seleccionada["activa"]:
                raise ValueError(
                    "La categoría seleccionada está inactiva."
                )

            cursor.execute(
                """
                INSERT INTO cartelera (
                    tipo,
                    titulo,
                    genero,
                    categoria,
                    categoria_id,
                    descripcion,
                    anio,
                    url,
                    poster,
                    banner,
                    tendencia,
                    destacado,
                    publicado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tipo,
                    titulo,
                    genero,
                    categoria_seleccionada["nombre"],
                    categoria_id,
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

    resellers.inicializar_revendedores()

    solicita_precio_reseller = any(
        str(request.form.get(campo, "")).strip()
        for campo in ("precio_reseller_cuenta_completa", "precio_reseller_perfil")
    )
    if solicita_precio_reseller and not _validar_csrf_revendedores():
        flash("Token CSRF no valido ❌")
        return redirect("/admin/productos#productos")

    nombre = request.form.get("nombre", "").strip()
    categoria = request.form.get("categoria", "").strip()
    if not categoria:
        categoria = "Sin categoría"

    # Se conserva el contrato heredado (plan/precio) y se amplía para la
    # creación inicial de los dos planes que ya modela la tabla productos.
    planes = []
    if "plan" in request.form or "precio" in request.form:
        plan = request.form.get("plan", "").strip()
        precio = request.form.get("precio", "").strip()
        if plan and precio:
            planes.append((plan, precio, None))
    else:
        if request.form.get("cuenta_completa_activa") == "on":
            planes.append(("Cuenta completa", request.form.get("precio_cuenta_completa", "").strip(), request.form.get("precio_reseller_cuenta_completa", "").strip()))
        if request.form.get("perfil_activo") == "on":
            planes.append(("Perfil", request.form.get("precio_perfil", "").strip(), request.form.get("precio_reseller_perfil", "").strip()))

    categorias_validas = {item["nombre"] for item in obtener_categorias()}
    categorias_validas.add("Sin categoría")
    precios_validos = all(precio and re.search(r"\d", precio) for _, precio, _ in planes)
    try:
        planes = [
            (plan, precio, int(re.sub(r"\D", "", precio_reseller)) if precio_reseller else None)
            for plan, precio, precio_reseller in planes
        ]
        if any(precio_reseller is not None and precio_reseller <= 0 for _, _, precio_reseller in planes):
            raise ValueError
    except (TypeError, ValueError):
        flash("El precio reseller general no es valido ❌")
        return redirect("/admin/productos#productos")
    imagen_file = request.files.get("imagen")

    if not nombre or len(nombre) > 120:
        flash("Escribe un nombre de producto válido ❌")
        return redirect("/admin/productos#productos")
    if categoria not in categorias_validas:
        flash("Categoría no válida ❌")
        return redirect("/admin/productos#productos")
    if not planes or not precios_validos:
        flash("Activa al menos un plan con un precio válido ❌")
        return redirect("/admin/productos#productos")
    if not imagen_file or not imagen_file.filename:
        flash("Selecciona una imagen válida ❌")
        return redirect("/admin/productos#productos")
    try:
        formato_imagen = (Image.open(imagen_file.stream).format or "").upper()
        imagen_file.stream.seek(0)
    except Exception:
        formato_imagen = ""
    if formato_imagen not in {"JPEG", "PNG", "WEBP"}:
        flash("La imagen no es válida. Usa JPG, PNG o WEBP ❌")
        return redirect("/admin/productos#productos")

    conn = conectar()
    try:
        cursor = conn.cursor()
        if cursor.execute("SELECT 1 FROM productos WHERE lower(trim(nombre)) = lower(?) LIMIT 1", (nombre,)).fetchone():
            flash("Ya existe un producto con ese nombre ❌")
            return redirect("/admin/productos#productos")
        try:
            filename = guardar_imagen_optimizada(imagen_file)
        except Exception:
            flash("La imagen no es válida. Usa JPG, PNG o WEBP ❌")
            return redirect("/admin/productos#productos")
        for plan, precio, precio_reseller in planes:
            cursor.execute("""
                INSERT INTO productos (nombre, imagen, plan, precio, categoria)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, filename, plan, precio, categoria))
            if precio_reseller is not None:
                resellers.guardar_precio_general_en_cursor(
                    cursor, cursor.lastrowid, precio_reseller, _actor_admin()
                )
        conn.commit()
    except Exception:
        conn.rollback()
        flash("No se pudo crear el producto ❌")
        return redirect("/admin/productos#productos")
    finally:
        conn.close()
    
    flash("Producto y planes creados correctamente ✅")

    return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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
        return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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
        return redirect("/admin/productos#productos")

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

    return redirect("/admin/productos#productos")

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
    return redirect("/admin/productos#productos")

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
    if request.content_length and request.content_length > 16 * 1024 * 1024:
        flash("Las imágenes de la promoción superan el tamaño máximo permitido.")
        return redirect("/admin/promociones")

    imagen_file = request.files.get("imagen")
    imagen_desktop_file = request.files.get("imagen_desktop")
    activa = 1 if request.form.get("activa") == "on" else 0

    if not imagen_file or not imagen_file.filename:
        flash("Selecciona una imagen móvil para crear la promoción.")
        return redirect("/admin/promociones")

    filename = None
    filename_desktop = None
    try:
        filename = guardar_imagen_promocion(imagen_file)
        filename_desktop = guardar_imagen_promocion(imagen_desktop_file)
    except ValueError as error:
        eliminar_imagen_promocion_si_huerfana(filename)
        eliminar_imagen_promocion_si_huerfana(filename_desktop)
        flash(str(error))
        return redirect("/admin/promociones")

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO promociones (imagen, imagen_desktop, activa)
        VALUES (?, ?, ?)
    """, (filename, filename_desktop, activa))

    conn.commit()
    conn.close()

    flash("Promoción agregada correctamente 🔥")
    return redirect("/admin/promociones")

@app.route("/actualizar-promocion", methods=["POST"])
def actualizar_promocion():

    if not session.get("admin"):
        return redirect("/pechy-panel-seguro")
    if request.content_length and request.content_length > 16 * 1024 * 1024:
        flash("Las imágenes de la promoción superan el tamaño máximo permitido.")
        return redirect("/admin/promociones")

    promo_id = request.form.get("id")

    if not promo_id:
        flash("No se recibió la promoción seleccionada.")
        return redirect("/admin/promociones")

    activa = 1 if request.form.get("activa") == "on" else 0

    imagen_file = request.files.get("imagen")
    imagen_desktop_file = request.files.get("imagen_desktop")
    eliminar_imagen = request.form.get("eliminar_imagen") == "1"
    eliminar_imagen_desktop = request.form.get("eliminar_imagen_desktop") == "1"

    conn = conectar()
    cursor = conn.cursor()

    fila_anterior = cursor.execute(
        "SELECT imagen, imagen_desktop FROM promociones WHERE id = ?",
        (promo_id,)
    ).fetchone()
    if not fila_anterior:
        conn.close()
        flash("La promoción seleccionada ya no existe.")
        return redirect("/admin/promociones")

    filename = fila_anterior[0]
    filename_desktop = fila_anterior[1]
    try:
        filename = (
            guardar_imagen_promocion(imagen_file)
            if imagen_file and imagen_file.filename
            else "" if eliminar_imagen
            else fila_anterior[0]
        )
        filename_desktop = (
            guardar_imagen_promocion(imagen_desktop_file)
            if imagen_desktop_file and imagen_desktop_file.filename
            else None if eliminar_imagen_desktop
            else fila_anterior[1]
        )
    except ValueError as error:
        conn.close()
        if filename != fila_anterior[0]:
            eliminar_imagen_promocion_si_huerfana(filename)
        if filename_desktop != fila_anterior[1]:
            eliminar_imagen_promocion_si_huerfana(filename_desktop)
        flash(str(error))
        return redirect("/admin/promociones")

    cursor.execute("""
        UPDATE promociones
        SET imagen = ?, imagen_desktop = ?, activa = ?
        WHERE id = ?
    """, (filename, filename_desktop, activa, promo_id))

    conn.commit()
    conn.close()

    if filename != fila_anterior[0]:
        eliminar_imagen_promocion_si_huerfana(fila_anterior[0])
    if filename_desktop != fila_anterior[1]:
        eliminar_imagen_promocion_si_huerfana(fila_anterior[1])

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
        "SELECT imagen, imagen_desktop FROM promociones WHERE id = ?",
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
        eliminar_imagen_promocion_si_huerfana(fila[0])
        eliminar_imagen_promocion_si_huerfana(fila[1])

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
    app.run(host="0.0.0.0", port=5000, debug=True)
