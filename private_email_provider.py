"""Proveedor Private Email sobre transporte IMAP inyectable; no abre red por sí mismo."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from mail_providers import MailProvider, ProviderMessage


class ProviderError(Exception):
    safe_code = "provider_error"
class ProviderUnavailable(ProviderError): safe_code = "provider_unavailable"
class ProviderTLSFailed(ProviderError): safe_code = "provider_tls_failed"
class ProviderTimeout(ProviderError): safe_code = "provider_timeout"
class ProviderAuthenticationFailed(ProviderError): safe_code = "provider_auth_failed"
class ProviderConfigurationError(ProviderError): safe_code = "provider_config_invalid"
class ProviderCursorInvalid(ProviderError): safe_code = "provider_cursor_invalid"
class ProviderMessageMalformed(ProviderError): safe_code = "message_malformed"
class ProviderMessageTooLarge(ProviderError): safe_code = "message_too_large"
class ProviderProtocolError(ProviderError): safe_code = "provider_protocol_error"


@dataclass(frozen=True)
class ProviderCursor:
    binding_id: int
    folder_key: str
    uidvalidity: int
    uidnext_boundary: int
    captured_at: datetime
    binding_version: int

    def __post_init__(self):
        if min(self.binding_id, self.uidvalidity, self.uidnext_boundary, self.binding_version) <= 0:
            raise ProviderCursorInvalid()
        if self.folder_key != "INBOX" or self.captured_at.tzinfo is None:
            raise ProviderCursorInvalid()


@dataclass(frozen=True)
class ProviderLocator:
    binding_id: int
    folder_key: str
    uidvalidity: int
    uid: int

    def canonical(self):
        if min(self.binding_id, self.uidvalidity, self.uid) <= 0 or self.folder_key != "INBOX":
            raise ProviderCursorInvalid()
        return json.dumps({"b":self.binding_id,"f":self.folder_key,"v":self.uidvalidity,"u":self.uid},
                          sort_keys=True,separators=(",",":"))

    def audit_hash(self):
        return hashlib.sha256(self.canonical().encode()).hexdigest()


class IMAPTransport:
    """Interface sin implementación de red en 5B.1."""
    def examine(self, provider_config_id, folder_key): raise NotImplementedError
    def search_uids(self, provider_config_id, folder_key, minimum_uid, limit): raise NotImplementedError
    def fetch_metadata(self, provider_config_id, folder_key, uid): raise NotImplementedError
    def fetch_body_peek(self, provider_config_id, folder_key, uid, part): raise NotImplementedError
    def close(self): pass


class PrivateEmailMailProvider(MailProvider):
    def __init__(self, transport, parser_registry, *, limit=20):
        if transport is None: raise ProviderConfigurationError()
        self.transport, self.parsers, self.limit = transport, parser_registry, min(max(int(limit),1),50)

    def begin_request(self, *, request_id, binding, requested_at):
        try: state = self.transport.examine(binding.provider_config_id, binding.folder_key)
        except ProviderError: raise
        except TimeoutError as exc: raise ProviderTimeout() from exc
        except Exception as exc: raise ProviderProtocolError() from exc
        cursor = ProviderCursor(binding.binding_id, binding.folder_key, int(state["uidvalidity"]),
            int(state["uidnext"]), requested_at.astimezone(timezone.utc), binding.binding_version)
        return cursor

    def _validate(self, binding, cursor):
        if (cursor.binding_id != binding.binding_id or cursor.binding_version != binding.binding_version
                or cursor.folder_key != binding.folder_key): raise ProviderCursorInvalid()

    def messages_after(self, *, binding, cursor, limit=None, action=None):
        self._validate(binding, cursor)
        state = self.transport.examine(binding.provider_config_id, binding.folder_key)
        if int(state["uidvalidity"]) != cursor.uidvalidity: raise ProviderCursorInvalid()
        uids = self.transport.search_uids(binding.provider_config_id, binding.folder_key,
            cursor.uidnext_boundary, min(limit or self.limit, self.limit))
        results=[]; candidates=[]
        registry=self.parsers
        if action is not None:
            from mail_center import action_metadata_matches, build_action_registry
            registry=build_action_registry(action)
        if action is not None:
            for uid in sorted({int(x) for x in uids if int(x) >= cursor.uidnext_boundary},reverse=True):
                meta=self.transport.fetch_metadata(binding.provider_config_id,binding.folder_key,uid)
                if not action_metadata_matches(action,meta):
                    continue
                candidates.append((uid,meta))
                break
        for uid,meta in candidates if action is not None else []:
            parsed=registry.classify(meta, lambda part: self.transport.fetch_body_peek(
                binding.provider_config_id,binding.folder_key,uid,part), requested_at=cursor.captured_at)
            if parsed.kind == "unsupported": continue
            locator=ProviderLocator(binding.binding_id,binding.folder_key,cursor.uidvalidity,uid)
            results.append(ProviderMessage(locator.canonical(),f"binding:{binding.binding_id}",
                parsed.service,parsed.kind,parsed.value,meta["internaldate"],locator))
        if action is None:
            for uid in sorted({int(x) for x in uids if int(x) >= cursor.uidnext_boundary}):
                meta=self.transport.fetch_metadata(binding.provider_config_id,binding.folder_key,uid)
                parsed=registry.classify(meta, lambda part: self.transport.fetch_body_peek(
                    binding.provider_config_id,binding.folder_key,uid,part), requested_at=cursor.captured_at)
                if parsed.kind == "unsupported": continue
                locator=ProviderLocator(binding.binding_id,binding.folder_key,cursor.uidvalidity,uid)
                results.append(ProviderMessage(locator.canonical(),f"binding:{binding.binding_id}",
                    parsed.service,parsed.kind,parsed.value,meta["internaldate"],locator))
        return results

    def message_by_reference(self, *, binding, provider_locator, action=None):
        locator = provider_locator if isinstance(provider_locator, ProviderLocator) else None
        if not locator or locator.binding_id != binding.binding_id: raise ProviderCursorInvalid()
        state=self.transport.examine(binding.provider_config_id,binding.folder_key)
        if int(state["uidvalidity"]) != locator.uidvalidity: return None
        meta=self.transport.fetch_metadata(binding.provider_config_id,binding.folder_key,locator.uid)
        registry=self.parsers
        if action is not None:
            from mail_center import action_metadata_matches, build_action_registry
            if not action_metadata_matches(action,meta): return None
            registry=build_action_registry(action)
        parsed=registry.classify(meta,lambda part:self.transport.fetch_body_peek(
            binding.provider_config_id,binding.folder_key,locator.uid,part),requested_at=None)
        if parsed.kind == "unsupported": return None
        return ProviderMessage(locator.canonical(),f"binding:{binding.binding_id}",parsed.service,
            parsed.kind,parsed.value,meta["internaldate"],locator)

    def can_resume_request(self, *, binding, cursor):
        try:
            self._validate(binding,cursor)
            return int(self.transport.examine(binding.provider_config_id,binding.folder_key)["uidvalidity"]) == cursor.uidvalidity
        except Exception: return False
