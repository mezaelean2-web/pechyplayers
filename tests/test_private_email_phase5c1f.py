import contextlib
import imaplib
import inspect
import io
import json
import socket
import sqlite3
import unittest
from unittest.mock import patch

from mail_sender_auth_policy import SenderAuthMalformed
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import ProviderMessageMalformed
from private_email_sender_auth_probe import (PrivateEmailSenderAuthProbe,SenderProbeDenied,
    SenderProbeFromInvalid,SenderProbeUIDInvalid,SenderProbeUIDValidityMismatch,_summarize)


CONFIG="pechy_pilot"; VALIDITY=1755066514; UID=157615
LOCALPART="sender-localpart-canary-5c1f"; FROM=f"Private Display <{LOCALPART}@service.example>"
AUTH="receiver.example; dkim=pass header.d=service.example; spf=pass smtp.mailfrom=bounce@service.example"
BUNDLE={CONFIG:{"username":"internal@example.invalid","password":"credential-canary-5c1f"}}


class FakeTransport:
    def __init__(self,headers=None): self.headers=headers or {"from":(FROM,),"authentication_results":(AUTH,)}; self.validity=VALIDITY; self.commands=[]; self.fetches=0
    def examine(self,config,folder): self.commands.append(("EXAMINE",config,folder)); return {"uidvalidity":self.validity,"uidnext":UID+1}
    def fetch_sender_auth_headers(self,config,folder,uid):
        self.commands.append(("FETCH_SENDER_AUTH",config,folder,uid)); self.fetches+=1
        if uid==999: raise ProviderMessageMalformed()
        return self.headers


class SenderProbeTests(unittest.TestCase):
    def setUp(self):
        self.transport=FakeTransport(); self.resolver=ProviderCredentialResolver(bundle=BUNDLE)
        self.probe=PrivateEmailSenderAuthProbe(self.resolver,self.transport)
        self.sock=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.sock.start()
        self.imap=patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("IMAP forbidden")); self.imap.start()
    def tearDown(self): self.imap.stop(); self.sock.stop()
    def run_probe(self): return self.probe.probe(CONFIG,"INBOX",VALIDITY,UID)

    def test_01_valid_from_domain(self): self.assertEqual(self.run_probe()["from_domain"],"service.example")
    def test_02_localpart_never_output(self): self.assertNotIn(LOCALPART,json.dumps(self.run_probe()))
    def test_03_display_name_never_output(self): self.assertNotIn("Private Display",json.dumps(self.run_probe()))
    def test_04_one_authentication_results(self): self.assertEqual(self.run_probe()["authentication_results_count"],1)
    def test_05_multiple_bounded_authentication_results(self):
        self.transport.headers["authentication_results"]=(AUTH,AUTH); self.assertEqual(self.run_probe()["authentication_results_count"],2)
    def test_06_dkim_association(self): self.assertEqual((self.run_probe()["dkim_results"],self.run_probe()["dkim_domains"]),(["pass"],["service.example"]))
    def test_07_spf_association(self): self.assertEqual((self.run_probe()["spf_results"],self.run_probe()["spf_mailfrom_domains"]),(["pass"],["service.example"]))
    def test_08_dkim_fail(self):
        self.transport.headers["authentication_results"]=(AUTH.replace("dkim=pass","dkim=fail"),); self.assertEqual(self.run_probe()["dkim_results"],["fail"])
    def test_09_spf_fail(self):
        self.transport.headers["authentication_results"]=(AUTH.replace("spf=pass","spf=fail"),); self.assertEqual(self.run_probe()["spf_results"],["fail"])
    def test_10_contradictory_results(self):
        self.transport.headers["authentication_results"]=(AUTH,AUTH.replace("dkim=pass","dkim=fail")); self.assertTrue(self.run_probe()["contradictory"])
    def test_11_multiple_authserv_ids(self):
        self.transport.headers["authentication_results"]=(AUTH,AUTH.replace("receiver.example","other.receiver.example")); self.assertTrue(self.run_probe()["multiple_authserv_ids"])
    def test_12_malformed_authserv(self):
        self.transport.headers["authentication_results"]=("invalid authserv; dkim=pass",)
        with self.assertRaises(SenderAuthMalformed): self.run_probe()
    def test_13_malformed_from(self):
        self.transport.headers["from"]=("not-an-address",)
        with self.assertRaises(SenderProbeFromInvalid): self.run_probe()
    def test_14_multiple_from_addresses(self):
        self.transport.headers["from"]=("a@example.invalid, b@example.invalid",)
        with self.assertRaises(SenderProbeFromInvalid): self.run_probe()
    def test_15_encoded_from(self):
        self.transport.headers["from"]=(f"=?utf-8?q?Private_Name?= <{LOCALPART}@service.example>",); self.assertEqual(self.run_probe()["from_domain"],"service.example")
    def test_16_oversized_from(self):
        self.transport.headers["from"]=("x"*2050+"@service.example",)
        with self.assertRaises(SenderProbeFromInvalid): self.run_probe()
    def test_17_oversized_authentication_results(self):
        self.transport.headers["authentication_results"]=("x"*4097,)
        with self.assertRaises(SenderAuthMalformed): self.run_probe()
    def test_18_excessive_auth_records(self):
        self.transport.headers["authentication_results"]=(AUTH,)*11
        with self.assertRaises(SenderAuthMalformed): self.run_probe()
    def test_19_invalid_uid(self):
        for value in (0,-1,"bad"):
            with self.subTest(value=value),self.assertRaises(SenderProbeUIDInvalid): self.probe.probe(CONFIG,"INBOX",VALIDITY,value)
    def test_20_missing_uid(self):
        with self.assertRaises(ProviderMessageMalformed): self.probe.probe(CONFIG,"INBOX",VALIDITY,999)
    def test_21_uidvalidity_mismatch(self):
        with self.assertRaises(SenderProbeUIDValidityMismatch): self.probe.probe(CONFIG,"INBOX",1,UID)
        self.assertEqual(self.transport.fetches,0)
    def test_22_provider_rejected(self):
        with self.assertRaises(SenderProbeDenied): self.probe.probe("other","INBOX",VALIDITY,UID)
    def test_23_folder_rejected(self):
        with self.assertRaises(SenderProbeDenied): self.probe.probe(CONFIG,"Archive",VALIDITY,UID)
    def test_24_exactly_one_uid(self):
        self.run_probe(); self.assertEqual(self.transport.fetches,1); self.assertEqual([x[0] for x in self.transport.commands],["EXAMINE","FETCH_SENDER_AUTH","EXAMINE"])
    def test_25_no_mutations(self):
        self.run_probe(); self.assertFalse({"STORE","APPEND","COPY","MOVE","DELETE","EXPUNGE"}&{x[0] for x in self.transport.commands})
    def test_26_no_credentials_output(self):
        exposed=json.dumps(self.run_probe())+repr(self.resolver); self.assertNotIn(BUNDLE[CONFIG]["password"],exposed); self.assertNotIn(BUNDLE[CONFIG]["username"],exposed)
    def test_27_canary_raw_header_absent(self):
        exposed=json.dumps(self.run_probe()); self.assertNotIn(FROM,exposed); self.assertNotIn(AUTH,exposed)
    def test_28_no_persistence_or_sqlite(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")): self.run_probe()
    def test_29_trusted_boundary_is_always_false(self): self.assertFalse(self.run_probe()["trusted_boundary_proven"])
    def test_30_malformed_flag_is_false_on_success(self): self.assertFalse(self.run_probe()["malformed"])


class TransportContractTests(unittest.TestCase):
    def _capture_query(self):
        class Client:
            sock=None
            def __init__(self): self.query=None
            def login(self,*_): return "OK",[]
            def select(self,*_,**__): return "OK",[]
            def uid(self,_command,_uid,query): self.query=query; return "OK",[(b"1 (UID 157615)",b"From: x@service.example\r\nAuthentication-Results: receiver.example; dkim=pass header.d=service.example\r\n\r\n")]
            def logout(self): pass
        client=Client(); transport=PrivateEmailIMAPTransport(ProviderCredentialResolver(bundle=BUNDLE),client_factory=lambda *_a,**_k:client)
        transport.fetch_sender_auth_headers(CONFIG,"INBOX",UID); return client.query
    def test_31_exact_header_query(self): self.assertEqual(self._capture_query(),"(UID BODY.PEEK[HEADER.FIELDS (FROM AUTHENTICATION-RESULTS)])")
    def test_32_no_subject_or_body_requested(self):
        query=self._capture_query().upper(); self.assertNotIn("SUBJECT",query); self.assertNotIn("BODY[]",query); self.assertNotIn("RFC822",query)
    def test_33_no_recipient_headers_requested(self):
        query=self._capture_query().upper()
        for forbidden in (" TO "," CC ","DELIVERED-TO","X-ORIGINAL-TO","ENVELOPE-TO"): self.assertNotIn(forbidden,query)
    def test_34_no_received_return_path_or_dkim_signature(self):
        query=self._capture_query().upper()
        for forbidden in ("RECEIVED","RETURN-PATH","DKIM-SIGNATURE","MESSAGE-ID","DATE"): self.assertNotIn(forbidden,query)
    def test_35_no_network_on_import_construction_or_fake_probe(self):
        with patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")),patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("IMAP forbidden")):
            resolver=ProviderCredentialResolver(bundle=BUNDLE); PrivateEmailSenderAuthProbe(resolver,FakeTransport()).probe(CONFIG,"INBOX",VALIDITY,UID)


if __name__=="__main__": unittest.main()
