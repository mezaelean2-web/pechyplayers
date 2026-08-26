try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import concurrent.futures
import os
import sqlite3
import tempfile
import unittest

import customer_fulfillment as fulfillment
import customer_fulfillment_rules as rules
import database


class CustomerFulfillmentPhase2C2Test(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db");os.close(fd);self.previous=database.DB;database.DB=self.path
        conn=sqlite3.connect(self.path)
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT,plan TEXT);
          INSERT INTO productos VALUES(1,'Apple TV','Cuenta'),(2,'Netflix','Perfil'),(3,'Max','Perfil');
          CREATE TABLE customer_orders(id INTEGER PRIMARY KEY,public_order_id TEXT UNIQUE,status TEXT,
            customer_first_name TEXT,customer_last_name TEXT,customer_whatsapp TEXT);
          CREATE TABLE customer_order_lines(id INTEGER PRIMARY KEY,order_id INTEGER,line_number INTEGER,
            source_plan_id INTEGER,product_name TEXT,plan_name TEXT);
          CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY,nombre TEXT,telefono TEXT,telefono_normalizado TEXT,
            fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT,contrasena TEXT,pin TEXT,
            modalidad TEXT,estado TEXT,nombre_cliente TEXT,cliente_id INTEGER,telefono TEXT,fecha_entrega TEXT,
            dias_cuenta INTEGER,fecha_vencimiento TEXT,duracion_unidad_dias INTEGER,
            fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER,nombre_perfil TEXT,pin TEXT,
            estado TEXT,nombre_cliente TEXT,cliente_id INTEGER,telefono TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,
            fecha_vencimiento TEXT,orden INTEGER,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,cuenta_id INTEGER,tipo TEXT,descripcion TEXT,
            estado_anterior TEXT,estado_nuevo TEXT,cliente_nombre TEXT,fecha TEXT DEFAULT CURRENT_TIMESTAMP);
          CREATE TABLE reseller_plan_inventory_rules(id INTEGER PRIMARY KEY,plan_id INTEGER UNIQUE,
            plataforma TEXT,tipo_unidad TEXT,duracion_dias INTEGER,activo INTEGER);
          CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,cuenta_id INTEGER,perfil_id INTEGER,
            estado_persistido TEXT);
          CREATE TABLE reseller_wallet_transactions(id INTEGER PRIMARY KEY,monto INTEGER);
          INSERT INTO nube_cuentas VALUES(1,'APPLE TV','apple@example.test','secret-a','1111','cuenta_completa','disponible','',NULL,'','',0,'',NULL,CURRENT_TIMESTAMP);
          INSERT INTO nube_cuentas VALUES(2,'Netflix','netflix@example.test','secret-n','','perfiles','disponible','',NULL,'','',0,'',NULL,CURRENT_TIMESTAMP);
          INSERT INTO nube_cuentas VALUES(3,'Max','max@example.test','secret-m','','perfiles','disponible','',NULL,'','',0,'',NULL,CURRENT_TIMESTAMP);
          INSERT INTO nube_perfiles VALUES(20,2,'Uno','2222','disponible','',NULL,'','',0,'',1,CURRENT_TIMESTAMP);
          INSERT INTO nube_perfiles VALUES(21,2,'Dos','3333','disponible','',NULL,'','',0,'',2,CURRENT_TIMESTAMP);
          INSERT INTO nube_perfiles VALUES(30,3,'Max 1','4444','disponible','',NULL,'','',0,'',1,CURRENT_TIMESTAMP);
        """);conn.commit();conn.close();rules.initialize_schema();fulfillment.initialize_schema()

    def tearDown(self):
        database.DB=self.previous
        for suffix in ("","-wal","-shm"):
            try:os.remove(self.path+suffix)
            except FileNotFoundError:pass

    def execute(self,sql,args=()):
        conn=sqlite3.connect(self.path);cur=conn.execute(sql,args);conn.commit();value=cur.lastrowid;conn.close();return value
    def scalar(self,sql,args=()):
        conn=sqlite3.connect(self.path)
        try:return conn.execute(sql,args).fetchone()[0]
        finally:conn.close()
    def rows(self,sql,args=()):
        conn=sqlite3.connect(self.path)
        try:return conn.execute(sql,args).fetchall()
        finally:conn.close()
    def order(self,status="paid",plans=(1,)):
        number=self.scalar("SELECT COUNT(*) FROM customer_orders")+1
        oid=self.execute("INSERT INTO customer_orders(public_order_id,status,customer_first_name,customer_last_name,customer_whatsapp) VALUES(?,?,?,?,?)",(f"ORD-T{number}",status,"Ana","Perez","+573001234567"))
        for index,plan in enumerate(plans,1):
            names={1:("Apple TV","Cuenta"),2:("Netflix","Perfil"),3:("Max","Perfil")}[plan]
            self.execute("INSERT INTO customer_order_lines(order_id,line_number,source_plan_id,product_name,plan_name) VALUES(?,?,?,?,?)",(oid,index,plan,*names))
        return oid
    def rule(self,plan,platform,unit,active=True): return rules.guardar_regla(plan,platform,unit,30,active)

    def test_only_paid_and_rules_fail_closed(self):
        pending=self.order("pending_payment");self.assertEqual(fulfillment.fulfill_customer_order(pending)["code"],"order_not_paid")
        paid=self.order();self.assertEqual(fulfillment.fulfill_customer_order(paid)["code"],"rule_missing")
        self.rule(1,"APPLE TV","cuenta",False);self.assertEqual(fulfillment.fulfill_customer_order(paid)["code"],"rule_inactive")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM customer_order_fulfillment_lines"),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),0)

    def test_account_fulfilled_once_after_twenty_calls_without_secret_snapshot(self):
        self.rule(1,"apple tv","cuenta");oid=self.order()
        results=[fulfillment.fulfill_customer_order(oid) for _ in range(20)]
        self.assertEqual(results[0]["status"],"fulfilled");self.assertTrue(all(x["status"]=="fulfilled" for x in results))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM customer_order_fulfillment_lines"),1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),1)
        columns={x[1] for x in self.rows("PRAGMA table_info(customer_order_fulfillment_lines)")}
        self.assertTrue(columns.isdisjoint({"correo","contrasena","pin","password"}))

    def test_profile_and_quantity_two_use_distinct_units(self):
        self.rule(2,"Netflix","perfil");oid=self.order(plans=(2,2))
        self.assertEqual(fulfillment.fulfill_customer_order(oid)["status"],"fulfilled")
        self.assertEqual([x[0] for x in self.rows("SELECT nube_profile_id FROM customer_order_fulfillment_lines ORDER BY order_line_id")],[20,21])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),2)

    def test_multiline_missing_stock_is_all_or_nothing(self):
        self.rule(1,"APPLE TV","cuenta");self.rule(2,"Netflix","perfil");oid=self.order(plans=(1,2,2,2))
        result=fulfillment.fulfill_customer_order(oid)
        self.assertEqual((result["status"],result["code"]),("pending","inventory_insufficient"))
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM customer_order_fulfillment_lines"),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_cuentas WHERE estado='activa'"),0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='activa'"),0)

    def test_failures_after_assignment_or_movement_roll_back_all(self):
        self.rule(2,"Netflix","perfil")
        for point in ("after_first_assignment","after_movement"):
            oid=self.order(plans=(2,));result=fulfillment.fulfill_customer_order(oid,failure_injection=point)
            self.assertEqual(result["status"],"review")
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM customer_order_fulfillment_lines"),0)
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),0)
            self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_perfiles WHERE estado='activa'"),0)

    def test_two_concurrent_orders_never_share_account(self):
        self.rule(1,"APPLE TV","cuenta");orders=[self.order(),self.order()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(fulfillment.fulfill_customer_order,orders))
        self.assertEqual(sorted(x["status"] for x in results),["fulfilled","pending"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM customer_order_fulfillment_lines"),1)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM nube_movimientos"),1)

    def test_reseller_authorities_wallet_and_purchases_are_untouched(self):
        self.execute("INSERT INTO reseller_plan_inventory_rules VALUES(1,1,'APPLE TV','cuenta',90,1)")
        self.execute("INSERT INTO reseller_wallet_transactions VALUES(1,777)")
        before=(self.rows("SELECT * FROM reseller_plan_inventory_rules"),self.rows("SELECT * FROM reseller_wallet_transactions"),self.rows("SELECT * FROM reseller_purchases"))
        self.rule(1,"APPLE TV","cuenta");fulfillment.fulfill_customer_order(self.order())
        after=(self.rows("SELECT * FROM reseller_plan_inventory_rules"),self.rows("SELECT * FROM reseller_wallet_transactions"),self.rows("SELECT * FROM reseller_purchases"))
        self.assertEqual(before,after)


if __name__=="__main__":unittest.main()
