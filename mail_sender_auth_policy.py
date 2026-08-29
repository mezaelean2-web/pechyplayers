"""Parser y política genérica de identidad del sender, offline/testable."""

import re
from dataclasses import dataclass


STATUSES=frozenset({"authorized","denied","ambiguous","unsupported"})
RESULTS=frozenset({"pass","fail","neutral","softfail","none","temperror","permerror"})
MAX_AUTH_RESULTS_HEADERS=10
MAX_AUTH_RESULTS_BYTES=4096
MAX_METHOD_RESULTS=20
_LABEL_RE=re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def _bucket(number):
    if number==0:return "0"
    if number<=2:return "1-2"
    if number<=5:return "3-5"
    if number<=10:return "6-10"
    return ">10"


def _safe_structure(values,stage,failure):
    items=tuple(values or ())
    text=[]
    for value in items:
        if isinstance(value,bytes):
            try:value=value.decode("utf-8","strict")
            except UnicodeError:value=""
        text.append(str(value or ""))
    combined="\n".join(text)
    methods=re.findall(r"(?:^|;)\s*([A-Za-z][A-Za-z0-9_-]*)\s*=",combined)
    known={"dkim","spf","dmarc","arc","compauth"}
    properties=re.findall(r"\b([A-Za-z][A-Za-z0-9_.-]*)\s*=",combined)
    return {"header_present":bool(items),"header_count":len(items),
            "total_size_bucket":("<1KiB" if len(combined.encode("utf-8","replace"))<1024 else
                                 "1-4KiB" if len(combined.encode("utf-8","replace"))<=4096 else ">4KiB"),
            "folded_present":bool(re.search(r"\r?\n[ \t]+",combined)),
            "non_ascii_present":any(ord(ch)>127 for ch in combined),
            "parse_stage":stage,"safe_failure_class":failure,
            "unknown_method_present":any(method.lower() not in known for method in methods),
            "comment_present":"(" in combined and ")" in combined,
            "quoted_value_present":'"' in combined,
            "duplicate_property_present":len(properties)!=len({item.lower() for item in properties}),
            "method_count_bucket":_bucket(len(methods))}


class SenderAuthMalformed(Exception):
    safe_code="sender_auth_malformed"
    def __init__(self,stage="parse",failure="malformed",values=()):
        super().__init__()
        self.diagnostic=_safe_structure(values,stage,failure)


def normalize_domain(value):
    raw=str(value or "").strip().lower()
    if raw.endswith("."): raw=raw[:-1]
    if not raw or len(raw)>253 or "@" in raw or any(character.isspace() for character in raw):
        raise SenderAuthMalformed()
    try: domain=raw.encode("idna").decode("ascii")
    except (UnicodeError,ValueError) as exc: raise SenderAuthMalformed() from exc
    labels=domain.split(".")
    if len(labels)<2 or any(not _LABEL_RE.fullmatch(label) for label in labels):
        raise SenderAuthMalformed()
    return domain


@dataclass(frozen=True)
class AuthMethodResult:
    method: str
    result: str
    domain: str


@dataclass(frozen=True)
class AuthenticationResultRecord:
    authserv_id: str
    dkim: tuple
    spf: tuple


@dataclass(frozen=True)
class SenderAuthEvidence:
    from_domain: str
    records: tuple
    trusted_receiver_boundary: bool


@dataclass(frozen=True)
class SenderPolicyConfig:
    service_id: str
    approved_from_domains: frozenset
    approved_dkim_domains: frozenset
    approved_spf_domains: frozenset
    approved_authserv_ids: frozenset
    alignment_mode: str="exact"


@dataclass(frozen=True)
class SenderAuthDecision:
    status: str
    reason: str
    def __post_init__(self):
        if self.status not in STATUSES: raise ValueError("invalid_sender_auth_decision")


def _unfold_and_strip_name(value,all_values):
    if isinstance(value,bytes):
        try: raw=value.decode("utf-8","strict")
        except UnicodeError as exc: raise SenderAuthMalformed("representation","invalid_bytes",all_values) from exc
    elif isinstance(value,str): raw=value
    else: raise SenderAuthMalformed("representation","invalid_type",all_values)
    if len(raw.encode("utf-8","replace"))>MAX_AUTH_RESULTS_BYTES:
        raise SenderAuthMalformed("limits","header_oversized",all_values)
    if re.search(r"\r(?!\n)|(?<!\r)\n(?![ \t])|\r\n(?![ \t])",raw):
        raise SenderAuthMalformed("unfolding","header_injection",all_values)
    raw=re.sub(r"\r?\n[ \t]+"," ",raw)
    match=re.match(r"^Authentication-Results\s*:\s*",raw,re.I)
    if match: raw=raw[match.end():]
    if not raw: raise SenderAuthMalformed("representation","header_empty",all_values)
    return raw


def _remove_comments(raw,all_values):
    output=[]; depth=0; quoted=False; escaped=False
    for character in raw:
        if escaped: escaped=False; output.append(character if depth==0 else " "); continue
        if character=="\\": escaped=True; output.append(character if depth==0 else " "); continue
        if character=='"' and depth==0: quoted=not quoted; output.append(character); continue
        if not quoted and character=="(": depth+=1
        elif not quoted and character==")":
            if depth==0: raise SenderAuthMalformed("comments","unbalanced_comment",all_values)
            depth-=1
        else: output.append(character if depth==0 else " ")
        if depth>5: raise SenderAuthMalformed("comments","comment_depth",all_values)
    if depth or quoted or escaped: raise SenderAuthMalformed("comments","unterminated_construct",all_values)
    return "".join(output)


def _split_semicolons(raw,all_values):
    parts=[]; current=[]; quoted=False; escaped=False
    for character in raw:
        if escaped: current.append(character); escaped=False; continue
        if character=="\\" and quoted: current.append(character); escaped=True; continue
        if character=='"': quoted=not quoted; current.append(character); continue
        if character==";" and not quoted: parts.append("".join(current).strip()); current=[]
        else: current.append(character)
    if quoted or escaped: raise SenderAuthMalformed("tokenization","unterminated_quote",all_values)
    parts.append("".join(current).strip()); return parts


_PROPERTY_RE=re.compile(r"([A-Za-z][A-Za-z0-9_.-]*)\s*=\s*(?:\"((?:\\.|[^\"])*)\"|([^\s]+))")
def _properties(tail,all_values):
    result={}
    for match in _PROPERTY_RE.finditer(tail):
        key=match.group(1).lower(); value=match.group(2) if match.group(2) is not None else match.group(3)
        if key in result: raise SenderAuthMalformed("properties","duplicate_property",all_values)
        result[key]=value.strip("<>")
    return result


def parse_authentication_results(values):
    if isinstance(values,str): values=(values,)
    values=tuple(values or ())
    if len(values)>MAX_AUTH_RESULTS_HEADERS: raise SenderAuthMalformed("limits","record_count",values)
    records=[]
    for value in values:
        raw=_unfold_and_strip_name(value,values)
        raw=_remove_comments(raw,values)
        segments=_split_semicolons(raw,values)
        if not segments or not segments[0]: raise SenderAuthMalformed("authserv_id","missing",values)
        authserv_token=segments[0].split()[0]
        try: authserv_id=normalize_domain(authserv_token)
        except SenderAuthMalformed as exc: raise SenderAuthMalformed("authserv_id","invalid",values) from exc
        methods={"dkim":[],"spf":[]}
        for segment in segments[1:]:
            if not segment: continue
            match=re.match(r"^([a-z][a-z0-9_-]*)\s*=\s*([a-z]+)\b(.*)$",segment,re.I)
            if not match:
                if re.match(r"^(dkim|spf)\b",segment,re.I):
                    raise SenderAuthMalformed("methods","required_method_malformed",values)
                continue
            method,result,tail=match.group(1).lower(),match.group(2).lower(),match.group(3)
            if method not in {"dkim","spf"}: continue
            if result not in RESULTS: raise SenderAuthMalformed("methods","result_invalid",values)
            props=_properties(tail,values)
            key="header.d" if method=="dkim" else "smtp.mailfrom"
            domain=""
            if props.get(key):
                candidate=props[key].rsplit("@",1)[-1]
                try: domain=normalize_domain(candidate)
                except SenderAuthMalformed as exc: raise SenderAuthMalformed("domain","required_domain_invalid",values) from exc
            methods[method].append(AuthMethodResult(method,result,domain))
        records.append(AuthenticationResultRecord(authserv_id,tuple(methods["dkim"]),tuple(methods["spf"])))
    if sum(len(record.dkim) for record in records)>MAX_METHOD_RESULTS or sum(len(record.spf) for record in records)>MAX_METHOD_RESULTS:
        raise SenderAuthMalformed("limits","method_result_count",values)
    return tuple(records)


def _within(domain,base): return domain==base or domain.endswith("."+base)


def domains_aligned(left,right,mode):
    try: left,right=normalize_domain(left),normalize_domain(right)
    except SenderAuthMalformed: return False
    if mode=="exact": return left==right
    if mode=="explicit_subdomain": return _within(left,right) or _within(right,left)
    return False


def _approved(domain,approved,mode):
    if mode=="exact": return domain in approved
    return any(_within(domain,base) for base in approved)


def _decision(status,reason): return SenderAuthDecision(status,reason)


class MailSenderAuthPolicy:
    def evaluate(self,evidence,policy):
        if not isinstance(evidence,SenderAuthEvidence) or not isinstance(policy,SenderPolicyConfig):
            return _decision("denied","invalid_sender_policy_input")
        if not evidence.trusted_receiver_boundary:
            return _decision("denied","authentication_results_untrusted")
        if policy.alignment_mode not in {"exact","explicit_subdomain"}:
            return _decision("denied","alignment_mode_invalid")
        try:
            from_domain=normalize_domain(evidence.from_domain)
            approved_from=frozenset(normalize_domain(item) for item in policy.approved_from_domains)
            approved_dkim=frozenset(normalize_domain(item) for item in policy.approved_dkim_domains)
            approved_spf=frozenset(normalize_domain(item) for item in policy.approved_spf_domains)
            approved_authserv=frozenset(normalize_domain(item) for item in policy.approved_authserv_ids)
        except (SenderAuthMalformed,TypeError): return _decision("denied","sender_policy_invalid")
        if not policy.service_id or not all((approved_from,approved_dkim,approved_spf,approved_authserv)):
            return _decision("denied","sender_policy_invalid")
        if not _approved(from_domain,approved_from,policy.alignment_mode):
            return _decision("denied","from_domain_unapproved")
        if not evidence.records: return _decision("unsupported","authentication_results_missing")
        if any(record.authserv_id not in approved_authserv for record in evidence.records):
            return _decision("denied","authserv_id_untrusted")

        dkim=tuple(item for record in evidence.records for item in record.dkim)
        spf=tuple(item for record in evidence.records for item in record.spf)
        dkim_decision=self._method(dkim,"dkim",from_domain,approved_dkim,policy.alignment_mode)
        if dkim_decision: return dkim_decision
        spf_decision=self._method(spf,"spf",from_domain,approved_spf,policy.alignment_mode)
        if spf_decision: return spf_decision
        return _decision("authorized","sender_identity_authenticated")

    @staticmethod
    def _method(items,method,from_domain,approved,mode):
        if not items: return _decision("unsupported",f"{method}_missing")
        results={item.result for item in items}
        if len(results)>1: return _decision("ambiguous",f"{method}_results_conflict")
        result=next(iter(results))
        if result!="pass": return _decision("denied",f"{method}_{result}")
        domains={item.domain for item in items}
        if "" in domains: return _decision("denied",f"{method}_domain_missing")
        if len(domains)>1: return _decision("ambiguous",f"{method}_domains_conflict")
        domain=next(iter(domains))
        if not _approved(domain,approved,mode): return _decision("denied",f"{method}_domain_unapproved")
        if not domains_aligned(from_domain,domain,mode): return _decision("denied",f"{method}_alignment_failed")
        return None
