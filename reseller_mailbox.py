"""Flujo reseller de mensajes autorizados con repositorio efímero de Fase 3."""

import hashlib
import re
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import RLock

import database
import inventory_assignment_access
import reseller_mailbox_persistence
from mail_providers import SUPPORTED_MESSAGE_KINDS


REQUEST_TTL_SECONDS = 90
POLL_INTERVAL_SECONDS = 1
RATE_WINDOW_SECONDS = 60
RATE_MAX_REQUESTS = 5
MAX_HISTORY_PER_ASSIGNMENT = 20
EMAIL_RE = re.compile(r"^[^\s@]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\.[A-Za-z]{2,63}$")
PUBLIC_MESSAGE_KINDS = {
    "numeric_code": "Código de acceso",
    "alphanumeric_code": "Código alfanumérico",
    "action_link": "Enlace de acción",
    "approval_action": "Confirmación de acceso",
    "device_notice": "Aviso de dispositivo",
    "instructions": "Instrucciones",
}


def utcnow():
    return datetime.now(timezone.utc)


def normalize_email_query(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if len(normalized) <= 254 and EMAIL_RE.fullmatch(normalized) else None


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _opaque_reference(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:24]


class InMemoryMailboxRepository:
    """Estado local para demostrar el flujo; no es persistencia productiva."""

    def __init__(self):
        self.requests = {}
        self.history = defaultdict(list)
        self.audit = []
        self.rate = defaultdict(deque)
        self._lock = RLock()

    def reset(self):
        with self._lock:
            self.requests.clear()
            self.history.clear()
            self.audit.clear()
            self.rate.clear()


class ResellerMailboxService:
    def __init__(self, provider, repository=None, clock=None):
        self.provider = provider
        self.repository = repository or reseller_mailbox_persistence.SQLiteMailboxRepository()
        self.clock = clock or utcnow
        self._lock = getattr(self.repository, "_lock", RLock())
        self._rate = defaultdict(deque)
        self.worker_id = secrets.token_urlsafe(12)

    def _audit(self, *, reseller_id, purchase_id, unit, result, safe_code,
               request_id, provider_reference=None):
        event = {
            "event_id": secrets.token_urlsafe(18),
            "actor_type": "reseller",
            "reseller_id": int(reseller_id),
            "purchase_id": int(purchase_id) if purchase_id is not None else None,
            "inventory_unit": dict(unit) if unit else None,
            "result": str(result),
            "safe_code": str(safe_code),
            "timestamp": _iso(self.clock()),
            "request_id": str(request_id) if request_id else None,
            "provider_reference": (_opaque_reference(provider_reference)
                                   if provider_reference else None),
        }
        if isinstance(self.repository, InMemoryMailboxRepository):
            self.repository.audit.append(event)
        else:
            self.repository.append_audit(event)

    def _neutral(self, status="unavailable", request_id=None, retry_after=None):
        result = {
            "ok": True,
            "status": status,
            "message": "No hay mensajes disponibles para esta cuenta.",
        }
        if request_id:
            result["request_id"] = request_id
        if retry_after is not None:
            result["retry_after"] = max(1, int(retry_after))
        return result

    def _candidate_purchases(self, reseller_id, normalized_email):
        conn = database.conectar()
        try:
            return [int(row["id"]) for row in conn.execute("""
                SELECT rp.id
                FROM reseller_purchases rp
                JOIN nube_cuentas c ON c.id=rp.cuenta_id
                WHERE rp.revendedor_id=? AND lower(trim(c.correo))=?
                ORDER BY rp.id
            """, (int(reseller_id), normalized_email)).fetchall()]
        finally:
            conn.close()

    def _resolve_authorized_candidate(self, reseller_id, normalized_email, now):
        candidates = self._candidate_purchases(reseller_id, normalized_email)
        authorized = []
        denied_codes = []
        for purchase_id in candidates:
            result = inventory_assignment_access.authorize_reseller_message_access(
                reseller_id, purchase_id, now=now)
            if result.get("authorized") is True:
                authorized.append(result)
            else:
                denied_codes.append(result.get("safe_code") or "invalid_request")
        if not authorized:
            return None, denied_codes[0] if denied_codes else "purchase_not_found"
        unique = {
            (item["inventory_unit"]["type"], item["inventory_unit"]["account_id"],
             item["inventory_unit"]["profile_id"], item["assignment_version"])
            for item in authorized
        }
        if len(unique) != 1:
            return None, "ambiguous_assignment"
        return authorized[0], "authorized"

    def _rate_allowed(self, reseller_id, now):
        queue = (self.repository.rate[int(reseller_id)]
                 if isinstance(self.repository, InMemoryMailboxRepository)
                 else self._rate[int(reseller_id)])
        threshold = now - timedelta(seconds=RATE_WINDOW_SECONDS)
        while queue and queue[0] <= threshold:
            queue.popleft()
        if len(queue) >= RATE_MAX_REQUESTS:
            return False
        queue.append(now)
        return True

    def request_message(self, reseller_id, email):
        now = self.clock()
        normalized = normalize_email_query(email)
        with self._lock:
            if normalized is None or not self._rate_allowed(reseller_id, now):
                self._audit(reseller_id=reseller_id, purchase_id=None, unit=None,
                            result="denied", safe_code="invalid_or_limited",
                            request_id=None)
                return self._neutral()
            authorization, safe_code = self._resolve_authorized_candidate(
                reseller_id, normalized, now)
            if not authorization:
                self._audit(reseller_id=reseller_id, purchase_id=None, unit=None,
                            result="denied", safe_code=safe_code, request_id=None)
                return self._neutral()
            purchase_id = authorization["purchase_id"]
            if isinstance(self.repository, InMemoryMailboxRepository):
                existing = next((item for item in self.repository.requests.values()
                    if item["reseller_id"] == int(reseller_id)
                    and item["purchase_id"] == purchase_id and item["status"] == "waiting"
                    and item["expires_at"] > now), None)
            else:
                existing = self.repository.active_request(reseller_id, purchase_id, now)
                if existing and not self.provider.can_resume_request(existing["id"]):
                    existing["status"] = "expired"
                    self.repository.update_request(existing)
                    self._audit(reseller_id=reseller_id, purchase_id=purchase_id,
                                unit=existing["unit"], result="expired",
                                safe_code="provider_state_unavailable",
                                request_id=existing["id"])
                    existing = None
            if existing:
                result = self._neutral("waiting", existing["id"], POLL_INTERVAL_SECONDS)
                result["history"] = self._history_for(existing)
                return result
            request_id = secrets.token_urlsafe(24)
            record = {
                "id": request_id,
                "reseller_id": int(reseller_id),
                "purchase_id": purchase_id,
                "unit": dict(authorization["inventory_unit"]),
                "assignment_version": authorization["assignment_version"],
                "requested_at": now,
                "expires_at": now + timedelta(seconds=REQUEST_TTL_SECONDS),
                "last_polled_at": None,
                "status": "waiting",
                "delivery_id": None,
            }
            if isinstance(self.repository, InMemoryMailboxRepository):
                self.repository.requests[request_id] = record
            else:
                self.repository.create_request(record)
            self._audit(reseller_id=reseller_id, purchase_id=purchase_id,
                        unit=record["unit"], result="waiting", safe_code="authorized",
                        request_id=request_id)
            self.provider.begin_request(
                request_id=request_id, unit=record["unit"], requested_at=now)
            return {
                "ok": True, "status": "waiting", "request_id": request_id,
                "retry_after": POLL_INTERVAL_SECONDS,
                "message": "Esperando un mensaje nuevo…",
                "history": self._history_for(record),
            }

    def _current_authorization(self, record, now):
        result = inventory_assignment_access.authorize_reseller_message_access(
            record["reseller_id"], record["purchase_id"], now=now)
        return (result if result.get("authorized") is True
                and result.get("assignment_version") == record["assignment_version"]
                and result.get("inventory_unit") == record["unit"] else None)

    def _public_delivery(self, delivery):
        value = delivery.get("value")
        available = value is not None
        return {
            "id": delivery["id"],
            "service": delivery["service"],
            "kind": delivery["kind"],
            "kind_label": PUBLIC_MESSAGE_KINDS[delivery["kind"]],
            "value": value if available else "Contenido no disponible",
            "content_available": available,
            "received_at": _iso(delivery["received_at"]),
        }

    def _history_for(self, record):
        if isinstance(self.repository, InMemoryMailboxRepository):
            key = (record["reseller_id"], record["purchase_id"])
            items = list(reversed(self.repository.history[key]))
        else:
            items = self.repository.history_for(
                record["reseller_id"], record["purchase_id"], MAX_HISTORY_PER_ASSIGNMENT)
        return [self._public_delivery(self._restore_content(item)) for item in items]

    def _restore_content(self, delivery):
        if delivery.get("value") is not None:
            return delivery
        message = self.provider.message_by_reference(
            unit=delivery["unit"], opaque_reference=delivery["provider_reference"])
        if message is None or message.kind != delivery["kind"]:
            return delivery
        restored = dict(delivery)
        restored["value"] = message.value
        return restored

    def poll_request(self, reseller_id, request_id):
        if isinstance(self.repository, InMemoryMailboxRepository):
            return self._poll_request(reseller_id, request_id)
        now=self.clock()
        record=self.repository.get_request(request_id,reseller_id)
        if not record:
            return self._neutral()
        if record["status"]!="waiting":
            return self._poll_request(reseller_id,request_id)
        if not self.repository.claim_poll(request_id,reseller_id,self.worker_id,now):
            return self._neutral("waiting",str(request_id),POLL_INTERVAL_SECONDS)
        try:
            return self._poll_request(reseller_id,request_id)
        finally:
            self.repository.release_poll(request_id,self.worker_id)

    def _poll_request(self, reseller_id, request_id):
        now = self.clock()
        with self._lock:
            record = (self.repository.requests.get(str(request_id))
                      if isinstance(self.repository, InMemoryMailboxRepository)
                      else self.repository.get_request(request_id, reseller_id))
            if not record or record["reseller_id"] != int(reseller_id):
                return self._neutral()
            if not self._current_authorization(record, now):
                record["status"] = "denied"
                if not isinstance(self.repository, InMemoryMailboxRepository):
                    self.repository.update_request(record)
                self._audit(reseller_id=reseller_id, purchase_id=record["purchase_id"],
                            unit=record["unit"], result="denied",
                            safe_code="authorization_changed", request_id=record["id"])
                return self._neutral()
            if record["status"] == "found":
                if isinstance(self.repository, InMemoryMailboxRepository):
                    delivery = next((item for item in self.repository.history[
                        (record["reseller_id"], record["purchase_id"])]
                        if item["id"] == record["delivery_id"]), None)
                else:
                    delivery = self.repository.get_delivery(record["delivery_id"], reseller_id)
                if delivery:
                    delivery = self._restore_content(delivery)
                    return {"ok": True, "status": "found",
                            "message": self._public_delivery(delivery),
                            "history": self._history_for(record)}
                return self._neutral()
            if record["status"] in {"denied", "expired"}:
                return self._neutral("expired" if record["status"] == "expired" else "unavailable")
            if now >= record["expires_at"]:
                record["status"] = "expired"
                if not isinstance(self.repository, InMemoryMailboxRepository):
                    self.repository.update_request(record)
                self._audit(reseller_id=reseller_id, purchase_id=record["purchase_id"],
                            unit=record["unit"], result="expired", safe_code="request_expired",
                            request_id=record["id"])
                return self._neutral("expired")
            if (record["last_polled_at"] is not None
                    and (now - record["last_polled_at"]).total_seconds() < POLL_INTERVAL_SECONDS):
                return self._neutral("waiting", record["id"], POLL_INTERVAL_SECONDS)
            record["last_polled_at"] = now
            if not isinstance(self.repository, InMemoryMailboxRepository):
                self.repository.update_request(record)
            messages = self.provider.messages_after(
                unit=record["unit"], requested_at=record["requested_at"])
            message = next((item for item in messages
                            if item.kind in SUPPORTED_MESSAGE_KINDS), None)
            if message is None:
                return self._neutral("waiting", record["id"], POLL_INTERVAL_SECONDS)
            # Revalidación inmediatamente antes de conservar y revelar contenido.
            if not self._current_authorization(record, now):
                record["status"] = "denied"
                if not isinstance(self.repository, InMemoryMailboxRepository):
                    self.repository.update_request(record)
                return self._neutral()
            delivery = {
                "id": secrets.token_urlsafe(18),
                "reseller_id": record["reseller_id"],
                "purchase_id": record["purchase_id"],
                "unit": dict(record["unit"]),
                "service": message.service,
                "kind": message.kind,
                "value": message.value,
                "received_at": message.received_at,
                "provider_reference": _opaque_reference(message.reference),
                "provider_locator": getattr(message, "locator", None),
            }
            if isinstance(self.repository, InMemoryMailboxRepository):
                key = (record["reseller_id"], record["purchase_id"])
                self.repository.history[key].append(delivery)
                self.repository.history[key] = self.repository.history[key][-MAX_HISTORY_PER_ASSIGNMENT:]
                record["status"] = "found"
                record["delivery_id"] = delivery["id"]
            else:
                record["delivery_id"] = self.repository.create_delivery(record, delivery, now)
                delivery["id"] = record["delivery_id"]
            self._audit(reseller_id=reseller_id, purchase_id=record["purchase_id"],
                        unit=record["unit"], result="delivered", safe_code="message_delivered",
                        request_id=record["id"], provider_reference=message.reference)
            return {"ok": True, "status": "found",
                    "message": self._public_delivery(delivery),
                    "history": self._history_for(record)}

    def read_delivery(self, reseller_id, delivery_id):
        now = self.clock()
        with self._lock:
            if not isinstance(self.repository, InMemoryMailboxRepository):
                delivery = self.repository.get_delivery(delivery_id, reseller_id)
                if not delivery:
                    return self._neutral()
                authorization = inventory_assignment_access.authorize_reseller_message_access(
                    reseller_id, delivery["purchase_id"], now=now)
                if (authorization.get("authorized") is not True
                        or authorization.get("inventory_unit") != delivery["unit"]):
                    return self._neutral()
                return {"ok": True, "status": "found",
                        "message": self._public_delivery(self._restore_content(delivery))}
            for (owner, purchase_id), deliveries in self.repository.history.items():
                if owner != int(reseller_id):
                    continue
                delivery = next((item for item in deliveries if item["id"] == delivery_id), None)
                if not delivery:
                    continue
                authorization = inventory_assignment_access.authorize_reseller_message_access(
                    reseller_id, purchase_id, now=now)
                if (authorization.get("authorized") is not True
                        or authorization.get("inventory_unit") != delivery["unit"]):
                    return self._neutral()
                return {"ok": True, "status": "found",
                        "message": self._public_delivery(delivery)}
            return self._neutral()
