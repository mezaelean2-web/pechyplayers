try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import customer_delivery_access
import customer_fulfillment
import database
from app import app


class CustomerDeliveryRecoveryPhase2C7Test(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.previous = database.DB
        database.DB = self.path
        conn = sqlite3.connect(self.path)
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE customer_orders(id INTEGER PRIMARY KEY,public_order_id TEXT UNIQUE,status TEXT,
                guest_session_hash TEXT,item_count INTEGER,expires_at TEXT);
            CREATE TABLE customer_order_lines(id INTEGER PRIMARY KEY,order_id INTEGER,line_number INTEGER,
                source_plan_id INTEGER,product_name TEXT,plan_name TEXT);
            CREATE TABLE customer_checkout_sessions(session_hash TEXT PRIMARY KEY,current_order_id INTEGER,
                updated_at TEXT NOT NULL,expires_at TEXT NOT NULL);
            CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT,contrasena TEXT,pin TEXT,
                modalidad TEXT,estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,fecha_vencimiento TEXT,dias_cuenta INTEGER);
            CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER,nombre_perfil TEXT,pin TEXT,
                estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,fecha_vencimiento TEXT,dias_cuenta INTEGER);
            CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,cuenta_id INTEGER,tipo TEXT);
        """)
        conn.execute("INSERT INTO nube_cuentas VALUES(1,'NETFLIX','netflix@example.test','secret-password','','perfiles','disponible','','','',0)")
        conn.execute("INSERT INTO nube_perfiles VALUES(2,1,'PERFIL PRIVADO','4321','activa','Cliente','2026-08-26','2026-09-25',30)")
        conn.execute("INSERT INTO nube_movimientos VALUES(1,1,'asignacion_customer_order_perfil')")
        conn.commit(); conn.close()
        customer_fulfillment.initialize_schema()
        customer_delivery_access.initialize_schema()
        app.config.update(TESTING=True, SECRET_KEY="delivery-recovery-test")
        self.client = app.test_client()
        self.owner_token = "owner-token"
        self.owner_hash = hashlib.sha256(self.owner_token.encode()).hexdigest()
        self.other_token = "other-token"
        self.fulfilled = self._order("ORD-HISTORIC", "paid", self.owner_hash, "fulfilled")
        self.current = self._order("ORD-CURRENT", "pending_payment", self.owner_hash)
        self.pending = self._order("ORD-PENDING", "pending_payment", self.owner_hash)
        self.preparing = self._order("ORD-PREPARING", "paid", self.owner_hash, "pending")
        self.review = self._order("ORD-REVIEW", "paid", self.owner_hash, "review", "inventory_secret_code", "internal detail")
        self.foreign = self._order("ORD-FOREIGN", "paid", hashlib.sha256(self.other_token.encode()).hexdigest())
        conn=self._conn();conn.execute("INSERT INTO customer_checkout_sessions VALUES(?,?,?,?)",(self.owner_hash,self.current,"2026-08-26T00:00:00Z","2030-01-01T00:00:00Z"));conn.commit();conn.close()

    def tearDown(self):
        database.DB = self.previous
        for suffix in ("", "-wal", "-shm"):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def _conn(self):
        conn=sqlite3.connect(self.path);conn.row_factory=sqlite3.Row;return conn

    def _order(self, public_id, status, guest_hash, fulfillment=None, error_code=None, error_message=None):
        conn=self._conn();cur=conn.execute("INSERT INTO customer_orders(public_order_id,status,guest_session_hash,item_count,expires_at) VALUES(?,?,?,?,?)",(public_id,status,guest_hash,1,"2030-01-01T00:00:00Z"));oid=cur.lastrowid
        line=conn.execute("INSERT INTO customer_order_lines(order_id,line_number,source_plan_id,product_name,plan_name) VALUES(?,?,?,?,?)",(oid,1,2,"Netflix","Perfil")).lastrowid
        if fulfillment:
            fid=conn.execute("INSERT INTO customer_order_fulfillments(order_id,status,attempt_count,last_error_code,last_error_message,fulfilled_at) VALUES(?,?,?,?,?,?)",(oid,fulfillment,1,error_code,error_message,"2026-08-26T00:00:00Z" if fulfillment=="fulfilled" else None)).lastrowid
            if fulfillment=="fulfilled":conn.execute("INSERT INTO customer_order_fulfillment_lines(fulfillment_id,order_line_id,nube_account_id,nube_profile_id,tipo_unidad,assigned_at,expires_at) VALUES(?,?,?,?,?,?,?)",(fid,line,1,2,"perfil","2026-08-26T00:00:00Z","2026-09-25"))
        conn.commit();conn.close();return oid

    def _auth(self, token=None):
        token = self.owner_token if token is None else token
        with self.client.session_transaction() as session:
            session["csrf_customer_checkout"]="csrf"
            session["customer_checkout_guest_token"]=token
        return {"X-CSRF-Token":"csrf"}

    def _lookup(self, public_id, token=None):
        return self.client.post("/compras/pedidos/consultar",json={"public_order_id":public_id},headers=self._auth(token))

    def test_paid_fulfilled_historico_es_consultable_y_ofrece_entrega(self):
        response=self._lookup("ORD-HISTORIC");data=response.get_json()["order"]
        self.assertEqual(response.status_code,200);self.assertEqual(data["state"],"fulfilled");self.assertTrue(data["delivery_available"])
        self.assertIn("ORD-HISTORIC",data["delivery_url"])
        conn=self._conn();self.assertEqual(conn.execute("SELECT current_order_id FROM customer_checkout_sessions WHERE session_hash=?",(self.owner_hash,)).fetchone()[0],self.current);conn.close()

    def test_public_id_solo_no_autoriza_y_ajeno_es_indistinguible(self):
        missing_cookie=app.test_client().post("/compras/pedidos/consultar",json={"public_order_id":"ORD-HISTORIC"})
        foreign=self._lookup("ORD-FOREIGN")
        missing=self._lookup("ORD-DOES-NOT-EXIST")
        self.assertEqual((missing_cookie.status_code,foreign.status_code,missing.status_code),(404,200,200))
        self.assertTrue(foreign.get_json()["recovery_required"]);self.assertTrue(missing.get_json()["recovery_required"])
        self.assertEqual(set(foreign.get_json()),set(missing.get_json()))
        for response in (missing_cookie,foreign,missing):self.assertNotIn("secret-password",response.get_data(as_text=True))

    def test_estados_seguros_no_exponen_credenciales_ni_error_interno(self):
        cases=(("ORD-PENDING","pending_payment","todavía no registra"),("ORD-PREPARING","preparing","estamos preparando"),("ORD-REVIEW","review","Comunícate con soporte"))
        for public_id,state,text in cases:
            with self.subTest(public_id=public_id):
                response=self._lookup(public_id);body=response.get_data(as_text=True);data=response.get_json()["order"]
                self.assertEqual(data["state"],state);self.assertIn(text,data["message"]);self.assertFalse(data["delivery_available"])
                for forbidden in ("secret-password","4321","PERFIL PRIVADO","inventory_secret_code","internal detail"):self.assertNotIn(forbidden,body)

    def test_entrega_repetida_no_muta_fulfillment_inventario_o_movimientos(self):
        headers=self._auth();conn=self._conn();tables=("customer_orders","customer_order_fulfillments","customer_order_fulfillment_lines","nube_cuentas","nube_perfiles","nube_movimientos");before={t:[tuple(x) for x in conn.execute("SELECT * FROM "+t)] for t in tables};conn.close()
        for _ in range(20):
            response=self.client.get("/compras/pedidos/ORD-HISTORIC/entrega?account_id=999&profile_id=999&password=hacked",headers=headers)
            self.assertEqual(response.status_code,200)
        conn=self._conn();after={t:[tuple(x) for x in conn.execute("SELECT * FROM "+t)] for t in tables};events=conn.execute("SELECT COUNT(*) FROM customer_delivery_events").fetchone()[0];conn.close()
        self.assertEqual(before,after);self.assertEqual(events,40)

    def test_telemetria_es_acotada_no_sensible_y_rechaza_campos_libres(self):
        headers=self._auth();ok=self.client.post("/compras/pedidos/ORD-HISTORIC/telemetria-entrega",json={"event":"client_delivery_rendered","safe_code":"ok"},headers=headers)
        bad=self.client.post("/compras/pedidos/ORD-HISTORIC/telemetria-entrega",json={"event":"client_error","safe_code":"secret-password"},headers=headers)
        extra=self.client.post("/compras/pedidos/ORD-HISTORIC/telemetria-entrega",json={"event":"client_error","safe_code":"unknown","password":"leak"},headers=headers)
        self.assertEqual((ok.status_code,bad.status_code,extra.status_code),(204,400,400))
        conn=self._conn();columns={x[1] for x in conn.execute("PRAGMA table_info(customer_delivery_events)")};rows=[tuple(x) for x in conn.execute("SELECT * FROM customer_delivery_events")];conn.close()
        self.assertTrue(columns.isdisjoint({"correo","email","customer_email","contrasena","pin","guest_token","guest_session_hash","cookie","response_body"}))
        serialized=repr(rows)
        for forbidden in ("netflix@example.test","secret-password","4321",self.owner_token,self.owner_hash):self.assertNotIn(forbidden,serialized)

    def test_headers_no_cache_y_frontend_no_persiste_credenciales(self):
        response=self._lookup("ORD-HISTORIC")
        for key,value in (("Cache-Control","no-store"),("Pragma","no-cache"),("Referrer-Policy","no-referrer"),("X-Content-Type-Options","nosniff"),("Vary","Cookie")):self.assertIn(value,response.headers[key])
        lookup=Path("static/js/customer-order-lookup.js").read_text(encoding="utf-8")
        payment=Path("static/js/customer-payment-result.js").read_text(encoding="utf-8")
        self.assertNotIn("localStorage.setItem",lookup+payment);self.assertNotIn("sessionStorage",lookup+payment)
        self.assertNotIn("account_id",lookup);self.assertNotIn("profile_id",lookup)
        for event in ("client_result_loaded","client_polling_started","client_paid_observed","client_fulfilled_observed","client_delivery_requested","client_delivery_received","client_delivery_rendered","client_error"):self.assertIn(event,payment)


if __name__ == "__main__": unittest.main()
