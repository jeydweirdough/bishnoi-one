"""Registers a company's CRM people on the platform, once: each CRM account
becomes a platform user at that company, given the CRM with their CRM role.
Someone already there (the same email at that company) keeps their record and
is given the CRM if they didn't have it. Nobody is changed or removed.

    uv run python -m app.tools.import_crm_people --company getmeds \\
        --crm-db "sqlite:///../../bishnoi-crm/backend/.data/crm-getmeds.db" [--dry-run]

--crm-db is that company's CRM database (on Neon: the CRM project's pooled
address with the company's database, …/neondb_getmeds). The platform written
to is this app's DATABASE_URL, or --platform-db to name another (the online
one). Accounts at .test addresses (the demo accounts) are left out unless
--with-test-accounts. No passwords are copied: each person keeps signing in
to the CRM as before, or is given a Bishnoi One password under Users.
"""

import argparse
import sys

from sqlalchemy import func, select, text

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Application, Company, CompanyApp, Identity, IdentityApp

TOOL = "import tool"


def crm_people(url: str) -> list[dict]:
    """The CRM's accounts: email, name, role, and whether they're switched on."""
    with make_engine(url).connect() as c:
        rows = c.execute(text(
            "select u.email, u.full_name, u.is_active, r.name from nbcm_users u join nbcm_roles r on r.id = u.role_id order by lower(u.full_name)"
        )).all()
    return [{"email": e.strip().lower(), "name": n, "active": bool(a), "role": r} for e, n, a, r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a company's CRM people on the platform.")
    parser.add_argument("--company", required=True, help="the company's short name on the platform, e.g. getmeds")
    parser.add_argument("--crm-db", required=True, help="that company's CRM database address")
    parser.add_argument("--platform-db", help="the platform database to write to (default: DATABASE_URL)")
    parser.add_argument("--with-test-accounts", action="store_true", help="include .test addresses (the demo accounts)")
    parser.add_argument("--dry-run", action="store_true", help="say what would be done, change nothing")
    args = parser.parse_args()

    people = crm_people(args.crm_db)
    if not args.with_test_accounts:
        people = [p for p in people if not p["email"].endswith(".test")]
    engine = make_engine(args.platform_db or get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        company = db.scalar(select(Company).where(Company.slug == args.company.strip().lower()))
        if company is None:
            sys.exit(f"There's no company {args.company!r} on the platform. Add it under Companies first.")
        crm = db.scalar(select(Application).where(Application.key == "crm"))
        if crm is None or db.get(CompanyApp, (company.id, crm.id)) is None:
            sys.exit(f"{company.name} doesn't have the CRM on the platform. Give it the CRM (Companies → {company.name} → Applications) first.")
        made = given = already = 0
        for p in people:
            person = db.scalar(select(Identity).where(Identity.company_id == company.id, func.lower(Identity.email) == p["email"]))
            new = person is None
            if new:
                person = Identity(company_id=company.id, full_name=p["name"], email=p["email"], status="active" if p["active"] else "suspended",
                                  is_company_admin=p["role"] == "Administrator")
                db.add(person)
                db.flush()
                audit(db, TOOL, "user.created", target=person.email, target_type="user", target_id=person.id, company_id=company.id)
                made += 1
                print(f"  add   {p['email']:40} {p['role']}{'' if p['active'] else ' (switched off in the CRM: suspended)'}")
            if db.get(IdentityApp, (person.id, crm.id)) is None:
                db.add(IdentityApp(identity_id=person.id, application_id=crm.id, role=p["role"], is_app_admin=p["role"] == "Administrator", granted_by=TOOL))
                audit(db, TOOL, "access.granted", target=f"{person.email} · {crm.name}", target_type="user", target_id=person.id,
                      company_id=company.id, application_id=crm.id)
                given += 1
                if not new:
                    print(f"  give  {p['email']:40} the CRM as {p['role']}")
            else:
                already += 1
        if args.dry_run:
            db.rollback()
            print(f"Dry run: {made} would be added, {given} given the CRM, {already} already set. Nothing was changed.")
        else:
            db.commit()
            print(f"{company.name}: {made} added, {given} given the CRM, {already} already set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
