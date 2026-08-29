"""Adapter MIME estricto y exclusivo del piloto controlado 5B.4."""

import re
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses

from mail_message_parsers import ParsedMessage
from private_email_provider import ProviderMessageMalformed, ProviderMessageTooLarge


PILOT_CONFIG_ID = "pechy_pilot"
PILOT_SENDER = "mezaelean2@gmail.com"
PILOT_SUBJECT = "PECHY-PILOT-CODE"
PILOT_MAX_MESSAGE_BYTES = 8192
_CODE = re.compile(r"CODE: ([0-9]{6})")
_DKIM_PASS = re.compile(r"(?:^|[;\s])dkim\s*=\s*pass(?:[;\s]|$)", re.IGNORECASE)
_SPF_PASS = re.compile(r"(?:^|[;\s])spf\s*=\s*pass(?:[;\s]|$)", re.IGNORECASE)


class PilotMessageAdapterRegistry:
    """Registry de un solo adapter; no posee reglas comerciales ni fallback."""

    def __init__(self, recipient, *, max_message_bytes=PILOT_MAX_MESSAGE_BYTES):
        recipient = str(recipient or "").strip().lower()
        if not recipient or "@" not in recipient:
            raise ValueError("pilot_recipient_invalid")
        self._recipient = recipient
        self.max_message_bytes = min(max(int(max_message_bytes), 256), PILOT_MAX_MESSAGE_BYTES)

    @staticmethod
    def _unsupported():
        return ParsedMessage("Pechy Pilot", "unsupported", "")

    @staticmethod
    def _single_address(value):
        addresses = [address.lower() for _, address in getaddresses([str(value or "")]) if address]
        return addresses[0] if len(addresses) == 1 else None

    @staticmethod
    def _safe_header(value):
        value = str(value or "").strip()
        if not value or len(value) > 512 or "\r" in value or "\n" in value:
            raise ProviderMessageMalformed()
        return value

    def _message(self, metadata, raw):
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise ProviderMessageMalformed()
        if len(raw) > self.max_message_bytes:
            raise ProviderMessageTooLarge()
        content_type = self._safe_header(metadata.get("content_type", "text/plain"))
        transfer_encoding = str(metadata.get("content_transfer_encoding") or "").strip()
        headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n"
        if transfer_encoding:
            headers += f"Content-Transfer-Encoding: {self._safe_header(transfer_encoding)}\r\n"
        try:
            return BytesParser(policy=policy.default).parsebytes(
                headers.encode("ascii") + b"\r\n" + bytes(raw))
        except Exception as exc:
            raise ProviderMessageMalformed() from exc

    def classify(self, metadata, body_loader, *, requested_at):
        try:
            size = int(metadata.get("size", 0) or 0)
        except (TypeError, ValueError):
            raise ProviderMessageMalformed() from None
        if size <= 0:
            raise ProviderMessageMalformed()
        if size > self.max_message_bytes:
            raise ProviderMessageTooLarge()
        if self._single_address(metadata.get("from")) != PILOT_SENDER:
            return self._unsupported()
        if self._single_address(metadata.get("to")) != self._recipient:
            return self._unsupported()
        if str(metadata.get("subject") or "") != PILOT_SUBJECT:
            return self._unsupported()
        authentication = str(metadata.get("authentication_results") or "")
        if not _DKIM_PASS.search(authentication) or not _SPF_PASS.search(authentication):
            return self._unsupported()
        internaldate = metadata.get("internaldate")
        if internaldate is None or internaldate.tzinfo is None:
            raise ProviderMessageMalformed()
        if requested_at is not None and internaldate < requested_at:
            return self._unsupported()
        message = self._message(metadata, body_loader(metadata.get("body_part", "TEXT")))
        plain_parts = []
        for part in message.walk():
            if part.is_multipart() or part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                plain_parts.append(part.get_content())
            except (LookupError, UnicodeError) as exc:
                raise ProviderMessageMalformed() from exc
        if len(plain_parts) != 1:
            return self._unsupported()
        text = str(plain_parts[0]).strip()
        match = _CODE.fullmatch(text)
        return (ParsedMessage("Pechy Pilot", "numeric_code", match.group(1))
                if match else self._unsupported())


def build_pilot_message_registry(credential_resolver):
    """Obtiene el recipient solo desde la configuración administrativa del piloto."""
    credentials = credential_resolver.resolve(PILOT_CONFIG_ID)
    return PilotMessageAdapterRegistry(credentials.username)
