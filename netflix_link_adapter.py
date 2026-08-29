"""Netflix reset-link adapter V1; offline y sin configuración productiva."""

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit,urlunsplit

from mail_message_parsers import ParsedMessage,ServiceAdapter


ALLOWED_LINK_HOSTS_CONFIGURATION_REQUIRED=True
MAX_URL_BYTES=2048
_PERCENT_INVALID=re.compile(r"%(?![0-9A-Fa-f]{2})")
_ENCODED_CONTROL=re.compile(r"%(?:0[0-9A-Fa-f]|1[0-9A-Fa-f]|7F)",re.I)


@dataclass(frozen=True)
class LinkHostRule:
    hostname: str
    allow_subdomains: bool=False


def _normalize_words(value):
    decomposed=unicodedata.normalize("NFKD",str(value or ""))
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).lower().split())


def _normalize_host(value):
    raw=str(value or "").lower().rstrip(".")
    if not raw or any(ord(c)>127 for c in raw) or "%" in raw or raw.startswith("xn--") or ".xn--" in raw:
        return None
    labels=raw.split(".")
    if len(labels)<2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",label) for label in labels):
        return None
    return raw


class NetflixLinkAdapter(ServiceAdapter):
    service="Netflix"
    def __init__(self,*,subjects,allowed_link_hosts,cta_phrases=("password","contraseña","restablece","reset")):
        self.subjects=frozenset(str(value) for value in subjects)
        self.host_rules=tuple(allowed_link_hosts)
        self.cta_phrases=tuple(_normalize_words(value) for value in cta_phrases if str(value).strip())

    def _result(self,status,reason,value=""):
        kind="action_link" if status=="success" else "unsupported"
        return ParsedMessage(self.service,kind,value,reason,status)

    def _allowed_host(self,host):
        for rule in self.host_rules:
            base=_normalize_host(rule.hostname)
            if base and (host==base or (rule.allow_subdomains and host.endswith("."+base))): return True
        return False

    def _validated_url(self,value):
        raw=str(value or "")
        if not raw or len(raw.encode("utf-8","replace"))>MAX_URL_BYTES or any(ord(c)<32 or c.isspace() for c in raw): return None
        if _PERCENT_INVALID.search(raw) or _ENCODED_CONTROL.search(raw): return None
        try:
            parsed=urlsplit(raw)
            if parsed.scheme.lower()!="https" or not parsed.netloc or parsed.username is not None or parsed.password is not None:return None
            host=_normalize_host(parsed.hostname)
            if not host or not self._allowed_host(host):return None
            try:port=parsed.port
            except ValueError:return None
            if port not in (None,443):return None
            try:ipaddress.ip_address(host); return None
            except ValueError:pass
            netloc=host if port is None else f"{host}:443"
            return urlunsplit(("https",netloc,parsed.path or "/",parsed.query,""))
        except (TypeError,ValueError,UnicodeError): return None

    def parse_decoded(self,metadata,decoded):
        if not self.subjects:return self._result("unsupported","subject_configuration_required")
        if not self.host_rules:return self._result("unsupported","allowed_link_hosts_configuration_required")
        if str(metadata.get("subject") or "") not in self.subjects:return self._result("unsupported","unsupported_subject")
        cta=[]
        for text,href in decoded.anchors:
            normalized=_normalize_words(text)
            if any(phrase in normalized for phrase in self.cta_phrases):cta.append(href)
        if not cta:return self._result("unsupported","cta_not_found")
        valid={candidate for candidate in (self._validated_url(item) for item in cta) if candidate}
        if not valid:return self._result("unsupported","no_valid_link")
        if len(valid)>1:return self._result("ambiguous","ambiguous_link")
        return self._result("success","link_validated",next(iter(valid)))
