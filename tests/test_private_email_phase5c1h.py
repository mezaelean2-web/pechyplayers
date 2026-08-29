import contextlib
import inspect
import io
import json
import socket
import sqlite3
import unittest
from dataclasses import replace
from unittest.mock import patch

from delegated_sender_auth_policy import (DelegatedSenderPolicyConfig,
                                          DelegatedServiceSenderAuthPolicy)
from mail_sender_auth_policy import SenderAuthEvidence,SenderAuthMalformed,parse_authentication_results
from private_email_sender_auth_probe import _summarize


FIRST="stream.example"; AUX="mailer.example"; SPF="delivery.example"; RECEIVER="receiver.example"
BASE=f"{RECEIVER}; dkim=pass header.d={FIRST}; spf=pass smtp.mailfrom=x@{SPF}"
CANARY="DELEGATED-SENSITIVE-CANARY-5C1H"


def config(**changes):
    base=DelegatedSenderPolicyConfig("streaming",frozenset({FIRST}),frozenset({FIRST}),
        frozenset({AUX}),frozenset({SPF}),False,frozenset({RECEIVER}),True)
    return replace(base,**changes)
def evidence(raw=BASE,**changes):
    base=SenderAuthEvidence(FIRST,parse_authentication_results((raw,)),True)
    return replace(base,**changes)


class DelegatedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=DelegatedServiceSenderAuthPolicy()
        self.network=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.network.start()
    def tearDown(self): self.network.stop()
    def decide(self,raw=BASE,cfg=None,**changes): return self.policy.evaluate(evidence(raw,**changes),cfg or config())
    def test_01_first_party_dkim_and_delegated_spf(self): self.assertEqual(self.decide().status,"authorized")
    def test_02_auxiliary_dkim_only_denied(self):
        raw=BASE.replace(f"header.d={FIRST}",f"header.d={AUX}"); self.assertEqual(self.decide(raw).reason,"first_party_dkim_pass_required")
    def test_03_first_party_fail_plus_auxiliary_pass_denied(self):
        raw=BASE.replace("dkim=pass","dkim=fail")+f"; dkim=pass header.d={AUX}"
        self.assertEqual(self.decide(raw).reason,"first_party_dkim_failed")
    def test_04_first_party_and_approved_auxiliary_pass(self):
        self.assertEqual(self.decide(BASE+f"; dkim=pass header.d={AUX}").status,"authorized")
    def test_05_unrelated_dkim_pass_ambiguous(self):
        self.assertEqual(self.decide(BASE+"; dkim=pass header.d=attacker.invalid").status,"ambiguous")
    def test_06_unrelated_dkim_fail_does_not_override_first_party(self):
        self.assertEqual(self.decide(BASE+"; dkim=fail header.d=unrelated.invalid").status,"authorized")
    def test_07_spf_fail(self): self.assertEqual(self.decide(BASE.replace("spf=pass","spf=fail")).status,"denied")
    def test_08_unapproved_spf_infrastructure(self):
        raw=BASE.replace(f"x@{SPF}","x@other.invalid"); self.assertEqual(self.decide(raw).reason,"approved_spf_infrastructure_pass_required")
    def test_09_spf_exact(self): self.assertEqual(self.decide().status,"authorized")
    def test_10_spf_subdomain_requires_explicit_policy(self):
        raw=BASE.replace(f"x@{SPF}",f"x@region.{SPF}")
        self.assertEqual(self.decide(raw).status,"denied")
        self.assertEqual(self.decide(raw,config(spf_allow_subdomains=True)).status,"authorized")
    def test_11_spf_suffix_attack(self):
        raw=BASE.replace(f"x@{SPF}",f"x@{SPF}.attacker.invalid")
        self.assertEqual(self.decide(raw,config(spf_allow_subdomains=True)).status,"denied")
    def test_12_from_lookalike(self): self.assertEqual(self.policy.evaluate(evidence(from_domain="streám.example"),config()).status,"denied")
    def test_13_from_unapproved(self): self.assertEqual(self.policy.evaluate(evidence(from_domain="other.invalid"),config()).reason,"from_domain_unapproved")
    def test_14_authserv_unapproved(self):
        self.assertEqual(self.decide(BASE.replace(RECEIVER,"other.receiver")).reason,"authserv_id_unapproved")
    def test_15_trusted_boundary_false(self): self.assertEqual(self.decide(trusted_receiver_boundary=False).reason,"receiver_boundary_untrusted")
    def test_16_multiple_authserv_ids(self):
        records=parse_authentication_results((BASE,BASE.replace(RECEIVER,"second.receiver")))
        decision=self.policy.evaluate(SenderAuthEvidence(FIRST,records,True),config())
        self.assertEqual((decision.status,decision.reason),("ambiguous","multiple_authserv_ids"))
    def test_17_malformed_auth_fails_before_policy(self):
        with self.assertRaises(SenderAuthMalformed): parse_authentication_results(("bad authserv; dkim pass",))
    def test_18_missing_dkim(self):
        raw=f"{RECEIVER}; spf=pass smtp.mailfrom=x@{SPF}"; self.assertEqual(self.decide(raw).status,"unsupported")
    def test_19_missing_spf(self):
        raw=f"{RECEIVER}; dkim=pass header.d={FIRST}"; self.assertEqual(self.decide(raw).status,"unsupported")
    def test_20_recipient_policy_is_independent(self):
        source=inspect.getsource(DelegatedServiceSenderAuthPolicy)
        self.assertNotIn("Recipient",source); self.assertNotIn("delivered_to",source.lower())
    def test_21_reseller_input_cannot_modify_policy(self):
        parameters=inspect.signature(DelegatedServiceSenderAuthPolicy.evaluate).parameters
        self.assertNotIn("reseller",parameters); self.assertNotIn("email",parameters)
    def test_22_no_raw_header_address_or_canary_output(self):
        raw=BASE+f"; dkim=pass header.d={CANARY}.invalid"; output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output): print(self.decide(raw))
        self.assertNotIn(raw,output.getvalue()); self.assertNotIn(CANARY,output.getvalue()); self.assertNotIn("@",output.getvalue())
    def test_23_no_persistence_sqlite_or_network(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")): self.assertEqual(self.decide().status,"authorized")
    def test_24_multiple_pass_domains_not_intrinsically_contradictory(self):
        auth=(BASE+f"; dkim=pass header.d={AUX}",)
        result=_summarize((f"x@{FIRST}",),auth)
        self.assertFalse(result["contradictory"]); self.assertEqual(result["dkim_pass_domains"],[AUX,FIRST])
    def test_25_pass_and_fail_remain_contradictory(self):
        result=_summarize((f"x@{FIRST}",),(BASE+f"; dkim=fail header.d={FIRST}",))
        self.assertTrue(result["contradictory"]); self.assertEqual(result["dkim_fail_domains"],[FIRST])


if __name__=="__main__": unittest.main()
