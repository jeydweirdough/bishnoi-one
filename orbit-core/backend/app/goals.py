"""Focus goals: what each kind of work is measured on this month, against the
targets a division sets in Settings -> Goals.

Sales goals are per rep and per division; a team's target for a per-rep goal
is the rep target times the people on the team. Finance's and Inventory's
goals belong to the department. Monthly goals are also judged on pace: 12 of
30 quotes on the 18th of a 30-day month is on pace, not behind.

Units: percent in basis points (8000 = 80%), money in centavos, counts, and
days (averages to one decimal). The pure part is everything above the
database section.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CompanyGoal, GoalTarget
from app.catalogue import sales_keys
from app.retention import CustomerFacts, Rules, window_on


@dataclass(frozen=True)
class Goal:
    key: str
    name: str
    unit: str  # percent | count | money | days
    better: str  # higher | lower
    area: str  # sales | finance | inventory
    default: int
    per_rep_monthly: bool  # a count or amount each rep builds up over the month
    about: str


GOALS: tuple[Goal, ...] = (
    Goal("retention", "Retention", "percent", "higher", "sales", 8000, False,
         "Customers kept: quoted again within the division's window."),
    Goal("quotes", "Quotes", "count", "higher", "sales", 30, True,
         "Made this month, not counting rejected ones."),
    Goal("quoted_value", "Quoted value", "money", "higher", "sales", 5_000_000, True,
         "Pesos quoted this month, not counting rejected quotes."),
    Goal("follow_ups_on_time", "Follow-ups on time", "percent", "higher", "sales", 9000, False,
         "Of this month's follow-ups due so far, the share done by their due date."),
    Goal("new_customers", "New customers", "count", "higher", "sales", 4, True,
         "Customers added this month."),
    Goal("activities", "Calls, visits & messages", "count", "higher", "sales", 60, True,
         "Logged this month."),
    Goal("approval_days", "Days to decide approvals", "days", "lower", "finance", 2, False,
         "Average from quote to decision, for approvals decided this month."),
    Goal("letter_days", "Days to check letters", "days", "lower", "finance", 2, False,
         "Average from quote to check, for letters checked this month."),
    Goal("fully_priced", "Products fully priced", "percent", "higher", "inventory", 10000, False,
         "Products on sale with every price-list price filled in."),
)
BY_KEY: dict[str, Goal] = {g.key: g for g in GOALS}
SALES_GOALS = tuple(g for g in GOALS if g.area == "sales")
# The department whose targets hold each non-sales area's goals.
AREA_DIVISION = {"finance": "finance", "inventory": "inventory"}


@dataclass(frozen=True)
class Month:
    start: date
    today: date
    days: int  # in the month

    @property
    def elapsed(self) -> float:
        return self.today.day / self.days


def judge(goal: Goal, value: float | None, target: int, month: Month) -> dict:
    """Where a value stands: met, on_pace, behind (monthly), below (a rate), over (lower is better), or no_data."""
    expected = None
    if value is None:
        status = "no_data"
    elif goal.better == "lower":
        status = "met" if value <= target else "over"
    elif value >= target:
        status = "met"
    elif goal.per_rep_monthly:
        expected = round(target * month.elapsed)
        status = "on_pace" if value >= expected else "behind"
    else:
        status = "below"
    return {"key": goal.key, "value": value, "target": target, "expected": expected, "status": status}


@dataclass
class SalesMonth:
    """One division's records for measuring sales goals this month."""

    customers: list[CustomerFacts]
    quotes: list[dict]  # this month's quotes that count (not rejected)
    activities: list[dict]  # logged this month
    follow_ups: list[dict]  # due between the 1st and today
    done_on: Mapping[str, str]  # follow-up id -> day it was done (YYYY-MM-DD, Manila)


def measure_sales(data: SalesMonth, people: set[str] | None, rules: Mapping[str, Rules], month: Month) -> dict[str, float | None]:
    """The sales goals' values for these people (None: everyone in the data)."""
    ours = (lambda pid: True) if people is None else (lambda pid: pid in people)
    today = month.today.isoformat()
    quotes = [q for q in data.quotes if ours(q.get("createdById"))]
    owned = [c for c in data.customers if people is None or c.owner_id in people]
    due = [
        f for f in data.follow_ups
        if ours(f.get("assigneeId")) and (f["dueOn"] < today or (f["dueOn"] == today and f["status"] == "done"))
    ]
    on_time = [f for f in due if f["status"] == "done" and data.done_on.get(f["_id"], "9999") <= f["dueOn"]]
    retention = window_on(owned, rules, month.today).rate
    return {
        "retention": None if retention is None else round(retention * 10_000),
        "quotes": len(quotes),
        "quoted_value": sum(q.get("totalCentavos", 0) for q in quotes),
        "follow_ups_on_time": round(len(on_time) / len(due) * 10_000) if due else None,
        "new_customers": sum(
            1 for c in data.customers if c.created_on and c.created_on >= month.start and ours(c.created_by)
        ),
        "activities": sum(1 for a in data.activities if a.get("kind") in ("call", "visit", "message") and ours(a.get("byId"))),
    }


def goal_results(values: Mapping[str, float | None], targets: Mapping[str, int], month: Month, reps: int = 1,
                 goals: Iterable[Goal] = SALES_GOALS, keys: set[str] | None = None) -> list[dict]:
    """Judge each goal; per-rep monthly targets are scaled up to `reps` people.
    `keys` is what the company tracks, so a goal it switched off is simply not
    reported anywhere."""
    return [
        judge(g, values.get(g.key), targets[g.key] * (max(reps, 1) if g.per_rep_monthly else 1), month)
        for g in goals
        if keys is None or g.key in keys
    ]


def tracked(db: Session) -> set[str]:
    """The goals this company watches. Orbit knows how to work all of them out;
    which ones a company cares about is its own business. A goal with no row has
    never been switched off, so it counts as tracked."""
    off = {row.goal for row in db.scalars(select(CompanyGoal).where(CompanyGoal.is_active.is_(False)))}
    return {g.key for g in GOALS if g.key not in off}


def set_tracked(db: Session, keys: set[str]) -> None:
    """Remembers only the ones switched off, so a goal added to Orbit later
    arrives switched on rather than silently missing."""
    rows = {row.goal: row for row in db.scalars(select(CompanyGoal))}
    for goal in GOALS:
        wanted = goal.key in keys
        row = rows.get(goal.key)
        if row is None:
            if not wanted:
                db.add(CompanyGoal(goal=goal.key, is_active=False))
        elif row.is_active != wanted:
            row.is_active = wanted


def catalog_out(keys: set[str] | None = None) -> list[dict]:
    """Every goal Orbit can work out, and whether this company tracks it."""
    return [
        {"key": g.key, "name": g.name, "unit": g.unit, "better": g.better, "area": g.area,
         "perRepMonthly": g.per_rep_monthly, "about": g.about, "default": g.default,
         "isTracked": keys is None or g.key in keys}
        for g in GOALS
    ]


# --- targets in the database ---------------------------------------------------------


def goal_divisions(db: Session) -> tuple[str, ...]:
    """The divisions that have goals: this company's sales ones, and the
    departments whose desks keep figures of their own."""
    return (*sales_keys(db), *AREA_DIVISION.values())


def load_targets(db: Session) -> dict[str, dict[str, int]]:
    """division code -> goal key -> target, with each goal's default where none is set."""
    stored = {(r.division_code, r.goal): r.target for r in db.scalars(select(GoalTarget))}
    return {d: {g.key: stored.get((d, g.key), g.default) for g in GOALS} for d in goal_divisions(db)}
