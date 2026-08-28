"""Contratos de proveedores de mensajes; esta fase incluye solamente un fake local."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock


SUPPORTED_MESSAGE_KINDS = frozenset({
    "numeric_code",
    "alphanumeric_code",
    "action_link",
    "approval_action",
    "device_notice",
    "instructions",
})


@dataclass(frozen=True)
class ProviderMessage:
    reference: str
    unit_key: str
    service: str
    kind: str
    value: str
    received_at: datetime
    locator: object = None


class MailProvider:
    """Interfaz mínima que un proveedor real deberá implementar posteriormente."""

    def begin_request(self, *, request_id, unit, requested_at):
        raise NotImplementedError

    def messages_after(self, *, unit, requested_at):
        raise NotImplementedError

    def message_by_reference(self, *, unit, opaque_reference):
        """Recupera contenido permitido; una ausencia debe tratarse fail-closed."""
        raise NotImplementedError

    def can_resume_request(self, request_id):
        return False


def inventory_unit_key(unit):
    account_id = int(unit["account_id"])
    profile_id = unit.get("profile_id")
    return f"account:{account_id}:profile:{int(profile_id) if profile_id is not None else '-'}"


class FakeMailProvider(MailProvider):
    """Proveedor determinista, sin red, credenciales, sockets ni persistencia."""

    def __init__(self, *, auto_message=True, delay_seconds=2):
        self.auto_message = bool(auto_message)
        self.delay_seconds = int(delay_seconds)
        self._messages = []
        self._begun = set()
        self._lock = RLock()
        self.begin_calls = 0
        self.query_calls = 0

    def reset(self):
        with self._lock:
            self._messages.clear()
            self._begun.clear()
            self.begin_calls = 0
            self.query_calls = 0

    def can_resume_request(self, request_id):
        with self._lock:
            return str(request_id) in self._begun

    def add_message(self, *, reference, unit, service, kind, value, received_at):
        moment = received_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        message = ProviderMessage(
            reference=str(reference),
            unit_key=inventory_unit_key(unit),
            service=str(service or "PECHY PLAYERS")[:80],
            kind=str(kind),
            value=str(value),
            received_at=moment.astimezone(timezone.utc),
        )
        with self._lock:
            self._messages.append(message)
        return message

    def begin_request(self, *, request_id, unit, requested_at):
        with self._lock:
            self.begin_calls += 1
            if request_id in self._begun:
                return
            self._begun.add(request_id)
            if self.auto_message:
                self.add_message(
                    reference=f"fake-{request_id}", unit=unit,
                    service="Servicio digital", kind="numeric_code", value="482193",
                    received_at=requested_at + timedelta(seconds=self.delay_seconds),
                )

    def messages_after(self, *, unit, requested_at):
        key = inventory_unit_key(unit)
        with self._lock:
            self.query_calls += 1
            return sorted(
                (item for item in self._messages
                 if item.unit_key == key and item.received_at > requested_at),
                key=lambda item: (item.received_at, item.reference),
            )

    def message_by_reference(self, *, unit, opaque_reference):
        key = inventory_unit_key(unit)
        with self._lock:
            return next((item for item in self._messages
                         if item.unit_key == key and
                         hashlib.sha256(item.reference.encode()).hexdigest()[:24]
                         == str(opaque_reference)), None)
