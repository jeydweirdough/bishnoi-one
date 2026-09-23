"""Retention: whether customers keep coming back for quotes.

A customer here is a company; a quote made for one of its contacts counts for
it too. A quote counts unless it was rejected. With the windows from the CRM's
rules (Products → Pricing rules):

- healthy:   a quote in the last `at_risk_days`;
- at risk:   none since, but one in the last `lost_days`;
- lost:      none in `lost_days` (or the company is marked inactive);
- no quotes: never had one.

The rate compares two windows of `lost_days`: of the customers quoted in the
earlier one, how many were quoted again in the latest.

Needs customers.view. "mine" is the person's own companies; "team" is every
company their role reaches (needs a scope wider than own).
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.deps import DB, SettingsDep
from app.models import Activity, Company, Quote, Team, User
from app.pricing import sales_settings
from app.scope import within

router = APIRouter(prefix="/retention", tags=["retention"])

View = Annotated[Access, Depends(require("customers.view"))]
Which = Literal["mine", "team"]
MONTHS = 6


def rate(base: int, kept: int) -> float | None:
    return round(kept / base, 4) if base else None


class Book:
    """The companies in view, and the days each got a quote on."""

    def __init__(self, db: Session, access: Access, view: str, team: str | None, tz: str):
        query = within(select(Company), Company, access)
        if view == "mine":
            query = query.where(Company.owner_id == access.user_id)
        elif team:
            query = query.where(Company.team_id == team)
        self.companies = list(db.scalars(query.order_by(Company.name)).unique())
        ids = [c.id for c in self.companies]
        zone = ZoneInfo(tz)
        self.days: dict[str, list[date]] = defaultdict(list)
        rows = db.execute(
            select(Quote.company_id, Quote.created_at).where(
                Quote.company_id.in_(ids), Quote.approval_status != "rejected", Quote.letter_status != "rejected"
            )
        ).all()
        for company_id, at in rows:
            moment = at if at.tzinfo else at.replace(tzinfo=ZoneInfo("UTC"))
            self.days[company_id].append(moment.astimezone(zone).date())
        for d in self.days.values():
            d.sort()

    def quoted_between(self, company_id: str, after: date, upto: date) -> bool:
        return any(after < d <= upto for d in self.days[company_id])

    def last(self, company_id: str, on: date) -> date | None:
        before = [d for d in self.days[company_id] if d <= on]
        return before[-1] if before else None


def health(company: Company, last: date | None, on: date, at_risk: int, lost: int) -> str:
    if company.status == "inactive":
        return "lost"
    if last is None:
        return "no_quotes"
    days = (on - last).days
    return "healthy" if days < at_risk else "at_risk" if days < lost else "lost"


def summary(book: Book, companies: list[Company], on: date, at_risk: int, lost: int) -> dict:
    window = timedelta(days=lost)
    base = kept = new = 0
    counts = {"healthy": 0, "at_risk": 0, "lost": 0, "no_quotes": 0}
    for c in companies:
        earlier = book.quoted_between(c.id, on - 2 * window, on - window)
        latest = book.quoted_between(c.id, on - window, on)
        base += earlier
        kept += earlier and latest
        first = book.days[c.id][0] if book.days[c.id] else None
        new += bool(first and on - window < first <= on)
        counts[health(c, book.last(c.id, on), on, at_risk, lost)] += 1
    return {
        "rate": rate(base, kept),
        "base": base,
        "retained": kept,
        "lost": base - kept,
        "new": new,
        "customers": len(companies),
        "healthy": counts["healthy"],
        "atRisk": counts["at_risk"],
        "lostNow": counts["lost"],
        "noQuotes": counts["no_quotes"],
    }


def trend(book: Book, on: date, lost: int) -> list[dict]:
    points = []
    first = on.replace(day=1)
    for back in range(MONTHS - 1, -1, -1):
        y, m = divmod(first.month - 1 - back, 12)
        start = date(first.year + y, m + 1, 1)
        end = min(on, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1))
        window = timedelta(days=lost)
        base = kept = 0
        for c in book.companies:
            earlier = book.quoted_between(c.id, end - 2 * window, end - window)
            base += earlier
            kept += earlier and book.quoted_between(c.id, end - window, end)
        points.append({"month": start.isoformat()[:7], "asOf": end.isoformat(), "rate": rate(base, kept), "base": base, "retained": kept})
    return points


def next_follow_ups(db: Session, ids: list[str]) -> dict[str, dict]:
    """Each company's earliest open task."""
    found: dict[str, dict] = {}
    tasks = db.scalars(
        select(Activity).where(Activity.company_id.in_(ids), Activity.kind == "task", Activity.done_at.is_(None)).order_by(Activity.at)
    ).unique()
    for t in tasks:
        found.setdefault(t.company_id, {"dueOn": t.at.date().isoformat(), "title": t.subject, "assignee": t.owner.full_name if t.owner else None})
    return found


def rows(db: Session, access: Access, book: Book, on: date, at_risk: int, lost: int, *, only_slipping: bool) -> list[dict]:
    follow = next_follow_ups(db, [c.id for c in book.companies])
    teams = {t.id: t.name for t in db.scalars(select(Team))}
    out = []
    for c in book.companies:
        last = book.last(c.id, on)
        h = health(c, last, on, at_risk, lost)
        days = (on - last).days if last else 0
        # Worth a call: at risk, or lost lately enough to be winnable (within another window).
        if only_slipping and not (h == "at_risk" or (h == "lost" and last and days < 2 * lost)):
            continue
        out.append(
            {
                "customerId": c.id,
                "name": c.name,
                "team": c.team_id or "",
                "teamName": teams.get(c.team_id, "No team"),
                "owner": {"id": c.owner_id, "name": c.owner.full_name if c.owner else None},
                "health": h,
                "status": c.status,
                "lastQuoteOn": last.isoformat() if last else None,
                "daysSince": days,
                "followUp": follow.get(c.id),
                "canWinBack": access.can("activities.create"),
            }
        )
    if only_slipping:
        out.sort(key=lambda r: (r["health"] != "at_risk", -r["daysSince"] if r["health"] == "at_risk" else r["daysSince"]))
    return out


def load_book(db: Session, access: Access, settings, view: str, team: str | None) -> tuple[Book, date, int, int]:
    if view == "team" and access.scope == "own":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own customers.")
    tz = settings.org_timezone
    s = sales_settings(db)
    on = datetime.now(ZoneInfo(tz)).date()
    return Book(db, access, view, team if view == "team" else None, tz), on, s.at_risk_days, s.lost_days


@router.get("")
def read_retention(access: View, db: DB, settings: SettingsDep, view: Which = "mine", team: str | None = Query(None, max_length=36)) -> dict:
    book, on, at_risk, lost = load_book(db, access, settings, view, team)
    reps = []
    if view == "team":
        by_owner: dict[str, list[Company]] = defaultdict(list)
        for c in book.companies:
            by_owner[c.owner_id].append(c)
        names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(list(by_owner))))}
        reps = sorted(
            ({"id": o, "name": names.get(o), **summary(book, cs, on, at_risk, lost)} for o, cs in by_owner.items()),
            key=lambda r: (-r["atRisk"], r["name"] or ""),
        )
    team_query = select(Team).where(Team.is_active).order_by(Team.name)
    if access.scope == "team":
        team_query = team_query.where(Team.id == (access.team_id or ""))
    return {
        "view": view,
        "canSeeTeam": access.scope != "own",
        "teams": [{"id": t.id, "name": t.name} for t in db.scalars(team_query)] if access.scope == "all" else [],
        "team": team if view == "team" else None,
        "asOf": on.isoformat(),
        "rules": [{"atRiskDays": at_risk, "lostDays": lost, "division": "", "divisionName": "Sales"}],
        "summary": summary(book, book.companies, on, at_risk, lost),
        "trend": trend(book, on, lost),
        "reps": reps,
        "watch": rows(db, access, book, on, at_risk, lost, only_slipping=True)[:100],
    }


HEALTH_WORDS = {"healthy": "Healthy", "at_risk": "At risk", "lost": "Lost", "no_quotes": "No quotes yet"}


@router.get("/export")
def export_retention(access: View, db: DB, settings: SettingsDep, view: Which = "mine", team: str | None = Query(None, max_length=36)) -> Response:
    if view == "team":
        access.require("reports.export")
    book, on, at_risk, lost = load_book(db, access, settings, view, team)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Customer", "Team", "Owner", "Standing", "Type", "Last quote", "Days since", "Next task", "Task due"])
    for r in rows(db, access, book, on, at_risk, lost, only_slipping=False):
        f = r["followUp"] or {}
        w.writerow([r["name"], r["teamName"], r["owner"]["name"] or "", HEALTH_WORDS[r["health"]], r["status"], r["lastQuoteOn"] or "", r["daysSince"] if r["lastQuoteOn"] else "", f.get("title", ""), f.get("dueOn", "")])
    return Response(
        "﻿" + out.getvalue(),  # so Excel reads it as UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="retention-{view}-{on.isoformat()}.csv"'},
    )

