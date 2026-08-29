"""Parsing MIME limitado y adapters allowlisted; nunca renderiza HTML."""

import re
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

from private_email_provider import ProviderMessageMalformed, ProviderMessageTooLarge

KINDS=frozenset({"numeric_code","alphanumeric_code","action_link","approval_action",
                 "device_notice","instructions","unsupported"})

@dataclass(frozen=True)
class ParsedMessage:
    service: str
    kind: str
    value: str
    safe_reason: str = ""
    status: str = ""

@dataclass(frozen=True)
class DecodedMessage:
    text: str
    anchors: tuple

class _TextOnly(HTMLParser):
    def __init__(self,*,max_anchors=50):
        super().__init__(convert_charrefs=True); self.parts=[]; self.anchors=[]
        self._anchor=None; self._skip=0; self.max_anchors=max_anchors
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag in {"script","style"}: self._skip+=1; return
        if tag=="a" and not self._skip:
            href=next((value for key,value in attrs if key.lower()=="href"),None)
            self._anchor={"href":href,"text":[]}
    def handle_endtag(self,tag):
        tag=tag.lower()
        if tag in {"script","style"} and self._skip: self._skip-=1; return
        if tag=="a" and self._anchor is not None:
            if len(self.anchors)>=self.max_anchors: raise ValueError("too_many_anchors")
            text=" ".join(self._anchor["text"])[:512]
            href=self._anchor["href"]
            if href is not None and len(str(href))>2048: raise ValueError("href_too_large")
            self.anchors.append((text,str(href) if href is not None else "")); self._anchor=None
    def handle_data(self,data):
        if self._skip:return
        self.parts.append(data)
        if self._anchor is not None:self._anchor["text"].append(data)

class ServiceAdapter:
    service="Unknown"
    def parse(self, metadata, text): return ParsedMessage(self.service,"unsupported","")
    def parse_decoded(self,metadata,decoded): return self.parse(metadata,decoded.text)

class CodeServiceAdapter(ServiceAdapter):
    def __init__(self, service, *, senders, recipients, subject_tokens,
                 require_authentication=True, allowed_link_hosts=()):
        self.service=service; self.senders={x.lower() for x in senders}; self.recipients={x.lower() for x in recipients}
        self.subject_tokens=tuple(x.lower() for x in subject_tokens); self.require_authentication=require_authentication
    def parse(self, metadata, text):
        sender=str(metadata.get("from","")).strip().lower(); recipient=str(metadata.get("to","")).strip().lower()
        subject=str(metadata.get("subject","")).lower(); auth=str(metadata.get("authentication_results","")).lower()
        if sender not in self.senders or recipient not in self.recipients: return ParsedMessage(self.service,"unsupported","")
        if self.require_authentication and not ("dkim=pass" in auth and "spf=pass" in auth): return ParsedMessage(self.service,"unsupported","")
        if not any(token in subject for token in self.subject_tokens): return ParsedMessage(self.service,"unsupported","")
        codes=set(re.findall(r"(?<![A-Za-z0-9])([0-9]{6})(?![A-Za-z0-9])",text))
        if len(codes)!=1: return ParsedMessage(self.service,"unsupported","")
        return ParsedMessage(self.service,"numeric_code",next(iter(codes)))

class ServiceAdapterRegistry:
    def __init__(self, adapters=(), *, max_message_bytes=131072, max_parts=20, max_depth=5):
        self.adapters=list(adapters); self.max_message_bytes=max_message_bytes
        self.max_parts=max_parts; self.max_depth=max_depth

    def _decode(self, raw):
        if not isinstance(raw,(bytes,bytearray)) or not raw: raise ProviderMessageMalformed()
        if len(raw)>self.max_message_bytes: raise ProviderMessageTooLarge()
        try: message=BytesParser(policy=policy.default).parsebytes(bytes(raw))
        except Exception as exc: raise ProviderMessageMalformed() from exc
        parts=[]; anchors=[]; count=0
        def walk(node,depth=0):
            nonlocal count
            if depth>self.max_depth: raise ProviderMessageMalformed()
            count+=1
            if count>self.max_parts: raise ProviderMessageMalformed()
            if node.is_multipart():
                for child in node.iter_parts(): walk(child,depth+1)
                return
            if node.get_content_disposition()=="attachment": return
            kind=node.get_content_type()
            if kind not in {"text/plain","text/html"}: return
            try: value=node.get_content()
            except (LookupError,UnicodeError) as exc: raise ProviderMessageMalformed() from exc
            if kind=="text/html":
                try:
                    parser=_TextOnly(); parser.feed(value); parser.close()
                except (ValueError,AssertionError) as exc: raise ProviderMessageMalformed() from exc
                anchors.extend(parser.anchors); value=" ".join(parser.parts)
            parts.append(value)
        walk(message)
        text="\n".join(parts)[:self.max_message_bytes] if parts else ""
        return DecodedMessage(text,tuple(anchors))

    def classify(self, metadata, body_loader, *, requested_at):
        size=int(metadata.get("size",0) or 0)
        if size<=0: raise ProviderMessageMalformed()
        if size>self.max_message_bytes: raise ProviderMessageTooLarge()
        internaldate=metadata.get("internaldate")
        if internaldate is None or internaldate.tzinfo is None: raise ProviderMessageMalformed()
        # INTERNALDATE es defensa secundaria; el UID boundary sigue siendo autoridad primaria.
        if requested_at is not None and internaldate < requested_at:
            return ParsedMessage("Unknown","unsupported","")
        raw=body_loader(metadata.get("body_part","TEXT"))
        decoded=self._decode(raw)
        matches=[]; results=[]
        for adapter in self.adapters:
            result=adapter.parse_decoded(metadata,decoded)
            results.append(result)
            if result.kind!="unsupported": matches.append(result)
        if len(matches)!=1 or matches[0].kind not in KINDS:
            if not matches and len(results)==1:return results[0]
            return ParsedMessage("Unknown","unsupported","")
        return matches[0]
