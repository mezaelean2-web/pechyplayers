"""Transporte IMAP TLS read-only para Namecheap; la red solo abre al invocar operaciones."""

import email
import imaplib
import re
import socket
import ssl
import time
from contextlib import contextmanager
from datetime import datetime

from private_email_provider import (IMAPTransport,ProviderAuthenticationFailed,
    ProviderConfigurationError,ProviderMessageMalformed,ProviderProtocolError,
    ProviderTimeout,ProviderUnavailable,ProviderTLSFailed)

HOST="mail.privateemail.com"
PORT=993
FOLDER="INBOX"
_FETCH_RE=re.compile(rb"UID\s+(\d+).*INTERNALDATE\s+\"([^\"]+)\".*RFC822\.SIZE\s+(\d+)",re.I)
_UID_RE=re.compile(rb"\bUID\s+(\d+)\b",re.I)
_UID_INTERNALDATE_RE=re.compile(rb"\bUID\s+(\d+)\b.*\bINTERNALDATE\s+\"([^\"]+)\"",re.I)
RECIPIENT_ROUTING_HEADERS=("TO","CC","DELIVERED-TO","X-ORIGINAL-TO","ENVELOPE-TO")

class PrivateEmailIMAPTransport(IMAPTransport):
    def __init__(self,credential_resolver,*,connect_timeout=10,operation_timeout=15,
                 client_factory=imaplib.IMAP4_SSL,ssl_context_factory=ssl.create_default_context,
                 clock=time.monotonic):
        if credential_resolver is None: raise ProviderConfigurationError()
        self.credentials=credential_resolver; self.connect_timeout=max(1,min(int(connect_timeout),30))
        self.operation_timeout=max(1,min(int(operation_timeout),60)); self.client_factory=client_factory
        self.ssl_context_factory=ssl_context_factory; self.clock=clock; self._auth_blocked_until={}

    @contextmanager
    def _session(self,config_id):
        if self._auth_blocked_until.get(config_id,0)>self.clock(): raise ProviderAuthenticationFailed()
        creds=self.credentials.resolve(config_id); client=None
        try:
            context=self.ssl_context_factory()
            if context.check_hostname is not True or context.verify_mode!=ssl.CERT_REQUIRED:
                raise ProviderConfigurationError()
            client=self.client_factory(HOST,PORT,ssl_context=context,timeout=self.connect_timeout)
            try: typ,_=client.login(creds.username,creds.password)
            except imaplib.IMAP4.error as exc:
                self._auth_blocked_until[config_id]=self.clock()+30
                raise ProviderAuthenticationFailed() from exc
            if typ!="OK": raise ProviderAuthenticationFailed()
            sock=getattr(client,"sock",None)
            if sock is not None and hasattr(sock,"settimeout"): sock.settimeout(self.operation_timeout)
            yield client
        except ProviderAuthenticationFailed: raise
        except (socket.timeout,TimeoutError) as exc: raise ProviderTimeout() from exc
        except ssl.SSLError as exc: raise ProviderTLSFailed() from exc
        except (OSError,imaplib.IMAP4.abort) as exc: raise ProviderUnavailable() from exc
        except (ProviderConfigurationError,ProviderProtocolError,ProviderMessageMalformed): raise
        except Exception as exc: raise ProviderProtocolError() from exc
        finally:
            if client is not None:
                try: client.logout()
                except Exception:
                    try:
                        shutdown=getattr(client,"shutdown",None)
                        if shutdown: shutdown()
                    except Exception: pass

    @staticmethod
    def _positive(value):
        try: number=int(value)
        except (TypeError,ValueError) as exc: raise ProviderProtocolError() from exc
        if number<=0: raise ProviderProtocolError()
        return number

    @classmethod
    def _response_number(cls,client,name):
        response=client.response(name)
        if not response or not response[1] or response[1][0] is None: raise ProviderProtocolError()
        raw=response[1][0]; return cls._positive(raw.decode() if isinstance(raw,bytes) else raw)

    @staticmethod
    def _examine(client,folder):
        if folder!=FOLDER: raise ProviderConfigurationError()
        typ,_=client.select(folder,readonly=True)
        if typ!="OK": raise ProviderProtocolError()

    def examine(self,provider_config_id,folder_key):
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key)
            return {"uidvalidity":self._response_number(client,"UIDVALIDITY"),
                    "uidnext":self._response_number(client,"UIDNEXT")}

    def search_uids(self,provider_config_id,folder_key,minimum_uid,limit):
        minimum=self._positive(minimum_uid); limit=max(1,min(int(limit),50))
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key)
            typ,data=client.uid("SEARCH",None,f"UID {minimum}:*")
            if typ!="OK" or not isinstance(data,list): raise ProviderProtocolError()
            values=[]
            for token in (data[0] or b"").split():
                uid=self._positive(token); values.append(uid) if uid>=minimum else None
            # El servidor puede devolver una ventana grande; conservar los UIDs más altos
            # garantiza "latest valid" dentro del hard cap sin ampliar el FETCH.
            return sorted(set(values))[-limit:]

    def fetch_metadata(self,provider_config_id,folder_key,uid):
        uid=self._positive(uid)
        query="(UID INTERNALDATE RFC822.SIZE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT AUTHENTICATION-RESULTS CONTENT-TYPE CONTENT-TRANSFER-ENCODING)])"
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),query)
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2: raise ProviderMessageMalformed()
            attrs,headers=data[0]; match=_FETCH_RE.search(attrs)
            if not match or self._positive(match.group(1))!=uid: raise ProviderMessageMalformed()
            try: internal=datetime.strptime(match.group(2).decode(),"%d-%b-%Y %H:%M:%S %z")
            except Exception as exc: raise ProviderMessageMalformed() from exc
            parsed=email.message_from_bytes(headers)
            return {"uid":uid,"internaldate":internal,"size":self._positive(match.group(3)),
                "from":parsed.get("From",""),"to":parsed.get("To",""),"subject":parsed.get("Subject",""),
                "authentication_results":parsed.get("Authentication-Results",""),
                "content_type":parsed.get("Content-Type","text/plain"),
                "content_transfer_encoding":parsed.get("Content-Transfer-Encoding",""),
                "body_part":"TEXT"}

    def fetch_body_peek(self,provider_config_id,folder_key,uid,part):
        uid=self._positive(uid)
        if not re.fullmatch(r"(?:TEXT|\d+(?:\.\d+)*)",str(part)): raise ProviderConfigurationError()
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),f"(BODY.PEEK[{part}])")
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2: raise ProviderMessageMalformed()
            return bytes(data[0][1])

    def fetch_recipient_routing_headers(self,provider_config_id,folder_key,uid):
        """Fetch diagnóstico de un UID; no se usa en la política productiva."""
        uid=self._positive(uid)
        fields=" ".join(RECIPIENT_ROUTING_HEADERS)
        query=f"(UID BODY.PEEK[HEADER.FIELDS ({fields})])"
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),query)
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2:
                raise ProviderMessageMalformed()
            attrs,headers=data[0]
            match=_UID_RE.search(attrs)
            if not match or self._positive(match.group(1))!=uid: raise ProviderMessageMalformed()
            if not isinstance(headers,(bytes,bytearray)) or len(headers)>16384:
                raise ProviderMessageMalformed()
            parsed=email.message_from_bytes(bytes(headers))
            result={}
            for header in RECIPIENT_ROUTING_HEADERS:
                values=parsed.get_all(header,[])
                result[header.lower().replace("-","_")]=", ".join(str(value) for value in values)
            return result

    def fetch_sender_auth_headers(self,provider_config_id,folder_key,uid):
        """Fetch diagnóstico de identidad/auth de un UID; nunca obtiene contenido."""
        uid=self._positive(uid)
        query="(UID BODY.PEEK[HEADER.FIELDS (FROM AUTHENTICATION-RESULTS)])"
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),query)
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2:
                raise ProviderMessageMalformed()
            attrs,headers=data[0]; match=_UID_RE.search(attrs)
            if not match or self._positive(match.group(1))!=uid: raise ProviderMessageMalformed()
            if not isinstance(headers,(bytes,bytearray)) or len(headers)>49152:
                raise ProviderMessageMalformed()
            parsed=email.message_from_bytes(bytes(headers))
            return {"from":tuple(str(value) for value in parsed.get_all("From",[])),
                    "authentication_results":tuple(str(value) for value in
                                                   parsed.get_all("Authentication-Results",[]))}

    def fetch_from_header(self,provider_config_id,folder_key,uid):
        """Fetch count-only de identidad remitente; no solicita contenido ni otros headers."""
        uid=self._positive(uid)
        query="(UID BODY.PEEK[HEADER.FIELDS (FROM)])"
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),query)
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2:
                raise ProviderMessageMalformed()
            attrs,headers=data[0]; match=_UID_RE.search(attrs)
            if not match or self._positive(match.group(1))!=uid: raise ProviderMessageMalformed()
            if not isinstance(headers,(bytes,bytearray)) or len(headers)>4096:
                raise ProviderMessageMalformed()
            parsed=email.message_from_bytes(bytes(headers))
            values=tuple(str(value) for value in parsed.get_all("From",[]))
            if len(values)!=1: raise ProviderMessageMalformed()
            return values[0]

    def fetch_disambiguation_metadata(self,provider_config_id,folder_key,uid):
        """Metadata mínima para desambiguar UIDs; no solicita body, recipients ni auth."""
        uid=self._positive(uid)
        query="(UID INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])"
        with self._session(provider_config_id) as client:
            self._examine(client,folder_key); typ,data=client.uid("FETCH",str(uid),query)
            if typ!="OK" or not data or not isinstance(data[0],tuple) or len(data[0])!=2:
                raise ProviderMessageMalformed()
            attrs,headers=data[0]; match=_UID_INTERNALDATE_RE.search(attrs)
            if not match or self._positive(match.group(1))!=uid: raise ProviderMessageMalformed()
            if not isinstance(headers,(bytes,bytearray)) or len(headers)>8192:
                raise ProviderMessageMalformed()
            try: internal=datetime.strptime(match.group(2).decode(),"%d-%b-%Y %H:%M:%S %z")
            except Exception as exc: raise ProviderMessageMalformed() from exc
            parsed=email.message_from_bytes(bytes(headers))
            return {"uid":uid,"internaldate":internal,"from":tuple(str(value) for value in
                    parsed.get_all("From",[])),"subject":tuple(str(value) for value in
                    parsed.get_all("Subject",[])),"date":tuple(str(value) for value in
                    parsed.get_all("Date",[]))}
