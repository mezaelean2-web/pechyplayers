"""Discovery administrativo redacted para diseñar adapters de Private Email.

No es un endpoint ni forma parte del flujo del revendedor. La invocación CLI es la
única ruta que construye el transporte de red; las pruebas inyectan un transporte fake.
"""

import argparse
import hashlib
import json
import re
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path

from dotenv import load_dotenv

from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import (ProviderConfigurationError, ProviderError,
                                    ProviderMessageMalformed)


ALLOWED_PROVIDER_CONFIGS = frozenset({"pechy_pilot"})
FOLDER_KEY = "INBOX"
DEFAULT_LIMIT = 20
HARD_CAP = 50
MAX_MESSAGE_BYTES = 131072
MAX_PARTS = 30
MAX_DEPTH = 6

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
_NUMERIC_RE = re.compile(r"(?<![A-Za-z0-9])([0-9]{4,10})(?![A-Za-z0-9])")
_ALPHANUMERIC_RE = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]{6,20}(?![A-Za-z0-9]))"
    r"(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]+"
)
_ENCODED_WORD_RE = re.compile(r"=\?[^?\s]+\?[bqBQ]\?[^?]*\?=")
_ENVELOPE_HEADER_KEYS = ("delivered_to", "x_original_to", "envelope_to")
MAX_RECIPIENT_HEADER_BYTES = 2048
MAX_RECIPIENTS = 20


class DiscoveryDenied(Exception):
    safe_code = "discovery_denied"


class DiscoveryMailboxChanged(Exception):
    safe_code = "uidvalidity_changed"


class DiscoveryMalformed(Exception):
    safe_code = "message_malformed"


def _sha(value):
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _addresses(value):
    raw = str(value or "")
    if len(raw.encode("utf-8", "replace")) > MAX_RECIPIENT_HEADER_BYTES:
        return None
    try:
        decoded = []
        for fragment, charset in decode_header(raw):
            if isinstance(fragment, bytes):
                fragment = fragment.decode(charset or "ascii", "strict")
            decoded.append(str(fragment))
        parsed = [address.strip().lower() for _, address in getaddresses(["".join(decoded)]) if address]
    except (LookupError, UnicodeError, ValueError):
        return None
    if len(parsed) > MAX_RECIPIENTS:
        return None
    if raw.strip() and not parsed:
        return None
    if any(not re.fullmatch(r"[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", item)
           for item in parsed):
        return None
    return parsed


def _domain(address):
    return address.rsplit("@", 1)[1] if "@" in address else ""


def _encoding_family(charset):
    value = str(charset or "ascii").strip().lower().replace("_", "-")
    if value in {"ascii", "us-ascii"}: return "ascii"
    if value in {"utf-8", "utf8"}: return "utf-8"
    if value.startswith("iso-8859-"): return "iso-8859"
    if value.startswith("windows-") or value.startswith("cp12"): return "windows"
    return "other"


def _length_bucket(length):
    if length == 0: return "0"
    if length <= 32: return "1-32"
    if length <= 64: return "33-64"
    if length <= 128: return "65-128"
    return ">128"


def _subject_features(subject):
    raw = str(subject or "")
    families = set()
    pieces = []
    try:
        for fragment, charset in decode_header(raw):
            families.add(_encoding_family(charset))
            if isinstance(fragment, bytes):
                fragment = fragment.decode(charset or "ascii", "strict")
            pieces.append(str(fragment))
        decoded = "".join(pieces)
        decode_valid = True
    except (LookupError, UnicodeError, ValueError):
        decoded = ""
        decode_valid = False
    numeric = _NUMERIC_RE.findall(decoded)
    alphanumeric = _ALPHANUMERIC_RE.findall(decoded)
    return {
        "subject_present": bool(raw),
        "subject_encoded": bool(_ENCODED_WORD_RE.search(raw)),
        "subject_decode_valid": decode_valid,
        "subject_decoded_length_bucket": _length_bucket(len(decoded)),
        "subject_numeric_token_count": len(numeric),
        "subject_numeric_token_lengths": sorted(len(item) for item in numeric),
        "subject_alphanumeric_candidate_count": len(alphanumeric),
        "subject_alphanumeric_candidate_lengths": sorted(len(item) for item in alphanumeric),
        "subject_fingerprint": _sha(decoded) if decode_valid else "",
        "subject_encoding_families": sorted(families),
        "subject_contains_non_ascii": any(ord(character) > 127 for character in decoded),
    }


def recipient_match_flags(metadata, expected_recipient):
    expected = str(expected_recipient or "").strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", expected):
        return {"direct_match": False, "envelope_match": False, "alias_possible": False}
    direct = []
    for key in ("to", "cc"):
        parsed = _addresses(metadata.get(key))
        if parsed is None:
            return {"direct_match": False, "envelope_match": False, "alias_possible": False}
        direct.extend(parsed)
    envelope = []
    for key in _ENVELOPE_HEADER_KEYS:
        parsed = _addresses(metadata.get(key))
        if parsed is None:
            return {"direct_match": False, "envelope_match": False, "alias_possible": False}
        envelope.extend(parsed)
    direct_match = expected in direct
    envelope_match = expected in envelope
    return {"direct_match": direct_match, "envelope_match": envelope_match,
            "alias_possible": not direct_match and envelope_match}


def _auth_shape(value):
    raw = str(value or "").lower()
    def status(name):
        match = re.search(rf"(?:^|[;\s]){name}\s*=\s*([a-z]+)", raw)
        return match.group(1) if match else "missing"
    domains = set()
    for pattern in (r"header\.d\s*=\s*([^;\s]+)", r"smtp\.mailfrom\s*=\s*([^;\s]+)"):
        for candidate in re.findall(pattern, raw):
            candidate = candidate.strip("<>.,").rsplit("@", 1)[-1]
            if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,63}", candidate):
                domains.add(candidate)
    return {"dkim": status("dkim"), "spf": status("spf"),
            "auth_domains": sorted(domains)}


def _domain_alignment(sender_domain, auth_domains):
    sender = str(sender_domain or "").lower().strip(".")
    domains = [str(item).lower().strip(".") for item in auth_domains]
    aligned = any(sender == item or sender.endswith("." + item) or item.endswith("." + sender)
                  for item in domains if sender and item)
    return {"authenticated_domain_alignment_candidate": aligned}


def _safe_content_type(message):
    try:
        return message.get_content_type()
    except Exception:
        return "invalid"


def _analyze_body(metadata, raw):
    if not isinstance(raw, (bytes, bytearray)) or not raw:
        raise DiscoveryMalformed()
    if len(raw) > MAX_MESSAGE_BYTES:
        raise DiscoveryMalformed()
    prefix = (f"Content-Type: {metadata.get('content_type', 'text/plain')}\r\n"
              f"Content-Transfer-Encoding: {metadata.get('content_transfer_encoding', '')}\r\n\r\n").encode()
    try:
        message = BytesParser(policy=policy.default).parsebytes(prefix + bytes(raw))
    except Exception as exc:
        raise DiscoveryMalformed() from exc

    texts = []
    content_types = []
    encodings = set()
    charsets = set()
    attachments = 0
    part_count = 0
    max_depth_seen = 0

    def walk(node, depth=0):
        nonlocal attachments, part_count, max_depth_seen
        if depth > MAX_DEPTH:
            raise DiscoveryMalformed()
        part_count += 1
        if part_count > MAX_PARTS:
            raise DiscoveryMalformed()
        max_depth_seen = max(max_depth_seen, depth)
        if node.is_multipart():
            content_types.append(_safe_content_type(node))
            for child in node.iter_parts():
                walk(child, depth + 1)
            return
        disposition = node.get_content_disposition()
        if disposition == "attachment" or node.get_filename():
            attachments += 1
            return
        kind = _safe_content_type(node)
        content_types.append(kind)
        if kind not in {"text/plain", "text/html"}:
            return
        charset = node.get_content_charset() or "unspecified"
        charsets.add(charset.lower())
        encodings.add((node.get("Content-Transfer-Encoding") or "unspecified").lower())
        try:
            value = node.get_content()
        except (LookupError, UnicodeError, ValueError) as exc:
            raise DiscoveryMalformed() from exc
        texts.append((kind, str(value)))

    walk(message)
    combined = "\n".join(value for _, value in texts)
    numeric = _NUMERIC_RE.findall(combined)
    alphanumeric = _ALPHANUMERIC_RE.findall(combined)
    links = _URL_RE.findall(combined)
    total_candidates = len(numeric) + len(alphanumeric) + len(links)
    if total_candidates > 1:
        provisional = "ambiguous"
    elif len(numeric) == 1:
        provisional = "numeric_code"
    elif len(alphanumeric) == 1:
        provisional = "alphanumeric_code"
    elif len(links) == 1:
        provisional = "action_link"
    else:
        provisional = "unsupported"
    shape = {
        "content_types": sorted(content_types), "parts": part_count,
        "max_depth": max_depth_seen, "attachments": attachments,
        "numeric_lengths": sorted(len(item) for item in numeric),
        "alphanumeric_lengths": sorted(len(item) for item in alphanumeric),
        "link_count": len(links),
    }
    return {
        "mime": {"text_plain": any(kind == "text/plain" for kind, _ in texts),
                 "text_html": any(kind == "text/html" for kind, _ in texts),
                 "multipart": message.is_multipart(), "attachments": attachments,
                 "parts": part_count, "max_depth": max_depth_seen,
                 "encodings": sorted(encodings), "charsets": sorted(charsets)},
        "candidate_numeric_tokens": {"count": len(numeric),
                                     "lengths": sorted(len(item) for item in numeric)},
        "candidate_alphanumeric_tokens": {"count": len(alphanumeric),
                                          "lengths": sorted(len(item) for item in alphanumeric)},
        "candidate_links": {"count": len(links)},
        "possible_cta": bool(links), "provisional_type": provisional,
        "body_structure_fingerprint": _sha(json.dumps(shape, sort_keys=True)),
    }


def _size_bucket(size):
    for boundary, label in ((8192, "<8KiB"), (32768, "8-32KiB"),
                            (131072, "32-128KiB")):
        if size < boundary:
            return label
    return ">=128KiB"


class PrivateEmailAdapterDiscovery:
    def __init__(self, credential_resolver, transport, *, allowed_configs=ALLOWED_PROVIDER_CONFIGS):
        self.resolver = credential_resolver
        self.transport = transport
        self.allowed_configs = frozenset(allowed_configs)

    def discover(self, provider_config_id, *, limit=DEFAULT_LIMIT):
        config_id = str(provider_config_id or "").strip()
        if config_id not in self.allowed_configs:
            raise DiscoveryDenied()
        try:
            requested_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise DiscoveryDenied() from exc
        if requested_limit < 1 or requested_limit > HARD_CAP:
            raise DiscoveryDenied()
        credentials = self.resolver.resolve(config_id)
        expected_recipient = credentials.username.strip().lower()
        initial = self.transport.examine(config_id, FOLDER_KEY)
        uidvalidity = int(initial["uidvalidity"])
        uidnext = int(initial["uidnext"])
        if uidvalidity <= 0 or uidnext <= 0:
            raise DiscoveryMalformed()
        minimum_uid = max(1, uidnext - requested_limit)
        uids = self.transport.search_uids(config_id, FOLDER_KEY, minimum_uid, requested_limit)
        selected = sorted({int(uid) for uid in uids if minimum_uid <= int(uid) < uidnext})[-requested_limit:]
        reports = []
        for index, uid in enumerate(selected, 1):
            metadata = self.transport.fetch_metadata(config_id, FOLDER_KEY, uid)
            size = int(metadata.get("size", 0) or 0)
            senders = _addresses(metadata.get("from"))
            routing = recipient_match_flags(metadata, expected_recipient)
            sender = senders[0] if senders is not None and len(senders) == 1 else ""
            auth = _auth_shape(metadata.get("authentication_results"))
            sender_domain = _domain(sender)
            report = {
                "candidate": index,
                "identity": {"provider_config_id": config_id, "folder": FOLDER_KEY,
                             "uidvalidity": uidvalidity, "uid": uid},
                "sender_domain": sender_domain,
                "sender_localpart_hash": _sha(sender.rsplit("@", 1)[0]) if sender else "",
                **routing, **_subject_features(metadata.get("subject")), **auth,
                **_domain_alignment(sender_domain, auth["auth_domains"]),
                "size_bucket": _size_bucket(size), "body_inspected": False,
            }
            if size <= 0:
                report["safe_result"] = "message_malformed"
            elif size > MAX_MESSAGE_BYTES:
                report["safe_result"] = "message_too_large"
            elif not (report["direct_match"] or report["envelope_match"]):
                report["safe_result"] = "recipient_mismatch"
            elif auth["dkim"] != "pass" or auth["spf"] != "pass":
                report["safe_result"] = "authentication_failed"
            else:
                try:
                    raw = self.transport.fetch_body_peek(config_id, FOLDER_KEY, uid,
                                                         metadata.get("body_part", "TEXT"))
                    report.update(_analyze_body(metadata, raw))
                    report["body_inspected"] = True
                    report["safe_result"] = "inspected"
                except DiscoveryMalformed:
                    report["safe_result"] = "message_malformed"
            reports.append(report)
        final = self.transport.examine(config_id, FOLDER_KEY)
        if int(final["uidvalidity"]) != uidvalidity:
            raise DiscoveryMailboxChanged()
        return {"ok": True, "read_only": True, "provider_config_id": config_id,
                "folder": FOLDER_KEY, "hard_cap": HARD_CAP,
                "requested_limit": requested_limit, "candidate_count": len(reports),
                "uidvalidity": uidvalidity, "messages": reports}


def _parser():
    parser = argparse.ArgumentParser(description="Private Email adapter discovery (redacted)")
    parser.add_argument("--provider-config-id", required=True, choices=sorted(ALLOWED_PROVIDER_CONFIGS))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
        resolver = ProviderCredentialResolver()
        utility = PrivateEmailAdapterDiscovery(resolver, PrivateEmailIMAPTransport(resolver))
        result = utility.discover(args.provider_config_id, limit=args.limit)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (DiscoveryDenied, DiscoveryMailboxChanged, DiscoveryMalformed,
            ProviderError, ProviderConfigurationError) as exc:
        print(json.dumps({"ok": False, "error": getattr(exc, "safe_code", "discovery_failed")},
                         sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print('{"error":"discovery_failed","ok":false}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
