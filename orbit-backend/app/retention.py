"""Customer retention: who is still buying, and who is slipping away.

Orders live in the old order app, so "buying" here means getting a quote that
wasn't rejected by Finance. Each division sets two thresholds (Settings ->
Retention): a customer is at risk once `at_risk_days` pass with no quote, and
lost after `lost_days`, or as soon as a rep marks them inactive.

Retention rate on a day D, with L = the division's lost_days:
    of the customers who got a quote in (D-2L, D-L],
    the share who got another in (D-L, D].
The window is the division's own, so a division that buys quarterly isn't
judged month by month. Everything above the database section is pure.
"""

from bisect import bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Division, RetentionRule
from app.catalogue import sales_keys
from app.tenancy import org_get

DEFAULT_AT_RISK_DAYS = 45
DEFAULT_LOST_DAYS = 90
TREND_MONTHS = 12

HEALTHY, AT_RISK, LOST, NO_QUOTES = "healthy", "at_risk", "lost", "no_quotes"


@dataclass(frozen=True)
class Rules:
    at_risk_days: int = DEFAULT_AT_RISK_DAYS
    lost_days: int = DEFAULT_LOST_DAYS


@dataclass(frozen=True)
class CustomerFacts:
    id: str
    name: str
    division: str
    team: str
    status: str  # lead | active | inactive
    owner_id: str | None
    owner_name: str | None
    # Days of the quotes that count (not rejected), ascending, with their totals.
    quote_days: tuple[date, ...] = ()
    quote_totals: tuple[int, ...] = ()
    # When and by whom the customer was added (for the "new customers" goal).
    created_on: date | None = None
    created_by: str | None = None

    @property
    def last_quote(self) -> date | None:
        return self.quote_days[-1] if self.quote_days else None

    def quoted_between(self, after: date, until: date) -> bool:
        """A quote in (after, until]."""
        i = bisect_right(self.quote_days, after)
        return i < len(self.quote_days) and self.quote_days[i] <= until


def health(c: CustomerFacts, rules: Rules, today: date) -> str:
    if c.status == "inactive":
        return LOST
    if c.last_quote is None:
        return NO_QUOTES
    days = (today - c.last_quote).days
    return HEALTHY if days <= rules.at_risk_days else AT_RISK if days <= rules.lost_days else LOST


@dataclass
class Window:
    """Retention on one day: `base` quoted in the previous window, `retained` of them quoted again."""

    base: int = 0
    retained: int = 0
    new: int = 0  # first quote ever (as far as the look-back sees) in the current window

    @property
    def lost(self) -> int:
        return self.base - self.retained

    @property
    def rate(self) -> float | None:
        return self.retained / self.base if self.base else None


def window_on(customers: Iterable[CustomerFacts], rules: Mapping[str, Rules], day: date) -> Window:
    w = Window()
    for c in customers:
        span = timedelta(days=rules.get(c.division, Rules()).lost_days)
        if c.quoted_between(day - 2 * span, day - span):
            w.base += 1
            w.retained += c.quoted_between(day - span, day)
        if c.quote_days and day - span < c.quote_days[0] <= day:
            w.new += 1
    return w


def month_ends(today: date, months: int = TREND_MONTHS) -> list[date]:
    """The last day of each of the past months, ending with today for the current one."""
    ends = [today]
    first = today.replace(day=1)
    for _ in range(months - 1):
        ends.append(first - timedelta(days=1))
        first = ends[-1].replace(day=1)
    return ends[::-1]


def look_back(rules: Mapping[str, Rules], today: date) -> date:
    """How far back quotes are needed: the trend's first window, and then some."""
    longest = max((r.lost_days for r in rules.values()), default=DEFAULT_LOST_DAYS)
    return month_ends(today)[0] - timedelta(days=2 * longest)


@dataclass
class Summary:
    window: Window
    counts: dict[str, int] = field(default_factory=dict)  # health -> customers

    def out(self) -> dict:
        return {
            "rate": self.window.rate,
            "base": self.window.base,
            "retained": self.window.retained,
            "lost": self.window.lost,
            "new": self.window.new,
            "customers": sum(self.counts.values()),
            "healthy": self.counts.get(HEALTHY, 0),
            "atRisk": self.counts.get(AT_RISK, 0),
            "lostNow": self.counts.get(LOST, 0),
            "noQuotes": self.counts.get(NO_QUOTES, 0),
        }


def summarize(customers: list[CustomerFacts], rules: Mapping[str, Rules], today: date) -> Summary:
    counts: dict[str, int] = {}
    for c in customers:
        h = health(c, rules.get(c.division, Rules()), today)
        counts[h] = counts.get(h, 0) + 1
    return Summary(window_on(customers, rules, today), counts)


def trend(customers: list[CustomerFacts], rules: Mapping[str, Rules], today: date) -> list[dict]:
    points = []
    for day in month_ends(today):
        w = window_on(customers, rules, day)
        points.append({"month": day.strftime("%Y-%m"), "asOf": day.isoformat(), "rate": w.rate, "base": w.base, "retained": w.retained})
    return points


# --- rules in the database -----------------------------------------------------------


def load_rules(db: Session) -> dict[str, Rules]:
    rows = {r.division_code: r for r in db.scalars(select(RetentionRule))}
    return {k: Rules(rows[k].at_risk_days, rows[k].lost_days) if k in rows else Rules() for k in sales_keys(db)}


def seed_retention_rules(db: Session) -> None:
    """Adds the defaults for sales divisions that have no rule yet; never changes one an admin set."""
    for code in sales_keys(db):
        if org_get(db, Division, code) is not None and org_get(db, RetentionRule, code) is None:
            db.add(RetentionRule(division_code=code, at_risk_days=DEFAULT_AT_RISK_DAYS, lost_days=DEFAULT_LOST_DAYS))
    db.flush()
