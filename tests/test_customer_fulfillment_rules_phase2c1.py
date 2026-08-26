try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from dotenv import load_dotenv

import customer_fulfillment_rules as rules
import database
from app import app


class CustomerFulfillmentRulesPhase2C1Test(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd)
        self.previous=database.DB; database.DB=self.path
        conn=sqlite3.connect(self.path)
        conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE productos(id INTEGER PRIMARY KEY,nombre TEXT,plan TEXT);
            INSERT INTO productos VALUES(1,'Netflix','Perfil');
            CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,modalidad TEXT,
              estado TEXT,nombre_cliente TEXT,duracion_unidad_dias INTEGER,fecha_vencimiento TEXT,fecha_entrega TEXT);
            CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER,estado TEXT,
              nombre_cliente TEXT,orden INTEGER,fecha_entrega TEXT);
            CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY,cuenta_id INTEGER,tipo TEXT);
            INSERT INTO nube_cuentas VALUES(1,'Nueva Plataforma','perfiles','disponible','',30,'2030-01-01','');
            INSERT INTO nube_perfiles VALUES(1,1,'disponible','',1,'');
            CREATE TABLE reseller_plan_inventory_rules(id INTEGER PRIMARY KEY,plan_id INTEGER UNIQUE,
              plataforma TEXT,tipo_unidad TEXT,duracion_dias INTEGER,activo INTEGER);
            INSERT INTO reseller_plan_inventory_rules VALUES(1,1,'Nueva Plataforma','perfil',30,1);
            CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,cuenta_id INTEGER,perfil_id INTEGER,
              estado_persistido TEXT);
        """); conn.commit(); conn.close(); rules.initialize_schema()
        app.config.update(TESTING=True,SECRET_KEY="rules-test")
        self.client=app.test_client()

    def tearDown(self):
        database.DB=self.previous
        for suffix in ("","-wal","-shm"):
            try: os.remove(self.path+suffix)
            except FileNotFoundError: pass

    def rows(self,sql,args=()):
        conn=sqlite3.connect(self.path)
        try:return conn.execute(sql,args).fetchall()
        finally:conn.close()

    def test_schema_idempotent_empty_and_new_rule_inactive(self):
        rules.initialize_schema(); rules.initialize_schema()
        self.assertEqual(self.rows("SELECT COUNT(*) FROM customer_plan_fulfillment_rules")[0][0],0)
        saved=rules.guardar_regla(1,"  nueva plataforma ","perfil",30,False)
        self.assertEqual((saved["plataforma"],saved["activo"]),("Nueva Plataforma",0))
        self.assertIsNone(rules.obtener_regla(1))

    def test_validations_are_fail_closed(self):
        for args,exception in [((99,"Nueva Plataforma","perfil",30,False),LookupError),
          ((1,"","perfil",30,False),ValueError),((1,"Nueva Plataforma","otro",30,False),ValueError),
          ((1,"Nueva Plataforma","perfil",0,False),ValueError),((1,"Nueva Plataforma","perfil",30,"true"),ValueError)]:
            with self.assertRaises(exception): rules.guardar_regla(*args)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM customer_plan_fulfillment_rules")[0][0],0)

    def test_unique_plan_and_channels_are_independent(self):
        rules.guardar_regla(1,"Nueva Plataforma","perfil",30,False)
        rules.guardar_regla(1,"Nueva Plataforma","perfil",60,True)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM customer_plan_fulfillment_rules")[0][0],1)
        self.assertEqual(self.rows("SELECT duracion_dias FROM reseller_plan_inventory_rules")[0][0],30)
        conn=sqlite3.connect(self.path);conn.execute("UPDATE reseller_plan_inventory_rules SET duracion_dias=90");conn.commit();conn.close()
        self.assertEqual(rules.obtener_regla(1,True)["duracion_dias"],60)

    def test_explicit_copy_is_independent_and_inactive(self):
        copied=rules.copiar_desde_reseller(1)
        self.assertEqual((copied["duracion_dias"],copied["activo"]),(30,0))
        conn=sqlite3.connect(self.path);conn.execute("UPDATE reseller_plan_inventory_rules SET duracion_dias=90");conn.commit();conn.close()
        self.assertEqual(rules.obtener_regla(1,True)["duracion_dias"],30)

    def test_preview_is_read_only_and_uses_real_eligibility(self):
        rules.guardar_regla(1,"Nueva Plataforma","perfil",30,False)
        before=[self.rows("SELECT * FROM nube_cuentas"),self.rows("SELECT * FROM nube_perfiles"),self.rows("SELECT * FROM nube_movimientos")]
        self.assertEqual(rules.listar_reglas_admin()[0]["disponibles"],1)
        after=[self.rows("SELECT * FROM nube_cuentas"),self.rows("SELECT * FROM nube_perfiles"),self.rows("SELECT * FROM nube_movimientos")]
        self.assertEqual(before,after)

    def test_admin_auth_csrf_and_copy_payload(self):
        self.assertEqual(self.client.get("/admin/reglas-fulfillment-clientes").status_code,302)
        with self.client.session_transaction() as session: session["admin"]=True;session["csrf_admin"]="csrf"
        url="/admin/reglas-fulfillment-clientes/1"
        self.assertEqual(self.client.post(url,json={"plataforma":"Nueva Plataforma","tipo_unidad":"perfil","duracion_dias":30,"activo":False}).status_code,403)
        self.assertEqual(self.client.post(url,json={"plataforma":"Nueva Plataforma","tipo_unidad":"perfil","duracion_dias":30,"activo":False},headers={"X-CSRF-Token":"csrf"}).status_code,200)
        copy=url+"/copiar-reseller"
        self.assertEqual(self.client.post(copy,json={"perfil_id":1},headers={"X-CSRF-Token":"csrf"}).status_code,400)
        self.assertEqual(self.client.post(copy,json={},headers={"X-CSRF-Token":"csrf"}).status_code,200)
        self.assertEqual(rules.obtener_regla(1,True)["activo"],0)

    def test_dotenv_loads_missing_values_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/".env";path.write_text("BOLD_ENV=production\nBOLD_IDENTITY_KEY=from-file\nBOLD_SECRET_KEY=secret-file\n",encoding="utf-8")
            old={key:os.environ.get(key) for key in ("BOLD_ENV","BOLD_IDENTITY_KEY","BOLD_SECRET_KEY")}
            try:
                for key in old: os.environ.pop(key,None)
                os.environ["BOLD_IDENTITY_KEY"]="injected"
                load_dotenv(path,override=False)
                self.assertEqual(os.environ["BOLD_ENV"],"production")
                self.assertEqual(os.environ["BOLD_SECRET_KEY"],"secret-file")
                self.assertEqual(os.environ["BOLD_IDENTITY_KEY"],"injected")
            finally:
                for key,value in old.items():
                    if value is None: os.environ.pop(key,None)
                    else: os.environ[key]=value


if __name__=="__main__": unittest.main()
