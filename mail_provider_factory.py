"""Feature flag de proveedor; fake es el único modo operativo por defecto en 5B.1."""

import os

from mail_providers import FakeMailProvider
from private_email_provider import PrivateEmailMailProvider, ProviderConfigurationError
from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport

def provider_mode(environ=None):
    value=(environ or os.environ).get("MAIL_PROVIDER_MODE","fake").strip().lower()
    if value not in {"fake","private_email"}: raise ProviderConfigurationError()
    return value

def build_mail_provider(*, environ=None, transport=None, parser_registry=None,
                        credential_resolver=None, transport_factory=PrivateEmailIMAPTransport):
    mode=provider_mode(environ)
    if mode=="fake": return FakeMailProvider()
    if parser_registry is None: raise ProviderConfigurationError()
    if transport is None:
        resolver=credential_resolver or ProviderCredentialResolver(environ=environ)
        # Valida que exista una fuente, sin resolver username/password ni abrir red.
        if not getattr(resolver,"_configs",None): raise ProviderConfigurationError()
        transport=transport_factory(resolver)
    return PrivateEmailMailProvider(transport,parser_registry)
