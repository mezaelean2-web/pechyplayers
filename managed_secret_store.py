"""SecretStore portable con AES-256-GCM y master key externa al SQLite."""

import base64
import json
import os
import secrets
from abc import ABC, abstractmethod

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import database

MASTER_KEY_ENV = "PECHY_MAIL_SECRET_MASTER_KEY"
REFERENCE_PREFIX = "ms1_"

class SecretStoreError(Exception): safe_code = "secret_store_unavailable"
class SecretNotFound(SecretStoreError): safe_code = "secret_not_found"

class SecretStore(ABC):
    @abstractmethod
    def put(self, secret, *, connection=None): raise NotImplementedError
    @abstractmethod
    def get(self, reference, *, connection=None): raise NotImplementedError
    @abstractmethod
    def replace(self, reference, secret, *, connection=None): raise NotImplementedError
    @abstractmethod
    def delete(self, reference, *, connection=None): raise NotImplementedError

def _master_key(value):
    raw = str(value or "").strip()
    try: decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
    except (ValueError, UnicodeError) as exc: raise SecretStoreError() from exc
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).decode("ascii") != raw:
        raise SecretStoreError()
    return decoded

def generate_master_key():
    """Solo para setup/test explícito; el producto nunca la persiste automáticamente."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

def initialize_schema(connection=None):
    own = connection is None; conn = connection or database.conectar()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS managed_mail_secrets (
            secret_ref TEXT PRIMARY KEY,
            cipher_version INTEGER NOT NULL CHECK(cipher_version=1),
            nonce BLOB NOT NULL CHECK(length(nonce)=12),
            ciphertext BLOB NOT NULL CHECK(length(ciphertext)>16),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)
        if own: conn.commit()
    finally:
        if own: conn.close()

class SQLiteEncryptedSecretStore(SecretStore):
    def __init__(self, master_key, *, connect=None):
        self._aead = AESGCM(_master_key(master_key)); self._connect = connect or database.conectar

    @classmethod
    def from_environment(cls, environ=None, *, connect=None):
        source = os.environ if environ is None else environ
        return cls(source.get(MASTER_KEY_ENV), connect=connect)

    @staticmethod
    def _secret(value):
        if not isinstance(value, dict) or set(value) != {"username", "password"}: raise SecretStoreError()
        username = str(value.get("username") or "").strip(); password = str(value.get("password") or "")
        if not username or "@" not in username or len(username)>254 or not password or len(password)>1024:
            raise SecretStoreError()
        return json.dumps({"username":username,"password":password},sort_keys=True,
                          separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _reference(value):
        value = str(value or "")
        if not value.startswith(REFERENCE_PREFIX) or len(value)<32 or len(value)>80: raise SecretNotFound()
        return value

    def _encrypt(self, reference, secret):
        nonce=os.urandom(12); aad=f"pechy-mail-secret|1|{reference}".encode("ascii")
        return nonce,self._aead.encrypt(nonce,self._secret(secret),aad)

    def put(self, secret, *, connection=None):
        own=connection is None; conn=connection or self._connect()
        try:
            if own: initialize_schema(conn)
            reference=REFERENCE_PREFIX+secrets.token_urlsafe(24)
            nonce,ciphertext=self._encrypt(reference,secret)
            conn.execute("INSERT INTO managed_mail_secrets(secret_ref,cipher_version,nonce,ciphertext) VALUES(?,1,?,?)",
                         (reference,nonce,ciphertext))
            if own: conn.commit()
            return reference
        except SecretStoreError:
            if own: conn.rollback()
            raise
        except Exception as exc:
            if own: conn.rollback()
            raise SecretStoreError() from exc
        finally:
            if own: conn.close()

    def get(self, reference, *, connection=None):
        reference=self._reference(reference); own=connection is None; conn=connection or self._connect()
        try:
            row=conn.execute("SELECT cipher_version,nonce,ciphertext FROM managed_mail_secrets WHERE secret_ref=?",
                             (reference,)).fetchone()
            if not row or int(row[0])!=1: raise SecretNotFound()
            aad=f"pechy-mail-secret|1|{reference}".encode("ascii")
            try: value=json.loads(self._aead.decrypt(bytes(row[1]),bytes(row[2]),aad).decode("utf-8"))
            except (InvalidTag,UnicodeError,ValueError,TypeError,json.JSONDecodeError) as exc:
                raise SecretStoreError() from exc
            self._secret(value); return value
        finally:
            if own: conn.close()

    def replace(self, reference, secret, *, connection=None):
        reference=self._reference(reference); own=connection is None; conn=connection or self._connect()
        try:
            nonce,ciphertext=self._encrypt(reference,secret)
            if conn.execute("UPDATE managed_mail_secrets SET nonce=?,ciphertext=?,updated_at=CURRENT_TIMESTAMP WHERE secret_ref=?",
                            (nonce,ciphertext,reference)).rowcount!=1: raise SecretNotFound()
            if own: conn.commit()
        except SecretStoreError:
            if own: conn.rollback()
            raise
        except Exception as exc:
            if own: conn.rollback()
            raise SecretStoreError() from exc
        finally:
            if own: conn.close()

    def delete(self, reference, *, connection=None):
        reference=self._reference(reference); own=connection is None; conn=connection or self._connect()
        try:
            if conn.execute("DELETE FROM managed_mail_secrets WHERE secret_ref=?",(reference,)).rowcount!=1:
                raise SecretNotFound()
            if own: conn.commit()
        except SecretStoreError:
            if own: conn.rollback()
            raise
        finally:
            if own: conn.close()
