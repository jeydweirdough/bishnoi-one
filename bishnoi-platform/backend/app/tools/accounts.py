"""Bishnoi One accounts (feature plan step 4): what the move to one account per person
did, and the fixes operators make with a tool, never by editing the database (decision 9).

    uv run python -m app.tools.accounts report                 # accounts, operators, passwords that differed, people not placed
    uv run python -m app.tools.accounts suspend --email a@b.ph # stops them everywhere; their sign-ins end
    uv run python -m app.tools.accounts enable --email a@b.ph
    uv run python -m app.tools.accounts operator --email a@b.ph --on|--off

--platform-db names another database (a copy of the live one, to check first).
"""

import argparse
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.accounts import account_by_email
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Account, Company, Identity, IdentitySession, User

TOOL = "accounts tool"


def report(db) -> None:
    accounts = db.scalars(select(Account).order_by(Account.email)).all()
    operators = [a.email for a in accounts if a.is_operator]
    print(f"{len(accounts)} accounts, {sum(a.status == 'suspended' for a in accounts)} suspended; operators: {', '.join(operators) or 'none'}")
    # Where a copy of the password isn't the account's: the account kept the more recently changed one.
    differed = set()
    for a in accounts:
        copies = [m.password_hash for m in db.scalars(select(Identity).where(Identity.account_id == a.id))]
        staff = db.scalar(select(User.password_hash).where(func.lower(User.email) == a.email))
        if any(h and h != a.password_hash for h in [*copies, staff]):
            differed.add(a.email)
    print(f"Passwords that differed (the newer was kept; tell them): {', '.join(sorted(differed)) or 'none'}")
    no_password = [a.email for a in accounts if not a.password_hash]
    print(f"Without a password yet: {len(no_password)}")
    for c in db.scalars(select(Company).order_by(Company.name)):
        active = select(func.count()).select_from(Identity).where(Identity.company_id == c.id, Identity.status == "active", Identity.via_operator.is_(False))
        placed = db.scalar(active.where(Identity.main_unit_id.is_not(None)))
        print(f"  {c.name}: {db.scalar(active)} active people, {placed} placed on the org chart")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bishnoi One accounts.")
    parser.add_argument("action", choices=["report", "suspend", "enable", "operator"])
    parser.add_argument("--email")
    switch = parser.add_mutually_exclusive_group()
    switch.add_argument("--on", action="store_true")
    switch.add_argument("--off", action="store_true")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    args = parser.parse_args()

    engine = make_engine(args.platform_db or get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if args.action == "report":
            report(db)
            return 0
        account = account_by_email(db, args.email or "")
        if account is None:
            sys.exit(f"There's no account {args.email!r}.")
        if args.action in ("suspend", "enable"):
            account.status = "suspended" if args.action == "suspend" else "active"
            if args.action == "suspend":
                now = datetime.now(UTC)
                ids = select(Identity.id).where(Identity.account_id == account.id)
                for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id.in_(ids), IdentitySession.revoked_at.is_(None))):
                    s.revoked_at = now
            audit(db, TOOL, f"account.{'suspended' if args.action == 'suspend' else 'enabled'}", category="security", target=account.email, target_type="account", target_id=account.id)
        else:
            if not (args.on or args.off):
                sys.exit("Say --on or --off.")
            account.is_operator = args.on
            audit(db, TOOL, "account.operator_on" if args.on else "account.operator_off", category="security", target=account.email, target_type="account", target_id=account.id)
        db.commit()
        print(f"{account.email}: {account.status}{', operator' if account.is_operator else ''}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
