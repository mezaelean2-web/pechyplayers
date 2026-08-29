"""Política genérica y pura de recipient; no está conectada a producción."""

import re
from dataclasses import dataclass
from email.header import decode_header
from email.utils import getaddresses

from private_email_credentials import ProviderCredentials


MAX_HEADER_BYTES=2048
MAX_RECIPIENTS=20
STATUSES=frozenset({"authorized","denied","ambiguous","unsupported"})
_ADDRESS_RE=re.compile(r"[A-Za-z0-9.!#$%&'+/=?^_`{|}~-]+@[A-Za-z0-9.-]+")


@dataclass(frozen=True,repr=False)
class InternalRecipient:
    _value: str
    @classmethod
    def from_provider_credentials(cls,credentials):
        if not isinstance(credentials,ProviderCredentials): raise TypeError("internal_recipient_required")
        value=credentials.username.strip().lower()
        if not _ADDRESS_RE.fullmatch(value): raise ValueError("internal_recipient_invalid")
        return cls(value)
    def __repr__(self): return "InternalRecipient(<redacted>)"


@dataclass(frozen=True)
class RecipientHeaders:
    to: tuple=()
    cc: tuple=()
    delivered_to: tuple=()


@dataclass(frozen=True)
class RecipientSecurityContext:
    canonical_authorized: bool
    assignment_version_valid: bool
    binding_version_valid: bool
    post_t0_uid: bool
    uidvalidity_continuous: bool
    sender_allowlisted: bool
    service_adapter_approved: bool
    dkim_pass: bool
    spf_pass: bool
    from_dkim_aligned: bool
    from_spf_aligned: bool
    evidence_from_bound_imap_mailbox: bool


@dataclass(frozen=True)
class RecipientDecision:
    status: str
    reason: str
    evidence: str
    def __post_init__(self):
        if self.status not in STATUSES or self.evidence not in {"none","direct","delivery"}:
            raise ValueError("invalid_recipient_decision")


def _decision(status,reason,evidence="none"):
    return RecipientDecision(status,reason,evidence)


def _decode(value):
    raw=str(value or "")
    if "\r" in raw or "\n" in raw: raise ValueError("header_injection")
    if len(raw.encode("utf-8","replace"))>MAX_HEADER_BYTES: raise ValueError("header_oversized")
    pieces=[]
    for fragment,charset in decode_header(raw):
        if isinstance(fragment,bytes): fragment=fragment.decode(charset or "ascii","strict")
        pieces.append(str(fragment))
    decoded="".join(pieces)
    addresses=[address.strip().lower() for _,address in getaddresses([decoded]) if address]
    if raw.strip() and not addresses: raise ValueError("header_malformed")
    if any(not _ADDRESS_RE.fullmatch(address) for address in addresses):
        raise ValueError("header_malformed")
    return addresses


def _parse_values(values):
    if isinstance(values,str): raise TypeError("header_values_must_be_tuple")
    addresses=[]
    for value in tuple(values): addresses.extend(_decode(value))
    return addresses


def _context_failure(context):
    checks=(
        (context.canonical_authorized,"canonical_authorization_required"),
        (context.assignment_version_valid,"assignment_version_invalid"),
        (context.binding_version_valid,"binding_version_invalid"),
        (context.post_t0_uid,"pre_t0_message"),
        (context.uidvalidity_continuous,"uidvalidity_changed"),
        (context.evidence_from_bound_imap_mailbox,"untrusted_recipient_evidence_source"),
        (context.sender_allowlisted,"sender_not_allowlisted"),
        (context.service_adapter_approved,"service_adapter_not_approved"),
        (context.dkim_pass,"dkim_failed"),(context.spf_pass,"spf_failed"),
        (context.from_dkim_aligned,"dkim_alignment_failed"),
        (context.from_spf_aligned,"spf_alignment_failed"),
    )
    return next((reason for passed,reason in checks if not passed),None)


class MailRecipientPolicy:
    """Evalúa headers ya obtenidos de un mailbox/config resuelto internamente."""
    def evaluate(self,internal_recipient,headers,context,*,other_managed_recipients=()):
        if not isinstance(internal_recipient,InternalRecipient):
            return _decision("denied","internal_recipient_required")
        if not isinstance(headers,RecipientHeaders) or not isinstance(context,RecipientSecurityContext):
            return _decision("denied","invalid_policy_input")
        if any(not isinstance(item,InternalRecipient) for item in other_managed_recipients):
            return _decision("denied","managed_recipient_context_invalid")
        try:
            to=_parse_values(headers.to); cc=_parse_values(headers.cc)
            delivered=_parse_values(headers.delivered_to)
        except (TypeError,ValueError,LookupError,UnicodeError):
            return _decision("denied","recipient_header_invalid")
        if len(to)+len(cc)+len(delivered)>MAX_RECIPIENTS:
            return _decision("denied","recipient_limit_exceeded")

        failure=_context_failure(context)
        if failure: return _decision("denied",failure)
        expected=internal_recipient._value
        other={item._value for item in other_managed_recipients if item._value!=expected}
        visible=to+cc
        direct=expected in visible
        visible_other=bool(other.intersection(visible))

        # Delivered-To debe ser exactamente una ocurrencia con una dirección.
        if len(headers.delivered_to)>1:
            return _decision("ambiguous","multiple_delivered_to")
        if delivered and len(delivered)!=1:
            return _decision("ambiguous","delivered_to_multiple_recipients")
        delivery=delivered==[expected]
        delivery_other=bool(other.intersection(delivered))

        if direct:
            if delivered and not delivery:
                return _decision("ambiguous","direct_delivery_conflict")
            if visible_other or delivery_other:
                return _decision("ambiguous","managed_recipient_conflict")
            return _decision("authorized","direct_recipient_exact","direct")
        if delivery:
            if visible_other or delivery_other:
                return _decision("ambiguous","managed_recipient_conflict")
            return _decision("authorized","trusted_delivery_exact","delivery")
        if delivered:
            return _decision("denied","delivery_recipient_mismatch")
        if visible:
            return _decision("denied","direct_recipient_mismatch")
        return _decision("unsupported","recipient_evidence_absent")
