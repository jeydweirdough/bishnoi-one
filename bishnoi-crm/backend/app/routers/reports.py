"""The CRM's reports (decided 2026-10-25, benchmarks/surpass.md §11): one registry, each report in
a group (Sales, Customers, Activities, Field sales, Performance) and needing the permission for
its data. Every figure is narrowed to the person's reach (app/scope.py): a rep sees their own
work, a team lead their team's, a manager the teams they manage, an administrator everyone's.
The one app draws any of them with the shared report kit (src/platform/reports/).

- GET /reports: the reports this person may open.
- GET /reports/{key}?from&to&owner: one report: columns, rows, headline figures, chart.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.access import Access, CurrentAccess
from app.deps import DB, CurrentUser, SettingsDep
from app.models import (
    PLANNED_KINDS,
    Activity,
    AssistanceApplication,
    Company,
    CustomerType,
    Deal,
    DealStage,
    Quote,
    User,
    Visit,
)
from app.scope import reachable_people, within

router = APIRouter(prefix="/reports", tags=["reports"])


def col(key: str, label: str, kind: str = "text") -> dict:
    """kind: text, number, money, date, datetime, percent (a fraction)."""
    return {"key": key, "label": label, "kind": kind}


def fig(label: str, value, kind: str = "number", tone: str | None = None) -> dict:
    return {"label": label, "value": value, "kind": kind, **({"tone": tone} if tone else {})}


def bar(x: str, *series: str) -> dict:
    return {"kind": "bar", "x": x, "series": list(series)}


@dataclass
class Ctx:
    db: DB
    access: Access
    me: User
    start: datetime
    end: datetime
    first_day: date
    last_day: date
    owner: str | None
    names: dict[str, str]

    def scoped(self, query, model):
        """Within the person's reach, and to one owner when the filter asks for one in reach."""
        query = within(query, model, self.access)
        return query.where(model.owner_id == self.owner) if self.owner else query

    def name(self, user_id: str | None) -> str:
        return self.names.get(user_id or "", "Someone else")


@dataclass
class Report:
    key: str
    title: str
    group: str
    about: str
    build: Callable[[Ctx], tuple]
    needs: tuple[str, ...]
    dated: bool = True


# --- Sales -----------------------------------------------------------------------------------------


def pipeline(c: Ctx):
    stages = {s.code: s for s in c.db.scalars(select(DealStage))}
    rows: dict[str, dict] = {}
    for d in c.db.scalars(c.scoped(select(Deal), Deal)):
        s = stages.get(d.stage_code)
        if s is None or s.outcome != "open":
            continue
        r = rows.setdefault(s.code, {"stage": s.name, "order": s.sort_order, "deals": 0, "value": 0, "weighted": 0})
        r["deals"] += 1
        r["value"] += d.value_centavos
        r["weighted"] += d.value_centavos * d.probability // 100
    out = sorted(rows.values(), key=lambda r: r["order"])
    for r in out:
        r.pop("order")
    return (
        [col("stage", "Stage"), col("deals", "Open deals", "number"), col("value", "Value", "money"), col("weighted", "Weighted value", "money")],
        out,
        [fig("Open deals", sum(r["deals"] for r in out)), fig("Pipeline value", sum(r["value"] for r in out), "money"), fig("Weighted value", sum(r["weighted"] for r in out), "money", "good")],
        bar("stage", "value", "weighted"),
    )


def deals_closed(c: Ctx):
    stages = {s.code: s.outcome for s in c.db.scalars(select(DealStage))}
    q = c.scoped(select(Deal), Deal).where(Deal.closed_at >= c.start, Deal.closed_at < c.end)
    by: dict[str, dict] = {}
    for d in c.db.scalars(q):
        outcome = stages.get(d.stage_code)
        if outcome not in ("won", "lost"):
            continue
        r = by.setdefault(d.owner_id, {"owner": c.name(d.owner_id), "won": 0, "wonValue": 0, "lost": 0, "lostValue": 0})
        r["won" if outcome == "won" else "lost"] += 1
        r["wonValue" if outcome == "won" else "lostValue"] += d.value_centavos
    rows = sorted(by.values(), key=lambda r: -r["wonValue"])
    for r in rows:
        r["winRate"] = round(r["won"] / (r["won"] + r["lost"]), 3) if r["won"] + r["lost"] else None
    won, lost = sum(r["won"] for r in rows), sum(r["lost"] for r in rows)
    return (
        [col("owner", "Owner"), col("won", "Won", "number"), col("wonValue", "Won value", "money"), col("lost", "Lost", "number"), col("lostValue", "Lost value", "money"), col("winRate", "Win rate", "percent")],
        rows,
        [fig("Won", won, tone="good"), fig("Won value", sum(r["wonValue"] for r in rows), "money", "good"), fig("Lost", lost, tone="bad" if lost else None), fig("Win rate", round(won / (won + lost), 3) if won + lost else None, "percent")],
        bar("owner", "wonValue", "lostValue"),
    )


def lost_reasons(c: Ctx):
    stages = {s.code: s.outcome for s in c.db.scalars(select(DealStage))}
    q = c.scoped(select(Deal), Deal).where(Deal.closed_at >= c.start, Deal.closed_at < c.end)
    by: dict[str, dict] = {}
    for d in c.db.scalars(q):
        if stages.get(d.stage_code) != "lost":
            continue
        reason = (d.lost_reason or "No reason given").strip()
        r = by.setdefault(reason, {"reason": reason, "deals": 0, "value": 0})
        r["deals"] += 1
        r["value"] += d.value_centavos
    rows = sorted(by.values(), key=lambda r: -r["deals"])
    return ([col("reason", "Lost reason"), col("deals", "Deals", "number"), col("value", "Value", "money")], rows, [fig("Deals lost", sum(r["deals"] for r in rows))], bar("reason", "deals"))


def quotes_by_person(c: Ctx):
    q = c.scoped(select(Quote), Quote).where(Quote.created_at >= c.start, Quote.created_at < c.end)
    by: dict[str, dict] = {}
    for x in c.db.scalars(q):
        r = by.setdefault(x.owner_id, {"owner": c.name(x.owner_id), "quotes": 0, "value": 0, "approved": 0, "rejected": 0, "ordered": 0})
        r["quotes"] += 1
        r["value"] += x.total_centavos
        r["approved"] += x.approval_status == "approved"
        r["rejected"] += x.approval_status == "rejected"
        r["ordered"] += bool(x.sales_order)
    rows = sorted(by.values(), key=lambda r: -r["value"])
    for r in rows:
        r["conversion"] = round(r["ordered"] / r["quotes"], 3) if r["quotes"] else None
    n, ordered = sum(r["quotes"] for r in rows), sum(r["ordered"] for r in rows)
    return (
        [col("owner", "Owner"), col("quotes", "Quotes", "number"), col("value", "Value", "money"), col("approved", "Approved", "number"), col("rejected", "Rejected", "number"), col("ordered", "Ordered", "number"), col("conversion", "Quote to order", "percent")],
        rows,
        [fig("Quotes", n), fig("Quoted value", sum(r["value"] for r in rows), "money"), fig("Ordered", ordered, tone="good"), fig("Quote to order", round(ordered / n, 3) if n else None, "percent")],
        bar("owner", "value"),
    )


# --- Customers -------------------------------------------------------------------------------------


def type_names(c: Ctx) -> dict[str, str]:
    return {t.code: t.name for t in c.db.scalars(select(CustomerType))}


def new_customers(c: Ctx):
    types = type_names(c)
    q = c.scoped(select(Company), Company).where(Company.created_at >= c.start, Company.created_at < c.end).order_by(Company.created_at.desc())
    rows = [{"customer": x.name, "code": x.code or "", "type": types.get(x.status, x.status), "city": x.city or "", "owner": c.name(x.owner_id), "created": x.created_at.isoformat()} for x in c.db.scalars(q)]
    by_owner: dict[str, int] = defaultdict(int)
    for r in rows:
        by_owner[r["owner"]] += 1
    return (
        [col("customer", "Customer"), col("code", "Code"), col("type", "Type"), col("city", "City"), col("owner", "Owner"), col("created", "Added", "datetime")],
        rows,
        [fig("New customers", len(rows), tone="good" if rows else None), fig("People who added them", len(by_owner))],
        None,
    )


def customers_by_type(c: Ctx):
    types = type_names(c)
    q = c.scoped(select(Company.status, func.count()), Company).group_by(Company.status)
    rows = sorted(({"type": types.get(s, s), "customers": n} for s, n in c.db.execute(q)), key=lambda r: -r["customers"])
    return ([col("type", "Type"), col("customers", "Customers", "number")], rows, [fig("Customers", sum(r["customers"] for r in rows)), fig("Types", len(rows))], bar("type", "customers"))


def quiet_customers(c: Ctx):
    """Customers with no activity or visit in the last 60 days (from the period's end)."""
    since = c.end - timedelta(days=60)
    types = type_names(c)
    last_act = dict(c.db.execute(select(Activity.company_id, func.max(Activity.at)).where(Activity.company_id.is_not(None)).group_by(Activity.company_id)).all())
    last_visit = dict(c.db.execute(select(Visit.company_id, func.max(Visit.visited_at)).group_by(Visit.company_id)).all())
    rows = []
    for x in c.db.scalars(c.scoped(select(Company), Company).order_by(Company.name)):
        seen = [t for t in (last_act.get(x.id), last_visit.get(x.id)) if t]
        last = max(seen) if seen else None
        if last is not None and (last if last.tzinfo else last.replace(tzinfo=UTC)) >= since:
            continue
        rows.append({"customer": x.name, "type": types.get(x.status, x.status), "owner": c.name(x.owner_id), "last": last.isoformat() if last else None})
    rows.sort(key=lambda r: r["last"] or "")
    return (
        [col("customer", "Customer"), col("type", "Type"), col("owner", "Owner"), col("last", "Last activity or visit", "datetime")],
        rows,
        [fig("Quiet customers", len(rows), tone="warn" if rows else None), fig("Never contacted", sum(1 for r in rows if not r["last"]), tone="bad" if any(not r["last"] for r in rows) else None)],
        None,
    )


# --- Activities ------------------------------------------------------------------------------------


def activities_by_person(c: Ctx):
    q = c.scoped(select(Activity), Activity).where(Activity.done_at >= c.start, Activity.done_at < c.end)
    by: dict[str, dict] = {}
    for a in c.db.scalars(q):
        r = by.setdefault(a.owner_id, {"owner": c.name(a.owner_id), "call": 0, "meeting": 0, "email": 0, "task": 0, "note": 0, "total": 0})
        if a.kind in r:
            r[a.kind] += 1
        r["total"] += 1
    rows = sorted(by.values(), key=lambda r: -r["total"])
    return (
        [col("owner", "Person"), col("call", "Calls", "number"), col("meeting", "Meetings", "number"), col("email", "Emails", "number"), col("task", "Tasks", "number"), col("note", "Notes", "number"), col("total", "Total", "number")],
        rows,
        [fig("Activities done", sum(r["total"] for r in rows)), fig("Calls", sum(r["call"] for r in rows)), fig("Meetings", sum(r["meeting"] for r in rows))],
        bar("owner", "total"),
    )


def overdue_activities(c: Ctx):
    now = datetime.now(UTC)
    q = c.scoped(select(Activity), Activity).where(Activity.kind.in_(PLANNED_KINDS), Activity.done_at.is_(None), Activity.at < now).order_by(Activity.at)
    names = {x.id: x.name for x in c.db.scalars(select(Company))}
    rows = [{"due": a.at.isoformat(), "kind": a.kind.capitalize(), "subject": a.subject, "customer": names.get(a.company_id or "", ""), "owner": c.name(a.owner_id),
             "daysLate": (now - (a.at if a.at.tzinfo else a.at.replace(tzinfo=UTC))).days} for a in c.db.scalars(q)]
    return (
        [col("due", "Due", "datetime"), col("daysLate", "Days late", "number"), col("kind", "Kind"), col("subject", "Subject"), col("customer", "Customer"), col("owner", "Owner")],
        rows,
        [fig("Overdue", len(rows), tone="bad" if rows else "good"), fig("Over 7 days late", sum(1 for r in rows if r["daysLate"] > 7), tone="bad" if any(r["daysLate"] > 7 for r in rows) else None)],
        None,
    )


# --- Field sales -----------------------------------------------------------------------------------


def visits_by_agent(c: Ctx):
    q = c.scoped(select(Visit), Visit).where(Visit.visited_at >= c.start, Visit.visited_at < c.end)
    by: dict[str, dict] = {}
    places: dict[str, set] = defaultdict(set)
    for v in c.db.scalars(q):
        r = by.setdefault(v.owner_id, {"agent": c.name(v.owner_id), "visits": 0, "accounts": 0, "detailed": 0, "collected": 0})
        r["visits"] += 1
        r["detailed"] += v.outcome == "detailed"
        r["collected"] += v.amount_centavos if v.outcome == "collected" else 0
        places[v.owner_id].add(v.company_id)
    for owner, r in by.items():
        r["accounts"] = len(places[owner])
    rows = sorted(by.values(), key=lambda r: -r["visits"])
    return (
        [col("agent", "Agent"), col("visits", "Visits", "number"), col("accounts", "Different accounts", "number"), col("detailed", "Detailed", "number"), col("collected", "Collected", "money")],
        rows,
        [fig("Visits", sum(r["visits"] for r in rows)), fig("Accounts reached", len(set().union(*places.values())) if places else 0), fig("Collected", sum(r["collected"] for r in rows), "money")],
        bar("agent", "visits", "accounts"),
    )


TIER_VISITS = {1: 4, 2: 2, 3: 1}


def coverage(c: Ctx):
    """Each agent's tiered accounts against the visits the period gave them (tier 1: 4 a month, tier 2: 2, tier 3: 1)."""
    seen: dict[tuple, int] = defaultdict(int)
    for owner, company in c.db.execute(c.scoped(select(Visit.owner_id, Visit.company_id), Visit).where(Visit.visited_at >= c.start, Visit.visited_at < c.end)):
        seen[(owner, company)] += 1
    by: dict[str, dict] = {}
    for x in c.db.scalars(c.scoped(select(Company), Company).where(Company.field_tier.is_not(None))):
        r = by.setdefault(x.owner_id, {"agent": c.name(x.owner_id), "accounts": 0, "visited": 0, "onPlan": 0, "tier1": 0, "tier1Four": 0})
        n = seen.get((x.owner_id, x.id), 0)
        r["accounts"] += 1
        r["visited"] += n > 0
        r["onPlan"] += n >= TIER_VISITS.get(x.field_tier or 3, 1)
        if x.field_tier == 1:
            r["tier1"] += 1
            r["tier1Four"] += n >= 4
    rows = sorted(by.values(), key=lambda r: r["agent"].lower())
    for r in rows:
        r["coverage"] = round(r["visited"] / r["accounts"], 3) if r["accounts"] else None
    total, visited = sum(r["accounts"] for r in rows), sum(r["visited"] for r in rows)
    cov = round(visited / total, 3) if total else None
    return (
        [col("agent", "Agent"), col("accounts", "Tiered accounts", "number"), col("visited", "Visited", "number"), col("coverage", "Coverage", "percent"), col("onPlan", "On plan for their tier", "number"), col("tier1", "Tier 1", "number"), col("tier1Four", "Tier 1 seen 4 times", "number")],
        rows,
        [fig("Coverage", cov, "percent", None if cov is None else ("good" if cov >= 0.8 else "warn")), fig("Accounts visited", visited), fig("Tiered accounts", total)],
        bar("agent", "coverage"),
    )


def assistance(c: Ctx):
    q = c.scoped(select(AssistanceApplication), AssistanceApplication)
    first, last = c.first_day.isoformat(), c.last_day.isoformat()
    today = datetime.now(UTC).date()
    by: dict[str, dict] = {}
    for a in c.db.scalars(q):
        filed_in = first <= a.submitted_on <= last
        decided_in = a.decided_on is not None and first <= a.decided_on <= last
        pending = a.status == "pending"
        if not (filed_in or decided_in or pending):
            continue
        r = by.setdefault(a.owner_id, {"agent": c.name(a.owner_id), "filed": 0, "approved": 0, "denied": 0, "pending": 0, "followUp": 0})
        r["filed"] += filed_in
        r["approved"] += decided_in and a.status == "approved"
        r["denied"] += decided_in and a.status == "denied"
        if pending:
            r["pending"] += 1
            r["followUp"] += (today - date.fromisoformat(a.submitted_on)).days > 7
    rows = sorted(by.values(), key=lambda r: -r["approved"])
    return (
        [col("agent", "Agent"), col("filed", "Filed", "number"), col("approved", "Approved (PAP)", "number"), col("denied", "Denied", "number"), col("pending", "Pending", "number"), col("followUp", "Pending over 7 days", "number")],
        rows,
        [fig("Approved", sum(r["approved"] for r in rows), tone="good"), fig("Filed", sum(r["filed"] for r in rows)), fig("Pending over 7 days", sum(r["followUp"] for r in rows), tone="warn" if any(r["followUp"] for r in rows) else None)],
        bar("agent", "approved", "filed"),
    )


REACTIONS = {"will_prescribe": "Will prescribe", "already_prescribes": "Already prescribes", "interested": "Interested", "neutral": "Neutral", "concerns": "Has concerns", "not_interested": "Not interested"}


def products_presented(c: Ctx):
    by: dict[str, dict] = {}
    for v in c.db.scalars(c.scoped(select(Visit), Visit).where(Visit.visited_at >= c.start, Visit.visited_at < c.end)):
        for d in v.detailing or []:
            name = d.get("productName") or "Product"
            r = by.setdefault(name, {"product": name, "presented": 0, "positive": 0, "neutral": 0, "negative": 0})
            r["presented"] += 1
            reaction = d.get("reaction")
            r["positive" if reaction in ("will_prescribe", "already_prescribes", "interested") else "negative" if reaction in ("concerns", "not_interested") else "neutral"] += 1
    rows = sorted(by.values(), key=lambda r: -r["presented"])
    for r in rows:
        r["positiveRate"] = round(r["positive"] / r["presented"], 3) if r["presented"] else None
    return (
        [col("product", "Product"), col("presented", "Times presented", "number"), col("positive", "Positive", "number"), col("neutral", "Neutral", "number"), col("negative", "Concerns or not interested", "number"), col("positiveRate", "Positive share", "percent")],
        rows,
        [fig("Presentations", sum(r["presented"] for r in rows)), fig("Products", len(rows))],
        bar("product", "positive", "negative"),
    )


# --- Performance -----------------------------------------------------------------------------------


def scorecard_results(c: Ctx):
    """Each person's scorecard for the period's month (app/scorecards.py), every card in reach."""
    from app.routers.kpis import scorecards

    month = c.last_day.strftime("%Y-%m")
    settings = c.db.info.get("settings")
    first = scorecards(c.access, c.me, c.db, settings, month, None)
    rows = []
    for card in first["cards"]:
        got = first if first["card"] and first["card"]["code"] == card["code"] else scorecards(c.access, c.me, c.db, settings, month, card["code"])
        for p in got["people"]:
            rows.append({"person": p["person"]["name"], "team": (p.get("team") or {}).get("name") or "", "card": card["name"], "total": p["total"], "outOf": p["outOf"],
                         "percent": (p["percent"] / 100) if p["percent"] is not None else None, "band": (p.get("band") or {}).get("label") or "", "capped": (p.get("cap") or {}).get("why") or ""})
    rows.sort(key=lambda r: -(r["percent"] or 0))
    scored = [r for r in rows if r["percent"] is not None]
    return (
        [col("person", "Person"), col("team", "Team"), col("card", "Scorecard"), col("total", "Points", "number"), col("outOf", "Out of", "number"), col("percent", "Score", "percent"), col("band", "Band"), col("capped", "Capped by")],
        rows,
        [fig("People scored", len(scored)), fig("Average score", round(sum(r["percent"] for r in scored) / len(scored), 3) if scored else None, "percent"), fig("Below standard", sum(1 for r in scored if r["band"] == "Below standard"), tone="bad" if any(r["band"] == "Below standard" for r in scored) else None)],
        bar("person", "percent"),
    )


# --- Retention (the Retention page's own rules, app/routers/retention.py) --------------------------

HEALTH = {"healthy": "Healthy", "at_risk": "At risk", "lost": "Lost", "no_quotes": "No quotes yet"}


def _book(c: Ctx):
    from app.routers.retention import Book, Windows

    settings = c.db.info["settings"]
    view = "mine" if c.access.scope == "own" else "team"
    book = Book(c.db, c.access, view, None, settings.org_timezone)
    if c.owner:
        book.companies = [x for x in book.companies if x.owner_id == c.owner]
    return book, Windows(c.db)


def retention_by_team(c: Ctx):
    """Each department's customers by health, and its retention rate, as of the period's last day."""
    from app.models import Team
    from app.routers.retention import health, rate

    book, windows = _book(c)
    on = c.last_day
    teams = {t.id: t.name for t in c.db.scalars(select(Team))}
    by: dict[str, dict] = {}
    for x in book.companies:
        at_risk, lost = windows.of(x)
        r = by.setdefault(x.team_id or "", {"team": teams.get(x.team_id, "No team"), "customers": 0, "healthy": 0, "atRisk": 0, "lost": 0, "noQuotes": 0, "base": 0, "kept": 0})
        r["customers"] += 1
        h = health(x, book.last(x.id, on), on, at_risk, lost)
        r[{"healthy": "healthy", "at_risk": "atRisk", "lost": "lost", "no_quotes": "noQuotes"}[h]] += 1
        window = timedelta(days=lost)
        earlier = book.quoted_between(x.id, on - 2 * window, on - window)
        r["base"] += earlier
        r["kept"] += earlier and book.quoted_between(x.id, on - window, on)
    rows = sorted(by.values(), key=lambda r: r["team"].lower())
    for r in rows:
        r["rate"] = (rate(r["base"], r["kept"]) or 0) / 100 if r["base"] else None
    base, kept = sum(r["base"] for r in rows), sum(r["kept"] for r in rows)
    overall = kept / base if base else None
    at_risk = sum(r["atRisk"] for r in rows)
    return (
        [col("team", "Department"), col("customers", "Customers", "number"), col("rate", "Retention rate", "percent"), col("healthy", "Healthy", "number"), col("atRisk", "At risk", "number"),
         col("lost", "Lost", "number"), col("noQuotes", "No quotes yet", "number")],
        [{k: v for k, v in r.items() if k not in ("base", "kept")} for r in rows],
        [fig("Retention rate", overall, "percent", None if overall is None else ("good" if overall >= 0.8 else "warn")), fig("At risk now", at_risk, tone="warn" if at_risk else "good"),
         fig("Lost", sum(r["lost"] for r in rows), tone="bad" if any(r["lost"] for r in rows) else None)],
        bar("team", "healthy", "atRisk", "lost"),
    )


def retention_trend(c: Ctx):
    """The retention rate month by month (six months to the period's end)."""
    from app.routers.retention import trend

    book, windows = _book(c)
    points = trend(book, c.last_day, windows)
    rows = [{"month": p["month"], "rate": (p["rate"] / 100) if p["rate"] is not None else None, "base": p["base"], "retained": p["retained"], "lost": p["base"] - p["retained"]} for p in points]
    last = next((r for r in reversed(rows) if r["rate"] is not None), None)
    first = next((r for r in rows if r["rate"] is not None), None)
    change = round(last["rate"] - first["rate"], 3) if last and first else None
    return (
        [col("month", "Month"), col("rate", "Retention rate", "percent"), col("base", "Customers to keep", "number"), col("retained", "Kept", "number"), col("lost", "Not back", "number")],
        rows,
        [fig("This month", last["rate"] if last else None, "percent"), fig("Change over the year", change, "percent", None if change is None else ("good" if change >= 0 else "bad"))],
        {"kind": "line", "x": "month", "series": ["rate"]},
    )


def customers_at_risk(c: Ctx):
    """Customers slipping away: at risk, or lost recently enough to win back, longest quiet first."""
    from app.routers.retention import rows as slipping

    book, windows = _book(c)
    found = slipping(c.db, c.access, book, c.last_day, windows, only_slipping=True)
    rows = [{"customer": r["name"], "team": r["teamName"], "owner": r["owner"]["name"] or "", "health": HEALTH[r["health"]], "lastQuote": r["lastQuoteOn"], "days": r["daysSince"],
             "followUp": (r["followUp"] or {}).get("dueOn")} for r in found]
    planned = sum(1 for r in rows if r["followUp"])
    return (
        [col("customer", "Customer"), col("health", "Health"), col("days", "Days since last quote", "number"), col("lastQuote", "Last quote", "date"), col("followUp", "Follow-up due", "date"),
         col("owner", "Owner"), col("team", "Department")],
        rows,
        [fig("Slipping", len(rows), tone="warn" if rows else "good"), fig("With a follow-up planned", planned, tone="good" if planned == len(rows) else "warn")],
        None,
    )


# --- Performance: the KPIs (Deals' results, app/routers/sales.py) ---------------------------------


def _results(c: Ctx) -> dict:
    from app.routers.sales import results

    view = "mine" if c.access.scope == "own" else "team"
    return results(c.db, c.access, c.db.info["settings"], view, c.last_day.strftime("%Y-%m"), None)


def sales_attainment(c: Ctx):
    """Each salesperson's month: target, won, attainment, win rate and quoted (the month the period ends in)."""
    r = _results(c)
    rows = []
    for p in r["people"]:
        if c.owner and p["person"]["id"] != c.owner:
            continue
        rows.append({"person": p["person"]["name"], "team": (p.get("team") or {}).get("name") or "", "target": p.get("targetCentavos"), "won": p["wonCentavos"],
                     "attainment": (p["attainment"] / 100) if p.get("attainment") is not None else None, "winRate": (p["winRate"] / 100) if p.get("winRate") is not None else None,
                     "quoted": p["quotedCentavos"], "deals": p["wonCount"]})
    rows.sort(key=lambda x: -(x["attainment"] or 0))
    t = r["totals"]
    att = (t["attainment"] / 100) if t.get("attainment") is not None else None
    behind = sum(1 for x in rows if x["attainment"] is not None and x["attainment"] < 0.8)
    return (
        [col("person", "Salesperson"), col("team", "Team"), col("target", "Target", "money"), col("won", "Won", "money"), col("attainment", "Attainment", "percent"),
         col("winRate", "Win rate", "percent"), col("quoted", "Quoted", "money"), col("deals", "Deals won", "number")],
        rows,
        [fig(f"Attainment, {r['label']}", att, "percent", None if att is None else ("good" if att >= 1 else "warn")), fig("Won", t["wonCentavos"], "money"),
         fig("Below 80% of target", behind, tone="warn" if behind else "good")],
        bar("person", "target", "won"),
    )


def top_customers(c: Ctx):
    """Revenue by customer for the month, ranked, with each one's share and A/B/C class (A: the top 80% of revenue)."""
    r = _results(c)
    total = sum(x["wonCentavos"] for x in r["customers"]) or 0
    rows, running = [], 0
    for x in r["customers"]:
        running += x["wonCentavos"]
        share = running / total if total else 0
        rows.append({"customer": x["customer"]["name"], "won": x["wonCentavos"], "deals": x["wonCount"], "share": x["wonCentavos"] / total if total else None, "cumulative": share,
                     "class": "A" if share <= 0.8 or not rows else "B" if share <= 0.95 else "C"})
    a = sum(1 for x in rows if x["class"] == "A")
    return (
        [col("customer", "Customer"), col("class", "Class"), col("won", "Won", "money"), col("share", "Share", "percent"), col("cumulative", "Cumulative share", "percent"), col("deals", "Deals", "number")],
        rows,
        [fig("Customers buying", len(rows)), fig("Class A (80% of revenue)", a), fig("Revenue", total, "money")],
        bar("customer", "won") if rows else None,
    )


def top_products(c: Ctx):
    """What sold in the month: each product's units and revenue from deals won, ranked."""
    r = _results(c)
    total = sum(x["wonCentavos"] for x in r["products"]) or 0
    rows = [{"product": x["product"]["name"], "units": x["quantity"], "won": x["wonCentavos"], "share": x["wonCentavos"] / total if total else None} for x in r["products"]]
    return (
        [col("product", "Product"), col("units", "Units", "number"), col("won", "Revenue", "money"), col("share", "Share", "percent")],
        rows,
        [fig("Products sold", len(rows)), fig("Revenue", total, "money")],
        bar("product", "won") if rows else None,
    )


REPORTS: tuple[Report, ...] = (
    Report("pipeline", "Pipeline by stage", "Sales", "Open deals in each stage, with their value and weighted value.", pipeline, ("deals.view",), dated=False),
    Report("deals-closed", "Deals won and lost", "Sales", "Deals closed in the period, by owner, with the win rate.", deals_closed, ("deals.view",)),
    Report("lost-reasons", "Lost deals by reason", "Sales", "Why deals were lost in the period.", lost_reasons, ("deals.view",)),
    Report("quotes", "Quotes by person", "Sales", "Quotes made in the period: value, approved, rejected, and how many became orders.", quotes_by_person, ("quotes.view",)),
    Report("new-customers", "New customers", "Customers", "Customers added in the period, with who added them.", new_customers, ("customers.view",)),
    Report("customers-by-type", "Customers by type", "Customers", "How many customers of each type.", customers_by_type, ("customers.view",), dated=False),
    Report("quiet-customers", "Customers without recent activity", "Customers", "No activity or visit in the 60 days before the period ends.", quiet_customers, ("customers.view",)),
    Report("activities", "Activities by person", "Activities", "Calls, meetings, emails, tasks and notes done in the period.", activities_by_person, ("activities.view",)),
    Report("overdue-activities", "Overdue activities", "Activities", "Meetings and tasks past their time and not done.", overdue_activities, ("activities.view",), dated=False),
    Report("visits", "Visits by agent", "Field sales", "Visits in the period: different accounts reached, detailed, collected.", visits_by_agent, ("visits.view",)),
    Report("coverage", "Coverage by tier", "Field sales", "Tiered accounts visited in the period, and on plan for their tier (4, 2 or 1 visits).", coverage, ("visits.view",)),
    Report("assistance", "Patient assistance", "Field sales", "Applications filed, approved, denied and pending, by agent.", assistance, ("visits.view",)),
    Report("products-presented", "Products presented", "Field sales", "Each product presented on visits, and how doctors took it.", products_presented, ("visits.view",)),
    Report("scorecards", "Scorecard results", "Performance", "Each person's playbook scorecard for the month the period ends in.", scorecard_results, ("goals.view", "reports.view")),
    Report("sales-attainment", "Sales against target", "Performance", "Each salesperson's month: target, won, attainment, win rate and quoted.", sales_attainment, ("deals.view",)),
    Report("top-customers", "Top customers (A/B/C)", "Performance", "Revenue by customer for the month, ranked, with each one's share and class.", top_customers, ("deals.view",)),
    Report("top-products", "Top products", "Performance", "Units and revenue by product from deals won in the month.", top_products, ("deals.view",)),
    Report("retention-by-department", "Retention by department", "Retention", "Each department's customers by health, and its retention rate, as of the period's end.", retention_by_team, ("customers.view",), dated=False),
    Report("retention-trend", "Retention trend", "Retention", "The retention rate month by month, for the six months to the period's end.", retention_trend, ("customers.view",), dated=False),
    Report("customers-at-risk", "Customers at risk", "Retention", "Customers slipping away, longest without a quote first, with any follow-up planned.", customers_at_risk, ("customers.view",), dated=False),
)
BY_KEY = {r.key: r for r in REPORTS}


def allowed(r: Report, access: Access) -> bool:
    return access.can_any(*r.needs)


@router.get("")
def list_reports(access: CurrentAccess) -> list[dict]:
    """The reports this person may open, each with its group (the sidebar's report groups)."""
    return [{"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated} for r in REPORTS if allowed(r, access)]


@router.get("/{key}")
def read_report(
    access: CurrentAccess,
    me: CurrentUser,
    db: DB,
    settings: SettingsDep,
    key: str,
    start: date | None = Query(None, alias="from"),
    end: date | None = Query(None, alias="to"),
    owner: str | None = Query(None, max_length=36),
) -> dict:
    r = BY_KEY.get(key)
    if r is None or not allowed(r, access):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such report.")
    zone = ZoneInfo(settings.org_timezone)
    today = datetime.now(zone).date()
    end = end or today
    start = start or end.replace(day=1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The period starts after it ends.")
    people = reachable_people(db, access)
    names = {u.id: ("You" if u.id == me.id else u.full_name) for u in people}
    names.update({u.id: u.full_name for u in db.scalars(select(User)) if u.id not in names})
    if owner and owner not in {u.id for u in people}:
        owner = None
    db.info["settings"] = settings
    ctx = Ctx(db=db, access=access, me=me, start=datetime.combine(start, time.min, zone), end=datetime.combine(end + timedelta(days=1), time.min, zone),
              first_day=start, last_day=end, owner=owner, names=names)
    columns, rows, summary, chart = r.build(ctx)
    # Whose work: only for a role that reaches more than its own.
    filters = [] if access.scope == "own" else [{"key": "owner", "label": "Person", "options": [{"value": "", "label": "Everyone in reach"}] + [{"value": u.id, "label": names[u.id]} for u in people]}]
    return {"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "from": start.isoformat(), "to": end.isoformat(),
            "filters": filters, "columns": columns, "rows": rows, "summary": summary, "chart": chart}
