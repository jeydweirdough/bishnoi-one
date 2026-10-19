"""A B2B customer's trade profile, worked out, not typed (decided 2026-10-19):

- **Credit status**, from what Finance billed them and what's still unpaid:
  good standing; approaching due (an open invoice falls due within 5 days);
  overdue (one is past its due date); suspended (one is over 90 days late).
  Checked again on every quote for them, for Finance to confirm (app/routers/quotes.py).
- **Products they carry**, from what they ordered: quotes raised as orders,
  deals won with products on them, and the lines Finance invoiced them.
- **Profile**, from their contribution over the last 12 months: what GetMeds
  billed them (Finance's invoices; the CRM's won deals while Finance can't be
  asked) plus what 2MG sold them (the "2MG sales, last 12 months" field). Among
  the B2B customers who bought anything, the top fifth are High priority, the
  next three tenths Priority, the rest Regular: a share, so it needs no peso
  figure to be agreed first and keeps its meaning as sales grow.

Which customers are B2B is the forms' own answer: the teams the Credit terms
field is on (Settings → Forms), so a team added to it is credit-checked too.
"""

import math
import time
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import finance
from app.config import Settings
from app.models import Company, Deal, DealStage, FormField, Product, Quote

CREDIT_FIELD = "x_credit_terms"
TWO_MG_FIELD = "x_2mg_sales"
YEAR_DAYS = 365
SUSPENDED_DAYS = 90
# The profile, by share of the customers who bought anything, biggest first.
HIGH_SHARE, PRIORITY_SHARE = 0.20, 0.30

CREDIT_LABELS = {"good": "Good standing", "approaching": "Approaching due", "overdue": "Overdue", "suspended": "Suspended"}
PROFILE_LABELS = {"high": "High priority", "priority": "Priority", "regular": "Regular"}

# The profile ranks every B2B customer, so it's worked out once and kept a few minutes.
_RANKS: dict[str, tuple[float, dict]] = {}
RANK_SECONDS = 300


def trade_teams(db: Session) -> list[str] | None:
    """The teams that are B2B: those the Credit terms field is on. None: the field is on every team; []: no such field."""
    field = db.scalar(select(FormField).where(FormField.entity == "company", FormField.key == CREDIT_FIELD))
    if field is None:
        return []
    return list(field.only_teams or []) or None


def is_trade(db: Session, company: Company | None, teams: list[str] | None = ...) -> bool:  # type: ignore[assignment]
    if company is None:
        return False
    teams = trade_teams(db) if teams is ... else teams
    return teams is None or company.team_id in teams


def credit_of(row: dict | None) -> tuple[str, str]:
    """(status, words) from Finance's row for one customer; none means nothing billed: good standing."""
    if not row or not row.get("owedCentavos"):
        return "good", "Nothing owed."
    late = int(row.get("oldestDaysLate") or 0)
    owed = row["owedCentavos"]
    if late > SUSPENDED_DAYS:
        return "suspended", f"{late} days late on its oldest invoice."
    if late > 0:
        return "overdue", f"{late} {'day' if late == 1 else 'days'} late on its oldest invoice."
    if row.get("approaching"):
        return "approaching", f"An invoice falls due on {row.get('nextDueOn')}."
    return "good", f"{owed / 100:,.2f} owed, none of it due yet."


def credit_check(db: Session, settings: Settings, company: Company) -> dict:
    """What's kept on a quote: the customer's credit status now, for Finance to confirm."""
    rows = finance.customer_standing(settings, [company.id])
    now = datetime.now(UTC).isoformat()
    if rows is None:
        return {"status": None, "label": "Not checked", "detail": "Finance can't be asked right now, so the credit status wasn't checked.",
                "owedCentavos": 0, "overdueCentavos": 0, "oldestDaysLate": 0, "checkedAt": now, "decision": None}
    row = rows.get(company.id)
    status, detail = credit_of(row)
    return {
        "status": status, "label": CREDIT_LABELS[status], "detail": detail,
        "owedCentavos": (row or {}).get("owedCentavos", 0), "overdueCentavos": (row or {}).get("overdueCentavos", 0),
        "oldestDaysLate": (row or {}).get("oldestDaysLate", 0), "checkedAt": now, "decision": None,
    }


def _won_deals_since(db: Session, ids: list[str], since: datetime) -> list[Deal]:
    if not ids:
        return []
    won = select(DealStage.code).where(DealStage.outcome == "won")
    return list(db.scalars(select(Deal).where(Deal.company_id.in_(ids), Deal.stage_code.in_(won), Deal.closed_at >= since)))


def _sales(db: Session, companies: list[Company], rows: dict[str, dict] | None) -> dict[str, dict]:
    """Each customer's last 12 months: GetMeds (Finance's billings, or the CRM's won deals), 2MG, and the total."""
    since = datetime.now(UTC) - timedelta(days=YEAR_DAYS)
    won: dict[str, int] = {}
    if rows is None:
        for d in _won_deals_since(db, [c.id for c in companies], since):
            won[d.company_id] = won.get(d.company_id, 0) + d.value_centavos
    out = {}
    for c in companies:
        getmeds = (rows.get(c.id) or {}).get("billedYearCentavos", 0) if rows is not None else won.get(c.id, 0)
        # A money field keeps pesos (app/extra.py): here, centavos like the rest.
        try:
            two_mg = max(0, round(float((c.extra or {}).get(TWO_MG_FIELD) or 0) * 100))
        except (TypeError, ValueError):
            two_mg = 0
        out[c.id] = {"getmedsCentavos": getmeds, "twoMgCentavos": two_mg, "totalCentavos": getmeds + two_mg,
                     "source": "finance" if rows is not None else "deals"}
    return out


def _ranked(db: Session, settings: Settings) -> dict:
    """Every B2B customer's yearly contribution and profile, kept a few minutes."""
    key = str(db.get_bind().url)
    held = _RANKS.get(key)
    if held and time.monotonic() - held[0] < RANK_SECONDS:
        return held[1]
    teams = trade_teams(db)
    query = select(Company)
    if teams is not None:
        query = query.where(Company.team_id.in_(teams or ["-"]))
    companies = list(db.scalars(query))
    rows = finance.customer_standing(settings, [c.id for c in companies])
    sales = _sales(db, companies, rows)
    buyers = sorted((cid for cid, s in sales.items() if s["totalCentavos"] > 0), key=lambda cid: -sales[cid]["totalCentavos"])
    high = math.ceil(len(buyers) * HIGH_SHARE)
    priority = math.ceil(len(buyers) * (HIGH_SHARE + PRIORITY_SHARE))
    for rank, cid in enumerate(buyers, 1):
        sales[cid]["rank"] = rank
        sales[cid]["level"] = "high" if rank <= high else "priority" if rank <= priority else "regular"
    result = {"sales": sales, "buyers": len(buyers), "rows": rows}
    _RANKS[key] = (time.monotonic(), result)
    return result


def forget_ranks() -> None:
    """After a change that moves the profile (tests; a 2MG figure saved)."""
    _RANKS.clear()


def _carried(db: Session, company: Company, row: dict | None) -> list[dict]:
    """What they've ordered, most often first: orders raised from quotes, deals won with products, Finance's invoice lines."""
    seen: dict[str, dict] = {}

    def add(key: str, product_id: str | None, name: str, code: str | None, on: str | None, how: str) -> None:
        item = seen.setdefault(key, {"id": product_id, "name": name, "code": code, "times": 0, "lastOn": None, "from": set()})
        item["times"] += 1
        item["from"].add(how)
        if on and (item["lastOn"] is None or on > item["lastOn"]):
            item["lastOn"] = on

    products = {p.id: p for p in db.scalars(select(Product))}
    by_code = {(p.code or "").strip().lower(): p for p in products.values() if p.code}
    by_name = {p.name.strip().lower(): p for p in products.values()}
    for q in db.scalars(select(Quote).where(Quote.company_id == company.id, Quote.sales_order.is_not(None))):
        on = q.created_at.date().isoformat() if q.created_at else None
        for line in q.lines or []:
            p = products.get(line.get("productId") or "")
            if p is not None:
                add(p.id, p.id, p.name, p.code, on, "order")
    won = _won_deals_since(db, [company.id], datetime(2000, 1, 1, tzinfo=UTC))
    for d in won:
        on = d.closed_at.date().isoformat() if d.closed_at else None
        for line in d.lines or []:
            p = products.get(line.get("productId") or "")
            if p is not None:
                add(p.id, p.id, p.name, p.code, on, "deal")
    for line in (row or {}).get("lines") or []:
        ref, words = str(line.get("ref") or "").strip(), str(line.get("description") or "").strip()
        p = by_code.get(ref.lower()) or by_name.get(words.lower())
        for _ in range(int(line.get("invoices") or 1)):
            if p is not None:
                add(p.id, p.id, p.name, p.code, line.get("lastOn"), "invoice")
            elif words or ref:
                add(f"line:{(ref or words).lower()}", None, words or ref, ref or None, line.get("lastOn"), "invoice")
    items = sorted(seen.values(), key=lambda x: (-x["times"], x["name"].lower()))
    for x in items:
        x["from"] = sorted(x["from"])
    return items


def trade_out(db: Session, settings: Settings, company: Company) -> dict:
    """The customer page's Trade profile: credit status, profile and products they carry, each with where it came from."""
    if not is_trade(db, company):
        return {"applies": False}
    ranked = _ranked(db, settings)
    rows = ranked["rows"]
    row = (rows or {}).get(company.id) if rows is not None else None
    sales = ranked["sales"].get(company.id) or _sales(db, [company], rows)[company.id]
    if rows is None:
        credit = {"status": None, "label": "Not checked", "detail": "Finance can't be asked right now, so the credit status isn't known."}
    else:
        status, detail = credit_of(row)
        credit = {"status": status, "label": CREDIT_LABELS[status], "detail": detail}
    credit.update({"owedCentavos": (row or {}).get("owedCentavos", 0), "overdueCentavos": (row or {}).get("overdueCentavos", 0),
                   "oldestDaysLate": (row or {}).get("oldestDaysLate", 0), "nextDueOn": (row or {}).get("nextDueOn"),
                   "openInvoices": (row or {}).get("openInvoices", 0)})
    level = sales.get("level")
    return {
        "applies": True,
        "credit": credit,
        "profile": {
            "level": level, "label": PROFILE_LABELS.get(level or "", "No sales yet"),
            "rank": sales.get("rank"), "of": ranked["buyers"],
            "getmedsCentavos": sales["getmedsCentavos"], "twoMgCentavos": sales["twoMgCentavos"], "totalCentavos": sales["totalCentavos"],
            "source": sales["source"], "highShare": HIGH_SHARE, "priorityShare": PRIORITY_SHARE,
        },
        "carried": _carried(db, company, row),
        "financeLinked": rows is not None,
        "asOf": date.today().isoformat(),
    }
