"""Sales results: what was sold against what was expected (CRM gap-closing plan, phase 1).

- /sales/targets: each seller's revenue target for a month, set next to the
  field goals (goals.manage). A team's target is its people's added up.
- /sales/results: for a month or a quarter, the value quoted, deals won and
  lost, the win rate, and revenue by person, team, customer and product, each
  person against their target. "mine" needs deals.view; "team" (everyone the
  role reaches) needs reports.view and a scope wider than own.
- /sales/results/export: one of those tables as a CSV file; the team's needs
  reports.export.

Revenue is the value of the deals won in the period (a deal's close date is
the day it was won). By product, a deal won with a quote counts that quote's
lines; otherwise the products on the deal; a deal with neither counts as
"Not itemised".
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess, permissions_of, require
from app.api import Api, person_out, team_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.kpis import by_code, person_targets, set_person_target
from app.models import Company, Deal, DealStage, Quote, Team, User
from app.pricing import today
from app.routers.deals import period_bounds
from app.routers.field import month_or_now
from app.scope import reachable_people, within

router = APIRouter(prefix="/sales", tags=["sales"])

Manage = Annotated[Access, Depends(require("goals.manage"))]
Which = Literal["mine", "team"]
TOP = 10


# --- targets ---------------------------------------------------------------------------------


def is_seller(user: User) -> bool:
    """Someone whose job includes selling: they work deals or quotes."""
    granted = permissions_of(user.role)
    return not user.role.is_system and ("deals.create" in granted or "quotes.create" in granted)


@router.get("/targets")
def read_targets(access: Manage, db: DB, settings: SettingsDep, month: str | None = Query(None, max_length=7)) -> dict:
    """Everyone who sells (and anyone already given a target that month), with the month's targets."""
    month = month_or_now(month, settings)
    targets = person_targets(db, by_code(db, "revenue_won"), [month])
    people = [u for u in db.scalars(select(User).where(User.is_active).order_by(User.full_name)) if is_seller(u) or u.id in targets]
    return {
        "month": month,
        "people": [{"person": person_out(p), "team": team_out(p.team), "targetCentavos": targets.get(p.id)} for p in people],
    }


class TargetIn(Api):
    user_id: str = Field(max_length=36)
    # None takes the target away.
    amount_centavos: int | None = Field(None, ge=0, le=10**13)


class TargetsIn(Api):
    targets: list[TargetIn] = Field(max_length=1000)


@router.put("/targets")
def set_targets(access: Manage, me: CurrentUser, db: DB, settings: SettingsDep, body: TargetsIn, month: str | None = Query(None, max_length=7)) -> dict:
    month = month_or_now(month, settings)
    users = set(db.scalars(select(User.id).where(User.id.in_([t.user_id for t in body.targets]))))
    if missing := [t.user_id for t in body.targets if t.user_id not in users]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"No such person: {missing[0]}.")
    kpi = by_code(db, "revenue_won")
    if kpi is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The Revenue won KPI has been removed. Add it back under Settings → KPIs.")
    for t in body.targets:
        set_person_target(db, kpi, month, t.user_id, t.amount_centavos)
    audit(db, me, "revenue_targets.updated", target=f"Revenue targets for {month} ({len(body.targets)} people)", target_type="goals")
    db.commit()
    return read_targets(access, db, settings, month)


# --- results ---------------------------------------------------------------------------------


def months_in(start: str, end: str) -> list[str]:
    """The YYYY-MM months from start up to (not including) end."""
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while f"{y:04d}-{m:02d}-01" < end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def utc_bounds(start: str, end: str, settings: Settings) -> tuple[datetime, datetime]:
    zone = ZoneInfo(settings.org_timezone)
    first = datetime.combine(date.fromisoformat(start), datetime.min.time(), zone)
    last = datetime.combine(date.fromisoformat(end), datetime.min.time(), zone)
    return first.astimezone(UTC), last.astimezone(UTC)


def check_view(access: Access, view: Which) -> None:
    access.require("deals.view")
    if view == "team":
        access.require("reports.view")
        if access.scope == "own":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role sees only your own work.")


def narrowed(query: Select, model, access: Access, view: Which, team: str | None) -> Select:
    query = within(query, model, access)
    if view == "mine":
        return query.where(model.owner_id == access.user_id)
    if team:
        query = query.where(model.team_id == team)
    return query


def results(db: Session, access: Access, settings: Settings, view: Which, period: str | None, team: str | None) -> dict:
    period = period or today(settings.org_timezone)[:7]
    start, end, label = period_bounds(period)
    first, last = utc_bounds(start, end, settings)

    closed = db.scalars(
        narrowed(select(Deal).join(Deal.stage), Deal, access, view, team).where(
            DealStage.outcome.in_(("won", "lost")), Deal.expected_close_on >= start, Deal.expected_close_on < end
        )
    ).unique().all()
    won = [d for d in closed if d.stage.outcome == "won"]
    lost = [d for d in closed if d.stage.outcome == "lost"]
    quotes = db.scalars(
        narrowed(select(Quote), Quote, access, view, team).where(Quote.created_at >= first, Quote.created_at < last, Quote.approval_status != "rejected")
    ).all()

    # Who's in it: whoever the view reaches and sells, has a target, or has results.
    months = months_in(start, end)
    if view == "mine":
        people = [db.get(User, access.user_id)]
    else:
        people = [u for u in reachable_people(db, access) if not team or u.team_id == team]
    ids = {p.id for p in people}
    everyone = person_targets(db, by_code(db, "revenue_won"), months)
    targets: dict[str, int] = defaultdict(int, {u: v for u, v in everyone.items() if u in ids})
    active = {d.owner_id for d in closed} | {q.owner_id for q in quotes} | set(targets)
    people = [p for p in people if p.id in active or is_seller(p)]

    def figures(deals_won, deals_lost, quoted) -> dict:
        decided = len(deals_won) + len(deals_lost)
        return {
            "wonCentavos": sum(d.value_centavos for d in deals_won),
            "wonCount": len(deals_won),
            "lostCentavos": sum(d.value_centavos for d in deals_lost),
            "lostCount": len(deals_lost),
            "winRate": round(100 * len(deals_won) / decided) if decided else None,
            "quotedCentavos": sum(q.total_centavos for q in quoted),
            "quoteCount": len(quoted),
        }

    def of(items, key):
        out = defaultdict(list)
        for i in items:
            out[key(i)].append(i)
        return out

    won_by, lost_by, quoted_by = of(won, lambda d: d.owner_id), of(lost, lambda d: d.owner_id), of(quotes, lambda q: q.owner_id)
    by_person = []
    for p in sorted(people, key=lambda u: u.full_name.lower()):
        target = targets.get(p.id)
        row = {"person": person_out(p), "team": team_out(p.team), "targetCentavos": target, **figures(won_by[p.id], lost_by[p.id], quoted_by[p.id])}
        row["attainment"] = round(100 * row["wonCentavos"] / target) if target else None
        by_person.append(row)

    teams = {t.id: t for t in db.scalars(select(Team))}
    team_targets: dict[str | None, int] = defaultdict(int)
    for p in people:
        team_targets[p.team_id] += targets.get(p.id, 0)
    won_t, lost_t, quoted_t = of(won, lambda d: d.team_id), of(lost, lambda d: d.team_id), of(quotes, lambda q: q.team_id)
    by_team = []
    for tid in sorted(set(won_t) | set(lost_t) | set(quoted_t) | {k for k, v in team_targets.items() if v}, key=lambda t: (teams[t].name if t in teams else "~")):
        target = team_targets.get(tid) or None
        row = {"team": team_out(teams.get(tid)) if tid else None, "targetCentavos": target, **figures(won_t[tid], lost_t[tid], quoted_t[tid])}
        row["attainment"] = round(100 * row["wonCentavos"] / target) if target else None
        by_team.append(row)

    customers: dict[str, dict] = {}
    for d in won:
        c = customers.setdefault(d.company_id, {"customer": {"id": d.company.id, "name": d.company.name}, "wonCentavos": 0, "wonCount": 0})
        c["wonCentavos"] += d.value_centavos
        c["wonCount"] += 1

    products: dict[str, dict] = {}
    won_quotes = {q.id: q for q in db.scalars(select(Quote).where(Quote.id.in_([d.won_quote_id for d in won if d.won_quote_id])))}
    for d in won:
        quote = won_quotes.get(d.won_quote_id) if d.won_quote_id else None
        lines = quote.lines if quote else d.lines
        if not lines:
            lines = [{"productId": "", "productName": "Not itemised", "quantity": 0, "totalCentavos": d.value_centavos}]
        for line in lines:
            key = line.get("productId") or line.get("productName") or "?"
            p = products.setdefault(key, {"product": {"id": line.get("productId") or None, "name": line.get("productName") or "?"}, "quantity": 0, "wonCentavos": 0})
            p["quantity"] += line.get("quantity") or 0
            p["wonCentavos"] += line.get("totalCentavos") or 0

    total_target = sum(targets.get(p.id, 0) for p in people) or None
    totals = figures(won, lost, quotes) | {"targetCentavos": total_target}
    totals["attainment"] = round(100 * totals["wonCentavos"] / total_target) if total_target else None
    return {
        "period": period,
        "label": label,
        "start": start,
        "end": end,
        "view": view,
        "totals": totals,
        "people": by_person,
        "teams": by_team,
        "customers": sorted(customers.values(), key=lambda c: -c["wonCentavos"]),
        "products": sorted(products.values(), key=lambda p: -p["wonCentavos"]),
        "lostReasons": [
            {"reason": reason, "count": len(ds), "lostCentavos": sum(d.value_centavos for d in ds)}
            for reason, ds in sorted(of(lost, lambda d: d.lost_reason or "Not said").items(), key=lambda kv: -len(kv[1]))
        ],
    }


@router.get("/results")
def read_results(
    access: CurrentAccess,
    db: DB,
    settings: SettingsDep,
    view: Which = "mine",
    period: str | None = Query(None, max_length=22, description="a month (2026-10), a quarter (2026-Q4) or days (2026-07-01..2026-10-15); this month when not given"),
    team: str | None = Query(None, max_length=36),
) -> dict:
    check_view(access, view)
    out = results(db, access, settings, view, period, team)
    out["customers"] = out["customers"][:TOP]
    out["products"] = out["products"][:TOP]
    out["canExport"] = view == "mine" or access.can("reports.export")
    return out


@router.get("/results/export")
def export_results(
    access: CurrentAccess,
    db: DB,
    settings: SettingsDep,
    report: Literal["people", "teams", "customers", "products"],
    view: Which = "mine",
    period: str | None = Query(None, max_length=22),
    team: str | None = Query(None, max_length=36),
) -> Response:
    check_view(access, view)
    if view == "team":
        access.require("reports.export")
    r = results(db, access, settings, view, period, team)
    places = settings.org_minor_units
    money = lambda c: "" if c is None else f"{c / 10**places:.{places}f}"  # noqa: E731
    pct = lambda n: "" if n is None else f"{n}%"  # noqa: E731
    out = io.StringIO()
    w = csv.writer(out)
    if report in ("people", "teams"):
        w.writerow(["Person" if report == "people" else "Team", *(["Team"] if report == "people" else []), "Target", "Won", "Attainment", "Deals won", "Deals lost", "Win rate", "Lost value", "Quoted", "Quotes"])
        for row in r[report]:
            name = row["person"]["name"] if report == "people" else (row["team"]["name"] if row["team"] else "No team")
            team_col = [row["team"]["name"] if row["team"] else "No team"] if report == "people" else []
            w.writerow([name, *team_col, money(row["targetCentavos"]), money(row["wonCentavos"]), pct(row["attainment"]), row["wonCount"], row["lostCount"], pct(row["winRate"]), money(row["lostCentavos"]), money(row["quotedCentavos"]), row["quoteCount"]])
    elif report == "customers":
        w.writerow(["Customer", "Won", "Deals won"])
        for row in r["customers"]:
            w.writerow([row["customer"]["name"], money(row["wonCentavos"]), row["wonCount"]])
    else:
        w.writerow(["Product", "Quantity", "Won"])
        for row in r["products"]:
            w.writerow([row["product"]["name"], row["quantity"], money(row["wonCentavos"])])
    return Response(
        "﻿" + out.getvalue(),  # so Excel reads it as UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="sales-{report}-{r["period"].replace("..", "-to-")}.csv"'},
    )


# --- growth: month by month ----------------------------------------------------------------


@router.get("/trend")
def read_trend(
    access: CurrentAccess,
    db: DB,
    settings: SettingsDep,
    view: Which = "team",
    months: int = Query(12, ge=2, le=36),
    team: str | None = Query(None, max_length=36),
) -> dict:
    """The last `months` months, this one included: revenue won (deals won, by
    the day they were won), value quoted, and new customers, for the dashboard's
    growth chart. Growth: the last full month against the one before it."""
    check_view(access, view)
    this = today(settings.org_timezone)[:7]
    y, m = int(this[:4]), int(this[5:])
    keys = []
    for back in range(months - 1, -1, -1):
        yy, mm = divmod((y * 12 + m - 1) - back, 12)
        keys.append(f"{yy:04d}-{mm + 1:02d}")
    first_day, after = f"{keys[0]}-01", period_bounds(keys[-1])[1]
    first, last = utc_bounds(first_day, after, settings)
    zone = ZoneInfo(settings.org_timezone)

    won: dict[str, list[int]] = {k: [0, 0] for k in keys}
    for d in db.scalars(
        narrowed(select(Deal).join(Deal.stage), Deal, access, view, team).where(
            DealStage.outcome == "won", Deal.expected_close_on >= first_day, Deal.expected_close_on < after
        )
    ).unique():
        won[d.expected_close_on[:7]][0] += d.value_centavos
        won[d.expected_close_on[:7]][1] += 1
    quoted: dict[str, int] = defaultdict(int)
    for q in db.scalars(narrowed(select(Quote), Quote, access, view, team).where(Quote.created_at >= first, Quote.created_at < last, Quote.approval_status != "rejected")):
        quoted[as_month(q.created_at, zone)] += q.total_centavos
    new: dict[str, int] = defaultdict(int)
    for c in db.scalars(narrowed(select(Company), Company, access, view, team).where(Company.created_at >= first, Company.created_at < last)).unique():
        new[as_month(c.created_at, zone)] += 1

    points = [{"month": k, "wonCentavos": won[k][0], "wonCount": won[k][1], "quotedCentavos": quoted[k], "newCustomers": new[k]} for k in keys]
    before, latest = points[-3]["wonCentavos"] if len(points) > 2 else 0, points[-2]["wonCentavos"]
    return {
        "thisMonth": this,
        "points": points,
        # The last full month against the one before it; None with nothing to compare.
        "growth": round(100 * (latest - before) / before) if before else None,
    }


def as_month(moment: datetime, zone: ZoneInfo) -> str:
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(zone).strftime("%Y-%m")
