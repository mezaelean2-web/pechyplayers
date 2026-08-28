try:
    from tests._bootstrap import TEST_DB
except ModuleNotFoundError:
    from _bootstrap import TEST_DB

import imaplib,json,ssl,unittest
from unittest.mock import Mock

from mail_message_parsers import ServiceAdapterRegistry
from mail_provider_factory import build_mail_provider
from mail_providers import FakeMailProvider
from private_email_credentials import ProviderCredentialResolver,ProviderCredentials
from private_email_imap_transport import HOST,PORT,PrivateEmailIMAPTransport
from private_email_provider import (PrivateEmailMailProvider,ProviderAuthenticationFailed,
    ProviderConfigurationError,ProviderMessageMalformed,ProviderProtocolError,ProviderTimeout)
from private_email_smoke_test import run_smoke_test

FAKE_BUNDLE=json.dumps({"pilot":{"username":"fake@example.invalid","password":"FAKE_PASSWORD_DO_NOT_USE"}})

class FakeClient:
    def __init__(self):
        self.calls=[]; self.sock=Mock(); self.logout_fails=False; self.login_fails=False
        self.uidvalidity=b"77"; self.uidnext=b"100"; self.search=b"99 100 101"
    def login(self,u,p):
        self.calls.append(("LOGIN",u,p))
        if self.login_fails: raise imaplib.IMAP4.error("raw secret server detail")
        return "OK",[b"logged"]
    def select(self,f,readonly=False): self.calls.append(("EXAMINE",f,readonly)); return "OK",[b"0"]
    def response(self,n): return n,[self.uidvalidity if n=="UIDVALIDITY" else self.uidnext]
    def uid(self,cmd,*args):
        self.calls.append(("UID "+cmd,)+args)
        if cmd=="SEARCH": return "OK",[self.search]
        if "HEADER.FIELDS" in args[-1]:
            attrs=b'1 (UID 100 INTERNALDATE "28-Aug-2026 05:00:01 +0000" RFC822.SIZE 400)'
            headers=b"From: security@service.invalid\r\nTo: account@pechy.invalid\r\nSubject: Code\r\nAuthentication-Results: mx; dkim=pass; spf=pass\r\n\r\n"
            return "OK",[(attrs,headers),b")"]
        return "OK",[(b"1 (UID 100)",b"Code 482193"),b")"]
    def logout(self):
        self.calls.append(("LOGOUT",))
        if self.logout_fails: raise OSError("logout")
        return "BYE",[b""]

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client=FakeClient(); self.factory=Mock(return_value=self.client)
        self.resolver=ProviderCredentialResolver(bundle=FAKE_BUNDLE)
        self.transport=PrivateEmailIMAPTransport(self.resolver,client_factory=self.factory)
    def test_tls_host_port_timeout_and_secure_context(self):
        state=self.transport.examine("pilot","INBOX")
        self.assertEqual(state,{"uidvalidity":77,"uidnext":100})
        args,kwargs=self.factory.call_args; self.assertEqual(args,(HOST,PORT)); self.assertEqual(PORT,993)
        context=kwargs["ssl_context"]; self.assertTrue(context.check_hostname); self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertGreater(kwargs["timeout"],0); self.assertIn(("EXAMINE","INBOX",True),self.client.calls); self.assertIn(("LOGOUT",),self.client.calls)
    def test_credentials_redacted_and_not_serializable(self):
        creds=self.resolver.resolve("pilot"); self.assertNotIn("fake@",repr(creds)); self.assertNotIn("FAKE_PASSWORD",repr(creds))
        with self.assertRaises(TypeError): creds.__reduce__()
        with self.assertRaises(ProviderConfigurationError): ProviderCredentialResolver(bundle="{}").resolve("pilot")
    def test_auth_failure_safe_and_backoff(self):
        self.client.login_fails=True
        with self.assertRaises(ProviderAuthenticationFailed) as caught: self.transport.examine("pilot","INBOX")
        self.assertNotIn("secret",str(caught.exception).lower()); self.factory.reset_mock()
        with self.assertRaises(ProviderAuthenticationFailed): self.transport.examine("pilot","INBOX")
        self.factory.assert_not_called()
    def test_timeout_mapping_and_logout_failure(self):
        timeout_factory=Mock(side_effect=TimeoutError("secret")); t=PrivateEmailIMAPTransport(self.resolver,client_factory=timeout_factory)
        with self.assertRaises(ProviderTimeout): t.examine("pilot","INBOX")
        self.client.logout_fails=True; self.assertEqual(self.transport.examine("pilot","INBOX")["uidnext"],100)
    def test_examine_missing_or_invalid_cursor(self):
        for value in (None,b"0",b"bad"):
            self.client.uidvalidity=value
            with self.assertRaises(ProviderProtocolError): self.transport.examine("pilot","INBOX")
        with self.assertRaises(ProviderConfigurationError): self.transport.examine("pilot","Sent")
    def test_search_boundary_limit_and_malformed(self):
        self.assertEqual(self.transport.search_uids("pilot","INBOX",100,1),[100])
        search=[x for x in self.client.calls if x[0]=="UID SEARCH"][-1]; self.assertIn("UID 100:*",search)
        self.client.search=b"bad"
        with self.assertRaises(ProviderProtocolError): self.transport.search_uids("pilot","INBOX",100,20)
    def test_fetch_metadata_is_minimal_and_body_peek(self):
        meta=self.transport.fetch_metadata("pilot","INBOX",100); self.assertEqual(meta["uid"],100); self.assertEqual(meta["size"],400)
        body=self.transport.fetch_body_peek("pilot","INBOX",100,"TEXT"); self.assertEqual(body,b"Code 482193")
        commands=" ".join(str(x) for x in self.client.calls)
        self.assertIn("HEADER.FIELDS",commands); self.assertIn("BODY.PEEK[TEXT]",commands); self.assertNotIn("BODY[]",commands)
    def test_malformed_fetch_fails_closed(self):
        self.client.uid=Mock(return_value=("OK",[b"bad"]))
        with self.assertRaises(ProviderMessageMalformed): self.transport.fetch_metadata("pilot","INBOX",100)
    def test_no_mutating_commands_or_protocols(self):
        self.transport.examine("pilot","INBOX"); self.transport.search_uids("pilot","INBOX",100,20)
        commands=" ".join(str(x) for x in self.client.calls).upper()
        for forbidden in ("STORE","APPEND","COPY","MOVE","DELETE","EXPUNGE","SMTP","POP3","STARTTLS"):
            self.assertNotIn(forbidden,commands)

class FactoryAndSmokeTests(unittest.TestCase):
    def test_factory_default_fake_and_real_construction_zero_network(self):
        self.assertIsInstance(build_mail_provider(environ={}),FakeMailProvider)
        factory=Mock(); transport=Mock(); factory.return_value=transport
        provider=build_mail_provider(environ={"MAIL_PROVIDER_MODE":"private_email",
            "PRIVATE_EMAIL_CREDENTIALS_BUNDLE":FAKE_BUNDLE},parser_registry=ServiceAdapterRegistry(),transport_factory=factory)
        self.assertIsInstance(provider,PrivateEmailMailProvider); factory.assert_called_once(); self.assertEqual(transport.method_calls,[])
    def test_factory_missing_config_fails_closed(self):
        with self.assertRaises(ProviderConfigurationError): build_mail_provider(
            environ={"MAIL_PROVIDER_MODE":"private_email"},parser_registry=ServiceAdapterRegistry())
    def test_smoke_success_only_examine(self):
        transport=Mock(); transport.examine.return_value={"uidvalidity":77,"uidnext":100}
        result=run_smoke_test("pilot",transport=transport); self.assertEqual(result["connection"],"ok")
        transport.examine.assert_called_once_with("pilot","INBOX")
        self.assertFalse(transport.method_calls[1:])
    def test_smoke_failure_is_redacted(self):
        transport=Mock(); transport.examine.side_effect=ProviderAuthenticationFailed("FAKE_PASSWORD_DO_NOT_USE")
        result=run_smoke_test("pilot",transport=transport); self.assertEqual(result["connection"],"failed")
