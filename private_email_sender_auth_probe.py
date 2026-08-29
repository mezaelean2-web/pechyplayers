"""Probe administrativo metadata-only de identidad/auth para un único UID."""

import argparse
import json
from email.header import decode_header
from email.utils import getaddresses
from pathlib import Path

from dotenv import load_dotenv

from mail_sender_auth_policy import (MAX_AUTH_RESULTS_HEADERS,MAX_METHOD_RESULTS,SenderAuthMalformed,
    normalize_domain,parse_authentication_results)
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import ProviderError


ALLOWED_PROVIDER_CONFIGS=frozenset({"pechy_pilot"})
FOLDER_KEY="INBOX"
MAX_FROM_BYTES=2048


class SenderProbeError(Exception): safe_code="sender_probe_failed"
class SenderProbeDenied(SenderProbeError): safe_code="sender_probe_denied"
class SenderProbeUIDInvalid(SenderProbeError): safe_code="uid_invalid"
class SenderProbeUIDValidityMismatch(SenderProbeError): safe_code="uidvalidity_mismatch"
class SenderProbeFromInvalid(SenderProbeError): safe_code="from_invalid"


def _positive(value):
    try: number=int(value)
    except (TypeError,ValueError) as exc: raise SenderProbeUIDInvalid() from exc
    if number<=0: raise SenderProbeUIDInvalid()
    return number


def _from_domain(values):
    values=tuple(values or ())
    if len(values)!=1: raise SenderProbeFromInvalid()
    raw=str(values[0] or "")
    if not raw or "\r" in raw or "\n" in raw or len(raw.encode("utf-8","replace"))>MAX_FROM_BYTES:
        raise SenderProbeFromInvalid()
    try:
        pieces=[]
        for fragment,charset in decode_header(raw):
            if isinstance(fragment,bytes): fragment=fragment.decode(charset or "ascii","strict")
            pieces.append(str(fragment))
        addresses=[address.strip().lower() for _,address in getaddresses(["".join(pieces)]) if address]
        if len(addresses)!=1 or addresses[0].count("@")!=1: raise SenderProbeFromInvalid()
        return normalize_domain(addresses[0].rsplit("@",1)[1])
    except (LookupError,UnicodeError,ValueError,SenderAuthMalformed) as exc:
        if isinstance(exc,SenderProbeFromInvalid): raise
        raise SenderProbeFromInvalid() from exc


def _summarize(from_values,auth_values):
    domain=_from_domain(from_values)
    try: records=parse_authentication_results(tuple(auth_values or ()))
    except SenderAuthMalformed: raise
    dkim=[item for record in records for item in record.dkim]
    spf=[item for record in records for item in record.spf]
    if len(dkim)>MAX_METHOD_RESULTS or len(spf)>MAX_METHOD_RESULTS: raise SenderAuthMalformed()
    dkim_results=sorted({item.result for item in dkim})
    spf_results=sorted({item.result for item in spf})
    dkim_domains=sorted({item.domain for item in dkim if item.domain})
    spf_domains=sorted({item.domain for item in spf if item.domain})
    dkim_pass=sorted({item.domain for item in dkim if item.result=="pass" and item.domain})
    dkim_fail=sorted({item.domain for item in dkim if item.result!="pass" and item.domain})
    spf_pass=sorted({item.domain for item in spf if item.result=="pass" and item.domain})
    spf_fail=sorted({item.domain for item in spf if item.result!="pass" and item.domain})
    authserv=sorted({record.authserv_id for record in records})
    contradictory=(len(dkim_results)>1 or len(spf_results)>1)
    return {"from_domain":domain,"authentication_results_count":len(records),
            "authserv_id_candidates":authserv,"dkim_results":dkim_results,
            "dkim_domains":dkim_domains,"spf_results":spf_results,
            "spf_mailfrom_domains":spf_domains,"malformed":False,
            "dkim_pass_domains":dkim_pass,"dkim_fail_domains":dkim_fail,
            "spf_pass_domains":spf_pass,"spf_fail_domains":spf_fail,
            "contradictory":contradictory,"multiple_authserv_ids":len(authserv)>1,
            "trusted_boundary_proven":False}


class PrivateEmailSenderAuthProbe:
    def __init__(self,credential_resolver,transport,*,allowed_configs=ALLOWED_PROVIDER_CONFIGS):
        self.resolver=credential_resolver; self.transport=transport
        self.allowed_configs=frozenset(allowed_configs)
    def probe(self,provider_config_id,folder,uidvalidity,uid):
        config=str(provider_config_id or "").strip()
        if config not in self.allowed_configs or folder!=FOLDER_KEY: raise SenderProbeDenied()
        expected_validity=_positive(uidvalidity); expected_uid=_positive(uid)
        # Resolve local config to prove the allowlisted credential exists; never expose it.
        self.resolver.resolve(config)
        before=self.transport.examine(config,folder)
        if int(before["uidvalidity"])!=expected_validity: raise SenderProbeUIDValidityMismatch()
        headers=self.transport.fetch_sender_auth_headers(config,folder,expected_uid)
        after=self.transport.examine(config,folder)
        if int(after["uidvalidity"])!=expected_validity: raise SenderProbeUIDValidityMismatch()
        return {"ok":True,"uidvalidity_match":True,"uid_match":True,
                **_summarize(headers.get("from",()),headers.get("authentication_results",()))}


def _parser():
    parser=argparse.ArgumentParser(description="Single-UID sender authentication probe")
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
        result=PrivateEmailSenderAuthProbe(resolver,transport).probe(
            args.provider_config_id,args.folder,args.uidvalidity,args.uid)
        print(json.dumps(result,sort_keys=True,separators=(",",":"))); return 0
    except (SenderProbeError,SenderAuthMalformed,ProviderError) as exc:
        output={"ok":False,"error":getattr(exc,"safe_code","sender_probe_failed")}
        if isinstance(exc,SenderAuthMalformed): output["diagnostic"]=exc.diagnostic
        print(json.dumps(output,
                         sort_keys=True,separators=(",",":"))); return 2
    except Exception:
        print('{"error":"sender_probe_failed","ok":false}'); return 2


if __name__=="__main__": raise SystemExit(main())
