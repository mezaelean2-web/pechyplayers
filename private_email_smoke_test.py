"""Smoke test administrativo read-only. NO ejecutarlo sin autorización humana."""

import argparse

from private_email_credentials import ProviderCredentialResolver
from private_email_imap_transport import PrivateEmailIMAPTransport

def run_smoke_test(config_id,*,transport=None):
    result={"connection":"failed","authentication":"failed","folder":"failed",
            "uidvalidity_present":"no","uidnext_present":"no"}
    transport=transport or PrivateEmailIMAPTransport(ProviderCredentialResolver())
    try:
        state=transport.examine(config_id,"INBOX")
        result.update(connection="ok",authentication="ok",folder="ok",
            uidvalidity_present="yes" if state.get("uidvalidity") else "no",
            uidnext_present="yes" if state.get("uidnext") else "no")
    except Exception:
        pass
    return result

def main(argv=None):
    parser=argparse.ArgumentParser(description="Private Email read-only smoke test")
    parser.add_argument("--config-id",required=True)
    args=parser.parse_args(argv)
    for key,value in run_smoke_test(args.config_id).items(): print(f"{key}: {value}")

if __name__=="__main__": main()
