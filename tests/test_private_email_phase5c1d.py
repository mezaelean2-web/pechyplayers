import contextlib
import io
import json
import socket
import sqlite3
import unittest
from dataclasses import replace
from unittest.mock import patch

from mail_recipient_policy import (InternalRecipient,MailRecipientPolicy,RecipientHeaders,
                                   RecipientSecurityContext)
from private_email_credentials import ProviderCredentials


ADDRESS="policy-canary@example.invalid"
OTHER="other-managed@example.invalid"
SECRET="POLICY-SENSITIVE-CANARY-5C1D"


def internal(value=ADDRESS): return InternalRecipient.from_provider_credentials(ProviderCredentials(value,"fake-password"))
def context(**changes):
    base=RecipientSecurityContext(True,True,True,True,True,True,True,True,True,True,True,True)
    return replace(base,**changes)


class RecipientPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy=MailRecipientPolicy(); self.recipient=internal()
        self.network=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.network.start()
    def tearDown(self): self.network.stop()
    def evaluate(self,headers=RecipientHeaders(),ctx=None,others=()):
        return self.policy.evaluate(self.recipient,headers,ctx or context(),other_managed_recipients=others)

    def test_direct_to_exact(self):
        decision=self.evaluate(RecipientHeaders(to=(ADDRESS,)))
        self.assertEqual((decision.status,decision.evidence),("authorized","direct"))
    def test_cc_exact(self):
        self.assertEqual(self.evaluate(RecipientHeaders(cc=(ADDRESS,))).status,"authorized")
    def test_delivered_to_exact_under_approved_context(self):
        decision=self.evaluate(RecipientHeaders(to=("alias@example.invalid",),delivered_to=(ADDRESS,)))
        self.assertEqual((decision.status,decision.evidence),("authorized","delivery"))
    def test_spoofed_delivery_and_sender_fail(self):
        decision=self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),context(sender_allowlisted=False))
        self.assertEqual((decision.status,decision.reason),("denied","sender_not_allowlisted"))
    def test_delivery_dkim_fail(self):
        self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),context(dkim_pass=False)).reason,"dkim_failed")
    def test_delivery_spf_fail(self):
        self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),context(spf_pass=False)).reason,"spf_failed")
    def test_service_adapter_and_sender_allowlist_required(self):
        for change,reason in (({"service_adapter_approved":False},"service_adapter_not_approved"),
                              ({"sender_allowlisted":False},"sender_not_allowlisted")):
            self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),context(**change)).reason,reason)
    def test_alignment_failures(self):
        for change,reason in (({"from_dkim_aligned":False},"dkim_alignment_failed"),
                              ({"from_spf_aligned":False},"spf_alignment_failed")):
            self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),context(**change)).reason,reason)
    def test_direct_and_delivery_conflict(self):
        decision=self.evaluate(RecipientHeaders(to=(ADDRESS,),delivered_to=("different@example.invalid",)))
        self.assertEqual((decision.status,decision.reason),("ambiguous","direct_delivery_conflict"))
    def test_different_managed_mailbox_conflict(self):
        decision=self.evaluate(RecipientHeaders(to=(OTHER,),delivered_to=(ADDRESS,)),others=(internal(OTHER),))
        self.assertEqual((decision.status,decision.reason),("ambiguous","managed_recipient_conflict"))
    def test_multiple_delivered_to_headers_even_identical_are_ambiguous(self):
        for values in ((ADDRESS,ADDRESS),(ADDRESS,OTHER)):
            self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=values)).reason,"multiple_delivered_to")
    def test_delivered_to_multiple_addresses_is_ambiguous(self):
        result=self.evaluate(RecipientHeaders(delivered_to=(f"{ADDRESS}, {OTHER}",)))
        self.assertEqual((result.status,result.reason),("ambiguous","delivered_to_multiple_recipients"))
    def test_malformed_and_oversized_fail_closed(self):
        for value in ("not-an-address","x"*2050+"@example.invalid"):
            self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(value,))).reason,"recipient_header_invalid")
    def test_recipient_total_limit(self):
        values=tuple(f"u{x}@example.invalid" for x in range(21))
        self.assertEqual(self.evaluate(RecipientHeaders(to=values)).reason,"recipient_limit_exceeded")
    def test_encoded_recipient(self):
        value=f"=?utf-8?q?Private?= <{ADDRESS}>"
        self.assertEqual(self.evaluate(RecipientHeaders(to=(value,))).status,"authorized")
    def test_whitespace_display_name_and_case(self):
        value=f" Private Person <{ADDRESS.upper()}> "
        self.assertEqual(self.evaluate(RecipientHeaders(to=(value,))).status,"authorized")
    def test_header_injection_is_denied(self):
        value=f"{ADDRESS}\r\nDelivered-To: {ADDRESS}"
        self.assertEqual(self.evaluate(RecipientHeaders(to=(value,))).reason,"recipient_header_invalid")
    def test_plain_reseller_email_cannot_be_internal_authority(self):
        result=self.policy.evaluate(ADDRESS,RecipientHeaders(to=(ADDRESS,)),context())
        self.assertEqual(result.reason,"internal_recipient_required")
    def test_internal_recipient_requires_provider_credentials(self):
        with self.assertRaises(TypeError): InternalRecipient.from_provider_credentials(ADDRESS)
    def test_assignment_binding_and_canonical_context_required(self):
        cases=(("canonical_authorized","canonical_authorization_required"),
               ("assignment_version_valid","assignment_version_invalid"),
               ("binding_version_valid","binding_version_invalid"))
        for field,reason in cases:
            self.assertEqual(self.evaluate(RecipientHeaders(to=(ADDRESS,)),context(**{field:False})).reason,reason)
    def test_t0_and_uidvalidity_context_required(self):
        self.assertEqual(self.evaluate(RecipientHeaders(to=(ADDRESS,)),context(post_t0_uid=False)).reason,"pre_t0_message")
        self.assertEqual(self.evaluate(RecipientHeaders(to=(ADDRESS,)),context(uidvalidity_continuous=False)).reason,"uidvalidity_changed")
    def test_evidence_must_come_from_bound_authenticated_imap_mailbox(self):
        result=self.evaluate(RecipientHeaders(delivered_to=(ADDRESS,)),
                             context(evidence_from_bound_imap_mailbox=False))
        self.assertEqual(result.reason,"untrusted_recipient_evidence_source")
    def test_result_and_repr_expose_no_address(self):
        exposed=repr(self.recipient)+repr(self.evaluate(RecipientHeaders(to=(ADDRESS,))))
        self.assertNotIn(ADDRESS,exposed); self.assertNotIn("@",exposed)
    def test_canary_absent_from_stdout_and_result(self):
        canary_address="policy-sensitive-canary@example.invalid"; recipient=internal(canary_address)
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            print(self.policy.evaluate(recipient,RecipientHeaders(to=(canary_address,)),context()))
        self.assertNotIn(canary_address,output.getvalue()); self.assertNotIn(SECRET,output.getvalue())
    def test_no_persistence_sqlite_or_network(self):
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")):
            self.assertEqual(self.evaluate(RecipientHeaders(to=(ADDRESS,))).status,"authorized")
    def test_absent_evidence_is_unsupported(self):
        self.assertEqual(self.evaluate().status,"unsupported")
    def test_delivery_mismatch_is_denied(self):
        self.assertEqual(self.evaluate(RecipientHeaders(delivered_to=(OTHER,))).reason,"delivery_recipient_mismatch")


if __name__=="__main__": unittest.main()
