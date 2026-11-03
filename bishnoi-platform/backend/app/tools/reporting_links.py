"""Fills "Reports to" from today's org chart heads (2026-11-03), so switching to links costs nobody their reach.

Each employee who has no "reports to" yet is linked to the closest head above them on the chart (their unit's head,
else the head of the unit above, and so on), never themselves. A unit head with nobody above them stays unlinked.
Nobody already linked is changed. Writes a CSV of every link it would make, to check before saving; nothing is saved
without --apply, and it then tells the apps the chart again.

    uv run python -m app.tools.reporting_links --company getmeds-philippines-inc --csv links.csv [--apply]
"""

import argparse
import csv
import sys

from sqlalchemy import select

from app import org_push
from app.audit import audit
from app.config import get_settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import Company, Identity

TOOL = "reporting links tool"


def derive(db, company: Company) -> list[tuple[Identity, Identity, str]]:
    """(employee, who they'd report to, the unit the head leads) for each employee without a link."""
    units = org_push._units(db, company.id)
    out = []
    for p in db.scalars(select(Identity).where(Identity.company_id == company.id, Identity.deleted_at.is_(None), Identity.status == "active",
                                               Identity.via_operator.is_(False), Identity.reports_to_id.is_(None)).order_by(Identity.full_name)):
        for unit in reversed(org_push.path_of(units, p.main_unit_id)):
            if unit.manager_id and unit.manager_id != p.id:
                head = db.get(Identity, unit.manager_id)
                if head is not None and head.status == "active" and head.deleted_at is None:
                    out.append((p, head, unit.name))
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Fill 'reports to' from the org chart's heads.")
    parser.add_argument("--company", required=True, help="the company's short name, e.g. getmeds-philippines-inc")
    parser.add_argument("--csv", help="write every link it would make to this file, to check first")
    parser.add_argument("--platform-db", help="the platform database (default: DATABASE_URL)")
    parser.add_argument("--apply", action="store_true", help="save it (without this, only says what it would do)")
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(args.platform_db or settings.database_url)
    upgrade(engine)
    sessions = make_sessions(engine)
    with sessions() as db:
        company = db.scalar(select(Company).where(Company.slug == args.company.strip().lower()))
        if company is None:
            sys.exit(f"There's no company {args.company!r} on the platform.")
        links = derive(db, company)
        if args.csv:
            with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["employee", "email", "title", "reports to", "their email", "through"])
                for p, head, unit in links:
                    w.writerow([p.full_name, p.email, p.title or "", head.full_name, head.email, unit])
        for p, head, unit in links[:15]:
            print(f"  {p.full_name:32} -> {head.full_name}  (head of {unit})")
        if len(links) > 15:
            print(f"  ... and {len(links) - 15} more" + (f", all in {args.csv}" if args.csv else ""))
        if args.apply:
            for p, head, _ in links:
                p.reports_to_id = head.id
            audit(db, TOOL, "organisation.links_filled", target=company.name, target_type="company", target_id=company.id, company_id=company.id,
                  fields=[f"{len(links)} reports to"])
            db.commit()
            org_push.push(sessions, settings, company.id)
            print(f"{company.name}: {len(links)} linked; the apps are told.")
        else:
            db.rollback()
            print(f"Dry run, nothing saved: {len(links)} would be linked. Run again with --apply to save them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
