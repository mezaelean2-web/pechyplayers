try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib,imaplib,io,json,os,socket,sqlite3,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock,patch
from werkzeug.security import check_password_hash

import database
from mailbox_bindings import initialize_schema
from private_email_credentials import ProviderCredentialResolver
from private_email_pilot_utility import ControlledMailboxPilotUtility,PilotUtilityError


BUNDLE=json.dumps({"pechy_pilot":{"username":"pilot@example.invalid","password":"IMAP_ONLY_SECRET"}})
NOW=datetime(2026,8,28,12,0,tzinfo=timezone.utc)


class ControlledMailboxPilotUtilityTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(); self.db=Path(self.directory.name)/"pilot.db"
        self.manifest=Path(self.directory.name)/"manifest.json"; self.old_db=database.DB
        conn=sqlite3.connect(self.db)
        conn.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE revendedores(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,negocio TEXT,correo TEXT UNIQUE,
          telefono TEXT,password_hash TEXT,estado TEXT,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE reseller_wallets(id INTEGER PRIMARY KEY AUTOINCREMENT,revendedor_id INTEGER UNIQUE,saldo INTEGER);
        CREATE TABLE revendedores_actividad(id INTEGER PRIMARY KEY AUTOINCREMENT,revendedor_id INTEGER,tipo TEXT,
          descripcion TEXT,actor TEXT);
        CREATE TABLE nube_clientes(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,telefono TEXT,correo TEXT,notas TEXT,activo INTEGER);
        CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY AUTOINCREMENT,plataforma TEXT,correo TEXT,contrasena TEXT,pin TEXT,
          tipo_cuenta TEXT,cliente_id INTEGER,nombre_cliente TEXT,telefono TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,
          fecha_vencimiento TEXT,estado TEXT,notas TEXT,origen TEXT,modalidad TEXT,cantidad_perfiles INTEGER,
          duracion_unidad_dias INTEGER,fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER,estado TEXT,cliente_id INTEGER,
          nombre_cliente TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,fecha_vencimiento TEXT,fecha_actualizacion TEXT);
        CREATE TABLE nube_movimientos(id INTEGER PRIMARY KEY AUTOINCREMENT,cuenta_id INTEGER,tipo TEXT,descripcion TEXT,
          estado_nuevo TEXT,cliente_nombre TEXT);
        CREATE TABLE nube_reemplazos(id INTEGER PRIMARY KEY,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER);
        CREATE TABLE nube_reemplazos_perfiles(id INTEGER PRIMARY KEY,perfil_anterior_id INTEGER,perfil_nuevo_id INTEGER,
          cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER);
        CREATE TABLE productos(id INTEGER PRIMARY KEY);
        CREATE TABLE reseller_plan_inventory_rules(plan_id INTEGER PRIMARY KEY,plataforma TEXT,tipo_unidad TEXT,
          duracion_dias INTEGER,activo INTEGER);
        CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,revendedor_id INTEGER,plan_id INTEGER,
          cuenta_id INTEGER,perfil_id INTEGER,tipo_unidad TEXT,operacion_origen TEXT,fecha_compra TEXT,
          fecha_activacion TEXT,fecha_vencimiento TEXT,dias_contratados INTEGER,precio_pagado INTEGER,
          estado_persistido TEXT,cortada_at TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE reseller_purchase_events(id INTEGER PRIMARY KEY,purchase_id INTEGER);
        CREATE TABLE reseller_purchase_operations(id INTEGER PRIMARY KEY,purchase_id INTEGER);
        CREATE TABLE reseller_mailbox_requests(id INTEGER PRIMARY KEY,reseller_purchase_id INTEGER);
        CREATE TABLE reseller_authorized_message_deliveries(id INTEGER PRIMARY KEY,reseller_purchase_id INTEGER);
        CREATE TABLE reseller_message_audit_events(id INTEGER PRIMARY KEY,reseller_purchase_id INTEGER);
        INSERT INTO productos VALUES(1);
        INSERT INTO reseller_plan_inventory_rules VALUES(1,'Pilot Platform','cuenta',30,1);
        """); initialize_schema(conn); conn.close()
        self.resolver=ProviderCredentialResolver(bundle=BUNDLE)
        self.utility=ControlledMailboxPilotUtility(db_path=self.db,pilot_run_id="pp-5b3b-offline1",
          credential_resolver=self.resolver,plan_id=1,manifest_path=self.manifest)
        self.net=patch.object(socket,"create_connection",Mock(side_effect=AssertionError("network"))); self.net_mock=self.net.start()
        self.imap=patch.object(imaplib,"IMAP4_SSL",Mock(side_effect=AssertionError("imap"))); self.imap_mock=self.imap.start()

    def tearDown(self):
        self.net.stop(); self.imap.stop(); database.DB=self.old_db; self.directory.cleanup()

    def query(self,sql,args=()):
        conn=sqlite3.connect(self.db); conn.row_factory=sqlite3.Row
        try: return conn.execute(sql,args).fetchall()
        finally: conn.close()

    def apply(self,**kw): return self.utility.apply(now=NOW,**kw)

    def test_plan_is_read_only_safe_and_zero_network(self):
        before=self.db.stat().st_mtime_ns; result=self.utility.plan(); after=self.db.stat().st_mtime_ns
        self.assertTrue(result["read_only"]); self.assertEqual(before,after); self.assertFalse(self.manifest.exists())
        self.assertNotIn("pilot@example",repr(result)); self.net_mock.assert_not_called(); self.imap_mock.assert_not_called()

    def test_apply_creates_dedicated_full_account_purchase_authorization_binding(self):
        result=self.apply(); self.assertEqual(result["binding_version"],1); self.assertEqual(result["state"],"active")
        self.assertEqual(len(self.query("SELECT * FROM revendedores")),1); self.assertEqual(len(self.query("SELECT * FROM reseller_wallets")),1)
        account=self.query("SELECT * FROM nube_cuentas")[0]; self.assertEqual(account["modalidad"],"cuenta_completa")
        self.assertEqual(len(self.query("SELECT * FROM nube_perfiles")),0)
        purchase=self.query("SELECT * FROM reseller_purchases")[0]
        self.assertEqual((purchase["tipo_unidad"],purchase["precio_pagado"],purchase["estado_persistido"]),("cuenta",0,"active"))
        binding=self.query("SELECT * FROM reseller_mailbox_bindings")[0]
        self.assertEqual((binding["provider"],binding["provider_config_id"],binding["folder_key"],binding["binding_version"]),
          ("private_email","pechy_pilot","INBOX",1))

    def test_reseller_password_is_independent(self):
        self.apply(); stored=self.query("SELECT password_hash FROM revendedores")[0][0]
        self.assertFalse(check_password_hash(stored,"IMAP_ONLY_SECRET"))

    def test_manifest_contains_only_safe_fields(self):
        self.apply(); raw=self.manifest.read_text(encoding="utf-8"); data=json.loads(raw)
        for forbidden in ("email","username","password","bundle","otp","code","pilot@example","IMAP_ONLY_SECRET"):
            self.assertNotIn(forbidden,raw.lower())
        self.assertEqual(data["pilot_run_id"],"pp-5b3b-offline1")

    def test_failure_after_base_is_compensated(self):
        with self.assertRaises(PilotUtilityError): self.apply(fail_after_base=True)
        for table in ("revendedores","reseller_wallets","nube_clientes","nube_cuentas","reseller_purchases","reseller_mailbox_bindings"):
            self.assertEqual(len(self.query(f"SELECT * FROM {table}")),0)

    def test_second_apply_and_collision_fail_closed(self):
        self.apply()
        with self.assertRaises(PilotUtilityError) as caught: self.apply()
        self.assertEqual(caught.exception.safe_code,"pilot_run_collision")

    def test_explicit_db_and_provider_are_required(self):
        with self.assertRaises(PilotUtilityError) as caught:
            ControlledMailboxPilotUtility(db_path=None,pilot_run_id="pp-5b3b-offline1",credential_resolver=self.resolver,plan_id=1)
        self.assertEqual(caught.exception.safe_code,"explicit_db_required")
        bad=ControlledMailboxPilotUtility(db_path=self.db,pilot_run_id="pp-5b3b-other01",
          credential_resolver=ProviderCredentialResolver(bundle="{}"),plan_id=1)
        with self.assertRaises(PilotUtilityError) as caught: bad.plan()
        self.assertEqual(caught.exception.safe_code,"provider_config_invalid")

    def test_teardown_before_messages_physically_deletes(self):
        self.apply(); result=self.utility.teardown(now=NOW); self.assertEqual(result["state"],"deleted")
        self.assertEqual(len(self.query("SELECT * FROM revendedores")),0); self.assertEqual(len(self.query("SELECT * FROM reseller_mailbox_bindings")),0)

    def test_teardown_after_activity_retires_and_preserves(self):
        data=self.apply(); conn=sqlite3.connect(self.db)
        conn.execute("INSERT INTO reseller_mailbox_requests(reseller_purchase_id) VALUES(?)",(data["purchase_id"],))
        conn.execute("INSERT INTO reseller_message_audit_events(reseller_purchase_id) VALUES(?)",(data["purchase_id"],)); conn.commit(); conn.close()
        result=self.utility.teardown(now=NOW); self.assertEqual(result["state"],"retired")
        self.assertEqual(self.query("SELECT enabled FROM reseller_mailbox_bindings")[0][0],0)
        self.assertEqual(self.query("SELECT estado FROM revendedores")[0][0],"bloqueado")
        self.assertEqual(len(self.query("SELECT * FROM reseller_message_audit_events")),1)

    def test_unexpected_dependency_and_manifest_mismatch_fail_closed(self):
        data=self.apply(); conn=sqlite3.connect(self.db)
        conn.execute("INSERT INTO reseller_purchase_events(id,purchase_id) VALUES(1,?)",(data["purchase_id"],)); conn.commit(); conn.close()
        with self.assertRaises(PilotUtilityError) as caught: self.utility.teardown(now=NOW)
        self.assertEqual(caught.exception.safe_code,"unexpected_dependencies")
        manifest=json.loads(self.manifest.read_text()); manifest["account_id"]+=999
        self.manifest.write_text(json.dumps(manifest),encoding="utf-8")
        with self.assertRaises(PilotUtilityError) as caught: self.utility.teardown(now=NOW)
        self.assertEqual(caught.exception.safe_code,"manifest_mismatch")

    def test_no_sensitive_output_and_zero_network(self):
        stdout=io.StringIO(); stderr=io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr): self.apply()
        output=stdout.getvalue()+stderr.getvalue()
        for forbidden in ("pilot@example.invalid","IMAP_ONLY_SECRET",BUNDLE): self.assertNotIn(forbidden,output)
        self.net_mock.assert_not_called(); self.imap_mock.assert_not_called()


if __name__=="__main__": unittest.main()
