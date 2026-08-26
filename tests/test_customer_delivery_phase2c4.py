try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import customer_bold_payments
import customer_fulfillment
import database
from app import app


class CustomerDeliveryPhase2C4Test(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db");os.close(fd);self.previous=database.DB;database.DB=self.path
        conn=sqlite3.connect(self.path)
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE customer_orders(id INTEGER PRIMARY KEY,public_order_id TEXT UNIQUE,status TEXT,
            guest_session_hash TEXT,item_count INTEGER,expires_at TEXT);
          CREATE TABLE customer_order_lines(id INTEGER PRIMARY KEY,order_id INTEGER,line_number INTEGER,
            source_plan_id INTEGER,product_name TEXT,plan_name TEXT);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT,contrasena TEXT,pin TEXT,
            modalidad TEXT,estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,fecha_vencimiento TEXT,dias_cuenta INTEGER);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER,nombre_perfil TEXT,pin TEXT,
            estado TEXT,nombre_cliente TEXT,fecha_entrega TEXT,fecha_vencimiento TEXT,dias_cuenta INTEGER);
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,cuenta_id INTEGER,tipo TEXT);
          CREATE TABLE customer_checkout_sessions(session_hash TEXT PRIMARY KEY,current_order_id INTEGER,
            updated_at TEXT NOT NULL,expires_at TEXT NOT NULL);
        """);conn.commit();conn.close();customer_fulfillment.initialize_schema();customer_bold_payments.initialize_schema()
        app.config.update(TESTING=True,SECRET_KEY="delivery-test");self.client=app.test_client();self.guest="a"*64;self.other="b"*64
        self._inventory();self.full_order=self._order("ORD-FULL","paid",self.guest,[(1,10,"Apple TV","Cuenta")],"fulfilled")
        self.profile_order=self._order("ORD-PROFILE","paid",self.other,[(2,200,"Prime Video","Perfil")],"fulfilled")

    def tearDown(self):
        database.DB=self.previous
        for suffix in ("","-wal","-shm"):
            try:os.remove(self.path+suffix)
            except FileNotFoundError:pass

    def _conn(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;return c
    def _inventory(self):
        c=self._conn();c.execute("INSERT INTO nube_cuentas VALUES(10,'APPLE TV','apple@test','pass-a','9876','cuenta_completa','activa','Cliente','2026-08-26','2026-09-25',30)")
        c.execute("INSERT INTO nube_cuentas VALUES(20,'PRIME VIDEO','prime@test','pass-p','','perfiles','disponible','','','',0)")
        c.execute("INSERT INTO nube_cuentas VALUES(21,'NETFLIX','netflix@test','pass-n','','perfiles','disponible','','','',0)")
        c.execute("INSERT INTO nube_cuentas VALUES(11,'APPLE TV','apple-two@test','pass-b','','cuenta_completa','activa','Cliente','2026-08-26','2026-09-25',30)")
        c.execute("INSERT INTO nube_perfiles VALUES(200,20,'PERFIL 2','1234','activa','Cliente','2026-08-26','2026-09-25',30)")
        c.execute("INSERT INTO nube_perfiles VALUES(201,20,'PERFIL 3','','activa','Cliente','2026-08-26','2026-09-25',30)")
        c.execute("INSERT INTO nube_perfiles VALUES(210,21,'NIÑOS','5555','activa','Cliente','2026-08-26','2026-09-25',30)");c.commit();c.close()
    def _order(self,public,status,guest,units,fulfillment_status=None):
        c=self._conn();cur=c.execute("INSERT INTO customer_orders(public_order_id,status,guest_session_hash,item_count,expires_at) VALUES(?,?,?,?,?)",(public,status,guest,len(units),'2030-01-01T00:00:00Z'));oid=cur.lastrowid
        line_ids=[]
        for number,(kind,unit_id,product,plan) in enumerate(units,1):
            cur=c.execute("INSERT INTO customer_order_lines(order_id,line_number,source_plan_id,product_name,plan_name) VALUES(?,?,?,?,?)",(oid,number,number,product,plan));line_ids.append(cur.lastrowid)
        if fulfillment_status:
            cur=c.execute("INSERT INTO customer_order_fulfillments(order_id,status,attempt_count,fulfilled_at) VALUES(?,?,1,?)",(oid,fulfillment_status,'2026-08-26T00:00:00Z' if fulfillment_status=='fulfilled' else None));fid=cur.lastrowid
            if fulfillment_status=='fulfilled':
                for line_id,(kind,unit_id,product,plan) in zip(line_ids,units):
                    account=unit_id if kind==1 else c.execute("SELECT cuenta_id FROM nube_perfiles WHERE id=?",(unit_id,)).fetchone()[0]
                    c.execute("INSERT INTO customer_order_fulfillment_lines(fulfillment_id,order_line_id,nube_account_id,nube_profile_id,tipo_unidad,assigned_at,expires_at) VALUES(?,?,?,?,?,?,?)",(fid,line_id,account,None if kind==1 else unit_id,'cuenta' if kind==1 else 'perfil','2026-08-26T00:00:00Z','2026-09-25'))
        c.commit();c.close();return oid
    def _auth(self,token="guest-a"):
        with self.client.session_transaction() as s:s["csrf_customer_checkout"]="csrf";s["customer_checkout_guest_token"]=token
        return {"X-CSRF-Token":"csrf"}
    def _set_hash(self,order_id,token):
        c=self._conn();c.execute("UPDATE customer_orders SET guest_session_hash=? WHERE id=?",(hashlib.sha256(token.encode()).hexdigest(),order_id));c.commit();c.close()
    def _get(self,public,headers=None,query=""):return self.client.get(f"/compras/pedidos/{public}/entrega{query}",headers=headers or {})

    def test_owner_gets_account_only_and_security_headers(self):
        self._set_hash(self.full_order,"guest-a");response=self._get("ORD-FULL",self._auth());data=response.get_json()["delivery"]
        self.assertEqual(response.status_code,200);self.assertIn("no-store",response.headers["Cache-Control"]);self.assertIn("private",response.headers["Cache-Control"])
        self.assertEqual(response.headers["Referrer-Policy"],"no-referrer");self.assertEqual(len(data["deliveries"]),1)
        unit=data["deliveries"][0];self.assertEqual((unit["platform"],unit["username"],unit["password"],unit["pin"]),("APPLE TV","apple@test","pass-a","9876"))
        self.assertNotIn("nube_account_id",unit);self.assertNotIn("nube_profile_id",unit)

    def test_public_id_wrong_guest_and_missing_session_are_fail_closed(self):
        self._set_hash(self.full_order,"guest-a")
        self.assertEqual(self._get("ORD-FULL",self._auth("intruder")).status_code,404)
        self.client=app.test_client();self.assertEqual(self._get("ORD-FULL").status_code,404)

    def test_non_deliverable_states_never_expose_credentials(self):
        for index,(order_status,fulfill_status) in enumerate((("pending_payment",None),("cancelled",None),("paid",None),("paid","pending"),("paid","review")),1):
            oid=self._order(f"ORD-NO-{index}",order_status,self.guest,[(1,10,"Apple","Cuenta")],fulfill_status)
            response=self._get(f"ORD-NO-{index}",self._auth())
            self.assertEqual(response.status_code,404);body=response.get_data(as_text=True)
            self.assertNotIn("apple@test",body);self.assertNotIn("pass-a",body);self.assertNotIn("9876",body)

    def test_profile_uses_parent_credentials_and_profile_pin(self):
        self._set_hash(self.profile_order,"guest-b");unit=self._get("ORD-PROFILE",self._auth("guest-b")).get_json()["delivery"]["deliveries"][0]
        self.assertEqual((unit["username"],unit["password"],unit["profile"],unit["pin"]),("prime@test","pass-p","PERFIL 2","1234"))

    def test_null_pin_multiple_lines_and_distinct_units(self):
        oid=self._order("ORD-MULTI","paid",self.guest,[(2,201,"Prime","Perfil"),(2,210,"Netflix","Perfil"),(1,11,"Apple","Cuenta")],"fulfilled")
        self._set_hash(oid,"guest-a")
        units=self._get("ORD-MULTI",self._auth()).get_json()["delivery"]["deliveries"]
        self.assertEqual(len(units),3);self.assertIsNone(units[0]["pin"]);self.assertEqual(units[1]["pin"],"5555");self.assertEqual(units[2]["username"],"apple-two@test")

    def test_inventory_ids_in_query_are_ignored(self):
        self._set_hash(self.full_order,"guest-a");unit=self._get("ORD-FULL",self._auth(),"?account_id=20&profile_id=200&password=hacked").get_json()["delivery"]["deliveries"][0]
        self.assertEqual((unit["username"],unit["password"]),("apple@test","pass-a"))

    def test_repeated_get_is_read_only_and_does_not_log_credentials(self):
        self._set_hash(self.full_order,"guest-a");c=self._conn();before={t:[tuple(x) for x in c.execute('select * from '+t)] for t in ('customer_orders','customer_order_fulfillments','customer_order_fulfillment_lines','nube_cuentas','nube_perfiles','nube_movimientos')};c.close()
        with mock.patch.object(app.logger,"error") as error_log,mock.patch.object(app.logger,"exception") as exception_log:
            for _ in range(5):self.assertEqual(self._get("ORD-FULL",self._auth()).status_code,200)
        error_log.assert_not_called();exception_log.assert_not_called();c=self._conn();after={t:[tuple(x) for x in c.execute('select * from '+t)] for t in before};c.close();self.assertEqual(before,after)

    def test_status_contains_fulfilled_but_never_credentials(self):
        self._set_hash(self.full_order,"guest-a");response=self.client.get("/compras/pedidos/ORD-FULL/estado",headers=self._auth());body=response.get_data(as_text=True)
        self.assertTrue(response.get_json()["fulfilled"]);self.assertNotIn("apple@test",body);self.assertNotIn("pass-a",body);self.assertNotIn("9876",body)

    def test_two_buyers_cannot_cross_access(self):
        self._set_hash(self.full_order,"guest-a");self._set_hash(self.profile_order,"guest-b")
        self.assertEqual(self._get("ORD-PROFILE",self._auth("guest-a")).status_code,404)
        self.assertEqual(self._get("ORD-FULL",self._auth("guest-b")).status_code,404)

    def test_entrega_historica_no_depende_del_pedido_activo(self):
        self._set_hash(self.full_order,"guest-a")
        new_id=self._order("ORD-NEW","pending_payment",hashlib.sha256(b"guest-a").hexdigest(),[(1,11,"Apple","Cuenta")])
        c=self._conn();c.execute("INSERT INTO customer_checkout_sessions VALUES(?,?,?,?)",(hashlib.sha256(b"guest-a").hexdigest(),new_id,"2026-08-26T01:00:00Z","2030-01-01T00:00:00Z"));c.commit();c.close()
        self.assertEqual(self._get("ORD-FULL",self._auth("guest-a")).status_code,200)
        self.assertEqual(self._get("ORD-FULL",self._auth("intruder")).status_code,404)
        self.client=app.test_client();self.assertEqual(self._get("ORD-FULL").status_code,404)

    def test_frontend_copy_polling_and_cart_clear_are_server_gated(self):
        source=Path("static/js/customer-payment-result.js").read_text(encoding="utf-8")
        self.assertIn('data.fulfilled',source);self.assertIn('/entrega',source);self.assertIn('navigator.clipboard.writeText',source)
        self.assertIn('localStorage.removeItem("pechy.customerCart.v1")',source);self.assertNotIn('bold-tx-status',source)
        self.assertIn('if(unit.pin)',source);self.assertIn('maxAttempts=30',source);self.assertIn('setTimeout(poll,2000)',source)


if __name__=="__main__":unittest.main()
