import contextlib
import io
import json
import socket
import sqlite3
import unittest
from dataclasses import replace
from unittest.mock import patch

from mail_sender_auth_policy import (MailSenderAuthPolicy,SenderAuthEvidence,SenderAuthMalformed,
    SenderPolicyConfig,domains_aligned,normalize_domain,parse_authentication_results)


AUTH="receiver.example; dkim=pass header.d=service.example; spf=pass smtp.mailfrom=bounce@service.example"
CANARY="SENDER-SENSITIVE-CANARY-5C1E"


def config(**changes):
    base=SenderPolicyConfig("service",frozenset({"service.example"}),frozenset({"service.example"}),
        frozenset({"service.example"}),frozenset({"receiver.example"}),"exact")
    return replace(base,**changes)
def evidence(values=(AUTH,),**changes):
    base=SenderAuthEvidence("service.example",parse_authentication_results(values),True)
    return replace(base,**changes)


class SenderPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=MailSenderAuthPolicy()
        self.network=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.network.start()
    def tearDown(self): self.network.stop()
    def decide(self,ev=None,cfg=None): return self.policy.evaluate(ev or evidence(),cfg or config())

    def test_exact_from_dkim_spf_alignment(self): self.assertEqual(self.decide().status,"authorized")
    def test_explicit_approved_subdomain_policy(self):
        cfg=config(alignment_mode="explicit_subdomain")
        ev=evidence(("receiver.example; dkim=pass header.d=mail.service.example; spf=pass smtp.mailfrom=bounce@mail.service.example",),from_domain="service.example")
        self.assertEqual(self.decide(ev,cfg).status,"authorized")
    def test_suffix_attack_is_denied(self):
        ev=evidence(("receiver.example; dkim=pass header.d=service.example.attacker.invalid; spf=pass smtp.mailfrom=x@service.example.attacker.invalid",))
        self.assertEqual(self.decide(ev,config(alignment_mode="explicit_subdomain")).status,"denied")
    def test_lookalike_domain_is_denied(self):
        ev=evidence(from_domain="servíce.example")
        self.assertEqual(self.decide(ev).reason,"from_domain_unapproved")
    def test_dkim_fail(self):
        ev=evidence(("receiver.example; dkim=fail header.d=service.example; spf=pass smtp.mailfrom=x@service.example",))
        self.assertEqual(self.decide(ev).reason,"dkim_fail")
    def test_spf_fail_neutral_and_softfail(self):
        for result in ("fail","neutral","softfail"):
            ev=evidence((f"receiver.example; dkim=pass header.d=service.example; spf={result} smtp.mailfrom=x@service.example",))
            self.assertEqual(self.decide(ev).reason,f"spf_{result}")
    def test_missing_dkim(self):
        ev=evidence(("receiver.example; spf=pass smtp.mailfrom=x@service.example",))
        self.assertEqual((self.decide(ev).status,self.decide(ev).reason),("unsupported","dkim_missing"))
    def test_missing_spf(self):
        ev=evidence(("receiver.example; dkim=pass header.d=service.example",))
        self.assertEqual((self.decide(ev).status,self.decide(ev).reason),("unsupported","spf_missing"))
    def test_multiple_dkim_same_domain_is_allowed(self):
        raw=AUTH+"; dkim=pass header.d=service.example"
        self.assertEqual(self.decide(evidence((raw,))).status,"authorized")
    def test_conflicting_dkim_results(self):
        raw=AUTH+"; dkim=fail header.d=service.example"
        decision=self.decide(evidence((raw,))); self.assertEqual((decision.status,decision.reason),("ambiguous","dkim_results_conflict"))
    def test_multiple_auth_results_contradictory(self):
        second="receiver.example; dkim=fail header.d=service.example; spf=pass smtp.mailfrom=x@service.example"
        self.assertEqual(self.decide(evidence((AUTH,second))).status,"ambiguous")
    def test_conflicting_spf_results(self):
        raw=AUTH+"; spf=fail smtp.mailfrom=x@service.example"
        decision=self.decide(evidence((raw,)))
        self.assertEqual((decision.status,decision.reason),("ambiguous","spf_results_conflict"))
    def test_malformed_auth_result(self):
        for raw in ("", "not a domain; dkim=pass", "receiver.example\r\nforged; dkim=pass"):
            with self.assertRaises(SenderAuthMalformed): parse_authentication_results((raw,))
    def test_unapproved_from_dkim_and_spf_domains(self):
        self.assertEqual(self.decide(evidence(from_domain="other.invalid")).reason,"from_domain_unapproved")
        dkim=evidence(("receiver.example; dkim=pass header.d=other.invalid; spf=pass smtp.mailfrom=x@service.example",))
        self.assertEqual(self.decide(dkim).reason,"dkim_domain_unapproved")
        spf=evidence(("receiver.example; dkim=pass header.d=service.example; spf=pass smtp.mailfrom=x@other.invalid",))
        self.assertEqual(self.decide(spf).reason,"spf_domain_unapproved")
    def test_case_and_trailing_dot_normalization(self):
        raw="RECEIVER.EXAMPLE.; dkim=pass header.d=SERVICE.EXAMPLE.; spf=pass smtp.mailfrom=x@SERVICE.EXAMPLE."
        self.assertEqual(self.decide(evidence((raw,),from_domain="SERVICE.EXAMPLE.")).status,"authorized")
    def test_invalid_domain(self):
        for domain in ("invalid","service.example.attacker invalid","-bad.example"):
            with self.assertRaises(SenderAuthMalformed): normalize_domain(domain)
    def test_arbitrary_auth_results_injection_is_not_authority(self):
        self.assertEqual(self.decide(evidence(trusted_receiver_boundary=False)).reason,"authentication_results_untrusted")
    def test_untrusted_authserv_id(self):
        raw="attacker.invalid; dkim=pass header.d=service.example; spf=pass smtp.mailfrom=x@service.example"
        self.assertEqual(self.decide(evidence((raw,))).reason,"authserv_id_untrusted")
    def test_reseller_input_cannot_alter_policy_api(self):
        import inspect
        parameters=inspect.signature(MailSenderAuthPolicy.evaluate).parameters
        self.assertNotIn("email",parameters); self.assertNotIn("reseller",parameters)
    def test_no_substring_authorization(self):
        self.assertFalse(domains_aligned("service.example.attacker.invalid","service.example","explicit_subdomain"))
    def test_no_canary_or_raw_headers_in_decision(self):
        raw=f"receiver.example; dkim=fail header.d=service.example; spf=pass smtp.mailfrom={CANARY}@service.example"
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output): print(self.decide(evidence((raw,))))
        self.assertNotIn(CANARY,output.getvalue()); self.assertNotIn(raw,output.getvalue())
    def test_no_persistence_sqlite_or_network(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")):
            self.assertEqual(self.decide().status,"authorized")
    def test_multiple_pass_domains_are_ambiguous(self):
        raw=AUTH+"; dkim=pass header.d=other.invalid"
        self.assertEqual(self.decide(evidence((raw,))).reason,"dkim_domains_conflict")
    def test_duplicate_identical_auth_results_are_deterministic(self):
        self.assertEqual(self.decide(evidence((AUTH,AUTH))).status,"authorized")
    def test_authserv_and_method_domains_are_extracted(self):
        record=parse_authentication_results((AUTH,))[0]
        self.assertEqual(record.authserv_id,"receiver.example")
        self.assertEqual(record.dkim[0].domain,"service.example"); self.assertEqual(record.spf[0].domain,"service.example")
    def test_header_count_and_size_are_bounded(self):
        with self.assertRaises(SenderAuthMalformed): parse_authentication_results((AUTH,)*11)
        with self.assertRaises(SenderAuthMalformed): parse_authentication_results(("x"*4097,))


if __name__=="__main__": unittest.main()
