import contextlib
import imaplib
import inspect
import io
import json
import socket
import sqlite3
import unittest
from unittest.mock import patch

from private_email_adapter_discovery import DiscoveryDenied, DiscoveryMalformed
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport, RECIPIENT_ROUTING_HEADERS
from private_email_recipient_routing_probe import (PrivateEmailRecipientRoutingProbe,
    ProbeUIDInvalid, ProbeUIDValidityMismatch, _routing_result)


CONFIG="pechy_pilot"; RECIPIENT="routing-canary@example.invalid"
BUNDLE={CONFIG:{"username":RECIPIENT,"password":"credential-canary-5c1c"}}


class FakeIMAPTransport:
    def __init__(self,headers=None):
        self.headers=headers or {}; self.uidvalidity=1755066514; self.commands=[]; self.fetches=0
    def examine(self,config,folder):
        self.commands.append(("EXAMINE",config,folder)); return {"uidvalidity":self.uidvalidity,"uidnext":200}
    def fetch_recipient_routing_headers(self,config,folder,uid):
        self.commands.append(("FETCH_RECIPIENT_HEADERS",config,folder,uid)); self.fetches+=1
        if uid==999: raise DiscoveryMalformed()
        return self.headers


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.transport=FakeIMAPTransport(); self.resolver=ProviderCredentialResolver(bundle=BUNDLE)
        self.probe=PrivateEmailRecipientRoutingProbe(self.resolver,self.transport)
        self.socket_patch=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.socket_patch.start()
        self.imap_patch=patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("IMAP forbidden")); self.imap_patch.start()
    def tearDown(self): self.imap_patch.stop(); self.socket_patch.stop()
    def run_probe(self): return self.probe.probe(CONFIG,"INBOX",1755066514,157615)

    def test_to_exact_match(self):
        self.transport.headers={"to":RECIPIENT}; result=self.run_probe()
        self.assertTrue(result["direct_match"]); self.assertFalse(result["cc_match"])
    def test_cc_exact_match(self):
        self.transport.headers={"to":"other@example.invalid","cc":RECIPIENT}
        result=self.run_probe(); self.assertTrue(result["direct_match"]); self.assertTrue(result["cc_match"])
    def test_delivered_to_alias(self):
        self.transport.headers={"to":"alias@example.invalid","delivered_to":RECIPIENT}
        result=self.run_probe(); self.assertTrue(result["delivered_to_match"]); self.assertTrue(result["alias_possible"])
    def test_x_original_to_match(self):
        self.transport.headers={"x_original_to":RECIPIENT}; self.assertTrue(self.run_probe()["x_original_to_match"])
    def test_envelope_to_match(self):
        self.transport.headers={"envelope_to":RECIPIENT}; self.assertTrue(self.run_probe()["envelope_to_match"])
    def test_all_mismatch(self):
        self.transport.headers={key:"other@example.invalid" for key in ("to","cc","delivered_to","x_original_to","envelope_to")}
        result=self.run_probe(); self.assertFalse(result["direct_match"]); self.assertFalse(result["envelope_match"])
    def test_headers_absent(self):
        result=self.run_probe()
        keys=("to_present","cc_present","delivered_to_present","x_original_to_present","envelope_to_present")
        self.assertFalse(any(result[key] for key in keys))
    def test_multiple_recipients(self):
        self.transport.headers={"to":f"other@example.invalid, {RECIPIENT}"}; self.assertTrue(self.run_probe()["direct_match"])
    def test_case_normalization(self):
        self.transport.headers={"to":RECIPIENT.upper()}; self.assertTrue(self.run_probe()["direct_match"])
    def test_display_name(self):
        self.transport.headers={"to":f"Private Person <{RECIPIENT}>"}; self.assertTrue(self.run_probe()["direct_match"])
    def test_malformed_address(self):
        self.transport.headers={"to":"not-an-address"}
        with self.assertRaises(DiscoveryMalformed): self.run_probe()
    def test_oversized_header(self):
        self.transport.headers={"to":"x"*2050+"@example.invalid"}
        with self.assertRaises(DiscoveryMalformed): self.run_probe()
    def test_more_than_twenty_recipients(self):
        self.transport.headers={"to":", ".join(f"u{x}@example.invalid" for x in range(21))}
        with self.assertRaises(DiscoveryMalformed): self.run_probe()
    def test_encoded_recipient(self):
        self.transport.headers={"to":f"=?utf-8?q?Private?= <{RECIPIENT}>"}; self.assertTrue(self.run_probe()["direct_match"])
    def test_missing_uid_fails_closed(self):
        with self.assertRaises(DiscoveryMalformed): self.probe.probe(CONFIG,"INBOX",1755066514,999)
    def test_invalid_uid(self):
        for uid in (0,-1,"bad"):
            with self.subTest(uid=uid),self.assertRaises(ProbeUIDInvalid):
                self.probe.probe(CONFIG,"INBOX",1755066514,uid)
    def test_uidvalidity_mismatch_before_fetch(self):
        with self.assertRaises(ProbeUIDValidityMismatch): self.probe.probe(CONFIG,"INBOX",1,157615)
        self.assertEqual(self.transport.fetches,0)
    def test_provider_rejected(self):
        with self.assertRaises(DiscoveryDenied): self.probe.probe("other","INBOX",1755066514,157615)
    def test_folder_rejected(self):
        with self.assertRaises(DiscoveryDenied): self.probe.probe(CONFIG,"Archive",1755066514,157615)
    def test_exactly_one_uid_is_inspected(self):
        self.run_probe(); self.assertEqual(self.transport.fetches,1)
        self.assertEqual([x[0] for x in self.transport.commands],["EXAMINE","FETCH_RECIPIENT_HEADERS","EXAMINE"])
    def test_no_sensitive_address_or_credentials_in_output(self):
        self.transport.headers={"to":RECIPIENT}; output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output): print(json.dumps(self.run_probe()))
        exposed=output.getvalue()+repr(self.resolver)
        self.assertNotIn(RECIPIENT,exposed); self.assertNotIn(BUNDLE[CONFIG]["password"],exposed)
    def test_no_persistence_or_sqlite(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")): self.run_probe()
    def test_no_mutation_or_body_methods(self):
        self.run_probe(); names={x[0] for x in self.transport.commands}
        self.assertFalse(names & {"STORE","APPEND","COPY","MOVE","DELETE","EXPUNGE","BODY.PEEK"})


class TransportContractTests(unittest.TestCase):
    def test_allowed_header_tuple_is_exact(self):
        self.assertEqual(RECIPIENT_ROUTING_HEADERS,("TO","CC","DELIVERED-TO","X-ORIGINAL-TO","ENVELOPE-TO"))
    def test_generated_fetch_query_has_only_allowed_headers(self):
        class Client:
            sock=None
            def __init__(self): self.query=None
            def login(self,*_): return "OK",[]
            def select(self,*_,**__): return "OK",[]
            def uid(self,command,uid,query):
                self.query=query
                return "OK",[(b"1 (UID 157615)",b"To: routing-canary@example.invalid\r\n\r\n")]
            def logout(self): pass
        client=Client()
        transport=PrivateEmailIMAPTransport(ProviderCredentialResolver(bundle=BUNDLE),
            client_factory=lambda *_args,**_kwargs:client)
        transport.fetch_recipient_routing_headers(CONFIG,"INBOX",157615)
        self.assertEqual(client.query,
            "(UID BODY.PEEK[HEADER.FIELDS (TO CC DELIVERED-TO X-ORIGINAL-TO ENVELOPE-TO)])")
    def test_probe_has_no_sqlite_or_file_persistence_dependency(self):
        source=inspect.getsource(PrivateEmailRecipientRoutingProbe)
        for forbidden in ("sqlite","open(","write_text","write_bytes"):
            self.assertNotIn(forbidden,source.lower())
    def test_safe_result_contains_only_flags(self):
        result=_routing_result({"to":RECIPIENT},RECIPIENT)
        self.assertTrue(all(isinstance(value,bool) for value in result.values()))
        self.assertNotIn(RECIPIENT,json.dumps(result))
    def test_network_and_real_imap_are_not_constructed_by_import_or_probe(self):
        with patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")),patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("IMAP forbidden")):
            resolver=ProviderCredentialResolver(bundle=BUNDLE)
            PrivateEmailRecipientRoutingProbe(resolver,FakeIMAPTransport()).probe(CONFIG,"INBOX",1755066514,157615)
    def test_expected_recipient_is_not_a_probe_argument(self):
        signature=inspect.signature(PrivateEmailRecipientRoutingProbe.probe)
        self.assertNotIn("recipient",signature.parameters); self.assertNotIn("email",signature.parameters)
    def test_fetch_contract_is_one_explicit_uid(self):
        signature=inspect.signature(PrivateEmailIMAPTransport.fetch_recipient_routing_headers)
        self.assertEqual(tuple(signature.parameters),("self","provider_config_id","folder_key","uid"))


if __name__=="__main__": unittest.main()
