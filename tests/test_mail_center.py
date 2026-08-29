import contextlib
import io
import json
import os
import socket
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

import database
import mail_center
import app as app_module
from mailbox_bindings import MailboxBinding
from private_email_credentials import ProviderCredentialResolver
from private_email_provider import PrivateEmailMailProvider, ProviderCursor


NOW = datetime(2026, 8, 29, 18, 0, tzinfo=timezone.utc)
SUBJECT = "Completa tu solicitud de restablecimiento de contraseña"
URL = "https://secure.netflix.example/reset?token=SENSITIVE-CANARY"


class FakeTransport:
    def __init__(self):
        self.rows = {}
        self.commands = []
    def examine(self, config, folder):
        self.commands.append(("EXAMINE", config, folder)); return {"uidvalidity": 77, "uidnext": 100}
    def search_uids(self, config, folder, minimum, limit):
        self.commands.append(("SEARCH", minimum, limit)); return sorted(x for x in self.rows if x >= minimum)
    def fetch_metadata(self, config, folder, uid):
        self.commands.append(("META", uid)); return self.rows[uid][0]
    def fetch_body_peek(self, config, folder, uid, part):
        self.commands.append(("BODY", uid)); return self.rows[uid][1]


def mime(url=URL, second=None):
    links = f'<a href="{url}">Reset password</a>'
    if second: links += f'<a href="{second}">Reset password</a>'
    item = EmailMessage(); item.set_content("instructions"); item.add_alternative(links, subtype="html")
    return item.as_bytes()


def metadata(subject=SUBJECT, recipient="account@example.invalid", sender="notice@account.netflix.com"):
    return {"size": 500, "internaldate": NOW, "from": sender, "to": recipient,
            "subject": subject, "authentication_results": "dkim=pass; spf=pass",
            "content_type": "multipart/alternative", "content_transfer_encoding": "",
            "body_part": "TEXT"}


class MailCenterTests(unittest.TestCase):
    def setUp(self):
        descriptor, self.path = tempfile.mkstemp(suffix=".db"); os.close(descriptor)
        self.old_db = database.DB; database.DB = self.path
        conn = database.conectar()
        conn.executescript("""
          CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY,plataforma TEXT,correo TEXT);
          CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,revendedor_id INTEGER,cuenta_id INTEGER);
          INSERT INTO nube_cuentas VALUES(1,'Netflix','account@example.invalid');
        """)
        conn.commit(); conn.close(); mail_center.initialize_schema()
        self.network = patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden"))
        self.network.start()

    def tearDown(self):
        self.network.stop(); database.DB = self.old_db
        for suffix in ("-wal", "-shm", ""):
            try: os.remove(self.path + suffix)
            except FileNotFoundError: pass

    def action_payload(self, **changes):
        value = {"platform":"netflix", "internal_key":"password_reset",
                 "display_name":"Restablecer contraseña", "subject_policy":SUBJECT,
                 "extractor_type":"password_reset_link", "enabled":True,
                 "extractor_config":{"allowed_link_hosts":[{"hostname":"secure.netflix.example",
                    "allow_subdomains":False}], "sender_domains":["account.netflix.com"],
                    "require_dkim_spf":True}}
        value.update(changes); return value

    def test_multiple_mailboxes_store_only_secret_reference(self):
        for index in (1, 2):
            mail_center.save_mailbox({"display_name":f"Buzón {index}","provider":"private_email",
                "host":"mail.privateemail.com","port":993,"tls_mode":"required",
                "secret_ref":f"config_{index}","folder_key":"INBOX","enabled":True})
        self.assertEqual(len(mail_center.list_mailboxes()), 2)
        conn = database.conectar()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(mail_center_mailboxes)")}
        dump = json.dumps([dict(row) for row in conn.execute("SELECT * FROM mail_center_mailboxes")])
        conn.close()
        self.assertFalse({"password","username","bundle","app_password"} & columns)
        self.assertNotIn("PASSWORD-CANARY", dump)

    def test_mailbox_validation_is_fixed_tls_and_connection_is_injected(self):
        mailbox_id = mail_center.save_mailbox({"display_name":"Piloto","provider":"private_email",
            "host":"mail.privateemail.com","port":993,"tls_mode":"required",
            "secret_ref":"pechy_pilot","folder_key":"INBOX","enabled":True})
        resolver = ProviderCredentialResolver(bundle={"pechy_pilot":{"username":"x@example.invalid",
                                                      "password":"PASSWORD-CANARY"}})
        transport = FakeTransport()
        result = mail_center.test_mailbox_connection(mailbox_id, resolver, lambda _: transport)
        self.assertEqual(result, {"ok":True,"status":"connected"})
        self.assertEqual(transport.commands[0][0], "EXAMINE")
        with self.assertRaises(mail_center.MailCenterError):
            mail_center.save_mailbox({"display_name":"Bad","provider":"private_email",
                "host":"attacker.invalid","port":993,"tls_mode":"required",
                "secret_ref":"bad_ref","folder_key":"INBOX","enabled":True})

    def test_action_is_canonical_allowlist_and_disabled_fails_closed(self):
        action_id = mail_center.save_action(self.action_payload())
        action = mail_center.get_action(action_id)
        self.assertEqual(action["platform"], "Netflix")
        self.assertIsNotNone(mail_center.action_runtime(action,{"account_id":1}))
        mail_center.save_action(self.action_payload(enabled=False),action_id=action_id)
        self.assertIsNone(mail_center.get_action(action_id))
        with self.assertRaises(mail_center.MailCenterError):
            mail_center.save_action(self.action_payload(platform="Disney"))

    def test_arbitrary_extractor_and_dangerous_hosts_rejected(self):
        with self.assertRaises(mail_center.MailCenterError):
            mail_center.save_action(self.action_payload(extractor_type="show_full_email"))
        bad = self.action_payload(); bad["extractor_config"]["allowed_link_hosts"]=[{"hostname":"*.example.com"}]
        with self.assertRaises(mail_center.MailCenterError): mail_center.save_action(bad)

    def test_metadata_matching_is_exact_and_recipient_authoritative(self):
        action_id = mail_center.save_action(self.action_payload())
        runtime = mail_center.action_runtime(mail_center.get_action(action_id),{"account_id":1})
        self.assertTrue(mail_center.action_metadata_matches(runtime, metadata()))
        self.assertFalse(mail_center.action_metadata_matches(runtime, metadata(subject="change email")))
        self.assertFalse(mail_center.action_metadata_matches(runtime, metadata(recipient="other@example.invalid")))
        self.assertFalse(mail_center.action_metadata_matches(runtime, metadata(sender="x@attacker.invalid")))

    def test_latest_valid_uid_wins_and_other_actions_never_fetch_body(self):
        action_id = mail_center.save_action(self.action_payload())
        runtime = mail_center.action_runtime(mail_center.get_action(action_id),{"account_id":1})
        transport = FakeTransport()
        transport.rows = {
            100:(metadata(),mime()), 101:(metadata(subject="verification code"),mime()),
            102:(metadata(subject="change email"),mime()), 103:(metadata(),mime()),
            104:(metadata(subject="change email"),mime())}
        provider = PrivateEmailMailProvider(transport, mail_center.build_action_registry(runtime))
        binding = MailboxBinding(1,"private_email","pechy_pilot","INBOX",1,True,"cuenta",1,None)
        cursor = ProviderCursor(1,"INBOX",77,100,NOW,1)
        messages = provider.messages_after(binding=binding,cursor=cursor,action=runtime)
        self.assertEqual(len(messages),1); self.assertEqual(messages[0].locator.uid,103)
        self.assertEqual([command for command in transport.commands if command[0]=="BODY"],[("BODY",103)])

    def test_multiple_same_action_selects_latest_not_ambiguous(self):
        action_id=mail_center.save_action(self.action_payload())
        runtime=mail_center.action_runtime(mail_center.get_action(action_id),{"account_id":1})
        transport=FakeTransport(); transport.rows={uid:(metadata(),mime()) for uid in (200,201,205)}
        provider=PrivateEmailMailProvider(transport,mail_center.build_action_registry(runtime))
        binding=MailboxBinding(1,"private_email","pechy_pilot","INBOX",1,True,"cuenta",1,None)
        result=provider.messages_after(binding=binding,cursor=ProviderCursor(1,"INBOX",77,200,NOW,1),action=runtime)
        self.assertEqual(result[0].locator.uid,205); self.assertEqual([x for x in transport.commands if x[0]=="BODY"],[("BODY",205)])

    def test_internal_link_ambiguity_fails_closed_without_exposure(self):
        action_id=mail_center.save_action(self.action_payload())
        runtime=mail_center.action_runtime(mail_center.get_action(action_id),{"account_id":1})
        registry=mail_center.build_action_registry(runtime); raw=mime(second="https://secure.netflix.example/other?token=TWO")
        result=registry.classify(metadata(),lambda _:raw,requested_at=NOW)
        self.assertEqual(result.status,"ambiguous"); self.assertEqual(result.value,"")
        self.assertNotIn("SENSITIVE",repr(result)); self.assertNotIn("token",repr(result))

    def test_no_sensitive_output_or_db_content(self):
        canary="PASSWORD-CANARY"; output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            mail_center.save_action(self.action_payload())
        conn=database.conectar(); dump=json.dumps([dict(row) for row in conn.execute(
            "SELECT * FROM mail_center_admin_audit")]); conn.close()
        self.assertNotIn(canary,output.getvalue()+dump)

    def test_admin_ui_requires_session_and_uses_existing_csrf(self):
        client=app_module.app.test_client()
        self.assertEqual(client.get("/admin/centro-correo").status_code,302)
        with client.session_transaction() as session:
            session["admin"]=True; session["csrf_admin"]="csrf-mail-center"
        page=client.get("/admin/centro-correo")
        self.assertEqual(page.status_code,200)
        html=page.get_data(as_text=True)
        self.assertIn("Centro de Correo",html); self.assertIn("ACCIONES AUTORIZADAS",html)
        denied=client.post("/admin/centro-correo/api/acciones",json=self.action_payload())
        self.assertEqual(denied.status_code,403)
        created=client.post("/admin/centro-correo/api/acciones",json=self.action_payload(),
                            headers={"X-CSRF-Token":"csrf-mail-center"})
        self.assertEqual(created.status_code,200); self.assertTrue(created.get_json()["ok"])

    def test_reseller_cannot_submit_arbitrary_subject_or_extractor(self):
        source=Path("static/js/reseller-mailbox.js").read_text(encoding="utf-8")
        self.assertIn("action_id: selectedAction",source)
        self.assertNotIn("subject_policy",source); self.assertNotIn("extractor_type",source)
        rules=[rule.rule for rule in app_module.app.url_map.iter_rules()]
        self.assertNotIn("/revendedores/buzon/acciones/crear",rules)


if __name__ == "__main__": unittest.main()
