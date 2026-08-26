"""Fulfillment atomico e idempotente de pedidos pagados de cliente final."""
from datetime import datetime, timedelta, timezone

import database
import reseller_accounts


class CustomerFulfillmentError(Exception):
    def __init__(self, code, message, status="review"):
        super().__init__(message); self.code=code; self.safe_message=message; self.status=status


class CustomerDeliveryNotFound(Exception):
    """Respuesta indistinguible para pedido inexistente, ajeno o no entregable."""


def _connect():
    conn=database.conectar(); conn.execute("PRAGMA foreign_keys=ON"); return conn


def initialize_schema(connection=None):
    owns=connection is None; conn=_connect() if owns else connection
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customer_order_fulfillments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','processing','review','fulfilled')),
                attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count>=0),
                last_error_code TEXT,
                last_error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fulfilled_at TEXT,
                FOREIGN KEY(order_id) REFERENCES customer_orders(id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_customer_fulfillments_status
                ON customer_order_fulfillments(status,updated_at);
            CREATE TABLE IF NOT EXISTS customer_order_fulfillment_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fulfillment_id INTEGER NOT NULL,
                order_line_id INTEGER NOT NULL UNIQUE,
                nube_account_id INTEGER NOT NULL,
                nube_profile_id INTEGER,
                tipo_unidad TEXT NOT NULL CHECK(tipo_unidad IN ('cuenta','perfil')),
                assigned_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                CHECK((tipo_unidad='cuenta' AND nube_profile_id IS NULL) OR
                      (tipo_unidad='perfil' AND nube_profile_id IS NOT NULL)),
                FOREIGN KEY(fulfillment_id) REFERENCES customer_order_fulfillments(id) ON DELETE RESTRICT,
                FOREIGN KEY(order_line_id) REFERENCES customer_order_lines(id) ON DELETE RESTRICT,
                FOREIGN KEY(nube_account_id) REFERENCES nube_cuentas(id) ON DELETE RESTRICT,
                FOREIGN KEY(nube_profile_id) REFERENCES nube_perfiles(id) ON DELETE RESTRICT
            );
            CREATE INDEX IF NOT EXISTS idx_customer_fulfillment_lines_parent
                ON customer_order_fulfillment_lines(fulfillment_id,id);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_fulfillment_account
                ON customer_order_fulfillment_lines(nube_account_id) WHERE tipo_unidad='cuenta';
            CREATE UNIQUE INDEX IF NOT EXISTS uq_customer_fulfillment_profile
                ON customer_order_fulfillment_lines(nube_profile_id) WHERE nube_profile_id IS NOT NULL;
        """)
        if owns: conn.commit()
    except Exception:
        if owns: conn.rollback()
        raise
    finally:
        if owns: conn.close()


def _record_failure(order_id, code, message, status):
    conn=_connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        order=conn.execute("SELECT status FROM customer_orders WHERE id=?",(order_id,)).fetchone()
        if not order or order["status"]!="paid": conn.rollback(); return
        fulfilled=conn.execute("SELECT status FROM customer_order_fulfillments WHERE order_id=?",(order_id,)).fetchone()
        if fulfilled and fulfilled["status"]=="fulfilled": conn.commit(); return
        conn.execute("""INSERT INTO customer_order_fulfillments(order_id,status,attempt_count,last_error_code,last_error_message)
            VALUES(?,?,1,?,?) ON CONFLICT(order_id) DO UPDATE SET status=excluded.status,
            attempt_count=customer_order_fulfillments.attempt_count+1,last_error_code=excluded.last_error_code,
            last_error_message=excluded.last_error_message,updated_at=CURRENT_TIMESTAMP""",
            (order_id,status,code,message)); conn.commit()
    except Exception: conn.rollback(); raise
    finally: conn.close()


def fulfill_customer_order(order_id, *, failure_injection=None, now=None):
    """Asigna todas las lineas o ninguna. Nunca devuelve credenciales."""
    initialize_schema()
    try: order_id=int(order_id)
    except (TypeError,ValueError) as error: raise CustomerFulfillmentError("invalid_order","Pedido no valido.") from error
    moment=now or datetime.now(timezone.utc)
    if moment.tzinfo is None: moment=moment.replace(tzinfo=timezone.utc)
    assigned_at=moment.isoformat(); delivery_date=moment.date().isoformat()

    def fail(point):
        if failure_injection==point: raise RuntimeError("injected_fulfillment_failure")

    conn=_connect()
    try:
        conn.execute("BEGIN IMMEDIATE"); cur=conn.cursor()
        order=cur.execute("SELECT * FROM customer_orders WHERE id=?",(order_id,)).fetchone()
        if not order: raise CustomerFulfillmentError("order_not_found","Pedido no encontrado.")
        existing=cur.execute("SELECT * FROM customer_order_fulfillments WHERE order_id=?",(order_id,)).fetchone()
        if existing and existing["status"]=="fulfilled":
            count=cur.execute("SELECT COUNT(*) FROM customer_order_fulfillment_lines WHERE fulfillment_id=?",(existing["id"],)).fetchone()[0]
            conn.commit(); return {"status":"fulfilled","duplicate":True,"assigned_lines":count}
        if order["status"]!="paid": raise CustomerFulfillmentError("order_not_paid","Solo los pedidos pagados pueden entregarse.")
        lines=cur.execute("SELECT * FROM customer_order_lines WHERE order_id=? ORDER BY line_number,id",(order_id,)).fetchall()
        if not lines: raise CustomerFulfillmentError("order_without_lines","El pedido no tiene lineas validas.")
        prepared=[]; reserved=set()
        for line in lines:
            rule=cur.execute("SELECT * FROM customer_plan_fulfillment_rules WHERE plan_id=?",(line["source_plan_id"],)).fetchone()
            if not rule: raise CustomerFulfillmentError("rule_missing",f"Falta regla para la linea {line['line_number']}.")
            if not rule["activo"]: raise CustomerFulfillmentError("rule_inactive",f"La regla de la linea {line['line_number']} esta inactiva.")
            chosen=None
            for unit in reseller_accounts._unidades_elegibles_en_cursor(cur,dict(rule)):
                key=(rule["tipo_unidad"],unit["cuenta_id"] if rule["tipo_unidad"]=="cuenta" else unit["perfil_id"])
                if key not in reserved: reserved.add(key); chosen=unit; break
            if not chosen: raise CustomerFulfillmentError("inventory_insufficient",f"No hay inventario para la linea {line['line_number']}.","pending")
            prepared.append((line,dict(rule),chosen))
        if existing:
            cur.execute("""UPDATE customer_order_fulfillments SET status='processing',last_error_code=NULL,
                last_error_message=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status!='fulfilled'""",(existing["id"],)); fulfillment_id=existing["id"]
        else:
            cur.execute("INSERT INTO customer_order_fulfillments(order_id,status) VALUES(?,'processing')",(order_id,));fulfillment_id=cur.lastrowid
        label=f"Pedido cliente {order['public_order_id']} - {order['customer_first_name']} {order['customer_last_name']}"[:160]
        client_id=database._obtener_o_crear_cliente_nube(cur,label,order["customer_whatsapp"] or "")
        for line,rule,unit in prepared:
            expires=(moment+timedelta(days=int(rule["duracion_dias"]))).date().isoformat()
            table="nube_cuentas" if rule["tipo_unidad"]=="cuenta" else "nube_perfiles"
            unit_id=unit["cuenta_id"] if rule["tipo_unidad"]=="cuenta" else unit["perfil_id"]
            cur.execute(f"""UPDATE {table} SET cliente_id=?,nombre_cliente=?,telefono=?,fecha_entrega=?,
                dias_cuenta=?,fecha_vencimiento=?,estado='activa',fecha_actualizacion=CURRENT_TIMESTAMP
                WHERE id=? AND lower(COALESCE(estado,'disponible'))='disponible'
                  AND trim(COALESCE(nombre_cliente,''))='' AND trim(COALESCE(fecha_entrega,''))=''""",
                (client_id,label,order["customer_whatsapp"] or "",delivery_date,int(rule["duracion_dias"]),expires,unit_id))
            if cur.rowcount!=1: raise CustomerFulfillmentError("inventory_changed","El inventario cambio durante la asignacion.","pending")
            fail("after_first_assignment")
            cur.execute("""INSERT INTO customer_order_fulfillment_lines
                (fulfillment_id,order_line_id,nube_account_id,nube_profile_id,tipo_unidad,assigned_at,expires_at)
                VALUES(?,?,?,?,?,?,?)""",(fulfillment_id,line["id"],unit["cuenta_id"],unit["perfil_id"],rule["tipo_unidad"],assigned_at,expires))
            cur.execute("""INSERT INTO nube_movimientos(cuenta_id,tipo,descripcion,estado_anterior,estado_nuevo,cliente_nombre)
                VALUES(?,?,'Unidad asignada por pedido de cliente final','disponible','activa',?)""",
                (unit["cuenta_id"],"asignacion_customer_order_"+rule["tipo_unidad"],label))
            fail("after_movement")
        expected=len(lines); actual=cur.execute("SELECT COUNT(*) FROM customer_order_fulfillment_lines WHERE fulfillment_id=?",(fulfillment_id,)).fetchone()[0]
        if actual!=expected: raise CustomerFulfillmentError("line_invariant","No coinciden las lineas entregadas.")
        cur.execute("""UPDATE customer_order_fulfillments SET status='fulfilled',attempt_count=attempt_count+1,
            last_error_code=NULL,last_error_message=NULL,updated_at=CURRENT_TIMESTAMP,fulfilled_at=?
            WHERE id=? AND status='processing'""",(assigned_at,fulfillment_id))
        if cur.rowcount!=1: raise CustomerFulfillmentError("state_invariant","No pudo completarse el fulfillment.")
        fail("before_commit"); conn.commit()
        return {"status":"fulfilled","duplicate":False,"assigned_lines":actual}
    except CustomerFulfillmentError as error:
        conn.rollback(); _record_failure(order_id,error.code,error.safe_message,error.status); return {"status":error.status,"code":error.code,"message":error.safe_message}
    except Exception:
        conn.rollback(); _record_failure(order_id,"internal_error","El fulfillment requiere revision.","review"); return {"status":"review","code":"internal_error","message":"El fulfillment requiere revision."}
    finally: conn.close()


def get_admin(order_id):
    initialize_schema()
    conn=_connect()
    try:
        fulfillment=conn.execute("SELECT * FROM customer_order_fulfillments WHERE order_id=?",(int(order_id),)).fetchone()
        if not fulfillment: return None
        lines=conn.execute("""SELECT fl.id,fl.order_line_id,fl.nube_account_id,fl.nube_profile_id,fl.tipo_unidad,
            fl.assigned_at,fl.expires_at,ol.line_number,ol.product_name,ol.plan_name
            FROM customer_order_fulfillment_lines fl JOIN customer_order_lines ol ON ol.id=fl.order_line_id
            WHERE fl.fulfillment_id=? ORDER BY ol.line_number""",(fulfillment["id"],)).fetchall()
        result=dict(fulfillment);result["lines"]=[dict(x) for x in lines];return result
    finally: conn.close()


def get_customer_delivery(public_order_id, guest_session_hash):
    """Lee credenciales canonicas solo a traves del fulfillment propiedad del guest."""
    conn=_connect()
    try:
        order=conn.execute("""SELECT id,public_order_id,status,item_count
            FROM customer_orders WHERE public_order_id=? AND guest_session_hash=?""",
            (str(public_order_id or ""),str(guest_session_hash or ""))).fetchone()
        if not order or order["status"]!="paid": raise CustomerDeliveryNotFound()
        header=conn.execute("""SELECT id,status,fulfilled_at FROM customer_order_fulfillments
            WHERE order_id=? AND status='fulfilled'""",(order["id"],)).fetchone()
        if not header: raise CustomerDeliveryNotFound()
        rows=conn.execute("""SELECT fl.order_line_id,fl.tipo_unidad,fl.nube_account_id,
            fl.nube_profile_id,fl.assigned_at,fl.expires_at,
            ol.line_number,ol.product_name,ol.plan_name,
            c.plataforma,c.correo,c.contrasena,c.pin account_pin,
            p.cuenta_id profile_account_id,p.nombre_perfil,p.pin profile_pin
            FROM customer_order_fulfillment_lines fl
            JOIN customer_order_lines ol ON ol.id=fl.order_line_id AND ol.order_id=?
            JOIN nube_cuentas c ON c.id=fl.nube_account_id
            LEFT JOIN nube_perfiles p ON p.id=fl.nube_profile_id
            WHERE fl.fulfillment_id=? ORDER BY ol.line_number,fl.id""",
            (order["id"],header["id"])).fetchall()
        if len(rows)!=int(order["item_count"]): raise CustomerDeliveryNotFound()
        deliveries=[]
        for row in rows:
            unit=row["tipo_unidad"]
            if unit=="cuenta":
                if row["nube_profile_id"] is not None: raise CustomerDeliveryNotFound()
                profile_name=None;pin=(row["account_pin"] or "").strip()
            elif unit=="perfil":
                if row["nube_profile_id"] is None or row["profile_account_id"]!=row["nube_account_id"]:
                    raise CustomerDeliveryNotFound()
                profile_name=(row["nombre_perfil"] or "").strip();pin=(row["profile_pin"] or "").strip()
            else: raise CustomerDeliveryNotFound()
            expires=row["expires_at"]
            try: display_expires=datetime.fromisoformat(expires[:10]).strftime("%d/%m/%Y")
            except (TypeError,ValueError): raise CustomerDeliveryNotFound()
            deliveries.append({
                "line_number":row["line_number"],"product":row["product_name"],
                "plan":row["plan_name"],"platform":row["plataforma"],"unit_type":unit,
                "username":row["correo"],"password":row["contrasena"],"profile":profile_name,
                "pin":pin or None,"expires_at":expires,"expires_display":display_expires,
                "allowed_devices":1,
            })
        return {"order_id":order["public_order_id"],"status":"fulfilled",
                "fulfilled_at":header["fulfilled_at"],"deliveries":deliveries}
    finally: conn.close()
