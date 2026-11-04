"""Aligns access with the org chart (2026-11-04): the sales department's employees get the CRM, each with the role their
chart title calls for (Mentor, Coach, Coachee), and those three roles hold the standard defaults with the right reach.

- Only people in the chosen department's units (it and everything under it) who don't hold the CRM yet are given it.
- Nobody's existing role is changed; administrators and operators are never touched.
- The three roles only gain permissions (the standard defaults are added, nothing is taken away); Mentor and Coach reach
  "managed", Coachee "own", in each app that offers it.
- Dry run by default, with a CSV to check; --apply saves, then the roles and the chart are sent to the apps.

    uv run python -m app.tools.align_access --company getmeds-philippines-inc --csv who.csv [--department "SALES DEPARTMENT"] [--apply]
"""

import argparse
import csv
import re
import sys

from sqlalchemy import select

from app import access_roles, org_push, passes, standard_actions
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import AccessRole, Account, Company, Identity, IdentityApp, Unit

TOOL = "align access tool"
APP = "crm"
MENTORS = ["Vanessa Escalderon", "Javed Shaikh", "Subir Dey"]
COACHES = ["Ma. Anicia Maglatang", "Nicka Masusi", "Honey Cordero", "Daniel Cruz", "Julius Abucay", "Kindred Malaluan", "Saurav Kumar",
           "Jim Lord Palomares", "Jessa Domino", "Claire Gallana"]
LEVELS = {"Mentor": "mentor", "Coach": "coach", "Coachee": "coachee"}


def norm(name: str) -> str:
    return " ".join(re.sub(r"[^a-z ]", " ", (name or "").lower()).split())


def same_person(listed: str, full_name: str) -> bool:
    """The chart's short name against the full name on file: same surname, and the listed given names appear in it."""
    a, b = norm(listed).split(), norm(full_name).split()
    return bool(a and b) and a[-1] == b[-1] and all(t in b for t in a[:-1] if t != "ma")


def level_of(p: Identity) -> str:
    """The role the chart calls for: by name for the heads the chart lists, else by title."""
    if any(same_person(n, p.full_name) for n in MENTORS):
        return "Mentor"
    if any(same_person(n, p.full_name) for n in COACHES):
        return "Coach"
    title = (p.title or "").lower()
    if "mentor" in title:
        return "Mentor"
    return "Coach" if "manager" in title or "team lead" in title else "Coachee"


def subtree(units: dict[str, Unit], root: Unit) -> set[str]:
    ids, grew = {root.id}, True
    while grew:
        grew = False
        for u in units.values():
            if u.parent_id in ids and u.id not in ids:
                ids.add(u.id)
                grew = True
    return ids


def plan(db, company: Company, department: str, app, roles: dict[str, AccessRole]) -> list[dict]:
    units = org_push._units(db, company.id)
    roots = [u for u in units.values() if u.name.strip().lower() == department.strip().lower()]
    if not roots:
        sys.exit(f"There is no unit called {department!r} on {company.name}'s chart.")
    inside = set().union(*(subtree(units, r) for r in roots))
    rows = []
    for p in db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.deleted_at.is_(None), Identity.status == "active",
                                               Identity.via_operator.is_(False)).order_by(Identity.full_name)):
        if p.main_unit_id not in inside:
            continue
        account = db.get(Account, p.account_id) if p.account_id else None
        own = db.get(AccessRole, p.access_role_id) if p.access_role_id else None
        if (account is not None and account.is_operator) or p.is_company_admin or (own is not None and own.is_admin):
            continue
        if db.get(IdentityApp, (p.id, app.id)) is not None:
            continue
        level = level_of(p)
        rows.append({"person": p, "level": level, "role": roles[level], "unit": units[p.main_unit_id].name})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Give the CRM and the chart's role to a department's employees.")
    parser.add_argument("--company", required=True)
    parser.add_argument("--department", default="SALES DEPARTMENT")
    parser.add_argument("--csv")
    parser.add_argument("--platform-db")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(args.platform_db or settings.database_url)
    upgrade(engine)
    sessions = make_sessions(engine)
    with sessions() as db:
        passes.keep_in_database(sessions, settings)
        company = db.scalar(select(Company).where(Company.slug == args.company.strip().lower()))
        if company is None:
            sys.exit(f"There is no company {args.company!r} on the platform.")
        modules = access_roles.modules_of(db, company.id)
        crm = next((m for m in modules if m.key == APP), None)
        if crm is None:
            sys.exit("The company does not have the CRM.")
        roles = {r.name: r for r in db.scalars(select(AccessRole).where(AccessRole.company_id == company.id))}
        missing = [n for n in LEVELS if n not in roles]
        if missing:
            sys.exit(f"These roles are missing on the platform: {', '.join(missing)}.")
        rows = plan(db, company, args.department, crm, roles)

        # The standard defaults per role per app: additions only.
        additions = []
        for name, level in LEVELS.items():
            role = roles[name]
            held, scopes = access_roles.grants_of(db, role), access_roles.scopes_of(db, role)
            for m in modules:
                found = access_roles.catalog(m)
                if not found:
                    additions.append((name, m.key, None, None))
                    continue
                perms, reach = standard_actions.defaults(found["areas"], found.get("scopes") or [], level)
                new = sorted(set(perms) - set(held.get(m.key, [])))
                additions.append((name, m.key, new, reach if reach and reach != scopes.get(m.key) else None))

        for name, app_key, new, reach in additions:
            if new is None:
                print(f"  {name:8} {app_key:10} the app did not answer: left as it is")
            else:
                print(f"  {name:8} {app_key:10} +{len(new)} permissions" + (f", reach {reach}" if reach else ""))
        counts = {n: sum(1 for r in rows if r["level"] == n) for n in LEVELS}
        print(f"\n{len(rows)} employees would get the CRM: {counts}")
        if args.csv:
            with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["employee", "email", "title", "unit", "role they get"])
                for r in rows:
                    p = r["person"]
                    w.writerow([p.full_name, p.email, p.title or "", r["unit"], r["level"]])
        if not args.apply:
            print("Dry run: nothing saved. Add --apply to save.")
            return 0

        for name, app_key, new, reach in additions:
            if new is None or not (new or reach):
                continue
            role = roles[name]
            held, scopes = access_roles.grants_of(db, role), access_roles.scopes_of(db, role)
            access_roles.set_module(db, role, app_key, list(held.get(app_key, [])) + new, reach or scopes.get(app_key))
        for r in rows:
            p = r["person"]
            db.add(IdentityApp(identity_id=p.id, application_id=crm.id, role=None, is_app_admin=False, granted_by=TOOL, access_role_id=r["role"].id))
            if p.access_role_id is None:
                p.access_role_id = r["role"].id
        audit(db, TOOL, "access.aligned", target=company.name, target_type="company", target_id=company.id, company_id=company.id,
              fields=[f"{len(rows)} given the CRM"])
        db.commit()
    access_roles._send(sessions, settings, company.id)
    org_push._send(sessions, settings, company.id)
    print("Saved, and the roles and the chart were sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
