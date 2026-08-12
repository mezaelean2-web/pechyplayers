"""Configuración seccionada, versionada y preparada para múltiples negocios."""
import json
import re
from copy import deepcopy
from datetime import datetime

import database

TENANT_PREDETERMINADO = "default"

MODULOS = {
    "identidad": {
        "titulo": "Identidad del negocio", "icono": "shield-check",
        "campos": {
            "nombre_negocio": ("text", "PECHY PLAYERS", 80), "nombre_corto": ("text", "PECHY", 24),
            "eslogan": ("text", "Vive el cine a otro nivel", 120),
            "descripcion_corta": ("text", "Entretenimiento premium a tu alcance.", 180),
            "descripcion_negocio": ("textarea", "Entretenimiento, streaming y servicios digitales en un solo lugar.", 500),
            "copyright": ("text", "© PECHY PLAYERS", 120),
            "texto_footer": ("textarea", "PECHY PLAYERS - Todos los derechos reservados.", 300),
            "logo_url": ("asset", "", 240), "favicon_url": ("asset", "", 240),
        },
    },
    "apariencia": {
        "titulo": "Colores y apariencia", "icono": "palette",
        "campos": {
            "brand_primary": ("color", "#e50914", 7), "brand_secondary": ("color", "#18191d", 7),
            "brand_accent": ("color", "#d4af37", 7), "bg_primary": ("color", "#050506", 7),
            "bg_secondary": ("color", "#101116", 7), "surface": ("color", "#18191d", 7),
            "text_primary": ("color", "#f5f5f5", 7), "text_secondary": ("color", "#9ca3af", 7),
            "success": ("color", "#22c55e", 7), "warning": ("color", "#f59e0b", 7),
            "danger": ("color", "#e50914", 7), "border": ("color", "#2b2d33", 7),
            "glass": ("range", 70, (0, 100)), "radius": ("range", 14, (4, 28)),
            "shadow": ("select", "media", ["suave", "media", "profunda"]),
            "tema": ("select", "oscuro", ["oscuro", "claro"]),
            "fuente": ("select", "Inter", ["Inter", "Manrope", "Montserrat", "system-ui"]),
            "tamano_base": ("range", 16, (14, 19)), "peso_titulos": ("select", "800", ["600", "700", "800", "900"]),
        },
    },
    "contacto": {
        "titulo": "WhatsApp y contacto", "icono": "messages-square",
        "campos": {
            "whatsapp": ("phone", "573147735950", 18), "telefono": ("phone", "", 18),
            "correo": ("email", "", 120), "instagram": ("url", "", 240), "facebook": ("url", "", 240),
            "tiktok": ("url", "", 240), "telegram": ("url", "", 240), "horario": ("text", "", 160),
            "ubicacion": ("text", "Colombia", 160), "mensaje_whatsapp": ("textarea", "Hola, quiero información sobre sus servicios.", 500),
        },
    },
    "comercial": {
        "titulo": "Información comercial", "icono": "badge-info",
        "campos": {
            "moneda": ("select", "COP", ["COP", "USD", "EUR", "MXN"]), "simbolo": ("text", "$", 6),
            "pais": ("text", "Colombia", 80), "zona_horaria": ("text", "America/Bogota", 80),
            "garantia": ("textarea", "30 días de garantía.", 800), "condiciones": ("textarea", "", 1200),
            "politica_pagos": ("textarea", "", 1200), "politica_renovacion": ("textarea", "", 1200),
            "politica_soporte": ("textarea", "", 1200), "medios_pago": ("text", "Transferencia", 240),
        },
    },
    "inicio": {
        "titulo": "Página de inicio", "icono": "house",
        "campos": {
            "hero_visible": ("boolean", True, None), "hero_titulo": ("text", "EL MEJOR ENTRETENIMIENTO EN TUS MANOS", 160),
            "hero_subtitulo": ("textarea", "Plataformas premium al mejor precio.", 300), "hero_cta": ("text", "Explorar catálogo →", 60),
            "hero_imagen": ("asset", "", 240), "secciones_orden": ("text", "productos,promociones,cartelera,beneficios,contacto", 300),
            "productos_visible": ("boolean", True, None), "promociones_visible": ("boolean", True, None),
            "cartelera_visible": ("boolean", True, None), "beneficios_visible": ("boolean", True, None),
        },
    },
    "catalogo": {"titulo": "Catálogo", "icono": "package", "campos": {
        "mostrar_precios": ("boolean", True, None), "mostrar_ofertas": ("boolean", True, None), "mostrar_badges": ("boolean", True, None),
        "columnas": ("range", 4, (2, 6)), "tamano_tarjeta": ("select", "medio", ["compacto", "medio", "amplio"]),
        "orden": ("select", "actual", ["actual", "nombre", "precio", "destacados"]), "mostrar_agotados": ("boolean", True, None),
        "cta": ("text", "Comprar", 40), "titulo": ("text", "Catálogo", 80),
    }},
    "promociones": {"titulo": "Promociones", "icono": "flame", "campos": {
        "visible": ("boolean", True, None), "posicion": ("select", "inicio", ["inicio", "catalogo", "ambos"]),
        "duracion": ("range", 6, (2, 20)), "mostrar_badges": ("boolean", True, None), "prioridad": ("select", "manual", ["manual", "reciente"]),
        "estilo": ("select", "premium", ["premium", "compacto", "minimal"]), "banners_automaticos": ("boolean", True, None), "titulo": ("text", "Promociones", 80),
    }},
    "cartelera": {"titulo": "Cartelera", "icono": "clapperboard", "campos": {
        "visible": ("boolean", True, None), "ubicacion": ("select", "inicio", ["inicio", "catalogo"]), "cantidad": ("range", 12, (1, 30)),
        "carrusel": ("boolean", True, None), "autoplay": ("boolean", True, None), "velocidad": ("range", 6, (2, 20)),
        "titulo": ("text", "Cartelera", 80), "mostrar_estrenos": ("boolean", True, None), "destacados": ("boolean", True, None),
    }},
    "mensajes": {"titulo": "Mensajes automáticos", "icono": "message-square-text", "campos": {
        **{clave: ("textarea", valor, 1200) for clave, valor in {
            "compra": "Hola {cliente}, recibimos tu compra de {servicio}.", "confirmacion": "Tu servicio {servicio} fue confirmado.",
            "renovacion": "Hola {cliente}, ¿deseas renovar {servicio}?", "vencimiento": "Tu servicio {servicio} venció el {vencimiento}.",
            "notificacion": "Hola {cliente}, te informamos sobre {servicio}.", "corte": "El servicio {servicio} fue liberado.",
            "garantia": "Tu garantía de {servicio} está en proceso.", "reemplazo": "Tu servicio {servicio} fue reemplazado.",
            "soporte": "Hola {cliente}, estamos atendiendo tu solicitud.", "bienvenida": "Bienvenido a {negocio}, {cliente}.",
        }.items()}
    }},
    "sistema": {"titulo": "Estado del sistema", "icono": "activity", "campos": {
        "tienda_activa": ("boolean", True, None), "mantenimiento": ("boolean", False, None),
        "mensaje_mantenimiento": ("textarea", "Estamos realizando mejoras. Volveremos pronto.", 500), "fecha_estimada": ("text", "", 60),
        "bloquear_compras": ("boolean", False, None), "permitir_admin": ("boolean", True, None), "aviso_global": ("textarea", "", 300), "banner": ("boolean", False, None),
    }},
    "accesos": {"titulo": "Accesos rápidos", "icono": "layout-grid", "campos": {
        "visibles": ("text", "productos,promociones,cartelera,nube-cuentas", 300), "orden": ("text", "productos,promociones,cartelera,nube-cuentas", 300),
        "etiqueta_productos": ("text", "Productos", 40), "icono_productos": ("select", "package", ["package", "shopping-bag", "boxes"]),
    }},
    "cliente": {"titulo": "Modo cliente / White Label", "icono": "building-2", "campos": {
        "activo": ("boolean", False, None), "ocultar_pechy": ("boolean", False, None), "marca": ("text", "", 80),
        "logo": ("asset", "", 240), "favicon": ("asset", "", 240), "dominio": ("text", "", 160),
        "footer": ("textarea", "", 300), "soporte": ("text", "", 160), "contacto": ("text", "", 160),
        "textos_legales": ("textarea", "", 1200), "powered_by": ("boolean", True, None),
    }},
    "seguridad": {"titulo": "Seguridad", "icono": "lock-keyhole", "campos": {
        "timeout_minutos": ("range", 60, (10, 1440)), "confirmar_criticas": ("boolean", True, None),
        "registro_accesos": ("boolean", True, None), "max_intentos": ("range", 5, (3, 10)), "cerrar_otras_sesiones": ("boolean", False, None),
    }},
    "respaldo": {"titulo": "Respaldo y mantenimiento", "icono": "database-backup", "campos": {
        "recordatorio": ("select", "semanal", ["diario", "semanal", "mensual"]), "limpieza_temporales": ("boolean", False, None),
        "exportacion_habilitada": ("boolean", True, None), "verificar_integridad": ("boolean", True, None),
    }},
    "auditoria": {"titulo": "Auditoría", "icono": "scroll-text", "campos": {
        "retencion_dias": ("range", 365, (30, 3650)), "registrar_publicaciones": ("boolean", True, None),
        "registrar_restauraciones": ("boolean", True, None), "registrar_seguridad": ("boolean", True, None),
    }},
}

LEGACY = {
    "identidad": {"nombre_negocio": "nombre_negocio", "nombre_corto": "nombre_corto", "eslogan": "eslogan", "descripcion_negocio": "descripcion_negocio", "texto_footer": "texto_footer"},
    "apariencia": {"brand_primary": "color_principal", "brand_secondary": "color_secundario", "brand_accent": "color_acento"},
    "contacto": {"whatsapp": "whatsapp"},
    "comercial": {"simbolo": "moneda_simbolo", "garantia": "dias_garantia"},
    "inicio": {"hero_visible": "inicio_hero_activo", "hero_cta": "inicio_boton_catalogo"},
}

VARIABLES_MENSAJE = {"cliente", "servicio", "fecha", "vencimiento", "dias", "telefono", "negocio"}

def _tablas(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS configuracion_modulos (
      tenant_id TEXT NOT NULL, modulo TEXT NOT NULL, borrador_json TEXT NOT NULL DEFAULT '{}',
      publicado_json TEXT NOT NULL DEFAULT '{}', version INTEGER NOT NULL DEFAULT 0,
      actualizado_en TEXT DEFAULT CURRENT_TIMESTAMP, publicado_en TEXT,
      PRIMARY KEY (tenant_id, modulo));
    CREATE TABLE IF NOT EXISTS configuracion_auditoria (
      id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, usuario TEXT NOT NULL,
      modulo TEXT NOT NULL, accion TEXT NOT NULL, resumen_anterior TEXT, resumen_nuevo TEXT,
      fecha TEXT DEFAULT CURRENT_TIMESTAMP);
    """)

def defaults(modulo=None):
    resultado = {k: {campo: deepcopy(spec[1]) for campo, spec in meta["campos"].items()} for k, meta in MODULOS.items()}
    return resultado[modulo] if modulo else resultado

def _legacy(conn, modulo):
    mapa = LEGACY.get(modulo, {})
    if not mapa: return {}
    try: filas = dict(conn.execute("SELECT clave, valor FROM config").fetchall())
    except Exception: return {}
    salida = {}
    for campo, clave in mapa.items():
        if clave not in filas: continue
        valor = filas[clave]
        tipo = MODULOS[modulo]["campos"][campo][0]
        salida[campo] = valor == "1" if tipo == "boolean" else valor
    return salida

def _fila(conn, tenant, modulo):
    _tablas(conn)
    conn.execute("INSERT OR IGNORE INTO configuracion_modulos(tenant_id,modulo) VALUES(?,?)", (tenant, modulo))
    return conn.execute("SELECT * FROM configuracion_modulos WHERE tenant_id=? AND modulo=?", (tenant, modulo)).fetchone()

def _json(valor):
    try: return json.loads(valor or "{}")
    except (TypeError, ValueError): return {}

def obtener_modulo(modulo, tenant=TENANT_PREDETERMINADO):
    if modulo not in MODULOS: raise KeyError("Módulo desconocido")
    conn = database.conectar()
    try:
        fila = _fila(conn, tenant, modulo); base = defaults(modulo); legado = _legacy(conn, modulo)
        publicado = {**base, **legado, **_json(fila["publicado_json"])}
        borrador_guardado = _json(fila["borrador_json"])
        borrador = {**publicado, **borrador_guardado}
        conn.commit()
        return {"modulo": modulo, "meta": MODULOS[modulo], "original": base, "publicado": publicado,
                "borrador": borrador, "pendiente": borrador != publicado, "version": fila["version"]}
    finally: conn.close()

def _validar(modulo, datos):
    if not isinstance(datos, dict): raise ValueError("Los datos deben ser un objeto.")
    campos = MODULOS[modulo]["campos"]
    desconocidos = set(datos) - set(campos)
    if desconocidos: raise ValueError("Campos no permitidos: " + ", ".join(sorted(desconocidos)))
    salida = {}
    for clave, valor in datos.items():
        tipo, _, regla = campos[clave]
        if tipo == "boolean": valor = bool(valor)
        elif tipo == "range":
            try: valor = int(valor)
            except (TypeError, ValueError): raise ValueError(f"{clave} debe ser numérico.")
            if not regla[0] <= valor <= regla[1]: raise ValueError(f"{clave} está fuera del rango permitido.")
        else:
            valor = str(valor or "").strip()
            if isinstance(regla, int) and len(valor) > regla: raise ValueError(f"{clave} supera el tamaño permitido.")
            if tipo == "color" and not re.fullmatch(r"#[0-9a-fA-F]{6}", valor): raise ValueError(f"{clave} no es un color válido.")
            if tipo == "select" and valor not in regla: raise ValueError(f"{clave} no es una opción permitida.")
            if tipo == "phone": valor = re.sub(r"\D", "", valor)
            if tipo == "phone" and valor and not 7 <= len(valor) <= 15: raise ValueError(f"{clave} no es un teléfono válido.")
            if tipo == "email" and valor and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor): raise ValueError("Correo inválido.")
            if tipo == "url" and valor and not re.match(r"^https://", valor, re.I): raise ValueError(f"{clave} debe usar HTTPS.")
            if tipo == "asset" and valor and not re.match(r"^/static/uploads/configuracion/[\w./-]+$", valor): raise ValueError(f"{clave} no es un recurso permitido.")
            if modulo == "mensajes":
                variables = set(re.findall(r"\{([^{}]+)\}", valor))
                if variables - VARIABLES_MENSAJE: raise ValueError(f"{clave} contiene variables no permitidas.")
        salida[clave] = valor
    return salida

def _auditar(conn, tenant, usuario, modulo, accion, anterior, nuevo):
    sensibles = {"password", "contrasena", "token", "secret"}
    limpiar = lambda d: {k: v for k, v in (d or {}).items() if not any(s in k.lower() for s in sensibles)}
    conn.execute("INSERT INTO configuracion_auditoria(tenant_id,usuario,modulo,accion,resumen_anterior,resumen_nuevo) VALUES(?,?,?,?,?,?)",
                 (tenant, usuario, modulo, accion, json.dumps(limpiar(anterior), ensure_ascii=False), json.dumps(limpiar(nuevo), ensure_ascii=False)))

def guardar_borrador(modulo, datos, tenant=TENANT_PREDETERMINADO, usuario="admin"):
    if modulo not in MODULOS: raise KeyError("Módulo desconocido")
    validados = _validar(modulo, datos); conn = database.conectar()
    try:
        fila = _fila(conn, tenant, modulo); anterior = _json(fila["borrador_json"])
        nuevo = {**anterior, **validados}
        conn.execute("UPDATE configuracion_modulos SET borrador_json=?,actualizado_en=CURRENT_TIMESTAMP WHERE tenant_id=? AND modulo=?",
                     (json.dumps(nuevo, ensure_ascii=False), tenant, modulo))
        _auditar(conn, tenant, usuario, modulo, "guardar_borrador", anterior, nuevo); conn.commit()
        return obtener_modulo(modulo, tenant)
    except Exception: conn.rollback(); raise
    finally: conn.close()

def restaurar_modulo(modulo, tenant=TENANT_PREDETERMINADO, usuario="admin"):
    if modulo not in MODULOS: raise KeyError("Módulo desconocido")
    conn = database.conectar()
    try:
        fila = _fila(conn, tenant, modulo); anterior = _json(fila["borrador_json"]); nuevo = defaults(modulo)
        conn.execute("UPDATE configuracion_modulos SET borrador_json=?,actualizado_en=CURRENT_TIMESTAMP WHERE tenant_id=? AND modulo=?",
                     (json.dumps(nuevo, ensure_ascii=False), tenant, modulo))
        _auditar(conn, tenant, usuario, modulo, "restaurar_modulo", anterior, nuevo); conn.commit()
        return obtener_modulo(modulo, tenant)
    except Exception: conn.rollback(); raise
    finally: conn.close()

def restaurar_todo(tenant=TENANT_PREDETERMINADO, usuario="admin"):
    conn = database.conectar()
    try:
        _tablas(conn)
        for modulo in MODULOS:
            fila = _fila(conn, tenant, modulo); anterior = _json(fila["borrador_json"]); nuevo = defaults(modulo)
            conn.execute("UPDATE configuracion_modulos SET borrador_json=?,actualizado_en=CURRENT_TIMESTAMP WHERE tenant_id=? AND modulo=?",
                         (json.dumps(nuevo, ensure_ascii=False), tenant, modulo))
            _auditar(conn, tenant, usuario, modulo, "restaurar_global", anterior, nuevo)
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()

def publicar(tenant=TENANT_PREDETERMINADO, usuario="admin"):
    conn = database.conectar()
    try:
        _tablas(conn)
        for modulo in MODULOS:
            fila = _fila(conn, tenant, modulo); borrador = _json(fila["borrador_json"]); anterior = _json(fila["publicado_json"])
            if borrador:
                conn.execute("UPDATE configuracion_modulos SET publicado_json=?,version=version+1,publicado_en=CURRENT_TIMESTAMP WHERE tenant_id=? AND modulo=?",
                             (json.dumps(borrador, ensure_ascii=False), tenant, modulo))
                _auditar(conn, tenant, usuario, modulo, "publicar", anterior, borrador)
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()

def estado_general(tenant=TENANT_PREDETERMINADO):
    modulos = {m: obtener_modulo(m, tenant) for m in MODULOS}
    return {"tenant_id": tenant, "pendiente": any(v["pendiente"] for v in modulos.values()), "modulos": modulos}

def configuracion_efectiva(tenant=TENANT_PREDETERMINADO, borrador=False):
    salida = {}
    for modulo in MODULOS:
        estado = obtener_modulo(modulo, tenant)
        salida[modulo] = estado["borrador" if borrador else "publicado"]
    plana = database.obtener_config()
    for valores in salida.values(): plana.update(valores)
    plana["modulos"] = salida
    plana.update({"color_principal": salida["apariencia"]["brand_primary"], "color_secundario": salida["apariencia"]["brand_secondary"],
                  "color_acento": salida["apariencia"]["brand_accent"], "inicio_hero_activo": "1" if salida["inicio"]["hero_visible"] else "0",
                  "inicio_boton_catalogo": salida["inicio"]["hero_cta"]})
    return plana

def auditoria(tenant=TENANT_PREDETERMINADO, modulo="", accion="", limite=100):
    conn = database.conectar()
    try:
        _tablas(conn); condiciones = ["tenant_id=?"]; params = [tenant]
        if modulo: condiciones.append("modulo=?"); params.append(modulo)
        if accion: condiciones.append("accion=?"); params.append(accion)
        params.append(min(max(int(limite), 1), 500))
        return [dict(f) for f in conn.execute(f"SELECT * FROM configuracion_auditoria WHERE {' AND '.join(condiciones)} ORDER BY id DESC LIMIT ?", params).fetchall()]
    finally: conn.close()
