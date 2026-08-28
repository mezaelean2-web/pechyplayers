try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import contextlib
import imaplib
import inspect
import io
import json
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
from datetime import date
from unittest.mock import Mock, patch

import database
from mailbox_bindings import (AdministrativeMailboxBindingService,
    MailboxBindingAdminError, initialize_schema)
from private_email_credentials import ProviderCredentialResolver


TODAY=date(2026,8,27)
START="2026-08-01"
END="2026-09-30"
CONFIGS=json.dumps({
    "pechy_pilot":{"username":"pilot@example.invalid","password":"OFFLINE_PILOT_SECRET"},
    "pechy_backup":{"username":"backup@example.invalid","password":"OFFLINE_BACKUP_SECRET"},
})


class AdministrativeMailboxBindingServiceTests(unittest.TestCase):
    def setUp(self):
        descriptor,self.path=tempfile.mkstemp(suffix=".db"); os.close(descriptor)
        self.original_db=database.DB; database.DB=self.path
        conn=sqlite3.connect(self.path)
        conn.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE revendedores(id INTEGER PRIMARY KEY,nombre TEXT NOT NULL,estado TEXT NOT NULL);
          CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,revendedor_id INTEGER NOT NULL,
            cuenta_id INTEGER NOT NULL,perfil_id INTEGER,tipo_unidad TEXT NOT NULL,
            fecha_activacion TEXT,fecha_vencimiento TEXT,estado_persistido TEXT,cortada_at TEXT,updated_at TEXT);
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,modalidad TEXT,estado TEXT,cliente_id INTEGER,
            nombre_cliente TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,fecha_vencimiento TEXT,fecha_actualizacion TEXT);
          CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER NOT NULL,estado TEXT,cliente_id INTEGER,
            nombre_cliente TEXT,fecha_entrega TEXT,dias_cuenta INTEGER,fecha_vencimiento TEXT,fecha_actualizacion TEXT);
          CREATE TABLE nube_reemplazos(id INTEGER PRIMARY KEY,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER,cliente_id INTEGER);
          CREATE TABLE nube_reemplazos_perfiles(id INTEGER PRIMARY KEY,perfil_anterior_id INTEGER,
            perfil_nuevo_id INTEGER,cuenta_anterior_id INTEGER,cuenta_nueva_id INTEGER);
          INSERT INTO revendedores VALUES(1,'Uno','activo');
          INSERT INTO revendedores VALUES(2,'Dos','activo');
        """); conn.commit(); initialize_schema(conn); conn.close()
        self.resolver=ProviderCredentialResolver(bundle=CONFIGS)
        self.service=AdministrativeMailboxBindingService(self.resolver,
            approved_provider_configs={"pechy_pilot","pechy_backup"})
        self.socket_patch=patch.object(socket,"create_connection",Mock(side_effect=AssertionError("network forbidden")))
        self.imap_patch=patch.object(imaplib,"IMAP4_SSL",Mock(side_effect=AssertionError("imap forbidden")))
        self.socket_mock=self.socket_patch.start(); self.imap_mock=self.imap_patch.start()

    def tearDown(self):
        self.socket_patch.stop(); self.imap_patch.stop(); database.DB=self.original_db
        for suffix in ("-wal","-shm",""):
            try: os.remove(self.path+suffix)
            except FileNotFoundError: pass

    def execute(self,sql,params=()):
        conn=sqlite3.connect(self.path)
        try: conn.execute(sql,params); conn.commit()
        finally: conn.close()

    def account(self,account_id=10,*,mode="cuenta_completa",state="activa",reseller_id=1,assigned=True):
        label=f"Reseller #{reseller_id} - {'Uno' if reseller_id==1 else 'Dos'}" if assigned else "Otra persona"
        self.execute("INSERT INTO nube_cuentas VALUES(?,?,?,?,?,?,?,?,?)",
            (account_id,mode,state,reseller_id if assigned else 99,label,START,60,END,"account-v1"))

    def profile(self,profile_id=20,account_id=10,*,state="activa",reseller_id=1):
        label=f"Reseller #{reseller_id} - {'Uno' if reseller_id==1 else 'Dos'}"
        self.execute("INSERT INTO nube_perfiles VALUES(?,?,?,?,?,?,?,?,?)",
            (profile_id,account_id,state,reseller_id,label,START,60,END,"profile-v1"))

    def purchase(self,purchase_id=100,*,reseller_id=1,account_id=10,profile_id=None,
                 unit_type="cuenta",state="active",cut=None,end=END):
        self.execute("INSERT INTO reseller_purchases VALUES(?,?,?,?,?,?,?,?,?,?)",
            (purchase_id,reseller_id,account_id,profile_id,unit_type,START,end,state,cut,"purchase-v1"))

    def bind(self,**changes):
        args={"reseller_id":1,"reseller_purchase_id":100,"provider":"private_email",
              "provider_config_id":"pechy_pilot","folder_key":"INBOX","now":TODAY}
        args.update(changes); return self.service.create_or_replace(**args)

    def rows(self):
        conn=sqlite3.connect(self.path); conn.row_factory=sqlite3.Row
        try: return conn.execute("SELECT * FROM reseller_mailbox_bindings ORDER BY id").fetchall()
        finally: conn.close()

    def assert_closed(self,code,**changes):
        with self.assertRaises(MailboxBindingAdminError) as caught: self.bind(**changes)
        self.assertEqual(caught.exception.safe_code,code); self.assertEqual(self.rows(),[])

    def test_valid_account_initial_version_and_zero_network(self):
        self.account(); self.purchase(); binding=self.bind()
        self.assertEqual((binding.inventory_type,binding.account_id,binding.profile_id),("cuenta",10,None))
        self.assertEqual(binding.binding_version,1); self.assertTrue(binding.enabled)
        self.socket_mock.assert_not_called(); self.imap_mock.assert_not_called()

    def test_valid_profile_and_canonical_unit(self):
        self.account(mode="perfiles",state="disponible",assigned=False); self.profile(); self.purchase(profile_id=20,unit_type="perfil")
        binding=self.bind(); self.assertEqual((binding.inventory_type,binding.account_id,binding.profile_id),("perfil",10,20))

    def test_profile_from_other_account_fails_closed(self):
        self.account(10,mode="perfiles",state="disponible",assigned=False)
        self.account(11,mode="perfiles",state="disponible",assigned=False); self.profile(account_id=11)
        self.purchase(profile_id=20,unit_type="perfil"); self.assert_closed("assignment_not_authorized")

    def test_wrong_reseller_fails_closed(self):
        self.account(reseller_id=2); self.purchase(reseller_id=2)
        self.assert_closed("assignment_not_authorized")

    def test_expired_cut_and_inactive_purchases_fail_closed(self):
        for purchase_id,changes in ((100,{"end":"2026-08-20"}),(101,{"cut":"2026-08-20"}),(102,{"state":"cut"})):
            with self.subTest(purchase_id=purchase_id):
                self.account(purchase_id); self.purchase(purchase_id,account_id=purchase_id,**changes)
                with self.assertRaises(MailboxBindingAdminError): self.bind(reseller_purchase_id=purchase_id)
        self.assertEqual(self.rows(),[])

    def test_missing_and_inactive_units_fail_closed(self):
        self.purchase(); self.assert_closed("assignment_not_authorized")
        self.account(state="papelera")
        self.assert_closed("assignment_not_authorized")

    def test_provider_config_and_folder_validation(self):
        self.account(); self.purchase()
        self.assert_closed("provider_invalid",provider="smtp")
        self.assert_closed("provider_config_not_approved",provider_config_id="unknown")
        self.assert_closed("folder_invalid",folder_key="Sent")
        limited=AdministrativeMailboxBindingService(ProviderCredentialResolver(bundle="{}"))
        with self.assertRaises(MailboxBindingAdminError) as caught:
            limited.create_or_replace(reseller_id=1,reseller_purchase_id=100,provider="private_email",
                provider_config_id="pechy_pilot",folder_key="INBOX",now=TODAY)
        self.assertEqual(caught.exception.safe_code,"provider_config_invalid")
        disabled=AdministrativeMailboxBindingService(self.resolver,approved_provider_configs=set())
        with self.assertRaises(MailboxBindingAdminError) as caught:
            disabled.create_or_replace(reseller_id=1,reseller_purchase_id=100,provider="private_email",
                provider_config_id="pechy_pilot",folder_key="INBOX",now=TODAY)
        self.assertEqual(caught.exception.safe_code,"provider_config_not_approved")

    def test_identical_operation_is_idempotent(self):
        self.account(); self.purchase(); first=self.bind(); second=self.bind()
        self.assertEqual(first,second); self.assertEqual(len(self.rows()),1)

    def test_replacement_increments_version_disables_and_preserves_history(self):
        self.account(); self.purchase(); first=self.bind()
        second=self.bind(provider_config_id="pechy_backup")
        rows=self.rows(); self.assertEqual((first.binding_version,second.binding_version),(1,2))
        self.assertEqual(len(rows),2); self.assertEqual([row["enabled"] for row in rows],[0,1])
        self.assertIsNotNone(rows[0]["updated_at"])

    def test_rollback_is_complete_when_insert_fails(self):
        self.account(); self.purchase(); first=self.bind()
        self.execute("""CREATE TRIGGER reject_binding BEFORE INSERT ON reseller_mailbox_bindings
          WHEN NEW.binding_version=2 BEGIN SELECT RAISE(ABORT,'rejected'); END""")
        with self.assertRaises(MailboxBindingAdminError) as caught:
            self.bind(provider_config_id="pechy_backup")
        self.assertEqual(caught.exception.safe_code,"binding_write_failed")
        rows=self.rows(); self.assertEqual(len(rows),1); self.assertEqual(rows[0]["id"],first.binding_id); self.assertEqual(rows[0]["enabled"],1)

    def test_concurrent_identical_operations_create_one_binding(self):
        self.account(); self.purchase(); barrier=threading.Barrier(2); results=[]; errors=[]
        def worker():
            try: barrier.wait(); results.append(self.bind())
            except Exception as exc: errors.append(exc)
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for item in threads: item.start()
        for item in threads: item.join()
        self.assertEqual(errors,[]); self.assertEqual(len({item.binding_id for item in results}),1)
        self.assertEqual(len(self.rows()),1)

    def test_no_email_authority_and_no_secret_output(self):
        self.account(); self.purchase(); stdout=io.StringIO(); stderr=io.StringIO()
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr): result=self.bind()
        serialized=repr(result)+repr(stdout.getvalue())+repr(stderr.getvalue())
        for secret in ("OFFLINE_PILOT_SECRET","pilot@example.invalid",CONFIGS): self.assertNotIn(secret,serialized)
        parameters=inspect.signature(self.service.create_or_replace).parameters
        self.assertNotIn("email",parameters); self.assertNotIn("domain",parameters)
        self.socket_mock.assert_not_called(); self.imap_mock.assert_not_called()


if __name__=="__main__": unittest.main()
