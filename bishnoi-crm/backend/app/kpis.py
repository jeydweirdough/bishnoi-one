"""KPIs: what the CRM can measure for a person in a month, and how a result is
judged against its target.

A KPI (models.Kpi) counts one of MEASURES below, maybe narrowed by a filter,
or is entered by hand ("manual"). Every measure gives, for each person, a
number and, for a rate, what it's out of; a team's result adds those up first,
so a team's win rate is its deals won out of its deals decided, not an average
of rates.

Status, for a KPI with a target: how far the result is towards it, as a
percentage (for "lower is better", the target over the result). In the month
that's still running, a count or an amount where higher is better is judged
against the pace (the target spread evenly over the month so far), so the 3rd
of the month isn't red. Green from the KPI's green_at, amber from amber_at.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ACTIVITY_KINDS, VISIT_OUTCOMES, Activity, AssistanceApplication, AuditEntry, Company, Deal, DealStage, Kpi, KpiEntry, KpiTarget, Quote, Visit

# A person's figure for a measure: (value, out of) — "out of" only for a rate.
Figure = tuple[int, int | None]


@dataclass
class Period:
    """A month, as the measures need it: [start, end) in UTC, and as dates."""

    month: str
    start: datetime
    end: datetime
    first_day: str  # YYYY-MM-DD, the company's own
    next_first_day: str
    # The company's today (YYYY-MM-DD) and its settings, for the measures read from Finance.
    today: str | None = None
    settings: Any = None
    _feeds: dict = field(default_factory=dict)

    def sales(self, previous: bool = False) -> dict | None:
        """Finance's invoices for this month (or the one before), read once per period."""
        from app.finance import sales_feed

        if self.settings is None:
            return None
        first, after = date.fromisoformat(self.first_day), self.next_first_day
        if previous:
            after = self.first_day
            first = (first - timedelta(days=1)).replace(day=1)
        key = (first.isoformat(), after)
        if key not in self._feeds:
            self._feeds[key] = sales_feed(self.settings, *key)
        return self._feeds[key]

    def working_days(self) -> int:
        """Monday to Saturday from the 1st to today (the whole month once it's over), as the playbooks count sales days."""
        first, last = date.fromisoformat(self.first_day), date.fromisoformat(self.next_first_day) - timedelta(days=1)
        if self.today:
            last = min(last, date.fromisoformat(self.today))
        return sum(1 for i in range((last - first).days + 1) if (first + timedelta(days=i)).weekday() < 6)


@dataclass
class Measure:
    label: str
    unit: str  # count | money | percent
    about: str
    # The filter it takes, if any: "kind" (activity kind), "outcome" (visit outcome), "productId".
    filter: str | None
    count: Callable[[Session, list[str], Period, dict], dict[str, Figure]]


def _per_owner(db: Session, query) -> dict[str, Figure]:
    return {owner: (int(value or 0), None) for owner, value in db.execute(query)}


def _visits(db, users, p, f):
    q = select(Visit.owner_id, func.count()).where(Visit.owner_id.in_(users), Visit.visited_at >= p.start, Visit.visited_at < p.end)
    if f.get("outcome"):
        q = q.where(Visit.outcome == f["outcome"])
    return _per_owner(db, q.group_by(Visit.owner_id))


def _doctors_visited(db, users, p, f):
    q = select(Visit.owner_id, func.count(func.distinct(Visit.company_id))).where(Visit.owner_id.in_(users), Visit.visited_at >= p.start, Visit.visited_at < p.end)
    return _per_owner(db, q.group_by(Visit.owner_id))


def _collection_visits(db, users, p, f):
    return _visits(db, users, p, {"outcome": "collected"})


def _collections_amount(db, users, p, f):
    q = select(Visit.owner_id, func.sum(Visit.amount_centavos)).where(
        Visit.owner_id.in_(users), Visit.visited_at >= p.start, Visit.visited_at < p.end, Visit.outcome == "collected"
    )
    return _per_owner(db, q.group_by(Visit.owner_id))


def _customers_updated(db, users, p, f):
    # Counted once per customer, however often it was changed (the audit log says who changed which).
    q = select(AuditEntry.actor_id, func.count(func.distinct(AuditEntry.target_id))).where(
        AuditEntry.actor_id.in_(users), AuditEntry.action == "company.updated", AuditEntry.at >= p.start, AuditEntry.at < p.end
    )
    return _per_owner(db, q.group_by(AuditEntry.actor_id))


def _new_customers(db, users, p, f):
    q = select(Company.created_by_id, func.count()).where(Company.created_by_id.in_(users), Company.created_at >= p.start, Company.created_at < p.end)
    return _per_owner(db, q.group_by(Company.created_by_id))


def _activities(db, users, p, f):
    q = select(Activity.owner_id, func.count()).where(Activity.owner_id.in_(users), Activity.done_at >= p.start, Activity.done_at < p.end)
    if f.get("kind"):
        q = q.where(Activity.kind == f["kind"])
    return _per_owner(db, q.group_by(Activity.owner_id))


def _quotes(db, users, p, f, value=False):
    q = select(Quote.owner_id, func.sum(Quote.total_centavos) if value else func.count()).where(
        Quote.owner_id.in_(users), Quote.created_at >= p.start, Quote.created_at < p.end, Quote.approval_status != "rejected"
    )
    return _per_owner(db, q.group_by(Quote.owner_id))


def _closed(db, users, p, outcome, value=False):
    # A deal's close date is the day it was won or lost.
    q = (
        select(Deal.owner_id, func.sum(Deal.value_centavos) if value else func.count())
        .join(Deal.stage)
        .where(Deal.owner_id.in_(users), DealStage.outcome == outcome, Deal.expected_close_on >= p.first_day, Deal.expected_close_on < p.next_first_day)
    )
    return _per_owner(db, q.group_by(Deal.owner_id))


def _win_rate(db, users, p, f):
    won, lost = _closed(db, users, p, "won"), _closed(db, users, p, "lost")
    out = {}
    for u in set(won) | set(lost):
        w, l_ = won.get(u, (0, None))[0], lost.get(u, (0, None))[0]
        if w + l_:
            out[u] = (w, w + l_)
    return out


def _products_detailed(db, users, p, f):
    out: dict[str, int] = defaultdict(int)
    q = select(Visit.owner_id, Visit.detailing).where(Visit.owner_id.in_(users), Visit.visited_at >= p.start, Visit.visited_at < p.end)
    for owner, detailing in db.execute(q):
        out[owner] += sum(1 for d in detailing or [] if not f.get("productId") or d.get("productId") == f["productId"])
    return {u: (n, None) for u, n in out.items()}



# --- sales, as Finance invoiced them (the playbooks score from invoices sent or paid) ---------


def _issued(p: Period, users: list[str], previous: bool = False) -> list[dict] | None:
    feed = p.sales(previous)
    if feed is None:
        return None
    wanted = set(users)
    return [i for i in feed["invoices"] if i["status"] == "issued" and i.get("salespersonId") in wanted]


def _invoiced(db, users, p, f):
    out: dict[str, int] = defaultdict(int)
    for i in _issued(p, users) or []:
        out[i["salespersonId"]] += i["totalCentavos"]
    return {u: (v, None) for u, v in out.items()}


def _sale_days(db, users, p, f):
    # NZSD: days with at least one sale (of at least minCentavos, when set) out of the working days so far.
    rows = _issued(p, users)
    if rows is None:
        return {}
    least = int(f.get("minCentavos") or 0)
    days: dict[str, set] = defaultdict(set)
    for i in rows:
        if i["totalCentavos"] >= least:
            days[i["salespersonId"]].add(i["date"])
    out_of = p.working_days()
    return {u: (min(len(days.get(u, ())), out_of), out_of) for u in users} if out_of else {}


def _customers_kept(db, users, p, f):
    # CRR / HRR: customers who bought last month and again this month, out of last month's (counted for last month's salesperson).
    before, now = _issued(p, users, previous=True), _issued(p, users)
    if before is None or now is None:
        return {}
    last: dict[str, set] = defaultdict(set)
    for i in before:
        if i.get("customerId"):
            last[i["salespersonId"]].add(i["customerId"])
    bought = {i["customerId"] for i in now if i.get("customerId")}
    return {u: (len(c & bought), len(c)) for u, c in last.items()}


def _new_accounts(db, users, p, f):
    # NBD: customers whose first sale ever is this month.
    rows = _issued(p, users)
    if rows is None:
        return {}
    first = p.sales().get("firstSale") or {}
    new: dict[str, set] = defaultdict(set)
    for i in rows:
        c = i.get("customerId")
        if c and first.get(c, "") >= p.first_day:
            new[i["salespersonId"]].add(c)
    return {u: (len(c), None) for u, c in new.items()}


def dso_days(p: Period, users: list[str]) -> int | None:
    """DSO for these people together: what their customers owe, over a day's
    sales this month (the days of the month so far). None: nothing owed, or
    Finance not linked; 999 when owed with no sales this month."""
    rows = _issued(p, users)
    if rows is None:
        return None
    owed = sum(v for u, v in (p.sales().get("owed") or {}).items() if u in set(users))
    if owed <= 0:
        return None
    sold = sum(i["totalCentavos"] for i in rows)
    first = date.fromisoformat(p.first_day)
    last = date.fromisoformat(p.next_first_day) - timedelta(days=1)
    if p.today:
        last = min(last, date.fromisoformat(p.today))
    days = max(1, (last - first).days + 1)
    return min(999, round(owed * days / sold)) if sold else 999


def _dso(db, users, p, f):
    out = {}
    for u in users:
        days = dso_days(p, [u])
        if days is not None:
            out[u] = (days, None)
    return out


def _cancel_rate(db, users, p, f):
    # OCR: invoices voided out of those made this month.
    feed = p.sales()
    if feed is None:
        return {}
    wanted, made, voided = set(users), defaultdict(int), defaultdict(int)
    for i in feed["invoices"]:
        if i.get("salespersonId") in wanted:
            made[i["salespersonId"]] += 1
            voided[i["salespersonId"]] += i["status"] == "void"
    return {u: (voided[u], n) for u, n in made.items()}


def _assistance_approved(db, users, p, f):
    # PAP: assistance applications (DSWD, PCSO, OVP...) approved this month.
    q = select(AssistanceApplication.owner_id, func.count()).where(
        AssistanceApplication.owner_id.in_(users),
        AssistanceApplication.status == "approved",
        AssistanceApplication.decided_on >= p.first_day,
        AssistanceApplication.decided_on < p.next_first_day,
    )
    return _per_owner(db, q.group_by(AssistanceApplication.owner_id))

# The measures read from Finance: without it they have no result at all (not a zero).
FROM_FINANCE = {"invoiced", "sale_days", "customers_kept", "new_accounts", "dso", "cancel_rate"}

MEASURES: dict[str, Measure] = {
    "deals_won_value": Measure("Revenue won", "money", "The value of deals won in the month.", None, lambda db, u, p, f: _closed(db, u, p, "won", value=True)),
    "deals_won": Measure("Deals won", "count", "Deals won in the month.", None, lambda db, u, p, f: _closed(db, u, p, "won")),
    "win_rate": Measure("Win rate", "percent", "Deals won out of those won or lost in the month.", None, _win_rate),
    "quotes": Measure("Quotes made", "count", "Quotes made in the month, other than rejected ones.", None, lambda db, u, p, f: _quotes(db, u, p, f)),
    "quotes_value": Measure("Value quoted", "money", "The total of quotes made in the month, other than rejected ones.", None, lambda db, u, p, f: _quotes(db, u, p, f, value=True)),
    "new_customers": Measure("New customers", "count", "Customers they added in the month.", None, _new_customers),
    "customers_updated": Measure("Customers updated", "count", "Different customers whose details they updated.", None, _customers_updated),
    "activities": Measure("Activities done", "count", "Calls, meetings, emails, notes and tasks done in the month; one kind if picked.", "kind", _activities),
    "visits": Measure("Visits", "count", "Visits logged in the month; one outcome if picked.", "outcome", _visits),
    "doctors_visited": Measure("Accounts visited", "count", "Different accounts visited in the month.", None, _doctors_visited),
    "collection_visits": Measure("Collection visits", "count", "Visits where a payment was collected.", None, _collection_visits),
    "collections_amount": Measure("Amount collected", "money", "Payments collected on visits.", None, _collections_amount),
    "products_detailed": Measure("Products presented", "count", "Products discussed on visits; one product if picked.", "productId", _products_detailed),
    # Read from Finance's invoices (sent or paid), by the salesperson on each: nothing shows while Finance isn't linked.
    "invoiced": Measure("Sales invoiced", "money", "The total of invoices sent or paid in the month (IST).", None, _invoiced),
    "sale_days": Measure("Sales days", "percent", "Days with at least one invoice, out of the working days (Monday to Saturday) so far (NZSD).", "minCentavos", _sale_days),
    "customers_kept": Measure("Customers kept", "percent", "Customers invoiced last month and again this month, out of last month's (CRR, HRR).", None, _customers_kept),
    "new_accounts": Measure("New accounts", "count", "Customers invoiced for the first time ever this month (NBD).", None, _new_accounts),
    "dso": Measure("Days sales outstanding", "count", "What their customers owe, over a day's sales this month (DSO). Lower is better.", None, _dso),
    "cancel_rate": Measure("Cancellation rate", "percent", "Invoices voided out of those made this month (OCR). Lower is better.", None, _cancel_rate),
    "assistance_approved": Measure("Assistance approved", "count", "Assistance applications (DSWD, PCSO, OVP and others) approved this month (PAP).", None, _assistance_approved),
}
FILTER_CHOICES = {"kind": ACTIVITY_KINDS, "outcome": VISIT_OUTCOMES}
UNITS = ("count", "money", "percent")


def unit_of(kpi: Kpi) -> str:
    return kpi.unit if kpi.measure == "manual" else MEASURES[kpi.measure].unit


def figures(db: Session, kpi: Kpi, users: list[str], period: Period) -> dict[str, Figure]:
    """Each person's figure for a KPI in a period (missing: nothing yet)."""
    if not users:
        return {}
    if kpi.measure == "manual":
        q = select(KpiEntry.user_id, KpiEntry.value).where(KpiEntry.kpi_id == kpi.id, KpiEntry.month == period.month, KpiEntry.user_id.in_(users))
        return {u: (v, None) for u, v in db.execute(q)}
    return MEASURES[kpi.measure].count(db, users, period, kpi.filters or {})


def combine(parts: list[Figure], unit: str) -> int | None:
    """A group's result from its people's figures: added up, or a rate of the sums."""
    if unit == "percent":
        top, bottom = sum(p[0] for p in parts), sum(p[1] or 0 for p in parts)
        return round(100 * top / bottom) if bottom else None
    return sum(p[0] for p in parts)


def value_of(figure: Figure | None, unit: str) -> int | None:
    if figure is None:
        return 0 if unit != "percent" else None
    return combine([figure], unit)


def judged(kpi: Kpi, actual: int | None, target: int | None, elapsed: float) -> dict:
    """How a result stands against its target: {attainment, expected, status}."""
    if target is None or actual is None:
        return {"attainment": None, "expected": None, "status": "none" if target is None else "waiting"}
    unit = unit_of(kpi)
    paced = kpi.better == "higher" and unit != "percent"
    expected = round(target * elapsed) if paced else target
    if kpi.better == "higher":
        attainment = round(100 * actual / target) if target else 100
        against = 100 * actual / expected if expected else 100
    else:
        attainment = round(100 * target / actual) if actual else 100
        against = attainment
    status = "green" if against >= kpi.green_at else "amber" if against >= kpi.amber_at else "red"
    return {"attainment": attainment, "expected": expected, "status": status}


def elapsed_in(period: Period, today: str) -> float:
    """How much of the month has gone by, today included: 1 for a month that's over."""
    first, after = date.fromisoformat(period.first_day), date.fromisoformat(period.next_first_day)
    day = date.fromisoformat(today)
    if day < first:
        return 0.0
    return min(1.0, ((day - first).days + 1) / (after - first).days)


# --- targets ---------------------------------------------------------------------------------


def by_code(db: Session, code: str) -> Kpi | None:
    return db.scalar(select(Kpi).where(Kpi.code == code))


def person_targets(db: Session, kpi: Kpi | None, months: list[str]) -> dict[str, int]:
    """Each person's target for a KPI, added up over the months given."""
    out: dict[str, int] = defaultdict(int)
    if kpi is None:
        return out
    for t in db.scalars(select(KpiTarget).where(KpiTarget.kpi_id == kpi.id, KpiTarget.month.in_(months), KpiTarget.user_id.is_not(None))):
        out[t.user_id] += t.value
    return out


def set_person_target(db: Session, kpi: Kpi, month: str, user_id: str, value: int | None) -> None:
    """Sets, changes or (None) takes away one person's target."""
    target = db.scalar(select(KpiTarget).where(KpiTarget.kpi_id == kpi.id, KpiTarget.month == month, KpiTarget.user_id == user_id))
    if value is None:
        if target is not None:
            db.delete(target)
        return
    target = target or KpiTarget(kpi_id=kpi.id, month=month, user_id=user_id)
    target.value = value
    db.add(target)
