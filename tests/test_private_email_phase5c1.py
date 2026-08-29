import contextlib
import imaplib
import io
import json
import socket
import sqlite3
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import patch

from private_email_adapter_discovery import (DiscoveryDenied, DiscoveryMailboxChanged,
    HARD_CAP, PrivateEmailAdapterDiscovery, _subject_features)
from private_email_credentials import ProviderCredentialResolver


CONFIG = "pechy_pilot"
RECIPIENT = "managed-mailbox@example.invalid"
BUNDLE = {CONFIG: {"username": RECIPIENT, "password": "discovery-password-canary"}}
NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


class FakeIMAPTransport:
    def __init__(self):
        self.uidvalidity = 91
        self.uidnext = 101
        self.rows = {}
        self.commands = []
        self.final_uidvalidity = None
        self.examine_count = 0
    def examine(self, config, folder):
        self.commands.append(("EXAMINE", config, folder)); self.examine_count += 1
        current = self.final_uidvalidity if self.examine_count > 1 and self.final_uidvalidity else self.uidvalidity
        return {"uidvalidity": current, "uidnext": self.uidnext}
    def search_uids(self, config, folder, minimum, limit):
        self.commands.append(("UID SEARCH", config, folder, minimum, limit))
        return sorted(uid for uid in self.rows if uid >= minimum)[:limit]
    def fetch_metadata(self, config, folder, uid):
        self.commands.append(("FETCH_METADATA", config, folder, uid)); return self.rows[uid][0]
    def fetch_body_peek(self, config, folder, uid, part):
        self.commands.append(("BODY.PEEK", config, folder, uid, part)); return self.rows[uid][1]


def meta(**changes):
    value = {"uid": 100, "internaldate": NOW, "size": 500,
             "from": "notices@mailer.example", "to": RECIPIENT,
             "subject": "Your verification code 482731",
             "authentication_results": "mx; dkim=pass header.d=mailer.example; spf=pass smtp.mailfrom=return.mailer.example",
             "content_type": "text/plain", "content_transfer_encoding": "", "body_part": "TEXT"}
    value.update(changes); return value


def mime_body(message):
    raw = message.as_bytes()
    marker = b"\r\n\r\n" if b"\r\n\r\n" in raw else b"\n\n"
    return raw.split(marker, 1)[1], message.get("Content-Type"), message.get("Content-Transfer-Encoding", "")


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeIMAPTransport()
        self.resolver = ProviderCredentialResolver(bundle=BUNDLE)
        self.utility = PrivateEmailAdapterDiscovery(self.resolver, self.transport)
        self.network = patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.imap = patch.object(imaplib, "IMAP4_SSL", side_effect=AssertionError("real IMAP forbidden"))
        self.imap.start()
    def tearDown(self): self.imap.stop(); self.network.stop()
    def add(self, uid=100, body=b"Use CODE: 482731", **changes):
        metadata = meta(uid=uid, **changes); self.transport.rows[uid] = (metadata, body)
    def discover(self, limit=20): return self.utility.discover(CONFIG, limit=limit)

    def test_zero_messages(self):
        result = self.discover()
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual([x[0] for x in self.transport.commands], ["EXAMINE", "UID SEARCH", "EXAMINE"])

    def test_valid_candidate_is_redacted(self):
        secret = "482731"; self.add(body=f"Use CODE: {secret}".encode())
        result = self.discover(); dumped = json.dumps(result)
        self.assertEqual(result["messages"][0]["provisional_type"], "numeric_code")
        self.assertNotIn(secret, dumped); self.assertTrue(result["read_only"])

    def test_sender_candidate_is_domain_and_hash_only(self):
        self.add(**{"from": "Variable.Local@mailer.example"})
        report = self.discover()["messages"][0]
        self.assertEqual(report["sender_domain"], "mailer.example")
        self.assertNotIn("variable.local", json.dumps(report).lower())

    def test_spf_fail_skips_body(self):
        self.add(authentication_results="dkim=pass header.d=mailer.example; spf=fail")
        report = self.discover()["messages"][0]
        self.assertEqual(report["safe_result"], "authentication_failed")
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_dkim_fail_skips_body(self):
        self.add(authentication_results="dkim=fail; spf=pass")
        self.assertEqual(self.discover()["messages"][0]["safe_result"], "authentication_failed")

    def test_multipart_plain_html(self):
        message = EmailMessage(); message.set_content("CODE: 482731"); message.add_alternative("<b>Welcome</b>", subtype="html")
        body, content_type, encoding = mime_body(message)
        self.add(body=body, content_type=content_type, content_transfer_encoding=encoding, size=len(body))
        mime = self.discover()["messages"][0]["mime"]
        self.assertTrue(mime["text_plain"]); self.assertTrue(mime["text_html"]); self.assertTrue(mime["multipart"])

    def test_html_only(self):
        self.add(body=b"<p>CODE: 482731</p>", content_type="text/html")
        report = self.discover()["messages"][0]
        self.assertFalse(report["mime"]["text_plain"]); self.assertTrue(report["mime"]["text_html"])

    def test_multiple_tokens_are_ambiguous(self):
        self.add(body=b"CODE: 482731 or 917264")
        self.assertEqual(self.discover()["messages"][0]["provisional_type"], "ambiguous")

    def test_subject_token_is_redacted(self):
        self.add(subject="Access code 482731", body=b"instructions only")
        report = self.discover()["messages"][0]
        self.assertEqual(report["subject_numeric_token_lengths"], [6]); self.assertNotIn("482731", json.dumps(report))

    def test_action_link_never_exposes_url(self):
        token = "sensitive-url-token"; self.add(body=f"Open https://example.invalid/action?token={token}".encode())
        dumped = json.dumps(self.discover())
        self.assertNotIn(token, dumped); self.assertIn('"provisional_type": "action_link"', dumped)

    def test_attachment_is_counted_and_ignored(self):
        message = EmailMessage(); message.set_content("instructions")
        message.add_attachment(b"CODE: 482731", maintype="text", subtype="plain", filename="secret.txt")
        body, content_type, encoding = mime_body(message)
        self.add(body=body, content_type=content_type, content_transfer_encoding=encoding, size=len(body))
        report = self.discover()["messages"][0]
        self.assertEqual(report["mime"]["attachments"], 1); self.assertEqual(report["provisional_type"], "unsupported")

    def test_oversized_skips_body(self):
        self.add(size=131073)
        self.assertEqual(self.discover()["messages"][0]["safe_result"], "message_too_large")
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_valid_charset(self):
        self.add(body="CODE: 482731".encode("utf-8"), content_type="text/plain; charset=utf-8")
        self.assertIn("utf-8", self.discover()["messages"][0]["mime"]["charsets"])

    def test_invalid_charset_fails_closed(self):
        self.add(body=b"CODE: \xff482731", content_type="text/plain; charset=x-invalid")
        self.assertEqual(self.discover()["messages"][0]["safe_result"], "message_malformed")

    def test_uid_identity_is_complete(self):
        self.add(); identity = self.discover()["messages"][0]["identity"]
        self.assertEqual(identity, {"provider_config_id":CONFIG,"folder":"INBOX","uidvalidity":91,"uid":100})

    def test_uidvalidity_change_fails_closed(self):
        self.add(); self.transport.final_uidvalidity = 92
        with self.assertRaises(DiscoveryMailboxChanged): self.discover()

    def test_hard_cap_and_recent_uid_window(self):
        self.transport.uidnext = 1000
        for uid in range(900, 1000): self.add(uid=uid)
        result = self.discover(HARD_CAP)
        self.assertEqual(result["candidate_count"], HARD_CAP)
        search = next(x for x in self.transport.commands if x[0] == "UID SEARCH")
        self.assertEqual((search[-2], search[-1]), (950, 50))
        with self.assertRaises(DiscoveryDenied): self.discover(51)

    def test_only_read_only_transport_commands(self):
        self.add(); self.discover()
        allowed = {"EXAMINE", "UID SEARCH", "FETCH_METADATA", "BODY.PEEK"}
        self.assertTrue({x[0] for x in self.transport.commands} <= allowed)
        self.assertFalse({"STORE", "APPEND", "COPY", "MOVE", "DELETE", "EXPUNGE"} & {x[0] for x in self.transport.commands})

    def test_code_body_and_url_absent_from_stdout_shape(self):
        canary = "CANARY-BODY-DO-NOT-PRINT"
        self.add(body=f"{canary} CODE: 482731 https://example.invalid/?x=url-canary".encode())
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            print(json.dumps(self.discover()))
        exposed = output.getvalue()
        for forbidden in (canary, "482731", "url-canary", "CODE:"):
            self.assertNotIn(forbidden, exposed)

    def test_credentials_never_exposed(self):
        self.add(); exposed = json.dumps(self.discover()) + repr(self.resolver)
        self.assertNotIn(BUNDLE[CONFIG]["password"], exposed); self.assertNotIn(RECIPIENT, exposed)

    def test_no_sqlite_persistence(self):
        self.add()
        with patch.object(sqlite3, "connect", side_effect=AssertionError("SQLite forbidden")):
            self.discover()

    def test_recipient_mismatch_skips_body(self):
        self.add(to="other@example.invalid")
        self.assertEqual(self.discover()["messages"][0]["safe_result"], "recipient_mismatch")
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_provider_config_must_be_explicitly_allowlisted(self):
        with self.assertRaises(DiscoveryDenied): self.utility.discover("other", limit=20)

    def test_alphanumeric_candidate_value_is_redacted(self):
        token = "AB12CD34"; self.add(body=f"Token {token}".encode())
        result = self.discover(); self.assertEqual(result["messages"][0]["provisional_type"], "alphanumeric_code")
        self.assertNotIn(token, json.dumps(result))

    def test_subject_shape_redacts_mixed_and_numeric_tokens(self):
        features = json.dumps(_subject_features("Verify AB12CD34 with 482731"))
        self.assertNotIn("Verify", features); self.assertNotIn("AB12CD34", features)
        self.assertNotIn("482731", features)


if __name__ == "__main__": unittest.main()
