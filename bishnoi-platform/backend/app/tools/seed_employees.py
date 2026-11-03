"""Fills a company's employees and organisation chart from a plan file (2026-11-03).

The plan is a JSON file made from the HR employee list and the org chart, kept off the repo
(it names people). For each company in it:

  units      made where missing, by name under their parent (a department, division or team);
             a unit already there is left as it is, except that its head is set when it has none
  employees  added where their email isn't there yet, with their title; someone already there
             keeps everything, and gets the plan's title only when theirs is empty
  placing    each employee's main unit, set only when they have none (--replace sets it anyway)

Nobody gets a password, a role or an app: send invitations and give roles on Employees after.
An email the company can't use (another domain, an operator's, another company's person's) is
reported and left out. Nothing is saved without --apply.

    uv run python -m app.tools.seed_employees --plan employees-plan.json [--apply] [--replace]

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

from app import email_rules
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Company, Identity, Unit

TOOL = "employee seed tool"
KINDS = {"department", "division", "team"}


def key(name: str) -> str:
    return " ".join(name.split()).lower()


def why(error: HTTPException) -> str:
    detail = error.detail
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return str(detail[0].get("msg", detail))
    return str(detail)


def seed(db, company: Company, plan: dict, replace: bool = False) -> tuple[Counter, list[str]]:
    said, problems = Counter(), []
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
    return said, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill a company's employees and organisation chart from a plan file.")
    parser.add_argument("--plan", required=True, help="the plan file (JSON)")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    parser.add_argument("--replace", action="store_true", help="also move people and heads already placed to the plan's")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    engine = make_engine(args.platform_db or get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        for part in plan["companies"]:
            company = db.scalar(select(Company).where(Company.slug == part["slug"]))
            if company is None:
                print(f"There's no company {part['slug']!r}: skipped.")
                continue
            print(f"\n{company.name}")
            said, problems = seed(db, company, part, args.replace)
            if args.apply:
                audit(db, TOOL, "employees.seeded", target=company.name, target_type="company", target_id=company.id, company_id=company.id,
                      fields=[f"{n} {what}" for what, n in said.items() if what != "not placed"])
                db.commit()
            print("  " + ", ".join(f"{n} {what}" for what, n in said.items()))
            if problems:
                print(f"  {len(problems)} left out, to fix in the plan or on Employees:")
                for p in problems:
                    print(f"    - {p}")
        if not args.apply:
            db.rollback()
            print("\nDry run, nothing saved. Run again with --apply to save it; then open Organisation once so every app gets the chart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
