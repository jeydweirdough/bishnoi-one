"""API keys, for programs rather than people (the Orders app's scheduled jobs).

    uv run python -m app.tools.api_key add getmeds "Orders recycle-bin job" --scope orders:config
    uv run python -m app.tools.api_key list getmeds
    uv run python -m app.tools.api_key revoke getmeds <key id>

`add` prints the key once: orbit_<id>_<secret>. Put it in that program's
settings and nowhere else; only its hash is kept here.
"""

import argparse
import secrets
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db import make_engine, make_sessions
from app.models import ApiKey, Organization, utcnow
from app.routers.orders_api import CONFIG_SCOPE
from app.routers.sso import digest
from app.tenancy import set_company

SCOPES = (CONFIG_SCOPE,)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.tools.api_key", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="make a key")
    add.add_argument("company", help="the company's short name (slug), e.g. getmeds")
    add.add_argument("name", help="what it's for")
    add.add_argument("--scope", action="append", choices=SCOPES, required=True)
    listing = sub.add_parser("list", help="a company's keys")
    listing.add_argument("company")
    revoke = sub.add_parser("revoke", help="stop a key working")
    revoke.add_argument("company")
    revoke.add_argument("key_id")
    args = parser.parse_args(argv)

    with make_sessions(make_engine(get_settings().database_url))() as db:
        org = db.scalar(select(Organization).where(Organization.slug == args.company))
        if org is None:
            raise SystemExit(f"No company {args.company!r}.")
        set_company(db, org.id)
        if args.command == "list":
            for k in db.scalars(select(ApiKey).order_by(ApiKey.created_at)):
                state = "revoked" if k.revoked_at else f"last used {k.last_used_at:%Y-%m-%d}" if k.last_used_at else "never used"
                print(f"{k.id}  {k.name}  [{', '.join(k.scopes)}]  {state}")
            return 0
        if args.command == "revoke":
            key = db.get(ApiKey, args.key_id)
            if key is None:
                raise SystemExit(f"No key {args.key_id!r} in {args.company}.")
            key.revoked_at = utcnow()
            db.commit()
            print(f"{args.key_id} no longer works.")
            return 0
        key_id, secret = secrets.token_hex(8), secrets.token_urlsafe(32)
        db.add(ApiKey(id=key_id, name=args.name, secret_hash=digest(secret), scopes=sorted(set(args.scope))))
        db.commit()
    print("The key (shown once; put it in that program's settings):")
    print(f"orbit_{key_id}_{secret}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
