"""One email, one account; one email domain per company (decided 2026-10-29): putting today's
accounts right, with a plan file, never by editing the database.

    uv run python -m app.tools.email_domains report                       # what doesn't fit the rules yet
    uv run python -m app.tools.email_domains run --plan plan.json         # dry run: what it would do, then the report
    uv run python -m app.tools.email_domains run --plan plan.json --apply

--platform-db names another database (a copy of the live one, to check first).

The plan file (JSON; keep it off the repository, it holds people's emails), each part optional,
done in this order:

    {"domains": {"getmeds": "getmeds.ph"},                              # each company's email domain
     "duplicates": [{"company": "getmeds", "email": "a / b", "keep": "a"}],  # a second entry for someone: suspended
     "operators": {"ai4@getmeds.ph": "ai4@bishnoione.ai"},              # the operator gets an email of their own
     "newCompanies": [{"name": "2MG", "slug": "2mg", "domain": "2mginc.com", "moveFrom": "getmeds"}],
     "emails": {"someone@gmail.com": "someone@getmeds.ph"}}           # "" = not given yet (skipped)

- operators: a new operator account with the new email takes the operator switch, the password, the
  staff record and the memberships made for the operator (so the apps keep their history under it).
  A membership a company made at a company whose domain isn't the old email's becomes the operator's
  let-in one there. The old email stays the person's at their own company.
- newCompanies: the company is made with its domain; everyone active at moveFrom whose email is at
  that domain joins it (same account: email, password, signature) and their membership at moveFrom is
  suspended, kept for what they did there. The new company has no applications until operators give
  it some, and no administrator of its own until one is made (operators administer it meanwhile).
- emails: the person's account takes the new email (their password and history stay).
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app import email_rules
from app.accounts import account_by_email, memberships
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Account, Company, Identity, IdentitySession, User

TOOL = "email domains tool"


class Stop(Exception):
    pass


def company_by_slug(db, slug: str) -> Company:
    c = db.scalar(select(Company).where(Company.slug == slug))
    if c is None:
        raise Stop(f"No company {slug!r}.")
    return c


def end_sessions(db, membership_ids: list[str], now: datetime) -> None:
    for s in db.scalars(select(IdentitySession).where(IdentitySession.identity_id.in_(membership_ids), IdentitySession.revoked_at.is_(None))):
        s.revoked_at = now


def set_domains(db, domains: dict[str, str]) -> None:
    for slug, domain in domains.items():
        c = company_by_slug(db, slug)
        try:
            value = email_rules.check_domain(db, c, domain)
        except Exception as e:  # field_error: its message
            raise Stop(f"{c.name}: {getattr(e, 'detail', e)}") from None
        if c.email_domain != value:
            print(f"  {c.name}: email domain {c.email_domain or '(none)'} -> {value}")
            c.email_domain = value
            audit(db, TOOL, "company.updated", target=c.name, target_type="company", target_id=c.id, company_id=c.id, fields=["emailDomain"])
    db.flush()


def duplicates(db, entries: list[dict], now: datetime) -> None:
    for d in entries:
        c = company_by_slug(db, d["company"])
        row = db.scalar(select(Identity).where(Identity.company_id == c.id, Identity.email == d["email"]))
        keep = db.scalar(select(Identity).where(Identity.company_id == c.id, func.lower(Identity.email) == d["keep"].lower()))
        if row is None:
            print(f"  {c.name}: no entry {d['email']!r} (already fixed?)")
            continue
        if keep is None:
            raise Stop(f"{c.name}: {d['keep']} isn't there, so {d['email']!r} can't be put down as its duplicate.")
        if row.status != "suspended":
            print(f"  {c.name}: {row.full_name} <{row.email}> suspended: a second entry for {keep.full_name} <{keep.email}>")
            row.status = "suspended"
            end_sessions(db, [row.id], now)
            audit(db, TOOL, "user.suspended", category="security", target=row.email, target_type="user", target_id=row.id, company_id=c.id,
                  fields=[f"a second entry for {keep.email}"])
        account = db.get(Account, row.account_id) if row.account_id else None
        if account is not None and account.id != keep.account_id and account.status != "suspended" and \
                not any(m.status == "active" for m in memberships(db, account)):
            account.status = "suspended"
    db.flush()


def split_operators(db, moves: dict[str, str], now: datetime) -> None:
    for old_email, new_email in moves.items():
        if not new_email:
            print(f"  operator {old_email}: no new email given yet, skipped")
            continue
        old = account_by_email(db, old_email)
        if old is None:
            if (new := account_by_email(db, new_email)) is not None and new.is_operator:
                print(f"  operator {old_email}: already {new_email}")
                continue
            raise Stop(f"No account {old_email}.")
        if not old.is_operator:
            if (new := account_by_email(db, new_email)) is not None and new.is_operator:
                print(f"  operator {old_email}: already {new_email}")
                continue
            raise Stop(f"{old_email} isn't an operator.")
        if account_by_email(db, new_email) is not None:
            raise Stop(f"{new_email} is already someone's account: pick another for {old_email}'s operator.")
        home_domain = email_rules.domain_of(old.email)
        stays = [m for m in memberships(db, old) if not m.via_operator and db.get(Company, m.company_id).email_domain in (None, home_domain)]
        if not stays:
            # Nobody's person at any company: the operator's account simply takes the new email.
            rows = memberships(db, old)
            old_email_was = old.email
            old.email = new_email.lower()
            db.flush()
            for m in rows:
                m.email, m.via_operator, m.is_company_admin = old.email, True, m.is_company_admin and m.via_operator
            staff = db.scalar(select(User).where(func.lower(User.email) == old_email_was.lower()))
            if staff is not None:
                staff.email = old.email
            audit(db, TOOL, "operator.separated", category="security", target=old.email, target_type="account", target_id=old.id, fields=[f"was {old_email_was}"])
            print(f"  operator {old_email_was} -> {old.email}: the same account (nobody's person at a company)")
            db.flush()
            continue
        new = Account(email=new_email.lower(), full_name=old.full_name, password_hash=old.password_hash,
                      password_changed_at=old.password_changed_at, is_operator=True, last_sign_in_at=old.last_sign_in_at)
        db.add(new)
        old.is_operator = False
        db.flush()
        staff = db.scalar(select(User).where(func.lower(User.email) == old.email.lower()))
        if staff is not None:
            staff.email = new.email  # the console's history and audit point at it: it goes with the operator
        moved = []
        for m in memberships(db, old):
            company = db.get(Company, m.company_id)
            # The person's own, at their company (or one without a domain yet): stays with the old email.
            if not m.via_operator and company.email_domain in (None, home_domain):
                continue
            note = "let-in" if m.via_operator else f"made by {company.name} (now the operator's let-in one; it was{'' if m.is_company_admin else ' not'} its administrator)"
            moved.append(f"{company.name} [{note}]")
            m.account_id, m.email, m.via_operator, m.is_company_admin = new.id, new.email, True, False
            end_sessions(db, [m.id], now)
        audit(db, TOOL, "operator.separated", category="security", target=new.email, target_type="account", target_id=new.id, fields=[f"was {old.email}"])
        print(f"  operator {old.email} -> {new.email} (same password); moved: {', '.join(moved) or 'nothing'}; {old.email} stays a person")
        db.flush()


def new_companies(db, entries: list[dict], now: datetime) -> None:
    for d in entries:
        source = company_by_slug(db, d["moveFrom"])
        c = db.scalar(select(Company).where(Company.slug == d["slug"]))
        if c is None:
            c = Company(name=d["name"], slug=d["slug"], currency=source.currency, timezone=source.timezone)
            db.add(c)
            db.flush()
            audit(db, TOOL, "company.created", target=c.name, target_type="company", target_id=c.id, company_id=c.id)
            print(f"  company {c.name} ({c.slug}) made")
        c.email_domain = email_rules.check_domain(db, c, d["domain"])
        admins = {e.lower() for e in d.get("admins", [])}
        for p in db.scalars(select(Identity).where(Identity.company_id == source.id, Identity.status == "active", Identity.via_operator.is_(False))
                            .order_by(Identity.full_name)).all():
            if email_rules.domain_of(p.email) != c.email_domain:
                continue
            there = db.scalar(select(Identity).where(Identity.company_id == c.id, func.lower(Identity.email) == p.email.lower()))
            if there is None:
                there = Identity(company_id=c.id, account_id=p.account_id, full_name=p.full_name, email=p.email, title=p.title,
                                 is_company_admin=p.email.lower() in admins, password_hash=p.password_hash, password_changed_at=p.password_changed_at)
                db.add(there)
                db.flush()
                audit(db, TOOL, "user.created", target=there.email, target_type="user", target_id=there.id, company_id=c.id, fields=[f"moved from {source.name}"])
            p.status = "suspended"
            end_sessions(db, [p.id], now)
            audit(db, TOOL, "user.suspended", category="security", target=p.email, target_type="user", target_id=p.id, company_id=source.id,
                  fields=[f"moved to {c.name}"])
            print(f"  {p.full_name} <{p.email}>: {source.name} -> {c.name}")
        db.flush()


def change_emails(db, emails: dict[str, str]) -> None:
    for old, new in emails.items():
        if not new:
            print(f"  {old}: no new email given yet, skipped (can't sign in until it's changed)")
            continue
        rows = [m for m in db.scalars(select(Identity).where(func.lower(Identity.email) == old.lower(), Identity.via_operator.is_(False),
                                                              Identity.status == "active"))]
        if not rows:
            if account_by_email(db, new) is not None:
                print(f"  {old}: already {new}")
                continue
            raise Stop(f"Nobody active has {old}.")
        if len(rows) > 1:
            raise Stop(f"{old} is at {len(rows)} companies: separate them first.")
        p = rows[0]
        company = db.get(Company, p.company_id)
        try:
            email_rules.check_company_email(company, new)
            email_rules.check_available(db, new, company.id, but_account=p.account_id)
        except Exception as e:
            detail = getattr(e, "detail", e)
            raise Stop(f"{old} -> {new}: {detail[0]['msg'] if isinstance(detail, list) else detail}") from None
        email_rules.change_email(db, p, new)
        audit(db, TOOL, "access.email_changed", category="security", target=new, target_type="identity", target_id=p.id, company_id=company.id,
              fields=["email"])
        print(f"  {p.full_name} ({company.name}): {old} -> {new}")


def report(db) -> int:
    """What doesn't fit the rules yet. Returns how many."""
    left = 0
    print("Companies:")
    for c in db.scalars(select(Company).order_by(Company.name)):
        print(f"  {c.name} ({c.slug}): {c.email_domain or 'no email domain set'}")
    print("Not at their company's domain (can't sign in until changed):")
    for p, c in db.execute(select(Identity, Company).join(Company, Company.id == Identity.company_id)
                           .where(Identity.status == "active", Identity.via_operator.is_(False)).order_by(Company.name, Identity.full_name)):
        if c.email_domain and email_rules.domain_of(p.email) != c.email_domain:
            print(f"  {c.name}: {p.full_name} <{p.email}>")
            left += 1
    print("One email at more than one company, or an operator who is also a company's person:")
    for a in db.scalars(select(Account).order_by(Account.email)):
        own = [m for m in memberships(db, a) if not m.via_operator and m.status == "active"]
        if len(own) > 1 or (a.is_operator and own):
            names = ", ".join(db.get(Company, m.company_id).name for m in own)
            print(f"  {a.email}: {'operator; ' if a.is_operator else ''}{names}")
            left += 1
    print(f"{left} left to put right." if left else "Everything fits the rules.")
    return left


def run(db, plan: dict) -> None:
    now = datetime.now(UTC)
    print("Email domains:")
    set_domains(db, plan.get("domains", {}))
    print("Second entries:")
    duplicates(db, plan.get("duplicates", []), now)
    print("Operators:")
    split_operators(db, plan.get("operators", {}), now)
    print("New companies:")
    new_companies(db, plan.get("newCompanies", []), now)
    print("Emails:")
    change_emails(db, plan.get("emails", {}))
    db.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="One email, one account; one email domain per company.")
    parser.add_argument("action", choices=["report", "run"])
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--apply", action="store_true", help="save the changes (without it, a dry run)")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    args = parser.parse_args()

    engine = make_engine(args.platform_db or get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        if args.action == "report":
            report(db)
            return 0
        if args.plan is None:
            parser.error("run needs --plan")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        try:
            run(db, plan)
        except Stop as e:
            db.rollback()
            print(f"Stopped, nothing saved: {e}", file=sys.stderr)
            return 1
        print()
        report(db)
        if args.apply:
            db.commit()
            print("Saved.")
        else:
            db.rollback()
            print("Dry run: nothing saved. Add --apply to save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
