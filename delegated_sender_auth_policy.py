"""Composición de auth para servicios con infraestructura delegada."""

from dataclasses import dataclass

from mail_sender_auth_policy import (AuthenticationResultRecord,SenderAuthEvidence,
                                     SenderAuthMalformed,normalize_domain)


@dataclass(frozen=True)
class DelegatedSenderPolicyConfig:
    service_id: str
    approved_from_domains: frozenset
    approved_first_party_dkim_domains: frozenset
    approved_auxiliary_dkim_domains: frozenset
    approved_spf_infrastructure_domains: frozenset
    spf_allow_subdomains: bool
    approved_authserv_ids: frozenset
    require_trusted_receiver_boundary: bool=True


@dataclass(frozen=True)
class DelegatedSenderDecision:
    status: str
    reason: str
    def __post_init__(self):
        if self.status not in {"authorized","denied","ambiguous","unsupported"}:
            raise ValueError("invalid_delegated_sender_decision")


def _decision(status,reason): return DelegatedSenderDecision(status,reason)
def _within(domain,base): return domain==base or domain.endswith("."+base)
def _approved(domain,domains,subdomains=False):
    return any(_within(domain,base) if subdomains else domain==base for base in domains)
def _aligned(left,right): return left==right or _within(left,right) or _within(right,left)


class DelegatedServiceSenderAuthPolicy:
    """Exige identidad DKIM first-party; SPF delegado nunca basta por sí solo."""
    def evaluate(self,evidence,config):
        if not isinstance(evidence,SenderAuthEvidence) or not isinstance(config,DelegatedSenderPolicyConfig):
            return _decision("denied","invalid_delegated_policy_input")
        if config.require_trusted_receiver_boundary and not evidence.trusted_receiver_boundary:
            return _decision("denied","receiver_boundary_untrusted")
        try:
            from_domain=normalize_domain(evidence.from_domain)
            from_allowed=frozenset(normalize_domain(x) for x in config.approved_from_domains)
            first_party=frozenset(normalize_domain(x) for x in config.approved_first_party_dkim_domains)
            auxiliary=frozenset(normalize_domain(x) for x in config.approved_auxiliary_dkim_domains)
            spf_infra=frozenset(normalize_domain(x) for x in config.approved_spf_infrastructure_domains)
            authserv_allowed=frozenset(normalize_domain(x) for x in config.approved_authserv_ids)
        except (SenderAuthMalformed,TypeError): return _decision("denied","delegated_policy_invalid")
        if not config.service_id or not all((from_allowed,first_party,spf_infra,authserv_allowed)):
            return _decision("denied","delegated_policy_invalid")
        if from_domain not in from_allowed: return _decision("denied","from_domain_unapproved")
        if not evidence.records: return _decision("unsupported","authentication_results_missing")
        authserv={record.authserv_id for record in evidence.records}
        if len(authserv)>1: return _decision("ambiguous","multiple_authserv_ids")
        if not authserv.issubset(authserv_allowed): return _decision("denied","authserv_id_unapproved")

        dkim=tuple(item for record in evidence.records for item in record.dkim)
        spf=tuple(item for record in evidence.records for item in record.spf)
        if not dkim: return _decision("unsupported","dkim_missing")
        if not spf: return _decision("unsupported","spf_missing")

        first_party_pass={item.domain for item in dkim if item.result=="pass" and item.domain in first_party and _aligned(from_domain,item.domain)}
        first_party_fail={item.domain for item in dkim if item.result!="pass" and item.domain in first_party and _aligned(from_domain,item.domain)}
        if first_party_fail: return _decision("denied","first_party_dkim_failed")
        if not first_party_pass: return _decision("denied","first_party_dkim_pass_required")
        unexpected_pass={item.domain for item in dkim if item.result=="pass" and item.domain and
                         item.domain not in first_party and item.domain not in auxiliary}
        if unexpected_pass: return _decision("ambiguous","unapproved_additional_dkim_pass")

        approved_spf_pass={item.domain for item in spf if item.result=="pass" and item.domain and
                           _approved(item.domain,spf_infra,config.spf_allow_subdomains)}
        approved_spf_fail={item.domain for item in spf if item.result!="pass" and item.domain and
                           _approved(item.domain,spf_infra,config.spf_allow_subdomains)}
        if approved_spf_fail: return _decision("denied","approved_spf_infrastructure_failed")
        if not approved_spf_pass: return _decision("denied","approved_spf_infrastructure_pass_required")
        unexpected_spf_pass={item.domain for item in spf if item.result=="pass" and item.domain and
                             not _approved(item.domain,spf_infra,config.spf_allow_subdomains)}
        if unexpected_spf_pass: return _decision("ambiguous","unapproved_additional_spf_pass")
        return _decision("authorized","delegated_sender_authenticated")
