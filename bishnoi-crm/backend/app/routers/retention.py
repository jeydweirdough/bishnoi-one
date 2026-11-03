"""Retention: whether customers keep coming back for quotes.

A customer here is a company; a quote made for one of its contacts counts for
it too. A quote counts unless it was rejected. With the windows of the
customer's department (its team's, set by its manager under /retention/windows),
else the company's (Products → Pricing rules):

- healthy:   a quote in the last `at_risk_days`;
- at risk:   none since, but one in the last `lost_days`;
- lost:      none in `lost_days` (or the company is marked inactive);
- no quotes: never had one.

The rate compares two windows of `lost_days` (each customer's own): of the
customers quoted in the earlier one, how many were quoted again in the latest.

Needs customers.view. "mine" is the person's own companies; "team" is every
company their role reaches (needs a scope wider than own). Setting a
department's windows needs admin.settings, or department.manage for one's own.
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import DEPARTMENT, Access, require, settings_change
from app.api import Api, field_error
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Activity, Company, Quote, Team, User
from app.pricing import sales_settings
from app.scope import within

router = APIRouter(prefix="/retention", tags=["retention"])

View = Annotated[Access, Depends(require("customers.view"))]
Manage = Annotated[Access, Depends(settings_change(*DEPARTMENT))]
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


class Windows:
    """The retention windows (at risk, lost) of each customer's department:
    its team's own, else the company's."""

    def __init__(self, db: Session):
        s = sales_settings(db)
        self.company = (s.at_risk_days, s.lost_days)
        self.teams = {t.id: t for t in db.scalars(select(Team))}

    def of_team(self, team_id: str | None) -> tuple[int, int]:
        t = self.teams.get(team_id) if team_id else None
        if t is None or t.at_risk_days is None or t.lost_days is None:
            return self.company
        return (t.at_risk_days, t.lost_days)

    def of(self, company: Company) -> tuple[int, int]:
        return self.of_team(company.team_id)

    def rules(self, companies: list[Company]) -> list[dict]:
        """The windows in play: the company's first, then each department's own."""
        out = [{"atRiskDays": self.company[0], "lostDays": self.company[1], "division": "", "divisionName": "Sales"}]
        for team_id in sorted({c.team_id for c in companies if c.team_id}, key=lambda t: self.teams[t].name if t in self.teams else ""):
            t = self.teams.get(team_id)
            if t is not None and self.of_team(team_id) != self.company:
                out.append({"atRiskDays": t.at_risk_days, "lostDays": t.lost_days, "division": t.id, "divisionName": t.name})
        # When every customer in view is judged by one department's windows, those lead (the page words itself by the first).
        if len({self.of(c) for c in companies}) == 1 and len(out) == 2:
            out.reverse()
        return out


def health(company: Company, last: date | None, on: date, at_risk: int, lost: int) -> str:
    if company.status == "inactive":
        return "lost"
    if last is None:
        return "no_quotes"
    days = (on - last).days
    return "healthy" if days < at_risk else "at_risk" if days < lost else "lost"


def summary(book: Book, companies: list[Company], on: date, windows: Windows) -> dict:
    base = kept = new = 0
    counts = {"healthy": 0, "at_risk": 0, "lost": 0, "no_quotes": 0}
    for c in companies:
        at_risk, lost = windows.of(c)
        window = timedelta(days=lost)
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


def trend(book: Book, on: date, windows: Windows) -> list[dict]:
    points = []
    first = on.replace(day=1)
    for back in range(MONTHS - 1, -1, -1):
        y, m = divmod(first.month - 1 - back, 12)
        start = date(first.year + y, m + 1, 1)
        end = min(on, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1))
        base = kept = 0
        for c in book.companies:
            window = timedelta(days=windows.of(c)[1])
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


def rows(db: Session, access: Access, book: Book, on: date, windows: Windows, *, only_slipping: bool) -> list[dict]:
    follow = next_follow_ups(db, [c.id for c in book.companies])
    teams = {t.id: t.name for t in db.scalars(select(Team))}
    out = []
    for c in book.companies:
        last = book.last(c.id, on)
        at_risk, lost = windows.of(c)
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


def load_book(db: Session, access: Access, settings, view: str, team: str | None) -> tuple[Book, date, Windows]:
    if view == "team" and access.scope == "own":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own customers.")
    tz = settings.org_timezone
    on = datetime.now(ZoneInfo(tz)).date()
    return Book(db, access, view, team if view == "team" else None, tz), on, Windows(db)


@router.get("")
def read_retention(access: View, db: DB, settings: SettingsDep, view: Which = "mine", team: str | None = Query(None, max_length=36)) -> dict:
    book, on, windows = load_book(db, access, settings, view, team)
    reps = []
    if view == "team":
        by_owner: dict[str, list[Company]] = defaultdict(list)
        for c in book.companies:
            by_owner[c.owner_id].append(c)
        names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(list(by_owner))))}
        reps = sorted(
            ({"id": o, "name": names.get(o), **summary(book, cs, on, windows)} for o, cs in by_owner.items()),
            key=lambda r: (-r["atRisk"], r["name"] or ""),
        )
    team_query = select(Team).where(Team.is_active).order_by(Team.name)
    if access.scope in ("team", "managed"):
        team_query = team_query.where(Team.id.in_(access.team_ids or {""}))
    return {
        "view": view,
        "canSeeTeam": access.scope != "own",
        "teams": [{"id": t.id, "name": t.name} for t in db.scalars(team_query)] if access.scope in ("all", "managed") else [],
        "team": team if view == "team" else None,
        "asOf": on.isoformat(),
        "rules": windows.rules(book.companies),
        "summary": summary(book, book.companies, on, windows),
        "trend": trend(book, on, windows),
        "reps": reps,
        "watch": rows(db, access, book, on, windows, only_slipping=True)[:100],
    }


HEALTH_WORDS = {"healthy": "Healthy", "at_risk": "At risk", "lost": "Lost", "no_quotes": "No quotes yet"}


@router.get("/export")
def export_retention(access: View, db: DB, settings: SettingsDep, view: Which = "mine", team: str | None = Query(None, max_length=36)) -> Response:
    if view == "team":
        access.require("reports.export")
    book, on, windows = load_book(db, access, settings, view, team)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Customer", "Team", "Owner", "Standing", "Type", "Last quote", "Days since", "Next task", "Task due"])
    for r in rows(db, access, book, on, windows, only_slipping=False):
        f = r["followUp"] or {}
        w.writerow([r["name"], r["teamName"], r["owner"]["name"] or "", HEALTH_WORDS[r["health"]], r["status"], r["lastQuoteOn"] or "", r["daysSince"] if r["lastQuoteOn"] else "", f.get("title", ""), f.get("dueOn", "")])
    return Response(
        "﻿" + out.getvalue(),  # so Excel reads it as UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="retention-{view}-{on.isoformat()}.csv"'},
    )



# --- a department's own windows ------------------------------------------------------------


def windows_out(db: Session, access: Access) -> dict:
    s = sales_settings(db)
    teams = [t for t in db.scalars(select(Team).where(Team.is_active).order_by(Team.name)) if access.runs(t.id)]
    return {
        "company": {"atRiskDays": s.at_risk_days, "lostDays": s.lost_days},
        "teams": [
            {"id": t.id, "name": t.name, "atRiskDays": t.at_risk_days, "lostDays": t.lost_days, "own": t.at_risk_days is not None and t.lost_days is not None}
            for t in teams
        ],
    }


@router.get("/windows")
def read_windows(access: Manage, db: DB) -> dict:
    """The company's windows, and each department's own (a manager's: theirs)."""
    return windows_out(db, access)


class WindowsIn(Api):
    # Both None: back to the company's.
    at_risk_days: int | None = Field(None, ge=1, le=3650)
    lost_days: int | None = Field(None, ge=1, le=3650)


@router.put("/windows/{team_id}")
def set_windows(access: Manage, me: CurrentUser, db: DB, team_id: str, body: WindowsIn) -> dict:
    team = db.get(Team, team_id)
    if team is None or not access.runs(team.id):
        raise field_error("teamId", "Pick one of your own teams.")
    if (body.at_risk_days is None) != (body.lost_days is None):
        raise field_error("lostDays", "Give both, or neither to use the company's.")
    if body.at_risk_days is not None and body.lost_days is not None and body.at_risk_days >= body.lost_days:
        raise field_error("lostDays", "Lost comes after at risk: make it more days.")
    team.at_risk_days, team.lost_days = body.at_risk_days, body.lost_days
    audit(db, me, "team.updated", target=team.name, target_type="team", target_id=team.id, fields=["atRiskDays", "lostDays"])
    db.commit()
    return windows_out(db, access)
