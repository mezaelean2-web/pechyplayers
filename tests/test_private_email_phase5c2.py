import contextlib
import io
import json
import socket
import sqlite3
import unittest
from datetime import datetime,timezone
from email.message import EmailMessage
from unittest.mock import patch

from mail_message_parsers import ServiceAdapterRegistry
from netflix_link_adapter import (ALLOWED_LINK_HOSTS_CONFIGURATION_REQUIRED,LinkHostRule,
                                  NetflixLinkAdapter)
from private_email_provider import ProviderMessageMalformed,ProviderMessageTooLarge


NOW=datetime(2026,8,29,tzinfo=timezone.utc); SUBJECT="restablecimiento de contrase"
HOST="netflix.example"; SECRET_URL=f"https://{HOST}/reset?token=SENSITIVE-URL-CANARY"


def message(html,plain="Instructions",attachment=None):
    item=EmailMessage(); item.set_content(plain); item.add_alternative(html,subtype="html")
    if attachment is not None:item.add_attachment(attachment.encode(),maintype="text",subtype="html",filename="fake.html")
    return item.as_bytes()
def metadata(subject=SUBJECT,size=1000): return {"subject":subject,"size":size,"internaldate":NOW,"body_part":"TEXT"}


class NetflixLinkAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter=NetflixLinkAdapter(subjects={SUBJECT},allowed_link_hosts={LinkHostRule(HOST)})
        self.registry=ServiceAdapterRegistry([self.adapter],max_message_bytes=8192,max_parts=8,max_depth=3)
        self.network=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden")); self.network.start()
    def tearDown(self):self.network.stop()
    def classify(self,html,**meta):
        raw=message(html); return self.registry.classify(metadata(size=len(raw),**meta),lambda _:raw,requested_at=NOW)
    def anchor(self,url=SECRET_URL,text="Restablecer contraseña"):return f'<a href="{url}">{text}</a>'
    def test_valid_single_cta(self):
        result=self.classify(self.anchor()); self.assertEqual((result.status,result.kind,result.value),("success","action_link",SECRET_URL))
    def test_html_and_plain_are_bounded(self):self.assertEqual(self.classify(self.anchor()).status,"success")
    def test_expected_anchor_required(self):self.assertEqual(self.classify(self.anchor(text="Restablecer contraseña")).status,"success")
    def test_cta_absent(self):self.assertEqual(self.classify(self.anchor(text="Manage preferences")).safe_reason,"cta_not_found")
    def test_subject_incorrect(self):self.assertEqual(self.classify(self.anchor(),subject="Other").safe_reason,"unsupported_subject")
    def test_zero_links(self):self.assertEqual(self.classify("<p>Restablecer contraseña</p>").safe_reason,"cta_not_found")
    def test_two_valid_links_ambiguous(self):
        result=self.classify(self.anchor(SECRET_URL)+self.anchor(f"https://{HOST}/other")); self.assertEqual((result.status,result.safe_reason),("ambiguous","ambiguous_link"))
    def test_duplicate_link_deterministic(self):
        result=self.classify(self.anchor()+self.anchor()); self.assertEqual((result.status,result.value),("success",SECRET_URL))
    def test_http_rejected(self):self.assertEqual(self.classify(self.anchor(f"http://{HOST}/reset")).safe_reason,"no_valid_link")
    def test_attacker_host_rejected(self):self.assertEqual(self.classify(self.anchor("https://attacker.example/reset")).safe_reason,"no_valid_link")
    def test_suffix_attack_rejected(self):self.assertEqual(self.classify(self.anchor(f"https://{HOST}.attacker.example/reset")).safe_reason,"no_valid_link")
    def test_userinfo_attack_rejected(self):self.assertEqual(self.classify(self.anchor(f"https://{HOST}@attacker.example/reset")).safe_reason,"no_valid_link")
    def test_ip_literal_rejected(self):self.assertEqual(self.classify(self.anchor("https://127.0.0.1/reset")).safe_reason,"no_valid_link")
    def test_malformed_url_rejected(self):self.assertEqual(self.classify(self.anchor("https://[invalid/reset")).safe_reason,"no_valid_link")
    def test_oversized_mime(self):
        raw=b"x"*8193
        with self.assertRaises(ProviderMessageTooLarge):self.registry.classify(metadata(size=len(raw)),lambda _:raw,requested_at=NOW)
    def test_too_many_parts(self):
        item=EmailMessage(); item.set_content("plain")
        for index in range(9):item.add_attachment(str(index),filename=f"{index}.txt")
        raw=item.as_bytes()
        with self.assertRaises(ProviderMessageMalformed):self.registry.classify(metadata(size=len(raw)),lambda _:raw,requested_at=NOW)
    def test_attachment_link_ignored(self):
        raw=message(self.anchor(),attachment=self.anchor("https://attacker.example/reset"))
        result=self.registry.classify(metadata(size=len(raw)),lambda _:raw,requested_at=NOW); self.assertEqual(result.value,SECRET_URL)
    def test_tracking_and_unsubscribe_before_cta_ignored(self):
        html='<a href="https://tracker.example/x">tracking</a><a href="https://attacker.example/u">unsubscribe</a>'+self.anchor()
        self.assertEqual(self.classify(html).value,SECRET_URL)
    def test_attacker_cta_before_valid_is_ignored(self):
        html=self.anchor("https://attacker.example/phish")+self.anchor(); self.assertEqual(self.classify(html).value,SECRET_URL)
    def test_encoded_href_is_decoded_safely(self):
        html=f'<a href="https://{HOST}/reset?x=1&amp;y=2">Reset password</a>'
        self.assertEqual(self.classify(html).value,f"https://{HOST}/reset?x=1&y=2")
    def test_unicode_and_idna_suspicious_hosts_rejected(self):
        for url in ("https://netflíx.example/reset","https://xn--netflx-2va.example/reset"):
            with self.subTest(url=url):self.assertEqual(self.classify(self.anchor(url)).status,"unsupported")
    def test_parser_never_returns_body_or_html(self):
        body="BODY-SENSITIVE-CANARY"; result=self.classify(self.anchor()+f"<p>{body}</p>")
        self.assertNotIn(body,repr(result)); self.assertNotIn("<a",repr(result))
    def test_errors_never_include_sensitive_url(self):
        bad="https://attacker.example/?token=SENSITIVE-URL-CANARY"; result=self.classify(self.anchor(bad)); self.assertNotIn(bad,repr(result)); self.assertNotIn("SENSITIVE",repr(result))
    def test_no_persistence_sqlite_logs_or_network(self):
        output=io.StringIO()
        with patch.object(sqlite3,"connect",side_effect=AssertionError("SQLite forbidden")),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):result=self.classify(self.anchor())
        self.assertEqual(output.getvalue(),""); self.assertNotIn("BODY",json.dumps(result.__dict__))
    def test_configuration_is_fail_closed(self):
        self.assertTrue(ALLOWED_LINK_HOSTS_CONFIGURATION_REQUIRED)
        decoded=self.registry._decode(message(self.anchor()))
        no_hosts=NetflixLinkAdapter(subjects={SUBJECT},allowed_link_hosts=()).parse_decoded(metadata(),decoded)
        no_subjects=NetflixLinkAdapter(subjects=(),allowed_link_hosts={LinkHostRule(HOST)}).parse_decoded(metadata(),decoded)
        self.assertEqual(no_hosts.safe_reason,"allowed_link_hosts_configuration_required")
        self.assertEqual(no_subjects.safe_reason,"subject_configuration_required")
    def test_subdomains_require_explicit_rule(self):
        url=f"https://secure.{HOST}/reset"
        self.assertEqual(self.classify(self.anchor(url)).status,"unsupported")
        adapter=NetflixLinkAdapter(subjects={SUBJECT},allowed_link_hosts={LinkHostRule(HOST,True)})
        registry=ServiceAdapterRegistry([adapter]); raw=message(self.anchor(url))
        self.assertEqual(registry.classify(metadata(size=len(raw)),lambda _:raw,requested_at=NOW).status,"success")


if __name__=="__main__":unittest.main()
