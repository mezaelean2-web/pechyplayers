"""Autoridad administrativa de plan a inventario para cliente final.

Este modulo solo configura y consulta reglas. No reserva ni asigna inventario.
"""
import database
import reseller_accounts

TIPOS_UNIDAD = {"cuenta", "perfil"}

def _conectar():
    conn = database.conectar(); conn.execute("PRAGMA foreign_keys=ON"); return conn

def initialize_schema(connection=None):
    propia = connection is None; conn = _conectar() if propia else connection
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS customer_plan_fulfillment_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL UNIQUE,
            plataforma TEXT NOT NULL COLLATE NOCASE CHECK(length(trim(plataforma))>0),
            tipo_unidad TEXT NOT NULL CHECK(tipo_unidad IN ('cuenta','perfil')),
            duracion_dias INTEGER NOT NULL CHECK(duracion_dias>0),
            activo INTEGER NOT NULL DEFAULT 0 CHECK(activo IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(plan_id) REFERENCES productos(id) ON DELETE CASCADE)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_customer_fulfillment_rules_active ON customer_plan_fulfillment_rules(activo,plan_id)")
        if propia: conn.commit()
    except Exception:
        if propia: conn.rollback()
        raise
    finally:
        if propia: conn.close()

def listar_plataformas_inventario(cursor=None):
    propia=cursor is None; conn=_conectar() if propia else cursor.connection; cur=conn.cursor() if propia else cursor
    try:
        return [x[0] for x in cur.execute("""SELECT MIN(trim(plataforma)) FROM nube_cuentas
            WHERE trim(COALESCE(plataforma,''))!='' GROUP BY lower(trim(plataforma)) ORDER BY lower(trim(plataforma))""").fetchall()]
    finally:
        if propia: conn.close()

def _activo_estricto(valor):
    if isinstance(valor,bool): return int(valor)
    if isinstance(valor,int) and not isinstance(valor,bool) and valor in (0,1): return valor
    raise ValueError("activo debe ser un booleano estricto.")

def _validar_en_cursor(cursor,plan_id,plataforma,tipo_unidad,duracion_dias,activo):
    if isinstance(plan_id,bool): raise ValueError("El plan no es valido.")
    try: plan_id,duracion_dias=int(plan_id),int(duracion_dias)
    except (TypeError,ValueError) as error: raise ValueError("Plan y duracion deben ser enteros validos.") from error
    plataforma=" ".join(str(plataforma or "").strip().split()); tipo_unidad=str(tipo_unidad or "").strip().lower(); activo=_activo_estricto(activo)
    if plan_id<=0 or not cursor.execute("SELECT 1 FROM productos WHERE id=?",(plan_id,)).fetchone(): raise LookupError("Plan no encontrado.")
    if not plataforma: raise ValueError("La plataforma de inventario es obligatoria.")
    if tipo_unidad not in TIPOS_UNIDAD: raise ValueError("El tipo de unidad no es valido.")
    if duracion_dias<=0: raise ValueError("La duracion debe ser mayor que cero.")
    real=next((x for x in listar_plataformas_inventario(cursor) if x.casefold()==plataforma.casefold()),None)
    if not real: raise ValueError("La plataforma no existe en el inventario Nube.")
    modalidad="cuenta_completa" if tipo_unidad=="cuenta" else "perfiles"
    if not cursor.execute("SELECT 1 FROM nube_cuentas WHERE lower(trim(plataforma))=lower(trim(?)) AND COALESCE(modalidad,'cuenta_completa')=? LIMIT 1",(real,modalidad)).fetchone():
        raise ValueError("La plataforma no tiene inventario compatible con ese tipo de unidad.")
    return plan_id,real,tipo_unidad,duracion_dias,activo

def guardar_regla(plan_id,plataforma,tipo_unidad,duracion_dias,activo=False):
    conn=_conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); valores=_validar_en_cursor(conn.cursor(),plan_id,plataforma,tipo_unidad,duracion_dias,activo)
        conn.execute("""INSERT INTO customer_plan_fulfillment_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo)
            VALUES(?,?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET plataforma=excluded.plataforma,
            tipo_unidad=excluded.tipo_unidad,duracion_dias=excluded.duracion_dias,activo=excluded.activo,updated_at=CURRENT_TIMESTAMP""",valores); conn.commit()
        return obtener_regla(plan_id,True)
    except Exception: conn.rollback(); raise
    finally: conn.close()

def obtener_regla(plan_id,incluir_inactiva=False):
    conn=_conectar()
    try:
        sql="SELECT * FROM customer_plan_fulfillment_rules WHERE plan_id=?"+("" if incluir_inactiva else " AND activo=1")
        fila=conn.execute(sql,(int(plan_id),)).fetchone(); return dict(fila) if fila else None
    finally: conn.close()

def copiar_desde_reseller(plan_id):
    conn=_conectar()
    try:
        conn.execute("BEGIN IMMEDIATE"); regla=conn.execute("SELECT plataforma,tipo_unidad,duracion_dias FROM reseller_plan_inventory_rules WHERE plan_id=?",(int(plan_id),)).fetchone()
        if not regla: raise LookupError("El plan no tiene configuracion reseller para copiar.")
        valores=_validar_en_cursor(conn.cursor(),plan_id,regla["plataforma"],regla["tipo_unidad"],regla["duracion_dias"],False)
        conn.execute("""INSERT INTO customer_plan_fulfillment_rules(plan_id,plataforma,tipo_unidad,duracion_dias,activo)
            VALUES(?,?,?,?,0) ON CONFLICT(plan_id) DO UPDATE SET plataforma=excluded.plataforma,
            tipo_unidad=excluded.tipo_unidad,duracion_dias=excluded.duracion_dias,activo=0,updated_at=CURRENT_TIMESTAMP""",valores[:4]); conn.commit()
        return obtener_regla(plan_id,True)
    except Exception: conn.rollback(); raise
    finally: conn.close()

def listar_reglas_admin():
    conn=_conectar()
    try:
        filas=conn.execute("""SELECT p.id plan_id,p.nombre producto,p.plan,c.id regla_id,c.plataforma,c.tipo_unidad,
            c.duracion_dias,c.activo,c.updated_at,r.plataforma reseller_plataforma,r.tipo_unidad reseller_tipo_unidad,
            r.duracion_dias reseller_duracion_dias FROM productos p
            LEFT JOIN customer_plan_fulfillment_rules c ON c.plan_id=p.id
            LEFT JOIN reseller_plan_inventory_rules r ON r.plan_id=p.id
            ORDER BY p.nombre COLLATE NOCASE,p.plan COLLATE NOCASE,p.id""").fetchall()
        resultado=[]
        for fila in filas:
            item=dict(fila); item["disponibles"]=len(reseller_accounts._unidades_elegibles_en_cursor(conn.cursor(),item)) if item["regla_id"] else None; resultado.append(item)
        return resultado
    finally: conn.close()
