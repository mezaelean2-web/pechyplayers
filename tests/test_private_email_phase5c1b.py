import contextlib
import io
import json
import unittest
from email.header import Header

from private_email_adapter_discovery import (_domain_alignment, _subject_features,
                                             recipient_match_flags)


RECIPIENT = "authorized@example.invalid"
CANARY = "ULTRA-SENSITIVE-PERSON-NAME-5C1B"


class SubjectPrivacyTests(unittest.TestCase):
    def exposed(self, subject): return json.dumps(_subject_features(subject), sort_keys=True)

    def test_plain_subject_has_no_human_readable_output(self):
        subject = f"Hello {CANARY} account notice"
        exposed = self.exposed(subject)
        for word in ("Hello", CANARY, "account", "notice"):
            self.assertNotIn(word, exposed)

    def test_mime_encoded_subject_is_decoded_only_in_memory(self):
        subject = Header(f"Código privado {CANARY}", "utf-8").encode()
        features = _subject_features(subject); exposed = json.dumps(features)
        self.assertTrue(features["subject_encoded"]); self.assertTrue(features["subject_decode_valid"])
        self.assertNotIn(CANARY, exposed); self.assertNotIn("privado", exposed)

    def test_utf8_subject_reports_structure_only(self):
        features = _subject_features("Árbol privado")
        self.assertTrue(features["subject_contains_non_ascii"])
        self.assertEqual(features["subject_decoded_length_bucket"], "1-32")
        self.assertNotIn("Árbol", json.dumps(features))

    def test_subject_code_and_email_are_never_returned(self):
        subject = f"{CANARY} privateword 482731 for person@example.invalid"
        exposed = self.exposed(subject)
        for forbidden in (CANARY, "482731", "person@example.invalid", "privateword"):
            self.assertNotIn(forbidden, exposed)
        self.assertEqual(_subject_features(subject)["subject_numeric_token_lengths"], [6])

    def test_fingerprint_is_stable_and_content_sensitive(self):
        first = _subject_features("Stable private value")["subject_fingerprint"]
        self.assertEqual(first, _subject_features("Stable private value")["subject_fingerprint"])
        self.assertNotEqual(first, _subject_features("Different private value")["subject_fingerprint"])

    def test_canary_absent_from_stdout(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            print(json.dumps(_subject_features(CANARY)))
        self.assertNotIn(CANARY, output.getvalue())


class RecipientRoutingTests(unittest.TestCase):
    def test_direct_to_exact_match(self):
        self.assertEqual(recipient_match_flags({"to":RECIPIENT}, RECIPIENT),
            {"direct_match":True,"envelope_match":False,"alias_possible":False})

    def test_to_mismatch_is_closed(self):
        self.assertFalse(any(recipient_match_flags({"to":"other@example.invalid"}, RECIPIENT).values()))

    def test_synthetic_envelope_match_is_flagged_not_assumed(self):
        flags = recipient_match_flags({"to":"alias@example.invalid","delivered_to":RECIPIENT}, RECIPIENT)
        self.assertEqual(flags, {"direct_match":False,"envelope_match":True,"alias_possible":True})

    def test_each_explicit_envelope_header_is_supported_synthetically(self):
        for key in ("delivered_to", "x_original_to", "envelope_to"):
            with self.subTest(key=key):
                self.assertTrue(recipient_match_flags({key:RECIPIENT}, RECIPIENT)["envelope_match"])

    def test_multiple_visible_recipients(self):
        flags = recipient_match_flags({"to":f"other@example.invalid, {RECIPIENT}"}, RECIPIENT)
        self.assertTrue(flags["direct_match"])

    def test_cc_is_a_visible_recipient(self):
        self.assertTrue(recipient_match_flags({"to":"other@example.invalid","cc":RECIPIENT}, RECIPIENT)["direct_match"])

    def test_malformed_recipient_fails_closed(self):
        self.assertFalse(any(recipient_match_flags({"to":"not-an-address"}, "invalid").values()))

    def test_oversized_recipient_header_fails_closed(self):
        value = ("x" * 2050) + "@example.invalid"
        self.assertFalse(any(recipient_match_flags({"to":value}, RECIPIENT).values()))

    def test_wildcard_and_domain_only_never_authorize(self):
        for expected in ("@example.invalid", "example.invalid", "*@example.invalid", ""):
            self.assertFalse(any(recipient_match_flags({"to":RECIPIENT}, expected).values()))

    def test_case_normalization_is_exact(self):
        self.assertTrue(recipient_match_flags({"to":"AUTHORIZED@EXAMPLE.INVALID"}, RECIPIENT)["direct_match"])

    def test_encoded_display_name_does_not_change_address(self):
        value = f"=?utf-8?q?Private_Name?= <{RECIPIENT}>"
        flags = recipient_match_flags({"to":value}, RECIPIENT)
        self.assertTrue(flags["direct_match"]); self.assertNotIn("Private_Name", json.dumps(flags))

    def test_domain_only_match_is_never_enough(self):
        flags = recipient_match_flags({"to":"other@example.invalid"}, RECIPIENT)
        self.assertFalse(flags["direct_match"]); self.assertFalse(flags["envelope_match"])

    def test_no_sensitive_address_in_flags(self):
        self.assertNotIn(RECIPIENT, json.dumps(recipient_match_flags({"to":RECIPIENT}, RECIPIENT)))


class AuthenticationShapeTests(unittest.TestCase):
    def test_dkim_fail_is_not_alignment_authority(self):
        alignment = _domain_alignment("sender.example", ["sender.example"])
        self.assertTrue(alignment["authenticated_domain_alignment_candidate"])
        # Alignment is diagnostic only; DKIM/SPF policy remains separately mandatory.

    def test_spf_fail_cannot_be_hidden_by_domain_mismatch(self):
        self.assertFalse(_domain_alignment("sender.example", ["other.invalid"])
                         ["authenticated_domain_alignment_candidate"])

    def test_sender_mismatch_is_reported_only_as_false_flag(self):
        output = json.dumps(_domain_alignment("private.sender.example", ["auth.other.invalid"]))
        self.assertIn("false", output); self.assertNotIn("private.sender.example", output)


if __name__ == "__main__": unittest.main()
