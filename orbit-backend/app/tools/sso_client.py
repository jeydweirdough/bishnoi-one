"""Registers the apps people sign in to through Orbit (the Orders app).

    uv run python -m app.tools.sso_client add orders --name "Orders" --redirect https://orders.example.com/sso/callback
    uv run python -m app.tools.sso_client list
    uv run python -m app.tools.sso_client revoke orders

`add` prints the app's client secret once; put it in that app's settings
(ORBIT_CLIENT_SECRET) and nowhere else. Running `add` again for the same app
replaces its addresses and gives it a new secret (the old one stops working).
"""

import argparse
import secrets
import sys
from urllib.parse import urlsplit

from app.config import get_settings
from app.db import make_engine, make_sessions
from app.models import SsoClient, utcnow
from app.routers.sso import digest
from app.scope import is_code


def checked_address(url: str, production: bool) -> str:
    parts = urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1")
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.fragment or (parts.scheme == "http" and (production or not local)):
        raise SystemExit(f"{url!r}: use a full https:// address (http:// only for localhost while developing).")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.sso_client", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="register an app, or give it new addresses and a new secret")
    add.add_argument("client_id")
    add.add_argument("--name", help="what people see, e.g. Orders")
    add.add_argument("--redirect", action="append", required=True, help="an exact address to send people back to (repeatable)")
    sub.add_parser("list", help="the registered apps")
    revoke = sub.add_parser("revoke", help="stop an app signing people in")
    revoke.add_argument("client_id")
    args = parser.parse_args(argv)

    settings = get_settings()
    with make_sessions(make_engine(settings.database_url))() as db:
        if args.command == "list":
            for c in db.query(SsoClient).order_by(SsoClient.id):
                state = "revoked" if c.revoked_at else "active"
                print(f"{c.id:12} {state:8} {c.name} -> {', '.join(c.redirect_uris)}")
            return 0
        if not is_code(args.client_id):
            raise SystemExit("The client id is a short code: lowercase letters, digits and dashes.")
        client = db.get(SsoClient, args.client_id)
        if args.command == "revoke":
            if client is None:
                raise SystemExit(f"No app {args.client_id!r}.")
            client.revoked_at = utcnow()
            db.commit()
            print(f"{args.client_id} can no longer sign people in.")
            return 0
        secret = secrets.token_urlsafe(32)
        uris = [checked_address(u, settings.is_production) for u in args.redirect]
        if client is None:
            client = SsoClient(id=args.client_id, name=args.name or args.client_id.title(), secret_hash=digest(secret), redirect_uris=uris)
            db.add(client)
        else:
            client.name = args.name or client.name
            client.secret_hash, client.redirect_uris, client.revoked_at = digest(secret), uris, None
        db.commit()
    print(f"{args.client_id} is registered. Its client secret (shown once; put it in that app's settings as ORBIT_CLIENT_SECRET):")
    print(secret)
    return 0


if __name__ == "__main__":
    sys.exit(main())
