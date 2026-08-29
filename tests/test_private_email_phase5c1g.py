import json
import socket
import sqlite3
import unittest
from unittest.mock import patch

from mail_sender_auth_policy import (MailSenderAuthPolicy,SenderAuthEvidence,SenderAuthMalformed,
    SenderPolicyConfig,parse_authentication_results)


BASE="receiver.example; dkim=pass header.d=service.example; spf=pass smtp.mailfrom=bounce@service.example"
POLICY=SenderPolicyConfig("service",frozenset({"service.example"}),frozenset({"service.example"}),
    frozenset({"service.example"}),frozenset({"receiver.example"}),"exact")
CANARY="PARSER-SENSITIVE-CANARY-5C1G"


def parse(raw): return parse_authentication_results((raw,))
def decide(raw): return MailSenderAuthPolicy().evaluate(SenderAuthEvidence("service.example",parse(raw),True),POLICY)


class AuthenticationResultsCorpusTests(unittest.TestCase):
    def setUp(self): self.network=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.network.start()
    def tearDown(self): self.network.stop()
    def test_01_simple_dkim_pass(self): self.assertEqual(parse("receiver.example; dkim=pass header.d=service.example")[0].dkim[0].result,"pass")
    def test_02_simple_spf_pass(self): self.assertEqual(parse("receiver.example; spf=pass smtp.mailfrom=x@service.example")[0].spf[0].result,"pass")
    def test_03_dkim_spf_same_record(self): self.assertEqual(decide(BASE).status,"authorized")
    def test_04_folded_record(self): self.assertEqual(decide("receiver.example;\r\n\tdkim=pass header.d=service.example;\r\n spf=pass smtp.mailfrom=x@service.example").status,"authorized")
    def test_05_lf_whitespace_fold(self): self.assertEqual(decide("receiver.example;\n dkim=pass header.d=service.example; spf=pass smtp.mailfrom=x@service.example").status,"authorized")
    def test_06_tabs(self): self.assertEqual(decide("receiver.example;\tdkim = pass header.d = service.example; spf = pass smtp.mailfrom = x@service.example").status,"authorized")
    def test_07_comments(self): self.assertEqual(decide("receiver.example (receiver); dkim=pass (ok) header.d=service.example; spf=pass smtp.mailfrom=x@service.example").status,"authorized")
    def test_08_quoted_values(self): self.assertEqual(decide('receiver.example; dkim=pass header.d="service.example"; spf=pass smtp.mailfrom="x@service.example"').status,"authorized")
    def test_09_reason_property(self): self.assertEqual(decide(BASE+" reason=accepted").status,"authorized")
    def test_10_header_d(self): self.assertEqual(parse(BASE)[0].dkim[0].domain,"service.example")
    def test_11_header_i_unknown_property(self): self.assertEqual(decide(BASE.replace("header.d=service.example","header.d=service.example header.i=x@service.example")).status,"authorized")
    def test_12_smtp_mailfrom(self): self.assertEqual(parse(BASE)[0].spf[0].domain,"service.example")
    def test_13_smtp_helo_without_mailfrom_fails_policy(self):
        raw="receiver.example; dkim=pass header.d=service.example; spf=pass smtp.helo=service.example"
        self.assertEqual(decide(raw).reason,"spf_domain_missing")
    def test_14_dmarc_alongside(self): self.assertEqual(decide(BASE+"; dmarc=pass header.from=service.example").status,"authorized")
    def test_15_arc_alongside(self): self.assertEqual(decide(BASE+"; arc=pass").status,"authorized")
    def test_16_unknown_method_alongside(self): self.assertEqual(decide(BASE+"; futureauth=pass thing=value").status,"authorized")
    def test_17_unknown_property(self): self.assertEqual(decide(BASE.replace("header.d=service.example","header.d=service.example policy.x=value")).status,"authorized")
    def test_18_multiple_legitimate_records(self): self.assertEqual(len(parse_authentication_results((BASE,BASE))),2)
    def test_19_duplicate_dkim(self): self.assertEqual(decide(BASE+"; dkim=pass header.d=service.example").status,"authorized")
    def test_20_conflicting_dkim(self): self.assertEqual(decide(BASE+"; dkim=fail header.d=service.example").status,"ambiguous")
    def test_21_conflicting_spf(self): self.assertEqual(decide(BASE+"; spf=fail smtp.mailfrom=x@service.example").status,"ambiguous")
    def test_22_malformed_dkim(self):
        with self.assertRaises(SenderAuthMalformed): parse(BASE+"; dkim pass header.d=service.example")
    def test_23_malformed_spf(self):
        with self.assertRaises(SenderAuthMalformed): parse(BASE+"; spf pass smtp.mailfrom=x@service.example")
    def test_24_missing_header_d(self): self.assertEqual(decide(BASE.replace(" header.d=service.example"," ")).reason,"dkim_domain_missing")
    def test_25_missing_smtp_mailfrom(self): self.assertEqual(decide(BASE.replace(" smtp.mailfrom=bounce@service.example"," ")).reason,"spf_domain_missing")
    def test_26_malformed_authserv_id(self):
        with self.assertRaises(SenderAuthMalformed): parse("bad authserv; dkim=pass header.d=service.example")
    def test_27_duplicate_property_rejected(self):
        with self.assertRaises(SenderAuthMalformed) as caught: parse(BASE.replace("header.d=service.example","header.d=service.example header.d=attacker.invalid"))
        self.assertEqual(caught.exception.diagnostic["safe_failure_class"],"duplicate_property")
    def test_28_oversized_record(self):
        with self.assertRaises(SenderAuthMalformed): parse("x"*4097)
    def test_29_more_than_ten_records(self):
        with self.assertRaises(SenderAuthMalformed): parse_authentication_results((BASE,)*11)
    def test_30_more_than_twenty_results(self):
        raw="receiver.example; "+"; ".join("dkim=pass header.d=service.example" for _ in range(21))
        with self.assertRaises(SenderAuthMalformed): parse(raw)
    def test_31_suffix_attack(self):
        raw=BASE.replace("header.d=service.example","header.d=service.example.attacker.invalid")
        self.assertEqual(decide(raw).status,"denied")
    def test_32_idna_domain(self): self.assertTrue(parse("receiver.example; dkim=pass header.d=bücher.example")[0].dkim[0].domain.startswith("xn--"))
    def test_33_trailing_dot(self): self.assertEqual(parse(BASE.replace("service.example","service.example."))[0].dkim[0].domain,"service.example")
    def test_34_uppercase(self): self.assertEqual(parse(BASE.upper())[0].authserv_id,"receiver.example")
    def test_35_header_name_included(self): self.assertEqual(decide("Authentication-Results: "+BASE).status,"authorized")
    def test_36_header_name_removed(self): self.assertEqual(decide(BASE).status,"authorized")
    def test_37_bytes_representation(self): self.assertEqual(parse_authentication_results((BASE.encode(),))[0].authserv_id,"receiver.example")
    def test_38_string_representation(self): self.assertEqual(parse_authentication_results((BASE,))[0].authserv_id,"receiver.example")


class SecurityRegressionTests(unittest.TestCase):
    def test_injection_new_header_rejected(self):
        with self.assertRaises(SenderAuthMalformed): parse(BASE+"\r\nAuthentication-Results: attacker.invalid; dkim=pass header.d=service.example")
    def test_substrings_do_not_authorize(self):
        for raw in ("receiver.example; x=none note=dkim=pass", "receiver.example; x=none note=spf=pass"):
            decision=decide(raw); self.assertNotEqual(decision.status,"authorized")
    def test_unassociated_domains_do_not_authorize(self):
        raw="receiver.example; dkim=pass; spf=pass; x=none header.d=service.example smtp.mailfrom=x@service.example"
        self.assertNotEqual(decide(raw).status,"authorized")
    def test_unknown_method_never_substitutes_required_methods(self):
        self.assertNotEqual(decide("receiver.example; futureauth=pass header.d=service.example smtp.mailfrom=x@service.example").status,"authorized")
    def test_untrusted_boundary_remains_denied(self):
        evidence=SenderAuthEvidence("service.example",parse(BASE),False)
        self.assertEqual(MailSenderAuthPolicy().evaluate(evidence,POLICY).reason,"authentication_results_untrusted")
    def test_safe_diagnostic_contains_no_content(self):
        raw=f"receiver.example; dkim=pass header.d={CANARY} invalid"
        try: parse(raw)
        except SenderAuthMalformed as exc:
            exposed=json.dumps(exc.diagnostic); self.assertNotIn(CANARY,exposed); self.assertNotIn("receiver.example",exposed)
    def test_no_persistence_sqlite_or_network(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")):
            self.assertEqual(decide(BASE).status,"authorized")


if __name__=="__main__": unittest.main()
