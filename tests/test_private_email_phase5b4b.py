import contextlib
import imaplib
import io
import socket
import unittest
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from unittest.mock import patch

from mailbox_bindings import MailboxBinding
from pilot_message_adapter import (
    PILOT_MAX_MESSAGE_BYTES,
    PilotMessageAdapterRegistry,
    build_pilot_message_registry,
)
from pilot_private_email_gate import PilotPrivateEmailGate
from private_email_provider import ProviderMessageTooLarge


NOW=datetime(2026,8,28,18,0,tzinfo=timezone.utc)
RECIPIENT="pilot-recipient@example.invalid"


def metadata(**changes):
    value={"internaldate":NOW,"size":64,"from":"mezaelean2@gmail.com",
        "to":RECIPIENT,"subject":"PECHY-PILOT-CODE",
        "authentication_results":"mx; dkim=pass; spf=pass",
        "content_type":"text/plain; charset=utf-8","content_transfer_encoding":"",
        "body_part":"TEXT"}
    value.update(changes); return value


def mime_body(message):
    raw=message.as_bytes(policy=policy.SMTP)
    return raw.split(b"\r\n\r\n",1)[1],message["Content-Type"],message.get("Content-Transfer-Encoding","")


class PilotMessageAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry=PilotMessageAdapterRegistry(RECIPIENT)
        self.socket_patch=patch.object(socket,"create_connection",side_effect=AssertionError("network forbidden"))
        self.imap_patch=patch.object(imaplib,"IMAP4_SSL",side_effect=AssertionError("real IMAP forbidden"))
        self.socket_patch.start(); self.imap_patch.start()

    def tearDown(self):
        self.imap_patch.stop(); self.socket_patch.stop()

    def classify(self,body=b"CODE: 482731\r\n",**changes):
        meta=metadata(**changes); return self.registry.classify(meta,lambda _:body,requested_at=NOW)

    def test_valid_exact_pilot_message(self):
        parsed=self.classify()
        self.assertEqual((parsed.kind,parsed.value),("numeric_code","482731"))

    def test_subject_must_be_exact(self):
        for subject in ("pechy-pilot-code","PECHY-PILOT-CODE ","Re: PECHY-PILOT-CODE",""):
            with self.subTest(subject=subject):
                self.assertEqual(self.classify(subject=subject).kind,"unsupported")

    def test_code_length_and_format_are_strict(self):
        for body in (b"CODE: 12345",b"CODE: 1234567",b"Your number is 123456",
                     b"CODE: 123456\nCODE: 654321",b"prefix CODE: 123456"):
            with self.subTest(body=body): self.assertEqual(self.classify(body).kind,"unsupported")

    def test_html_only_cannot_supply_code(self):
        self.assertEqual(self.classify(b"<p>CODE: 482731</p>",content_type="text/html").kind,
                         "unsupported")

    def test_attachments_are_ignored(self):
        item=EmailMessage(); item.set_content("CODE: 482731")
        item.add_attachment(b"CODE: 111111",maintype="text",subtype="plain",filename="code.txt")
        body,content_type,encoding=mime_body(item)
        parsed=self.classify(body,content_type=content_type,
                             content_transfer_encoding=encoding,size=len(body))
        self.assertEqual(parsed.value,"482731")
        item=EmailMessage(); item.set_content("No pilot code")
        item.add_attachment(b"CODE: 111111",maintype="text",subtype="plain",filename="code.txt")
        body,content_type,encoding=mime_body(item)
        self.assertEqual(self.classify(body,content_type=content_type,
            content_transfer_encoding=encoding,size=len(body)).kind,"unsupported")

    def test_oversized_message_fails_closed(self):
        with self.assertRaises(ProviderMessageTooLarge):
            self.classify(size=PILOT_MAX_MESSAGE_BYTES+1)
        with self.assertRaises(ProviderMessageTooLarge):
            self.classify(b"x"*(PILOT_MAX_MESSAGE_BYTES+1),size=100)

    def test_recipient_and_authentication_are_exact(self):
        self.assertEqual(self.classify(to="other@example.invalid").kind,"unsupported")
        for auth in ("spf=pass", "dkim=pass", "dkim=fail; spf=pass",
                     "dkim=pass; spf=fail", ""):
            with self.subTest(auth=auth):
                self.assertEqual(self.classify(authentication_results=auth).kind,"unsupported")

    def test_sender_is_exact_and_registry_resolves_recipient_from_pilot_config(self):
        self.assertEqual(self.classify(**{"from":"other@example.invalid"}).kind,"unsupported")
        class Resolver:
            def __init__(self): self.calls=[]
            def resolve(self,config_id):
                self.calls.append(config_id)
                return type("Credentials",(),{"username":RECIPIENT})()
        resolver=Resolver(); output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            registry=build_pilot_message_registry(resolver)
        self.assertEqual(resolver.calls,["pechy_pilot"])
        self.assertEqual(registry.classify(metadata(),lambda _:b"CODE: 482731",requested_at=NOW).kind,
                         "numeric_code")
        self.assertEqual(output.getvalue(),"")

    def test_adapter_is_unreachable_outside_exact_gate(self):
        gate=PilotPrivateEmailGate()
        exact=MailboxBinding(1,"private_email","pechy_pilot","INBOX",1,True,"cuenta",979,None)
        unit={"type":"cuenta","account_id":979,"profile_id":None}
        self.assertTrue(gate.allows(reseller_id=6,purchase_id=41,unit=unit,binding=exact))
        variants=(
            (5,41,unit,exact),(6,42,unit,exact),
            (6,41,{"type":"cuenta","account_id":980,"profile_id":None},exact),
            (6,41,unit,MailboxBinding(2,"private_email","pechy_pilot","INBOX",1,True,"cuenta",979,None)),
            (6,41,unit,MailboxBinding(1,"private_email","other","INBOX",1,True,"cuenta",979,None)),
        )
        for reseller,purchase,current_unit,binding in variants:
            self.assertFalse(gate.allows(reseller_id=reseller,purchase_id=purchase,
                                         unit=current_unit,binding=binding))


if __name__=="__main__": unittest.main()
