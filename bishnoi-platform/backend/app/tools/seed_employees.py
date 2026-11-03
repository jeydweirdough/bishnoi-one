"""Fills a company's employees and organisation chart from a plan file (2026-11-03).

The plan is a JSON file made from the HR employee list and the org chart, kept off the repo
(it names people). For each company in it:

  units      made where missing, by name under their parent (a department, division or team);
             a unit already there is left as it is, except that its head is set when it has none
  employees  added where their email isn't there yet, with their title; someone already there
             keeps everything, and gets the plan's title only when theirs is empty
  placing    each employee's main unit, set only when they have none (--replace sets it anyway)

Nobody gets an app or a role: give them on Employees after. --password gives a first password to the employees this
adds, and to any already there with none (never to anyone who has one), which they must change at their first sign-in.
--rename-role "Manager=Mentor" renames a role (repeatable), and the apps are told.
An email the company can't use (another domain, an operator's, another company's person's) is
reported and left out. Nothing is saved without --apply.

    uv run python -m app.tools.seed_employees --plan employees-plan.json [--apply] [--replace] [--password X] [--rename-role OLD=NEW]

The plan:
    {"companies": [{"slug": "getmeds-philippines-inc",
                    "units": [{"name": "HR DEPARTMENT", "kind": "department", "parent": null, "head": "hr@getmeds.ph"}],
                    "employees": [{"email": "hr2@getmeds.ph", "fullName": "Gilbert Aboga Cabujat",
                                   "title": "HR Supervisor", "unit": "HR DEPARTMENT"}]}]}
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select

from datetime import UTC, datetime

from app import access_roles, email_rules, org_push, passwords
from app.accounts import account_of
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import AccessRole, Company, Identity, Unit
from app.security import check_password_rules, hash_password

TOOL = "employee seed tool"
KINDS = {"department", "division", "team"}


def key(name: str) -> str:
    return " ".join(name.split()).lower()


def why(error: HTTPException) -> str:
    detail = error.detail
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get("msg", detail))
    return str(detail)


def seed(db, company: Company, plan: dict, replace: bool = False) -> tuple[Counter, list[str], list[Identity]]:
    said, problems, added = Counter(), [], []
    members = {m.email.lower(): m for m in db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.deleted_at.is_(None)))}
    units = {key(u.name): u for u in db.scalars(select(Unit).where(Unit.company_id == company.id))}

    # Units, parents first: the plan lists them in that order, and a parent made here is found by the next.
    for u in plan.get("units", []):
        name, kind, parent = u["name"].strip(), u.get("kind", "team"), u.get("parent")
        if kind not in KINDS:
            problems.append(f"unit {name}: kind must be department, division or team")
            continue
        unit = units.get(key(name))
        if unit is None:
            above = units.get(key(parent)) if parent else None
            if parent and above is None:
                problems.append(f"unit {name}: its parent {parent} isn't there")
                continue
            unit = Unit(company_id=company.id, kind=kind, name=name, parent_id=above.id if above else None)
            db.add(unit)
            db.flush()
            units[key(name)] = unit
            said["units made"] += 1
            print(f"  + {kind:10} {name}" + (f"  (under {parent})" if parent else ""))

    # Employees.
    for e in plan.get("employees", []):
        email = (e.get("email") or "").strip().lower()
        name = " ".join((e.get("fullName") or "").split())
        if not email or not name:
            problems.append(f"{name or email or 'a row'}: needs a name and a work email")
            continue
        person = members.get(email)
        if person is None:
            try:
                email_rules.check_company_email(company, email)
                email_rules.check_available(db, email, company.id)
            except HTTPException as error:
                problems.append(f"{name} <{email}>: {why(error)}")
                continue
            person = Identity(company_id=company.id, full_name=name, email=email, title=e.get("title") or None)
            db.add(person)
            db.flush()
            members[email] = person
            added.append(person)
            said["employees added"] += 1
            print(f"  + employee   {name} <{email}>")
        elif not person.title and e.get("title"):
            person.title = e["title"]
            said["titles filled"] += 1
        unit = units.get(key(e["unit"])) if e.get("unit") else None
        if e.get("unit") and unit is None:
            problems.append(f"{name}: unit {e['unit']} isn't there")
        elif unit is not None and (person.main_unit_id is None or (replace and person.main_unit_id != unit.id)):
            person.main_unit_id = unit.id
            said["employees placed"] += 1

    # Heads, once everyone is in.
    for u in plan.get("units", []):
        unit, head = units.get(key(u["name"])), (u.get("head") or "").strip().lower()
        if unit is None or not head:
            continue
        if head not in members:
            problems.append(f"unit {unit.name}: its head {head} isn't an employee here")
        elif unit.manager_id is None or (replace and unit.manager_id != members[head].id):
            unit.manager_id = members[head].id
            said["heads set"] += 1
    db.flush()
    said["not placed"] = db.scalar(select(func.count()).select_from(Identity).where(
        Identity.company_id == company.id, Identity.status == "active", Identity.deleted_at.is_(None),
        Identity.main_unit_id.is_(None), Identity.via_operator.is_(False)))
    return said, problems, added


def give_passwords(db, company: Company, password: str, added: list[Identity]) -> int:
    """A first password for the new employees and any with none; each must choose their own at their first sign-in."""
    problem = check_password_rules(password)
    if problem:
        sys.exit(f"That password won't do: {problem}")
    hashed, now, given = hash_password(password), datetime.now(UTC), 0
    fresh = {p.id for p in added}
    for p in db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.deleted_at.is_(None), Identity.via_operator.is_(False))):
        account = account_of(db, p)
        has = bool(account.password_hash if account else p.password_hash)
        role = db.get(AccessRole, p.access_role_id) if p.access_role_id else None
        # A shared first password never goes on an administrator's account, nor an operator's.
        if p.is_company_admin or (role is not None and role.is_admin) or (account is not None and account.is_operator):
            continue
        if p.id in fresh or not has:
            passwords.set_for(db, p.email, hashed, now)
            account = account_of(db, p)
            if account is not None:
                account.must_change_password = True
            given += 1
    return given


def rename_roles(db, company: Company, pairs: list[str]) -> list[str]:
    done = []
    for pair in pairs:
        old, _, new = pair.partition("=")
        role = db.scalar(select(AccessRole).where(AccessRole.company_id == company.id, func.lower(AccessRole.name) == old.strip().lower()))
        taken = db.scalar(select(AccessRole).where(AccessRole.company_id == company.id, func.lower(AccessRole.name) == new.strip().lower()))
        if role is None or taken is not None or not new.strip():
            done.append(f"{old}: not renamed ({'no such role' if role is None else 'a role with that name exists'})")
            continue
        role.name = new.strip()
        audit(db, TOOL, "role.renamed", target=role.name, target_type="role", target_id=role.id, company_id=company.id, fields=["name"])
        done.append(f"{old.strip()} -> {role.name}")
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill a company's employees and organisation chart from a plan file.")
    parser.add_argument("--plan", help="optional plan file (JSON). If omitted, uses embedded employee plan.")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    parser.add_argument("--replace", action="store_true", help="also move people and heads already placed to the plan's")
    parser.add_argument("--password", help="a first password for new employees and any with none (they must change it at first sign-in)")
    parser.add_argument("--rename-role", action="append", default=[], metavar="OLD=NEW", help="rename a role at each company in the plan")
    args = parser.parse_args()

    if args.plan and Path(args.plan).exists():
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        print(f"[OK] Loaded employee plan from '{args.plan}'.")
    else:
        from app.tools.employees_plan_data import DEFAULT_PLAN
        plan = DEFAULT_PLAN
        print("[OK] Loaded employee plan from embedded plan data.")

    settings = get_settings()
    engine = make_engine(args.platform_db or settings.database_url)
    upgrade(engine)
    sessions = make_sessions(engine)
    told = []
    with sessions() as db:
        for part in plan["companies"]:
            target_slug = part["slug"]
            company = db.scalar(select(Company).where(Company.slug == target_slug))
            if company is None and target_slug == "getmeds-philippines-inc":
                company = db.scalar(select(Company).where(Company.slug == "getmeds"))
            if company is None and target_slug == "getmeds":
                company = db.scalar(select(Company).where(Company.slug == "getmeds-philippines-inc"))
            if company is None and target_slug == "2mg-incoporated":
                company = db.scalar(select(Company).where(Company.slug.in_(["2mg", "2mg-inc"])))

            if company is None:
                print(f"There's no company {part['slug']!r}: skipped.")
                continue
            print(f"\n{company.name} ({company.slug})")
            said, problems, added = seed(db, company, part, args.replace)
            if args.password:
                said["first passwords"] = give_passwords(db, company, args.password, added)
            for line in rename_roles(db, company, args.rename_role) if args.rename_role else []:
                print(f"  role {line}")
            if args.apply:
                audit(db, TOOL, "employees.seeded", target=company.name, target_type="company", target_id=company.id, company_id=company.id,
                      fields=[f"{n} {what}" for what, n in said.items() if what != "not placed"])
                db.commit()
                told.append(company.id)
            print("  " + ", ".join(f"{n} {what}" for what, n in said.items()))
            if problems:
                print(f"  {len(problems)} left out, to fix in the plan or on Employees:")
                for p in problems:
                    print(f"    - {p}")
        if args.apply:
            for company_id in told:  # the apps get the chart, and the role names, now
                org_push._send(sessions, settings, company_id)
                access_roles._send(sessions, settings, company_id)
            print(chr(10) + "Saved, and the apps are told (the chart and the role names).")
        else:
            db.rollback()
            print("\nDry run, nothing saved. Run again with --apply to save it; then open Organisation once so every app gets the chart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
