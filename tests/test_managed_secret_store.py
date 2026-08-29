import contextlib
import io
import json
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module
import database
import mail_center
from managed_secret_store import (SQLiteEncryptedSecretStore,SecretStoreError,
                                  generate_master_key)
from private_email_credentials import ProviderCredentialResolver
from private_email_provider import ProviderAuthenticationFailed,ProviderTLSFailed

USERNAME="managed@example.invalid"
PASSWORD="MANAGED-PASSWORD-CANARY"

class SuccessTransport:
    def __init__(self,*_):self.calls=[]
    def examine(self,config,folder):self.calls.append((config,folder));return {"uidvalidity":7,"uidnext":9}
class AuthFailureTransport:
    def __init__(self,*_):pass
    def examine(self,*_):raise ProviderAuthenticationFailed()
class TLSFailureTransport:
    def __init__(self,*_):pass
    def examine(self,*_):raise ProviderTLSFailed()
class UnavailableStore:
    def put(self,*_,**__):raise SecretStoreError()

class ManagedSecretStoreTests(unittest.TestCase):
    def setUp(self):
        descriptor,self.path=tempfile.mkstemp(suffix=".db");os.close(descriptor)
        self.old_db=database.DB;database.DB=self.path
        conn=database.conectar();conn.executescript("""
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT);
          CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,revendedor_id INTEGER,cuenta_id INTEGER);
          CREATE TABLE reseller_mailbox_bindings(id INTEGER PRIMARY KEY,provider_config_id TEXT);
          INSERT INTO nube_cuentas VALUES(1,'Netflix','managed@example.invalid');
        """);conn.commit();conn.close()
        mail_center.initialize_schema();self.key=generate_master_key()
        self.store=SQLiteEncryptedSecretStore(self.key)
        app_module.app.config.update(TESTING=True,SECRET_KEY="managed-secret-test")

    def tearDown(self):
        database.DB=self.old_db
        for suffix in ("-wal","-shm",""):
            try:os.remove(self.path+suffix)
            except FileNotFoundError:pass

    def payload(self,**changes):
        value={"display_name":"Managed","provider":"private_email","host":"mail.privateemail.com",
               "port":993,"tls_mode":"required","folder_key":"INBOX","enabled":True,
               "username":USERNAME,"password":PASSWORD}
        value.update(changes);return value

    def create(self):return mail_center.save_managed_mailbox(self.payload(),self.store)

    def test_create_managed_mailbox_and_resolve(self):
        mailbox_id=self.create();conn=database.conectar()
        reference=conn.execute("SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(mailbox_id,)).fetchone()[0]
        conn.close();creds=ProviderCredentialResolver(bundle={},secret_store=self.store).resolve(reference)
        self.assertEqual(creds.username,USERNAME);self.assertEqual(creds.password,PASSWORD)

    def test_plaintext_absent_from_sqlite_and_audit(self):
        self.create();conn=database.conectar()
        rows=conn.execute("SELECT hex(nonce),hex(ciphertext) FROM managed_mail_secrets").fetchall()
        audit=json.dumps([dict(row) for row in conn.execute("SELECT * FROM mail_center_admin_audit")])
        conn.close();dump=repr(rows)+audit
        self.assertNotIn(PASSWORD,dump);self.assertNotIn(USERNAME,dump)
        self.assertNotIn(PASSWORD.encode(),Path(self.path).read_bytes())

    def test_list_and_edit_shape_never_return_secret_or_reference(self):
        mailbox_id=self.create();listed=json.dumps(mail_center.list_mailboxes())
        self.assertNotIn(PASSWORD,listed);self.assertNotIn(USERNAME,listed);self.assertNotIn("secret_ref",listed)
        mail_center.update_mailbox_configuration(mailbox_id,{"display_name":"Edited","provider":"private_email",
            "host":"mail.privateemail.com","port":993,"tls_mode":"required","folder_key":"INBOX","enabled":True})
        self.assertNotIn(PASSWORD,json.dumps(mail_center.list_mailboxes()))

    def test_missing_and_wrong_master_keys_fail_closed(self):
        with self.assertRaises(SecretStoreError):SQLiteEncryptedSecretStore.from_environment({})
        mailbox_id=self.create();conn=database.conectar();ref=conn.execute(
            "SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(mailbox_id,)).fetchone()[0];conn.close()
        with self.assertRaises(SecretStoreError):SQLiteEncryptedSecretStore(generate_master_key()).get(ref)

    def test_reference_is_opaque_and_unpredictable(self):
        first=self.store.put({"username":USERNAME,"password":PASSWORD})
        second=self.store.put({"username":USERNAME,"password":PASSWORD})
        self.assertNotEqual(first,second);self.assertRegex(first,r"^ms1_[A-Za-z0-9_-]{30,}$")
        self.assertNotIn("mailbox",first);self.assertNotIn("1_password",first)

    def test_rotate_replaces_old_secret(self):
        mailbox_id=self.create();conn=database.conectar();ref=conn.execute(
            "SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(mailbox_id,)).fetchone()[0];conn.close()
        old_cipher=database.conectar();before=old_cipher.execute(
            "SELECT ciphertext FROM managed_mail_secrets WHERE secret_ref=?",(ref,)).fetchone()[0];old_cipher.close()
        mail_center.rotate_mailbox_credential(mailbox_id,USERNAME,"NEW-PASSWORD-CANARY",self.store)
        self.assertEqual(self.store.get(ref)["password"],"NEW-PASSWORD-CANARY")
        conn=database.conectar();after=conn.execute("SELECT ciphertext FROM managed_mail_secrets WHERE secret_ref=?",(ref,)).fetchone()[0];conn.close()
        self.assertNotEqual(before,after);self.assertNotEqual(self.store.get(ref)["password"],PASSWORD)

    def test_db_failure_rolls_back_new_secret(self):
        conn=database.conectar();conn.execute("""CREATE TRIGGER fail_mailbox BEFORE INSERT ON mail_center_mailboxes
            BEGIN SELECT RAISE(ABORT,'forced'); END""");conn.commit();conn.close()
        with self.assertRaises(mail_center.MailCenterError):self.create()
        conn=database.conectar();self.assertEqual(conn.execute("SELECT COUNT(*) FROM managed_mail_secrets").fetchone()[0],0);conn.close()

    def test_store_failure_creates_no_mailbox(self):
        with self.assertRaises(mail_center.MailCenterError):mail_center.save_managed_mailbox(self.payload(),UnavailableStore())
        conn=database.conectar();self.assertEqual(conn.execute("SELECT COUNT(*) FROM mail_center_mailboxes").fetchone()[0],0);conn.close()

    def test_unsaved_connection_success_never_persists(self):
        result=mail_center.test_unsaved_credentials(self.payload(),SuccessTransport)
        self.assertEqual(result,{"ok":True,"status":"connected"})
        conn=database.conectar();self.assertEqual(conn.execute("SELECT COUNT(*) FROM managed_mail_secrets").fetchone()[0],0);conn.close()

    def test_saved_managed_connection_uses_resolver_without_exposure(self):
        mailbox_id=self.create();resolver=ProviderCredentialResolver(bundle={},secret_store=self.store)
        result=mail_center.test_mailbox_connection(mailbox_id,resolver,SuccessTransport)
        self.assertEqual(result,{"ok":True,"status":"connected"})

    def test_unsaved_connection_errors_are_safe(self):
        self.assertEqual(mail_center.test_unsaved_credentials(self.payload(),AuthFailureTransport)["status"],"authentication_failed")
        self.assertEqual(mail_center.test_unsaved_credentials(self.payload(),TLSFailureTransport)["status"],"tls_failed")

    def test_delete_is_reference_safe_and_bound_mailbox_denied(self):
        mailbox_id=self.create();conn=database.conectar();ref=conn.execute(
            "SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(mailbox_id,)).fetchone()[0]
        conn.execute("INSERT INTO reseller_mailbox_bindings(id,provider_config_id) VALUES(1,?)",(ref,));conn.commit();conn.close()
        with self.assertRaises(mail_center.MailCenterError):mail_center.delete_managed_mailbox(mailbox_id,self.store)
        self.assertEqual(self.store.get(ref)["username"],USERNAME)

    def test_unbound_delete_removes_secret(self):
        mailbox_id=self.create();conn=database.conectar();ref=conn.execute(
            "SELECT secret_ref FROM mail_center_mailboxes WHERE id=?",(mailbox_id,)).fetchone()[0];conn.close()
        mail_center.delete_managed_mailbox(mailbox_id,self.store)
        with self.assertRaises(SecretStoreError):self.store.get(ref)

    def test_legacy_bundle_remains_supported(self):
        resolver=ProviderCredentialResolver(bundle={"pechy_pilot":{"username":"pilot@example.invalid","password":"LEGACY-CANARY"}},secret_store=self.store)
        self.assertEqual(resolver.resolve("pechy_pilot").username,"pilot@example.invalid")

    def test_web_authorization_csrf_and_no_secret_response(self):
        client=app_module.app.test_client()
        self.assertEqual(client.post("/admin/centro-correo/api/buzones",json=self.payload()).status_code,401)
        with client.session_transaction() as session:session["admin"]=True;session["csrf_admin"]="csrf"
        self.assertEqual(client.post("/admin/centro-correo/api/buzones",json=self.payload()).status_code,403)
        with patch.object(app_module,"_mail_center_secret_store",return_value=self.store):
            response=client.post("/admin/centro-correo/api/buzones",json=self.payload(),headers={"X-CSRF-Token":"csrf"})
        body=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200);self.assertNotIn(PASSWORD,body);self.assertNotIn(USERNAME,body);self.assertNotIn("ms1_",body)

    def test_web_create_enabled_and_disabled_persists_only_encrypted_secret(self):
        for enabled in (True,False):
            with self.subTest(enabled=enabled):
                client=app_module.app.test_client()
                with client.session_transaction() as session:session["admin"]=True;session["csrf_admin"]="csrf"
                payload=self.payload(enabled=enabled,display_name=f"Managed {enabled}")
                with patch.object(app_module,"_mail_center_secret_store",return_value=self.store):
                    response=client.post("/admin/centro-correo/api/buzones",json=payload,
                                         headers={"X-CSRF-Token":"csrf"})
                self.assertEqual(response.status_code,200)
                body=response.get_data(as_text=True)
                self.assertNotIn(PASSWORD,body);self.assertNotIn(USERNAME,body);self.assertNotIn("ms1_",body)
                mailbox_id=response.get_json()["mailbox_id"]
                conn=database.conectar()
                row=conn.execute("SELECT secret_ref,enabled FROM mail_center_mailboxes WHERE id=?",
                                 (mailbox_id,)).fetchone()
                secret_count=conn.execute("SELECT COUNT(*) FROM managed_mail_secrets WHERE secret_ref=?",
                                          (row["secret_ref"],)).fetchone()[0]
                conn.close()
                self.assertTrue(row["secret_ref"].startswith("ms1_"));self.assertEqual(row["enabled"],int(enabled))
                self.assertEqual(secret_count,1);self.assertNotIn(PASSWORD.encode(),Path(self.path).read_bytes())
                listed=json.dumps(mail_center.list_mailboxes())
                self.assertNotIn(PASSWORD,listed);self.assertNotIn(USERNAME,listed);self.assertNotIn("secret_ref",listed)

    def test_web_missing_master_key_fails_closed_with_safe_status(self):
        client=app_module.app.test_client()
        with client.session_transaction() as session:session["admin"]=True;session["csrf_admin"]="csrf"
        with patch.dict(os.environ,{"PECHY_MAIL_SECRET_MASTER_KEY":""}):
            response=client.post("/admin/centro-correo/api/buzones",json=self.payload(),
                                 headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.get_json(),{"ok":False,"error":"secret_store_unavailable"})
        body=response.get_data(as_text=True)
        self.assertNotIn(PASSWORD,body);self.assertNotIn(USERNAME,body)
        conn=database.conectar()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM mail_center_mailboxes").fetchone()[0],0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM managed_mail_secrets").fetchone()[0],0);conn.close()

    def test_provider_config_id_rejected_from_normal_ui(self):
        client=app_module.app.test_client()
        with client.session_transaction() as session:session["admin"]=True;session["csrf_admin"]="csrf"
        payload=self.payload();payload["secret_ref"]="chosen_by_browser"
        with patch.object(app_module,"_mail_center_secret_store",return_value=self.store):
            response=client.post("/admin/centro-correo/api/buzones",json=payload,headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(response.status_code,400)

    def test_rotation_requires_admin_and_csrf(self):
        mailbox_id=self.create();client=app_module.app.test_client();payload={"username":USERNAME,"password":"ROTATED-CANARY"}
        self.assertEqual(client.post(f"/admin/centro-correo/api/buzones/{mailbox_id}/credencial",json=payload).status_code,401)
        with client.session_transaction() as session:session["admin"]=True;session["csrf_admin"]="csrf"
        self.assertEqual(client.post(f"/admin/centro-correo/api/buzones/{mailbox_id}/credencial",json=payload).status_code,403)
        with patch.object(app_module,"_mail_center_secret_store",return_value=self.store):
            response=client.post(f"/admin/centro-correo/api/buzones/{mailbox_id}/credencial",json=payload,
                                 headers={"X-CSRF-Token":"csrf"})
        self.assertEqual(response.status_code,200);self.assertNotIn("ROTATED-CANARY",response.get_data(as_text=True))

    def test_ui_has_username_password_and_no_provider_config_field(self):
        source=Path("templates/admin/centro_correo.html").read_text(encoding="utf-8")
        self.assertIn('name="username"',source);self.assertIn('name="password" type="password"',source)
        self.assertNotIn('name="secret_ref"',source);self.assertNotIn("provider_config_id",source)

    def test_logs_and_safe_errors_do_not_reflect_secret(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            result=mail_center.test_unsaved_credentials(self.payload(),AuthFailureTransport)
        self.assertNotIn(PASSWORD,output.getvalue()+json.dumps(result));self.assertNotIn(USERNAME,output.getvalue()+json.dumps(result))

if __name__=="__main__":unittest.main()
