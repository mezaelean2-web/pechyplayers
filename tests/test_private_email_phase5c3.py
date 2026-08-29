import contextlib
import io
import json
import socket
import sqlite3
import unittest
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest.mock import patch

from private_email_credentials import ProviderCredentialResolver
from private_email_netflix_discovery import (NetflixDiscoveryAmbiguous,
    NetflixDiscoveryChanged, NetflixDiscoveryDenied, NetflixRealDiscovery)


CONFIG = "pechy_pilot"
BUNDLE = {CONFIG: {"username": "mailbox@example.invalid", "password": "PASSWORD-CANARY"}}
NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self):
        self.uidvalidity = 91
        self.uidnext = 101
        self.rows = {}
        self.commands = []
        self.changed = False

    def examine(self, config, folder):
        self.commands.append(("EXAMINE", config, folder))
        validity = self.uidvalidity + 1 if self.changed else self.uidvalidity
        return {"uidvalidity": validity, "uidnext": self.uidnext}

    def search_uids(self, config, folder, minimum, limit):
        self.commands.append(("UID SEARCH", config, folder, minimum, limit))
        return sorted(uid for uid in self.rows if uid >= minimum)[:limit]

    def fetch_metadata(self, config, folder, uid):
        self.commands.append(("FETCH_METADATA", config, folder, uid))
        return self.rows[uid][0]

    def fetch_body_peek(self, config, folder, uid, part):
        self.commands.append(("BODY.PEEK", config, folder, uid, part))
        return self.rows[uid][1]

    def fetch_from_header(self, config, folder, uid):
        self.commands.append(("FETCH_FROM", config, folder, uid))
        return self.rows[uid][0]["from"]

    def fetch_disambiguation_metadata(self, config, folder, uid):
        self.commands.append(("FETCH_DISAMBIGUATION", config, folder, uid))
        metadata = self.rows[uid][0]
        return {"uid": uid, "internaldate": metadata["internaldate"],
                "from": (metadata["from"],), "subject": (metadata["subject"],), "date": ()}


def message(url="https://reset.netflix.example/reset?token=URL-TOKEN-CANARY", text="Reset password"):
    item = EmailMessage()
    item.set_content("No sensitive extraction from plain text")
    item.add_alternative(f'<a href="{url}">{text}</a>', subtype="html")
    raw = item.as_bytes()
    marker = b"\r\n\r\n" if b"\r\n\r\n" in raw else b"\n\n"
    return raw.split(marker, 1)[1], item["Content-Type"]


def metadata(uid=101, sender="notice@account.netflix.com", subject="Reset your password", **changes):
    body, content_type = message()
    value = {"uid": uid, "size": len(body), "internaldate": NOW, "from": sender,
             "subject": subject, "content_type": content_type,
             "content_transfer_encoding": "", "body_part": "TEXT"}
    value.update(changes)
    return value, body


class NetflixRealDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.utility = NetflixRealDiscovery(ProviderCredentialResolver(bundle=BUNDLE), self.transport)
        self.net = patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden"))
        self.net.start()

    def tearDown(self):
        self.net.stop()

    def test_prepare_only_captures_t0(self):
        result = self.utility.prepare(CONFIG)
        self.assertEqual(result["ready"], "READY_FOR_NETFLIX_RESET_TRIGGER")
        self.assertEqual(result["uidnext_at_t0"], 101)
        self.assertEqual([x[0] for x in self.transport.commands], ["EXAMINE"])

    def test_inspect_single_post_t0_candidate_redacted(self):
        self.transport.rows[101] = metadata()
        result = self.utility.inspect(CONFIG, 91, 101)
        self.assertEqual(result["cta_destination_host"], "reset.netflix.example")
        self.assertEqual(result["cta_destination_scheme"], "https")
        self.assertTrue(result["subject_exact_rule_possible"])
        dumped = json.dumps(result)
        self.assertNotIn("URL-TOKEN-CANARY", dumped)
        self.assertNotIn("/reset", dumped)

    def test_count_only_distinguishes_zero_one_and_multiple_without_body(self):
        empty = self.utility.count_only(CONFIG, 91, 101)
        self.assertEqual((empty["netflix_candidate_count"], empty["candidate_uid"]), (0, "NONE"))
        self.transport.rows[101] = metadata(uid=101)
        one = self.utility.count_only(CONFIG, 91, 101)
        self.assertEqual((one["netflix_candidate_count"], one["candidate_uid"]), (1, 101))
        self.transport.rows[102] = metadata(uid=102)
        multiple = self.utility.count_only(CONFIG, 91, 101)
        self.assertEqual((multiple["netflix_candidate_count"], multiple["candidate_uid"]), (">1", "MULTIPLE"))
        self.assertEqual(multiple["candidate_uids"], [101, 102])
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_count_only_fetches_only_from_identity(self):
        self.transport.rows[101] = metadata(uid=101)
        self.utility.count_only(CONFIG, 91, 101)
        self.assertEqual([x[0] for x in self.transport.commands],
                         ["EXAMINE", "UID SEARCH", "FETCH_FROM", "EXAMINE"])

    def test_metadata_disambiguation_unique_and_redacted(self):
        subjects = ("Welcome", "Security notice", "Reset your password", "New sign-in")
        for offset, subject in enumerate(subjects):
            self.transport.rows[101 + offset] = metadata(uid=101 + offset, subject=subject)
        result = self.utility.disambiguate_metadata(CONFIG, 91, 101, (101, 102, 103, 104))
        self.assertEqual(result["unique_metadata_candidate"], 103)
        self.assertEqual(result["disambiguation_result"], "UNIQUE")
        dumped = json.dumps(result)
        for subject in subjects:
            self.assertNotIn(subject, dumped)
        self.assertTrue(all(len(row["subject_fingerprint"]) == 64
                            for row in result["candidate_summary"]))
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_metadata_disambiguation_ambiguous_and_exact_uid_set(self):
        for uid in (101, 102, 103, 104):
            self.transport.rows[uid] = metadata(uid=uid, subject="Reset password")
        result = self.utility.disambiguate_metadata(CONFIG, 91, 101, (101, 102, 103, 104))
        self.assertEqual(result["disambiguation_result"], "STILL_AMBIGUOUS")
        with self.assertRaises(NetflixDiscoveryDenied):
            self.utility.disambiguate_metadata(CONFIG, 91, 101, (101, 102, 103))

    def test_pre_t0_message_is_not_inspected(self):
        self.transport.rows[100] = metadata(uid=100)
        with self.assertRaises(NetflixDiscoveryAmbiguous):
            self.utility.inspect(CONFIG, 91, 101)
        self.assertNotIn("BODY.PEEK", [x[0] for x in self.transport.commands])

    def test_requires_exactly_one_candidate(self):
        self.transport.rows[101] = metadata(uid=101)
        self.transport.rows[102] = metadata(uid=102)
        with self.assertRaises(NetflixDiscoveryAmbiguous):
            self.utility.inspect(CONFIG, 91, 101)

    def test_other_sender_is_not_candidate(self):
        self.transport.rows[101] = metadata(sender="notice@example.invalid")
        with self.assertRaises(NetflixDiscoveryAmbiguous):
            self.utility.inspect(CONFIG, 91, 101)

    def test_multiple_ctas_fail_closed(self):
        item = EmailMessage()
        item.set_content("plain")
        item.add_alternative(
            '<a href="https://reset.netflix.example/x">Reset password</a>'
            '<a href="https://other.netflix.example/x">Reset password</a>', subtype="html")
        raw = item.as_bytes()
        marker = b"\r\n\r\n" if b"\r\n\r\n" in raw else b"\n\n"
        extra = raw.split(marker, 1)[1]
        self.transport.rows[101] = metadata(size=len(extra), content_type=item["Content-Type"])
        self.transport.rows[101] = (self.transport.rows[101][0], extra)
        with self.assertRaises(NetflixDiscoveryAmbiguous):
            self.utility.inspect(CONFIG, 91, 101)

    def test_sensitive_subject_is_redacted(self):
        self.transport.rows[101] = metadata(subject="Reset password 123456")
        result = self.utility.inspect(CONFIG, 91, 101)
        self.assertEqual(result["subject_fingerprint"], "REDACTED_VARIABLE_SUBJECT")
        self.assertFalse(result["subject_exact_rule_possible"])

    def test_uidvalidity_mismatch_fails_before_search(self):
        with self.assertRaises(NetflixDiscoveryChanged):
            self.utility.inspect(CONFIG, 92, 101)
        self.assertEqual([x[0] for x in self.transport.commands], ["EXAMINE"])

    def test_invalid_config_denied(self):
        with self.assertRaises(NetflixDiscoveryDenied):
            self.utility.prepare("other")

    def test_no_sqlite_or_output_or_network(self):
        self.transport.rows[101] = metadata()
        output = io.StringIO()
        with patch.object(sqlite3, "connect", side_effect=AssertionError("DB forbidden")), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.utility.inspect(CONFIG, 91, 101)
        self.assertEqual(output.getvalue(), "")

    def test_only_read_only_commands(self):
        self.transport.rows[101] = metadata()
        self.utility.inspect(CONFIG, 91, 101)
        commands = {x[0] for x in self.transport.commands}
        self.assertTrue(commands <= {"EXAMINE", "UID SEARCH", "FETCH_METADATA", "BODY.PEEK"})
        self.assertFalse(commands & {"STORE", "APPEND", "COPY", "MOVE", "DELETE", "EXPUNGE"})


if __name__ == "__main__":
    unittest.main()
