"""Brings a company's org chart in from its CRM (feature plan step 4, agreed 2026-10-28).

Each CRM team becomes a unit on the Platform with the same id, so the CRM's records keep
pointing at the right one: top-level teams arrive as divisions, the ones under them as
teams (the company changes any kind on the Organisation screen, e.g. Training to a
department). Each team's places become the areas it covers, its manager the membership
with the same email. Then each person's main team becomes their membership's main unit,
and their other teams its other units. Units and placings already there are left alone,
so it is safe to run twice. Nothing is changed without --apply.

    uv run python -m app.tools.org_chart --company getmeds \\
        --crm-db "sqlite:///../../bishnoi-crm/backend/.data/crm-getmeds.db" [--apply]

Check it on a copy of the live Platform first (app.tools.copy_database, then
--platform-db naming the copy): it brings that database up to date as it opens it.
"""

import argparse
import json
import sys
from collections import Counter

from sqlalchemy import func, select, text

from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Company, Identity, MembershipUnit, Unit

TOOL = "org chart tool"


def crm_chart(url: str) -> tuple[list, list, list]:
    with make_engine(url).connect() as c:
        teams = c.execute(text("select t.id, t.name, t.parent_id, t.headquarters, t.is_active, lower(m.email) as manager "
                               "from nbcm_teams t left join nbcm_users m on m.id = t.manager_id")).all()
        people = c.execute(text("select lower(trim(email)) as email, team_id, is_active from nbcm_users")).all()
        others = c.execute(text("select lower(trim(u.email)) as email, ut.team_id from nbcm_user_teams ut join nbcm_users u on u.id = ut.user_id")).all()
    return teams, people, others


def bring_in(db, company: Company, teams, people, others) -> Counter:
    said = Counter()
    members = {m.email.lower(): m for m in db.scalars(select(Identity).where(Identity.company_id == company.id))}
    have = {u.id for u in db.scalars(select(Unit).where(Unit.company_id == company.id))}
    taken = {i for i in db.scalars(select(Unit.id).where(Unit.company_id != company.id))}
    # Parents first, so each team finds its division.
    for t in sorted(teams, key=lambda t: t.parent_id is not None):
        if t.id in have:
            said["units already there"] += 1
            continue
        if t.id in taken:
            print(f"  skip  {t.name}: its id is another company's unit")
            said["skipped"] += 1
            continue
        areas = t.headquarters if isinstance(t.headquarters, list) else json.loads(t.headquarters or "[]")
        manager = members.get(t.manager) if t.manager else None
        kind = "team" if t.parent_id else "division"
        db.add(Unit(id=t.id, company_id=company.id, kind=kind, name=t.name, parent_id=t.parent_id, manager_id=manager.id if manager else None,
                    areas=areas, is_active=bool(t.is_active)))
        have.add(t.id)
        said[f"{kind}s"] += 1
        print(f"  {kind:9} {t.name}{'' if t.is_active else ' (switched off)'}" + (f", headed by {t.manager}" if manager else ""))
    db.flush()
    for p in people:
        m = members.get(p.email)
        if m is None or not p.team_id:
            continue
        if m.main_unit_id is None and p.team_id in have:
            m.main_unit_id = p.team_id
            said["people placed"] += 1
    for o in others:
        m = members.get(o.email)
        if m is not None and o.team_id in have and o.team_id != m.main_unit_id and db.get(MembershipUnit, (m.id, o.team_id)) is None:
            db.add(MembershipUnit(membership_id=m.id, unit_id=o.team_id))
            said["other units given"] += 1
    db.flush()
    said["not placed"] = db.scalar(select(func.count()).select_from(Identity).where(
        Identity.company_id == company.id, Identity.status == "active", Identity.main_unit_id.is_(None), Identity.via_operator.is_(False)))
    return said


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring a company's org chart in from its CRM.")
    parser.add_argument("--company", required=True, help="the company's short name on the platform, e.g. getmeds")
    parser.add_argument("--crm-db", required=True, help="that company's CRM database address")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    args = parser.parse_args()

    teams, people, others = crm_chart(args.crm_db)
    engine = make_engine(args.platform_db or get_settings().database_url)
    upgrade(engine)
    with make_sessions(engine)() as db:
        company = db.scalar(select(Company).where(Company.slug == args.company.strip().lower()))
        if company is None:
            sys.exit(f"There's no company {args.company!r} on the platform.")
        said = bring_in(db, company, teams, people, others)
        summary = ", ".join(f"{n} {what}" for what, n in said.items())
        if args.apply:
            audit(db, TOOL, "org_chart.imported", target=company.name, target_type="company", target_id=company.id, company_id=company.id)
            db.commit()
            print(f"{company.name}: {summary}.")
        else:
            db.rollback()
            print(f"Dry run, nothing saved: {summary}. Run again with --apply to save it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
