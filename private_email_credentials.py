"""Resolución interna de credenciales desde un bundle secreto estructurado."""

import json
import os

from private_email_provider import ProviderConfigurationError


class ProviderCredentials:
    __slots__=("username","password")
    def __init__(self,username,password):
        username=str(username or "").strip(); password=str(password or "")
        if not username or "@" not in username or not password: raise ProviderConfigurationError()
        self.username=username; self.password=password
    def __repr__(self): return "ProviderCredentials(username=<redacted>, password=<redacted>)"
    def __str__(self): return "ProviderCredentials(<redacted>)"
    def __reduce__(self): raise TypeError("ProviderCredentials is not serializable")


class ProviderCredentialResolver:
    def __init__(self,bundle=None,*,environ=None):
        raw=bundle if bundle is not None else (environ or os.environ).get("PRIVATE_EMAIL_CREDENTIALS_BUNDLE")
        if not raw: self._configs={}; return
        try: data=json.loads(raw) if isinstance(raw,str) else raw
        except Exception as exc: raise ProviderConfigurationError() from exc
        if not isinstance(data,dict): raise ProviderConfigurationError()
        self._configs=data
    def resolve(self,provider_config_id):
        key=str(provider_config_id or "").strip(); item=self._configs.get(key)
        if not key or not isinstance(item,dict) or set(item)!={"username","password"}:
            raise ProviderConfigurationError()
        return ProviderCredentials(item["username"],item["password"])
    def __repr__(self): return "ProviderCredentialResolver(configs=<redacted>)"
