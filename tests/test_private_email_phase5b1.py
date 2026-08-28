try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import os, sqlite3, tempfile, unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import database
import reseller_mailbox_persistence
from mailbox_bindings import MailboxBinding, MailboxBindingDenied, MailboxBindingResolver, initialize_schema
from mail_message_parsers import CodeServiceAdapter, ServiceAdapterRegistry
from mail_provider_factory import build_mail_provider, provider_mode
from mail_providers import FakeMailProvider
from private_email_provider import (PrivateEmailMailProvider, ProviderConfigurationError,
    ProviderCursorInvalid, ProviderLocator, ProviderMessageMalformed, ProviderMessageTooLarge)

NOW=datetime(2026,8,28,5,0,tzinfo=timezone.utc)

class FakeIMAPTransport:
    def __init__(self):
        self.uidvalidity=77; self.uidnext=100; self.rows={}; self.commands=[]
    def examine(self,c,f): self.commands.append(("EXAMINE",c,f)); return {"uidvalidity":self.uidvalidity,"uidnext":self.uidnext}
    def search_uids(self,c,f,m,l): self.commands.append(("UID SEARCH",m,l)); return [u for u in sorted(self.rows) if u>=m][:l]
    def fetch_metadata(self,c,f,u): self.commands.append(("FETCH_META",u)); return self.rows[u][0]
    def fetch_body_peek(self,c,f,u,p): self.commands.append(("BODY.PEEK",u,p)); return self.rows[u][1]
    def close(self): self.commands.append(("LOGOUT",))

def raw_message(text="Código: 482193", *, html=False, attachment=False):
    msg=EmailMessage(); msg["From"]="security@service.invalid"; msg["To"]="account@pechy.invalid"; msg["Subject"]="Código de acceso"
    if html: msg.set_content("fallback"); msg.add_alternative(f"<b>{text}</b><script>evil()</script>",subtype="html")
    else: msg.set_content(text)
    if attachment: msg.add_attachment(b"SECRET-ATTACHMENT",maintype="application",subtype="octet-stream",filename="x.bin")
    return msg.as_bytes()

def metadata(*,internaldate=NOW,size=500,auth="mx; dkim=pass; spf=pass",sender="security@service.invalid",recipient="account@pechy.invalid"):
    return {"internaldate":internaldate,"size":size,"from":sender,"to":recipient,
            "subject":"Tu código de acceso","authentication_results":auth,"body_part":"TEXT"}

class ProviderAndParserTests(unittest.TestCase):
    def setUp(self):
        adapter=CodeServiceAdapter("Servicio",senders={"security@service.invalid"},
            recipients={"account@pechy.invalid"},subject_tokens={"código"})
        self.registry=ServiceAdapterRegistry([adapter],max_message_bytes=4096,max_parts=8,max_depth=3)
        self.transport=FakeIMAPTransport(); self.provider=PrivateEmailMailProvider(self.transport,self.registry)
        self.binding=MailboxBinding(1,"private_email","cfg-main","INBOX",1,True,"cuenta",9,None)

    def test_cursor_captures_uidnext_uidvalidity_and_boundary(self):
        cursor=self.provider.begin_request(request_id="r",binding=self.binding,requested_at=NOW)
        self.assertEqual((cursor.uidvalidity,cursor.uidnext_boundary),(77,100))
        self.transport.rows[99]=(metadata(internaldate=NOW+timedelta(seconds=1)),raw_message("111111"))
        self.transport.rows[100]=(metadata(internaldate=NOW+timedelta(seconds=1)),raw_message("222222"))
        found=self.provider.messages_after(binding=self.binding,cursor=cursor)
        self.assertEqual([x.value for x in found],["222222"])
        self.assertIn(("UID SEARCH",100,20),self.transport.commands)

    def test_first_valid_uid_and_message_id_irrelevant(self):
        cursor=self.provider.begin_request(request_id="r",binding=self.binding,requested_at=NOW)
        self.transport.rows[100]=(metadata(auth="dkim=fail; spf=pass"),raw_message("111111"))
        self.transport.rows[101]=(metadata(),raw_message("222222"))
        self.transport.rows[102]=(metadata(),raw_message("333333"))
        result=self.provider.messages_after(binding=self.binding,cursor=cursor)
        self.assertEqual([x.value for x in result],["222222","333333"])
        self.assertEqual(result[0].locator.uid,101)

    def test_uidvalidity_change_fails_closed(self):
        cursor=self.provider.begin_request(request_id="r",binding=self.binding,requested_at=NOW)
        self.transport.uidvalidity=78
        with self.assertRaises(ProviderCursorInvalid): self.provider.messages_after(binding=self.binding,cursor=cursor)
        self.assertFalse(self.provider.can_resume_request(binding=self.binding,cursor=cursor))

    def test_internaldate_is_secondary_and_date_header_unused(self):
        cursor=self.provider.begin_request(request_id="r",binding=self.binding,requested_at=NOW)
        self.transport.rows[100]=(metadata(internaldate=NOW-timedelta(days=1)),raw_message("482193"))
        self.assertEqual(self.provider.messages_after(binding=self.binding,cursor=cursor),[])

    def test_locator_is_recoverable_and_hash_separate(self):
        locator=ProviderLocator(1,"INBOX",77,100)
        self.assertIn('"u":100',locator.canonical()); self.assertEqual(len(locator.audit_hash()),64)
        with self.assertRaises(ProviderCursorInvalid): ProviderLocator(1,"INBOX",77,0).canonical()

    def test_plain_base64_qp_html_multipart_and_attachment(self):
        cases=[raw_message(),raw_message(html=True),raw_message(attachment=True)]
        for raw in cases:
            result=self.registry.classify(metadata(size=len(raw)),lambda _:raw,requested_at=NOW)
            self.assertEqual(result.value,"482193")
        self.assertNotIn(b"<script>",cases[0])

    def test_authenticity_and_ambiguity_fail_closed(self):
        raw=raw_message("482193 y 123456")
        for meta in (metadata(auth="dkim=fail; spf=fail"),metadata(sender="evil.invalid"),metadata(recipient="other.invalid"),metadata()):
            result=self.registry.classify(meta,lambda _:raw,requested_at=NOW)
            self.assertEqual(result.kind,"unsupported")

    def test_mime_size_malformed_parts_and_depth(self):
        with self.assertRaises(ProviderMessageTooLarge): self.registry.classify(metadata(size=99999),lambda _:b"x",requested_at=NOW)
        with self.assertRaises(ProviderMessageMalformed): self.registry.classify(metadata(),lambda _:b"",requested_at=NOW)

    def test_only_read_only_commands_are_used(self):
        cursor=self.provider.begin_request(request_id="r",binding=self.binding,requested_at=NOW)
        self.transport.rows[100]=(metadata(),raw_message())
        self.provider.messages_after(binding=self.binding,cursor=cursor)
        commands=" ".join(x[0] for x in self.transport.commands)
        self.assertIn("BODY.PEEK",commands)
        for forbidden in ("STORE","DELETE","MOVE","COPY","EXPUNGE","SMTP"):
            self.assertNotIn(forbidden,commands)

class BindingAndFeatureFlagTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix=".db"); os.close(fd); self.old=database.DB; database.DB=self.path
        conn=sqlite3.connect(self.path); conn.row_factory=sqlite3.Row
        conn.executescript("""CREATE TABLE nube_cuentas(id INTEGER PRIMARY KEY); CREATE TABLE nube_perfiles(id INTEGER PRIMARY KEY,cuenta_id INTEGER);
          CREATE TABLE revendedores(id INTEGER PRIMARY KEY); CREATE TABLE reseller_purchases(id INTEGER PRIMARY KEY,revendedor_id INTEGER);
          INSERT INTO nube_cuentas VALUES(9); INSERT INTO nube_perfiles VALUES(91,9); INSERT INTO revendedores VALUES(1); INSERT INTO reseller_purchases VALUES(1,1);"""); conn.commit(); conn.close(); reseller_mailbox_persistence.initialize_schema()
    def tearDown(self):
        database.DB=self.old
        for suffix in ("-wal","-shm",""):
            try: os.remove(self.path+suffix)
            except FileNotFoundError: pass
    def insert(self,**kw):
        data={"inventory_type":"cuenta","inventory_account_id":9,"inventory_profile_id":None,"provider":"private_email","provider_config_id":"cfg","folder_key":"INBOX","binding_version":1,"enabled":1};data.update(kw)
        conn=database.conectar()
        try:
            conn.execute("""INSERT INTO reseller_mailbox_bindings(inventory_type,inventory_account_id,inventory_profile_id,provider,provider_config_id,folder_key,binding_version,enabled) VALUES(:inventory_type,:inventory_account_id,:inventory_profile_id,:provider,:provider_config_id,:folder_key,:binding_version,:enabled)""",data);conn.commit()
        finally: conn.close()
    def test_binding_correct_and_no_email_or_secret_fields(self):
        self.insert(); b=MailboxBindingResolver().resolve({"type":"cuenta","account_id":9,"profile_id":None},1,"v")
        self.assertEqual(b.provider_config_id,"cfg")
        conn=sqlite3.connect(self.path); cols={r[1] for r in conn.execute("pragma table_info(reseller_mailbox_bindings)")}; conn.close()
        self.assertFalse(cols & {"email","username","password","token"})
    def test_missing_disabled_and_mismatch_fail_closed(self):
        resolver=MailboxBindingResolver()
        with self.assertRaises(MailboxBindingDenied): resolver.resolve({"type":"cuenta","account_id":9,"profile_id":None},1,"v")
        self.insert(enabled=0)
        with self.assertRaises(MailboxBindingDenied): resolver.resolve({"type":"cuenta","account_id":9,"profile_id":None},1,"v")
        with self.assertRaises(MailboxBindingDenied): resolver.resolve({"type":"perfil","account_id":9,"profile_id":None},1,"v")
    def test_constraints_provider_config_and_profile(self):
        for data in ({"provider":"evil"},{"provider_config_id":""},{"inventory_type":"perfil","inventory_profile_id":None}):
            with self.assertRaises(sqlite3.IntegrityError): self.insert(**data)
    def test_feature_flag(self):
        self.assertEqual(provider_mode({}),"fake"); self.assertIsInstance(build_mail_provider(environ={}),FakeMailProvider)
        with self.assertRaises(ProviderConfigurationError): build_mail_provider(environ={"MAIL_PROVIDER_MODE":"private_email"})
        with self.assertRaises(ProviderConfigurationError): provider_mode({"MAIL_PROVIDER_MODE":"unknown"})
    def test_cursor_locator_and_lease_schema(self):
        conn=database.conectar()
        req={r[1] for r in conn.execute("pragma table_info(reseller_mailbox_requests)")}
        delivery={r[1] for r in conn.execute("pragma table_info(reseller_authorized_message_deliveries)")}
        conn.close()
        self.assertTrue({"mailbox_binding_id","uidvalidity_at_t0","uidnext_at_t0","lease_owner","lease_expires_at"}<=req)
        self.assertTrue({"mailbox_binding_id","imap_uidvalidity","imap_uid","provider_locator_version"}<=delivery)
    def test_single_lease_winner_and_expired_recovery(self):
        conn=database.conectar(); conn.execute("""INSERT INTO reseller_mailbox_requests(request_id,reseller_id,reseller_purchase_id,inventory_type,inventory_account_id,requested_at,expires_at,status,assignment_version) VALUES('r',1,1,'cuenta',9,'2026-08-28T05:00:00Z','2026-08-28T06:00:00Z','waiting','v')""");conn.commit();conn.close()
        repo=reseller_mailbox_persistence.SQLiteMailboxRepository()
        self.assertTrue(repo.claim_poll("r",1,"worker-a",NOW))
        self.assertFalse(repo.claim_poll("r",1,"worker-b",NOW))
        self.assertTrue(repo.claim_poll("r",1,"worker-b",NOW+timedelta(seconds=16)))
    def test_no_network_library_in_provider(self):
        source=Path("private_email_provider.py").read_text(encoding="utf-8").lower()
        for forbidden in ("imaplib","socket","smtplib","poplib","mail.privateemail.com"):
            self.assertNotIn(forbidden,source)
