"""Customer retention (see app/retention.py for what the numbers mean).

- /modules/{m}/retention: "mine" (customers I own) for anyone in the workspace;
  "team" (every customer, and a row per rep) needs the Reports grant there.
- /modules/{m}/retention/export: the same customers as a CSV.
- /me/at-risk: my at-risk customers across divisions, for the home page.
- /retention/divisions: every division I have Reports in, side by side.
- /admin/retention: each division's at-risk and lost thresholds (Admins).
"""

import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentAccess, CurrentUser, RecordsDep, SettingsDep, require_settings
from app.errors import invalid
from app.models import Division, RetentionRule, Subdivision
from app.catalogue import sales_keys
from app.modules import BY_KEY, REPORT
from app.quotes import QUOTE
from app.retention import (
    AT_RISK,
    HEALTHY,
    LOST,
    NO_QUOTES,
    CustomerFacts,
    Rules,
    health,
    load_rules,
    look_back,
    summarize,
    trend,
)
from app.routers.sales import CUSTOMER, FOLLOW_UP, WS, Workspace, today_date
from app.schemas import RetentionRulesIn
from app.scope import Scope
from app.store.query import MAX_LIMIT, Cmp, Eq, In, Query
from app.store.records import Records
from app.tenancy import org_get


router = APIRouter(tags=["retention"])

View = Literal["mine", "team"]
HEALTH_LABELS = {HEALTHY: "Healthy", AT_RISK: "At risk", LOST: "Lost", NO_QUOTES: "No recent quotes"}


def find_all(records: Records, doc_type: str, scopes: frozenset[Scope], where: tuple = ()) -> list[dict]:
    found: list[dict] = []
    offset = 0
    while True:
        page = records.find(Query(doc_type, scopes, where, (("_id", "asc"),), offset, MAX_LIMIT))
        found += page
        if len(page) < MAX_LIMIT:
            return found
        offset += MAX_LIMIT


def counts_as_buying(quote: dict) -> bool:
    return quote.get("approvalStatus") != "rejected" and quote.get("letterStatus") != "rejected"


def iso_at_start(day: date, settings: Settings) -> str:
    """Midnight of a Manila day, as the UTC timestamp records are stamped with."""
    at = datetime.combine(day, time.min, tzinfo=ZoneInfo(settings.timezone)).astimezone(UTC)
    return at.isoformat(timespec="seconds").replace("+00:00", "Z")


def local_day(iso: str, settings: Settings) -> date:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(settings.timezone)).date()


def gather(records: Records, scopes: frozenset[Scope], settings: Settings, since: date) -> list[CustomerFacts]:
    """Every customer in these scopes, with the days of their quotes since `since`."""
    if not scopes:
        return []
    quotes: dict[str, list[tuple[date, int]]] = {}
    for q in find_all(records, QUOTE, scopes, (Cmp("createdAt", ">=", iso_at_start(since, settings)),)):
        if counts_as_buying(q):
            quotes.setdefault(q["customerId"], []).append((local_day(q["createdAt"], settings), q.get("totalCentavos", 0)))
    facts = []
    for c in find_all(records, CUSTOMER, scopes):
        scope = Scope.of(c)
        mine = sorted(quotes.get(c["_id"], []))
        facts.append(
            CustomerFacts(
                id=c["_id"],
                name=c["name"],
                division=scope.division,
                team=scope.subdivision,
                status=c.get("status", "active"),
                owner_id=c.get("ownerId"),
                owner_name=c.get("ownerName"),
                quote_days=tuple(d for d, _ in mine),
                quote_totals=tuple(t for _, t in mine),
                created_on=local_day(c["createdAt"], settings) if c.get("createdAt") else None,
                # Older records have no createdById; whoever owns them added them.
                created_by=c.get("createdById") or c.get("ownerId"),
            )
        )
    return facts


def open_follow_ups(records: Records, scopes: frozenset[Scope], customer_ids: list[str]) -> dict[str, dict]:
    """The next open follow-up of each customer, so nobody sets up a second win-back."""
    if not customer_ids:
        return {}
    docs = records.find(
        Query(FOLLOW_UP, scopes, (Eq("status", "open"), In("customerId", tuple(customer_ids))), (("dueOn", "asc"),), limit=MAX_LIMIT)
    )
    nxt: dict[str, dict] = {}
    for d in docs:
        nxt.setdefault(d["customerId"], {"dueOn": d["dueOn"], "title": d["title"], "assignee": d.get("assigneeName")})
    return nxt


def watch_list(facts: list[CustomerFacts], rules: dict[str, Rules], today: date) -> list[tuple[CustomerFacts, str, int]]:
    """At risk (closest to lost first), then recently lost (most recent first): the ones worth a call."""
    at_risk, lost = [], []
    for c in facts:
        h = health(c, rules[c.division], today)
        if c.last_quote is None:
            continue
        days = (today - c.last_quote).days
        if h == AT_RISK:
            at_risk.append((c, h, days))
        elif h == LOST and days <= 2 * rules[c.division].lost_days:
            lost.append((c, h, days))
    return sorted(at_risk, key=lambda x: -x[2]) + sorted(lost, key=lambda x: x[2])


def rep_rows(facts: list[CustomerFacts], rules: dict[str, Rules], today: date) -> list[dict]:
    groups: dict[str | None, list[CustomerFacts]] = {}
    for c in facts:
        groups.setdefault(c.owner_id, []).append(c)
    rows = []
    for owner_id, group in groups.items():
        s = summarize(group, rules, today).out()
        rows.append({"id": owner_id, "name": group[0].owner_name if owner_id else None, **s})
    return sorted(rows, key=lambda r: (r["name"] is None, (r["name"] or "").casefold()))


# --- a sales module ----------------------------------------------------------------


def report_scopes(ws: Workspace) -> frozenset[Scope]:
    """Where this person may see the team's figures, across every division they
    sell in. Reports is granted per division, so someone may report in one and
    not the other — and then sees team figures for only the one."""
    return frozenset(
        scope for division in ws.divisions for scope in ws.access.scopes(division, REPORT) if scope.division == division
    )


def module_facts(
    ws: Workspace, view: View, division: str | None, team: str | None
) -> tuple[list[CustomerFacts], dict[str, Rules], date]:
    if view == "team":
        scopes = report_scopes(ws)
        if not scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Team figures need Reports access. Ask your admin.")
        if team and division:
            scopes = scopes & {ws.scope_of(division, team)}
        elif division:
            scopes = frozenset(s for s in scopes if s.division == division)
    else:
        scopes = ws.visible(division, team)
    rules = load_rules(ws.db)
    today = today_date(ws.settings)
    facts = gather(ws.records, scopes, ws.settings, look_back(rules, today))
    if view == "mine":
        facts = [c for c in facts if c.owner_id == ws.user.id]
    return facts, rules, today


@router.get("/retention")
def module_retention(ws: WS, view: View = "mine", division: str | None = None, team: str | None = None) -> dict:
    facts, rules, today = module_facts(ws, view, division, team)
    watch = watch_list(facts, rules, today)[:200]
    follow_ups = open_follow_ups(ws.records, ws.visible(), [c.id for c, _, _ in watch])
    return {
        "view": view,
        "canSeeTeam": bool(report_scopes(ws)),
        "asOf": today.isoformat(),
        # One window per division, because each division decides for itself when
        # a customer has gone quiet: a merged list has to group, never average.
        "rules": [
            {
                "division": code,
                "divisionName": ws.division_names.get(code, code),
                "atRiskDays": rules[code].at_risk_days,
                "lostDays": rules[code].lost_days,
            }
            for code in ws.divisions
            if code in rules
        ],
        "summary": summarize(facts, rules, today).out(),
        "trend": trend(facts, rules, today),
        "reps": rep_rows(facts, rules, today) if view == "team" else [],
        "watch": [
            {
                "customerId": c.id,
                "name": c.name,
                "division": c.division,
                "divisionName": ws.division_names.get(c.division, c.division),
                "team": c.team,
                "teamName": ws.team_names.get((c.division, c.team), c.team),
                "owner": {"id": c.owner_id, "name": c.owner_name},
                "health": h,
                "status": c.status,
                "lastQuoteOn": c.last_quote.isoformat() if c.last_quote else None,
                "daysSince": days,
                "followUp": follow_ups.get(c.id),
                "canWinBack": ws.can("create", Scope(c.division, c.team)),
            }
            for c, h, days in watch
        ],
    }


def safe(value: object) -> object:
    # A cell starting with = + - @ is run as a formula by spreadsheets; names come from people.
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/retention/export")
def export_retention(ws: WS, view: View = "mine", division: str | None = None, team: str | None = None) -> Response:
    facts, rules, today = module_facts(ws, view, division, team)
    year_ago = today - timedelta(days=365)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["Customer", "Division", "Team", "Owner", "Status", "Health", "Last quote", "Days since last quote",
         "Quotes in the last 12 months", "Quoted in the last 12 months (PHP)"]
    )
    for c in sorted(facts, key=lambda f: f.name.casefold()):
        recent = [t for d, t in zip(c.quote_days, c.quote_totals) if d > year_ago]
        writer.writerow(
            [safe(v) for v in (
                c.name,
                ws.division_names.get(c.division, c.division),
                ws.team_names.get((c.division, c.team), c.team),
                c.owner_name or "",
                c.status.capitalize(),
                HEALTH_LABELS[health(c, rules[c.division], today)],
                c.last_quote.isoformat() if c.last_quote else "",
                (today - c.last_quote).days if c.last_quote else "",
                len(recent),
                f"{sum(recent) / 100:.2f}",
            )]
        )
    # Named for what is actually in it: one division when asked for one,
    # otherwise everything this person sells.
    where = f"{division}-" if division else ""
    name = f"retention-{where}{view}-{today.isoformat()}.csv"
    # The BOM makes Excel read it as UTF-8, so names like Parañaque survive.
    return Response(
        "﻿" + out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --- across modules ------------------------------------------------------------------


def team_names(db) -> dict[tuple[str, str], str]:
    return {(d, c): n for d, c, n in db.execute(select(Subdivision.division_code, Subdivision.code, Subdivision.name))}


@router.get("/me/at-risk")
def my_at_risk(user: CurrentUser, access: CurrentAccess, db: DB, records: RecordsDep, settings: SettingsDep) -> dict:
    """Customers I own, in every sales division I can see, that have gone quiet."""
    scopes: frozenset[Scope] = frozenset().union(*(access.scopes(k, "view") for k in sales_keys(db)))
    rules = load_rules(db)
    today = today_date(settings)
    # Two windows back: enough to tell "lost lately" from "never quoted".
    since = today - timedelta(days=2 * max(r.lost_days for r in rules.values()) + 1)
    mine = [c for c in gather(records, scopes, settings, since) if c.owner_id == user.id]
    watch = watch_list(mine, rules, today)
    rows = [(c, days) for c, h, days in watch if h == AT_RISK]
    follow_ups = open_follow_ups(records, scopes, [c.id for c, _ in rows])
    names = team_names(db)
    return {
        "today": today.isoformat(),
        "recentlyLost": sum(1 for _, h, _ in watch if h == LOST),
        "items": [
            {
                "customerId": c.id,
                "name": c.name,
                "module": c.division,
                "moduleName": BY_KEY[c.division].name,
                "teamName": names.get((c.division, c.team), c.team),
                "lastQuoteOn": c.last_quote.isoformat() if c.last_quote else None,
                "daysSince": days,
                "lostAfterDays": rules[c.division].lost_days,
                "followUp": follow_ups.get(c.id),
                "canWinBack": access.can_in(c.division, "create", Scope(c.division, c.team)),
            }
            for c, days in rows
        ],
    }


@router.get("/retention/divisions")
def divisions(access: CurrentAccess, db: DB, records: RecordsDep, settings: SettingsDep) -> dict:
    """Each division I have Reports in, side by side, and all of them together."""
    rules = load_rules(db)
    today = today_date(settings)
    since = look_back(rules, today)
    rows, everyone = [], []
    for key in sales_keys(db):
        scopes = frozenset(s for s in access.scopes(key, REPORT) if s.division == key)
        if not scopes:
            continue
        facts = gather(records, scopes, settings, since)
        everyone += facts
        rows.append(
            {
                "code": key,
                "name": BY_KEY[key].name,
                "rules": {"atRiskDays": rules[key].at_risk_days, "lostDays": rules[key].lost_days},
                "summary": summarize(facts, rules, today).out(),
                "trend": trend(facts, rules, today),
            }
        )
    if not rows:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Division figures need Reports access. Ask your admin.")
    return {
        "asOf": today.isoformat(),
        "divisions": rows,
        "total": {"summary": summarize(everyone, rules, today).out(), "trend": trend(everyone, rules, today)},
    }


# --- settings ------------------------------------------------------------------------


def rules_out(db) -> dict:
    rules = load_rules(db)
    divisions = db.scalars(select(Division).where(Division.code.in_(sales_keys(db))).order_by(Division.sort_order))
    return {
        "divisions": [
            {"code": d.code, "name": d.name, "atRiskDays": rules[d.code].at_risk_days, "lostDays": rules[d.code].lost_days}
            for d in divisions
        ]
    }


@router.get("/admin/retention", tags=["settings"], dependencies=[Depends(require_settings)])
def retention_rules(db: DB) -> dict:
    return rules_out(db)


@router.put("/admin/retention", tags=["settings"], dependencies=[Depends(require_settings)])
def replace_retention_rules(body: RetentionRulesIn, db: DB, me: CurrentUser) -> dict:
    for code in body.divisions:
        if code not in sales_keys(db):
            raise invalid(f"{code} isn't a sales division.")
    for code, rule in body.divisions.items():
        row = org_get(db, RetentionRule, code) or RetentionRule(division_code=code)
        row.at_risk_days, row.lost_days = rule.at_risk_days, rule.lost_days
        db.add(row)
    db.commit()
    audit(db, me, "retention.rules_changed", ", ".join(sorted(body.divisions)))
    return rules_out(db)
