"""Probe administrativo metadata-only para routing de un único UID."""

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from private_email_adapter_discovery import (_addresses, DiscoveryDenied,
                                             DiscoveryMalformed)
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import ProviderError


ALLOWED_PROVIDER_CONFIGS=frozenset({"pechy_pilot"})
FOLDER_KEY="INBOX"
HEADER_KEYS=("to","cc","delivered_to","x_original_to","envelope_to")


class ProbeUIDValidityMismatch(Exception): safe_code="uidvalidity_mismatch"
class ProbeUIDInvalid(Exception): safe_code="uid_invalid"


def _positive(value):
    try: number=int(value)
    except (TypeError,ValueError) as exc: raise ProbeUIDInvalid() from exc
    if number<=0: raise ProbeUIDInvalid()
    return number


def _routing_result(headers,expected):
    matches={}; present={}
    for key in HEADER_KEYS:
        raw=str(headers.get(key,"") or "")
        present[key]=bool(raw.strip())
        parsed=_addresses(raw)
        if parsed is None: raise DiscoveryMalformed()
        matches[key]=expected in parsed
    direct=matches["to"] or matches["cc"]
    envelope=matches["delivered_to"] or matches["x_original_to"] or matches["envelope_to"]
    return {
        "to_present":present["to"],"cc_present":present["cc"],
        "delivered_to_present":present["delivered_to"],
        "x_original_to_present":present["x_original_to"],
        "envelope_to_present":present["envelope_to"],
        "direct_match":direct,"cc_match":matches["cc"],
        "delivered_to_match":matches["delivered_to"],
        "x_original_to_match":matches["x_original_to"],
        "envelope_to_match":matches["envelope_to"],
        "envelope_match":envelope,"alias_possible":not direct and envelope,
    }


class PrivateEmailRecipientRoutingProbe:
    def __init__(self,credential_resolver,transport,*,allowed_configs=ALLOWED_PROVIDER_CONFIGS):
        self.resolver=credential_resolver; self.transport=transport
        self.allowed_configs=frozenset(allowed_configs)

    def probe(self,provider_config_id,folder,uidvalidity,uid):
        config=str(provider_config_id or "").strip()
        if config not in self.allowed_configs or folder!=FOLDER_KEY: raise DiscoveryDenied()
        expected_uidvalidity=_positive(uidvalidity); expected_uid=_positive(uid)
        expected_recipient=self.resolver.resolve(config).username.strip().lower()
        before=self.transport.examine(config,folder)
        if int(before["uidvalidity"])!=expected_uidvalidity: raise ProbeUIDValidityMismatch()
        headers=self.transport.fetch_recipient_routing_headers(config,folder,expected_uid)
        after=self.transport.examine(config,folder)
        if int(after["uidvalidity"])!=expected_uidvalidity: raise ProbeUIDValidityMismatch()
        return {"ok":True,"uidvalidity_match":True,"uid_present":True,
                **_routing_result(headers,expected_recipient)}


def _parser():
    parser=argparse.ArgumentParser(description="Single-UID recipient routing probe")
    parser.add_argument("--provider-config-id",required=True,choices=sorted(ALLOWED_PROVIDER_CONFIGS))
    parser.add_argument("--folder",required=True,choices=[FOLDER_KEY])
    parser.add_argument("--uidvalidity",required=True,type=int)
    parser.add_argument("--uid",required=True,type=int)
    return parser


def main(argv=None):
    args=_parser().parse_args(argv)
    try:
        load_dotenv(Path(__file__).resolve().with_name(".env"),override=False)
        resolver=ProviderCredentialResolver(); transport=PrivateEmailIMAPTransport(resolver)
        result=PrivateEmailRecipientRoutingProbe(resolver,transport).probe(
            args.provider_config_id,args.folder,args.uidvalidity,args.uid)
        print(json.dumps(result,sort_keys=True,separators=(",",":"))); return 0
    except (DiscoveryDenied,DiscoveryMalformed,ProbeUIDValidityMismatch,ProbeUIDInvalid,
            ProviderError) as exc:
        print(json.dumps({"ok":False,"error":getattr(exc,"safe_code","probe_failed")},
                         sort_keys=True,separators=(",",":"))); return 2
    except Exception:
        print('{"error":"probe_failed","ok":false}'); return 2


if __name__=="__main__": raise SystemExit(main())
