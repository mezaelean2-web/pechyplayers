"""Discovery administrativo, acotado y redactado de un mensaje Netflix post-T0."""

import argparse
import hashlib
import html
import json
import re
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport
from private_email_provider import ProviderError


ALLOWED_CONFIGS = frozenset({"pechy_pilot"})
FOLDER = "INBOX"
NETFLIX_SENDER_DOMAIN = "account.netflix.com"
MAX_POST_T0_UIDS = 10
MAX_MESSAGE_BYTES = 131072
MAX_PARTS = 30
MAX_DEPTH = 6
MAX_ANCHORS = 50
MAX_TEXT_BYTES = 8192
MAX_DISAMBIGUATION_UIDS = 4
_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+")
_NUMERIC_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[0-9]{4,}(?![A-Za-z0-9])")
_MIXED_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?=[A-Za-z0-9]{6,}(?![A-Za-z0-9]))"
    r"(?=[A-Za-z0-9]*[A-Za-z])(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]+"
)


class NetflixDiscoveryError(Exception):
    safe_code = "netflix_discovery_failed"


class NetflixDiscoveryDenied(NetflixDiscoveryError):
    safe_code = "discovery_denied"


class NetflixDiscoveryChanged(NetflixDiscoveryError):
    safe_code = "uidvalidity_changed"


class NetflixDiscoveryAmbiguous(NetflixDiscoveryError):
    safe_code = "candidate_not_unique"


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a" and self._href is None:
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            if len(self.items) >= MAX_ANCHORS:
                raise NetflixDiscoveryError()
            self.items.append((" ".join("".join(self._text).split()), self._href))
            self._href = None
            self._text = []


def _decode_header(value):
    pieces = []
    try:
        for fragment, charset in decode_header(str(value or "")):
            if isinstance(fragment, bytes):
                fragment = fragment.decode(charset or "ascii", "strict")
            pieces.append(str(fragment))
    except (LookupError, UnicodeError, ValueError) as exc:
        raise NetflixDiscoveryError() from exc
    return "".join(pieces).strip()


def _safe_fingerprint(value):
    value = " ".join(str(value or "").split())
    if not value or len(value.encode("utf-8", "replace")) > 256:
        raise NetflixDiscoveryError()
    if _EMAIL_RE.search(value) or "http://" in value.lower() or "https://" in value.lower():
        return "REDACTED_VARIABLE_SUBJECT"
    if _NUMERIC_TOKEN_RE.search(value) or _MIXED_TOKEN_RE.search(value):
        return "REDACTED_VARIABLE_SUBJECT"
    return value


def _subject_summary(value):
    decoded = _decode_header(value)
    encoded = decoded.encode("utf-8", "replace")
    if not decoded or len(encoded) > 512:
        raise NetflixDiscoveryError()
    normalized = decoded.lower()
    semantic = any(word in normalized for word in
                   ("password", "contrase", "restable", "reset", "cambio de clave"))
    length = len(decoded)
    bucket = "1-32" if length <= 32 else ("33-64" if length <= 64 else
             ("65-128" if length <= 128 else "129-512"))
    return {"subject_fingerprint": hashlib.sha256(encoded).hexdigest(),
            "subject_length_bucket": bucket, "reset_semantic_match": semantic}


def _sender_domain(value):
    raw = str(value or "").strip().lower()
    matches = re.findall(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9.-]+)", raw)
    return matches[0].rstrip(".") if len(matches) == 1 else ""


def _extract_anchors(metadata, raw):
    if not isinstance(raw, (bytes, bytearray)) or not raw or len(raw) > MAX_MESSAGE_BYTES:
        raise NetflixDiscoveryError()
    prefix = (f"Content-Type: {metadata.get('content_type', 'text/plain')}\r\n"
              f"Content-Transfer-Encoding: {metadata.get('content_transfer_encoding', '')}\r\n\r\n").encode()
    try:
        root = BytesParser(policy=policy.default).parsebytes(prefix + bytes(raw))
    except Exception as exc:
        raise NetflixDiscoveryError() from exc
    anchors = []
    parts = 0

    def walk(node, depth=0):
        nonlocal parts
        if depth > MAX_DEPTH:
            raise NetflixDiscoveryError()
        parts += 1
        if parts > MAX_PARTS:
            raise NetflixDiscoveryError()
        if node.is_multipart():
            for child in node.iter_parts():
                walk(child, depth + 1)
            return
        if node.get_content_disposition() == "attachment" or node.get_filename():
            return
        if node.get_content_type() != "text/html":
            return
        try:
            value = str(node.get_content())
        except (LookupError, UnicodeError, ValueError) as exc:
            raise NetflixDiscoveryError() from exc
        if len(value.encode("utf-8", "replace")) > MAX_TEXT_BYTES:
            raise NetflixDiscoveryError()
        parser = _Anchors()
        try:
            parser.feed(value)
            parser.close()
        except Exception as exc:
            raise NetflixDiscoveryError() from exc
        anchors.extend(parser.items)

    walk(root)
    return anchors


def _cta_candidates(anchors):
    results = []
    for text, href in anchors:
        normalized = " ".join(text.lower().split())
        if not any(word in normalized for word in ("password", "contrase", "restable", "reset")):
            continue
        try:
            parsed = urlsplit(html.unescape(str(href or "")))
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except (TypeError, ValueError, UnicodeError):
            continue
        if parsed.scheme.lower() not in {"https", "http"} or not host or parsed.username or parsed.password:
            continue
        results.append((parsed.scheme.lower(), host, port, _safe_fingerprint(text)))
    return sorted(set(results))


class NetflixRealDiscovery:
    def __init__(self, resolver, transport):
        self.resolver = resolver
        self.transport = transport

    def _validate_config(self, config):
        config = str(config or "").strip()
        if config not in ALLOWED_CONFIGS:
            raise NetflixDiscoveryDenied()
        self.resolver.resolve(config)
        return config

    def prepare(self, config):
        config = self._validate_config(config)
        cursor = self.transport.examine(config, FOLDER)
        uidvalidity, uidnext = int(cursor["uidvalidity"]), int(cursor["uidnext"])
        if uidvalidity <= 0 or uidnext <= 0:
            raise NetflixDiscoveryError()
        return {"ok": True, "read_only": True, "ready": "READY_FOR_NETFLIX_RESET_TRIGGER",
                "uidvalidity": uidvalidity, "uidnext_at_t0": uidnext}

    def count_only(self, config, uidvalidity, uidnext_at_t0):
        config = self._validate_config(config)
        expected_validity, minimum = int(uidvalidity), int(uidnext_at_t0)
        if expected_validity <= 0 or minimum <= 0:
            raise NetflixDiscoveryDenied()
        before = self.transport.examine(config, FOLDER)
        if int(before["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        uids = sorted({int(uid) for uid in self.transport.search_uids(
            config, FOLDER, minimum, MAX_POST_T0_UIDS) if int(uid) >= minimum})
        candidates = []
        for uid in uids:
            if _sender_domain(self.transport.fetch_from_header(config, FOLDER, uid)) == NETFLIX_SENDER_DOMAIN:
                candidates.append(uid)
        after = self.transport.examine(config, FOLDER)
        if int(after["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        count = len(candidates)
        return {"ok": True, "uidvalidity_continuous": True, "post_t0_uid_count": len(uids),
                "netflix_candidate_count": count if count < 2 else ">1",
                "candidate_uid": candidates[0] if count == 1 else ("MULTIPLE" if count else "NONE"),
                "candidate_uids": candidates if count > 1 else [], "body_fetched": False}

    def disambiguate_metadata(self, config, uidvalidity, uidnext_at_t0, uids):
        config = self._validate_config(config)
        expected_validity, minimum = int(uidvalidity), int(uidnext_at_t0)
        selected = tuple(int(uid) for uid in uids)
        if (expected_validity <= 0 or minimum <= 0 or len(selected) != MAX_DISAMBIGUATION_UIDS
                or len(set(selected)) != len(selected) or any(uid < minimum for uid in selected)):
            raise NetflixDiscoveryDenied()
        before = self.transport.examine(config, FOLDER)
        if int(before["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        rows = []
        for uid in selected:
            item = self.transport.fetch_disambiguation_metadata(config, FOLDER, uid)
            from_values, subject_values = item.get("from", ()), item.get("subject", ())
            if len(from_values) != 1 or len(subject_values) != 1:
                raise NetflixDiscoveryError()
            rows.append({"uid": uid, "internaldate": item["internaldate"],
                         "sender_class": "netflix_candidate" if
                         _sender_domain(from_values[0]) == NETFLIX_SENDER_DOMAIN else "other",
                         **_subject_summary(subject_values[0])})
        after = self.transport.examine(config, FOLDER)
        if int(after["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        ordered = sorted(rows, key=lambda row: (row["internaldate"], row["uid"]))
        for order, row in enumerate(ordered, 1):
            row["arrival_order"] = order
            del row["internaldate"]
        matches = [row["uid"] for row in ordered if row["sender_class"] == "netflix_candidate"
                   and row["reset_semantic_match"]]
        result = "UNIQUE" if len(matches) == 1 else ("NONE" if not matches else "STILL_AMBIGUOUS")
        return {"ok": True, "uidvalidity_continuous": True, "candidates_inspected": len(ordered),
                "candidate_summary": ordered,
                "unique_metadata_candidate": matches[0] if len(matches) == 1 else "NONE",
                "disambiguation_result": result, "body_fetched": False,
                "url_exposed": False, "subject_exposed": False}

    def inspect(self, config, uidvalidity, uidnext_at_t0):
        config = self._validate_config(config)
        expected_validity, minimum = int(uidvalidity), int(uidnext_at_t0)
        if expected_validity <= 0 or minimum <= 0:
            raise NetflixDiscoveryDenied()
        before = self.transport.examine(config, FOLDER)
        if int(before["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        uids = self.transport.search_uids(config, FOLDER, minimum, MAX_POST_T0_UIDS)
        selected = sorted({int(uid) for uid in uids if int(uid) >= minimum})
        candidates = []
        for uid in selected:
            metadata = self.transport.fetch_metadata(config, FOLDER, uid)
            if _sender_domain(metadata.get("from")) == NETFLIX_SENDER_DOMAIN:
                candidates.append((uid, metadata))
        if len(candidates) != 1:
            raise NetflixDiscoveryAmbiguous()
        uid, metadata = candidates[0]
        size = int(metadata.get("size", 0) or 0)
        if size <= 0 or size > MAX_MESSAGE_BYTES:
            raise NetflixDiscoveryError()
        raw = self.transport.fetch_body_peek(config, FOLDER, uid, metadata.get("body_part", "TEXT"))
        ctas = _cta_candidates(_extract_anchors(metadata, raw))
        after = self.transport.examine(config, FOLDER)
        if int(after["uidvalidity"]) != expected_validity:
            raise NetflixDiscoveryChanged()
        if len(ctas) != 1:
            raise NetflixDiscoveryAmbiguous()
        scheme, host, port, cta_text = ctas[0]
        subject = _safe_fingerprint(_decode_header(metadata.get("subject")))
        return {"ok": True, "post_t0_message": True, "uidvalidity_continuous": True,
                "subject_fingerprint": subject,
                "subject_exact_rule_possible": subject != "REDACTED_VARIABLE_SUBJECT",
                "cta_text_fingerprint": cta_text, "cta_destination_scheme": scheme,
                "cta_destination_host": host,
                "cta_destination_port": "default" if port is None else port,
                "distinct_valid_cta_candidates": 1, "full_url_exposed": False,
                "body_exposed": False, "sensitive_content_persisted": False}


def _parser():
    parser = argparse.ArgumentParser(description="Controlled Netflix post-T0 discovery")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    inspect = sub.add_parser("inspect")
    count_only = sub.add_parser("count-only")
    disambiguate = sub.add_parser("disambiguate-metadata")
    for item in (prepare, inspect, count_only, disambiguate):
        item.add_argument("--provider-config-id", required=True, choices=sorted(ALLOWED_CONFIGS))
    for item in (inspect, count_only, disambiguate):
        item.add_argument("--uidvalidity", required=True, type=int)
        item.add_argument("--uidnext-at-t0", required=True, type=int)
    disambiguate.add_argument("--uids", required=True, nargs=MAX_DISAMBIGUATION_UIDS, type=int)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)
        resolver = ProviderCredentialResolver()
        utility = NetflixRealDiscovery(resolver, PrivateEmailIMAPTransport(resolver))
        if args.command == "prepare":
            result = utility.prepare(args.provider_config_id)
        elif args.command == "count-only":
            result = utility.count_only(args.provider_config_id, args.uidvalidity, args.uidnext_at_t0)
        elif args.command == "disambiguate-metadata":
            result = utility.disambiguate_metadata(args.provider_config_id, args.uidvalidity,
                                                   args.uidnext_at_t0, args.uids)
        else:
            result = utility.inspect(args.provider_config_id, args.uidvalidity, args.uidnext_at_t0)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (NetflixDiscoveryError, ProviderError) as exc:
        print(json.dumps({"ok": False, "error": getattr(exc, "safe_code", "provider_error")},
                         sort_keys=True, separators=(",", ":")))
        return 2
    except Exception:
        print('{"error":"netflix_discovery_failed","ok":false}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
