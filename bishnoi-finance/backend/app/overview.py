"""The Living Overview (Plans/Plan - Living Overview per account, approved by the user 2026-10-31).

GET /finance/overview?period=month|quarter|year: one lead card and up to five cards for each view (Overview,
Payables, Receivables, Cash, Tax), worked out for the person asking. Read-only: nothing is stored.

- Shown by what you can see, acted on by what you can do. A card is built only with its view permission and a
  slice of a mixed picture only with that source's; "waiting for you" and buttons need the doing permission
  too. What isn't allowed is never built, so the page has nothing to hide (the rules: CARD_NEEDS, `doing`).
- Only approved journal entries count in any figure; bills count once recorded, petty cash once posted.
- Each picture reads what its list reads: the agings (routers/receivables.py, payables_work.py), the BIR books
  (bir_reports.py), BIR readiness, the money accounts, the saved Zoho copies. Those copies are labelled on the
  screen: they aren't in the books.
- An aging is today's state. Its period picture is the part of it on documents dated in the period; the whole
  figure, which is what its list shows, is sent beside it (`wholeCentavos`).
- Who may check what comes from the routers' own rules (`may_bill`, `filter_bills`, petty cash `may`, funds'
  `check_hold`, sales orders' `permissions`), so nobody sees their own record as theirs to check.
- The CRM's prices aren't asked here (GET /finance/dashboard/waiting-prices, on their own), and BIR deadlines
  stay a placeholder until Sir Mel's list exists: no legal date is worked out or guessed here.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app import bir_reports as bir
from app.access import CurrentAccess
from app.bir_readiness import SOURCE_NAMES
from app.deps import DB, SettingsDep
from app.models import Bill, FundRequest, ImportedExpense, Invoice, JournalEntry, JournalLine, PaymentVoucher, PettyCashVoucher, SalesOrder, ZohoSourceDocument, ZohoSourceRun
from app.money_accounts import money_account_ids

router = APIRouter(tags=["overview"])

Period = Literal["month", "quarter", "year"]

# Which card each person may get: every permission in a tuple is needed, any one tuple is enough.
CARD_NEEDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "cash": (("accounts.view", "journal.view"),),
    "inout": (("journal.view",),),
    "went": (("bills.view",), ("petty_cash.view",), ("funds.view",)),
    "ar": (("invoices.view",),),
    "od": (("invoices.view",),),
    "coll": (("invoices.view",),),
    "due": (("invoices.view",),),
    "zoho": (("invoices.view",),),
    "ap": (("bills.view",),),
    "petty": (("petty_cash.view",),),
    "mkt": (("funds.view",),),
    "vat": (("bir.view",),),
    "ewt": (("bir.view",),),
    "ready": (("bir.view",),),
    "books": (("journal.view",),),
    "dl": (("bir.view",),),
    "soon": (("calendar.use",), ("bills.view",)),
    "link": (("integrations.manage",),),
}
# Each hand-off needs the doing permission and the view that opens the record.
DOING = (
    ("bills.create", "bills.view"), ("bills.approve", "bills.view"), ("bills.check", "bills.view"),
    ("vouchers.prepare", "vouchers.view"), ("vouchers.release", "vouchers.view"),
    ("petty_cash.create", "petty_cash.view"), ("petty_cash.check", "petty_cash.view"),
    ("journal.approve", "journal.view"), ("journal.post", "journal.view"),
    ("funds.release", "funds.view"), ("funds.check", "funds.view"), ("funds.settle", "funds.view"),
    ("sales_orders.approve", "sales_orders.view"), ("sales_orders.create", "sales_orders.view"),
    ("prices.approve", "prices.view"),
)
CARD_AREAS = {"cash": "cash", "inout": "cash", "petty": "cash", "books": "tax", "went": "payables", "ar": "receivables", "od": "receivables",
              "coll": "receivables", "due": "receivables", "zoho": "receivables", "ap": "payables", "mkt": "payables", "vat": "tax",
              "ewt": "tax", "ready": "tax", "dl": "tax", "soon": "payables", "wait": "payables", "link": "settings"}
# A lead and its own card are never on one view.
LEAD_CARD = {"cash": "cash", "vat": "vat", "recv": "ar", "sup": "ap", "petty": "petty"}
CARD_ORDER = ("wait", "cash", "ar", "ap", "vat", "petty", "mkt", "went", "ready", "ewt", "books", "zoho", "od", "coll", "due", "inout", "soon", "dl", "link")
SUGGESTED = {
    "release": ("wait", "cash", "petty", "mkt", "went"),
    "cash": ("wait", "ar", "ap", "vat", "went"),
    "vat": ("wait", "ready", "ewt", "books", "dl"),
    "recv": ("zoho", "od", "coll", "due"),
    "mine": ("wait", "ap", "petty", "went", "soon"),
}
AREA_CARDS = {
    "payables": ("wait", "ap", "went", "mkt", "soon"),
    "receivables": ("zoho", "od", "coll", "due"),
    "cash": ("inout", "petty", "books"),
    "tax": ("ready", "ewt", "books", "dl"),
}
MOST_CARDS = 5
RANKED = 5
BOOK_ROWS = 5
LISTED = 6
SOON_DAYS = 30
WEEK = 7
STALE_DAYS = 3  # a hand-off older than this says how long it has waited
ZOHO_UNPAID_NOT = ("void", "draft", "paid")
ZOHO_COMPANIES = {"2mg": "2MG", "gpi": "GPI", "unknown": "Not yet attributed"}


def link(path: str, **params) -> str:
    q = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{path}?{urlencode(q)}" if q else path


def row(title: str, meta: str = "", href: str | None = None, amount: int | None = None, chip: tuple[str, str] | None = None, on: date | None = None, **extra) -> dict:
    """One line of a list on a card; its picture is drawn by the page."""
    return {"title": title, "meta": meta, "href": href, "amountCentavos": amount, "chip": {"text": chip[0], "tone": chip[1]} if chip else None,
            "on": on.isoformat() if on else None, **extra}


@dataclass(frozen=True)
class Span:
    """One bar of a chart: a stretch of days, and how it's labelled."""

    label: str
    start: date
    end: date


def weeks(start: date, end: date) -> list[Span]:
    out, d = [], start
    while d <= end:
        last = min(d + timedelta(days=6), end)
        out.append(Span(f"{d:%b} {d.day}–{last.day}", d, last))
        d = last + timedelta(days=1)
    return out


def period_of(key: str, on: date, fiscal_end: int) -> tuple[date, date, list[Span], int, int]:
    """The period's first and last day, its bars, and the fiscal quarter today is in (as the BIR pages count it)."""
    year, q = next((y, n) for y in (on.year, on.year + 1) for n in (1, 2, 3, 4)
                   if bir.quarter(y, n, fiscal_end).start <= on <= bir.quarter(y, n, fiscal_end).end)
    this_quarter = bir.quarter(year, q, fiscal_end)
    if key == "month":
        start, end = on.replace(day=1), bir.month_end(on.year, on.month)
        return start, end, weeks(start, end), year, q
    if key == "quarter":
        start, end = this_quarter.start, this_quarter.end
    else:
        start, end = bir.quarter(year, 1, fiscal_end).start, bir.quarter(year, 4, fiscal_end).end
    return start, end, [Span(f"{m.start:%b}", m.start, m.end) for m in bir.months_of(bir.Period(start, end, ""))], year, q


@dataclass
class Ctx:
    access: object
    db: object
    settings: object
    key: str
    on: date
    zone: ZoneInfo
    start: date
    end: date
    spans: list[Span]
    fiscal_year: int
    fiscal_quarter: int
    kept: dict = field(default_factory=dict)

    def can(self, permission: str) -> bool:
        return self.access.can(permission)

    def has(self, card: str) -> bool:
        return any(all(self.can(p) for p in need) for need in CARD_NEEDS[card])

    def within(self, day: date) -> bool:
        return self.start <= day <= self.end

    def span_of(self, day: date) -> int:
        return next(i for i, s in enumerate(self.spans) if s.start <= day <= s.end)

    def once(self, name: str, make):
        if name not in self.kept:
            self.kept[name] = make()
        return self.kept[name]

    def local_day(self, at: datetime) -> date:
        return (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(self.zone).date()

    def days_since(self, at: datetime) -> int:
        return max((self.on - self.local_day(at)).days, 0)


# ---- Money (approved entries only) ------------------------------------------------------------


def money_moves(c: Ctx) -> list[tuple[date, int, int]]:
    """Every approved entry touching a money account up to today: its date, what came in, what went out."""
    def read():
        ids = money_account_ids(c.db)
        if not ids:
            return []
        rows = c.db.execute(
            select(JournalEntry.entry_date, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos))
            .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
            .where(JournalEntry.status == "approved", JournalLine.account_id.in_(ids), JournalEntry.entry_date <= c.on)
            .group_by(JournalEntry.id, JournalEntry.entry_date)
        ).all()
        return sorted((d, int(i or 0), int(o or 0)) for d, i, o in rows)

    return c.once("moves", read)


def cash_points(c: Ctx) -> list[tuple[str, date]]:
    """The days the cash line stands on: the day before the period, each week or month end so far, and today."""
    days = [(f"{c.start - timedelta(days=1):%b} {(c.start - timedelta(days=1)).day}", c.start - timedelta(days=1))]
    ends = [s.end for s in c.spans] if c.key != "quarter" else [s.end for s in weeks(c.start, c.end)]
    for end in ends:
        if end < c.on:
            days.append((f"{end:%b} {end.day}", end))
    days.append((f"{c.on:%b} {c.on.day}", c.on))
    return days


def cash_card(c: Ctx) -> dict:
    moves = money_moves(c)
    points = []
    previous: date | None = None
    for label, day in cash_points(c):
        points.append({"label": label, "on": day.isoformat(), "amountCentavos": sum(i - o for d, i, o in moves if d <= day),
                       "count": sum(1 for d, _, _ in moves if d <= day and (previous is None or d > previous)),
                       "href": link("/finance/ledger/trial-balance", to=day.isoformat())})
        previous = day
    return {"balanceCentavos": points[-1]["amountCentavos"], "changeCentavos": points[-1]["amountCentavos"] - points[0]["amountCentavos"],
            "points": points, "href": "/finance/ledger/accounts"}


def inout_card(c: Ctx) -> dict:
    """Money accounts debited and credited, by bar. Paid out is what the Cash Disbursements Journal shows, approved entries only."""
    moves = money_moves(c)
    series_in, series_out = [], []
    for s in c.spans:
        here = [(i, o) for d, i, o in moves if s.start <= d <= s.end]
        common = {"label": s.label, "start": s.start.isoformat(), "end": s.end.isoformat()}
        entries = link("/finance/ledger", **{"from": s.start.isoformat(), "to": s.end.isoformat()})
        series_in.append(common | {"amountCentavos": sum(i for i, _ in here), "count": sum(1 for i, _ in here if i), "href": entries})
        paid_out = link("/finance/bir", book="cash-disbursements", start=s.start.isoformat(), end=s.end.isoformat()) if c.can("bir.view") else entries
        series_out.append(common | {"amountCentavos": sum(o for _, o in here), "count": sum(1 for _, o in here if o), "href": paid_out})
    return {"in": series_in, "out": series_out, "inCentavos": sum(p["amountCentavos"] for p in series_in),
            "outCentavos": sum(p["amountCentavos"] for p in series_out)}


# ---- Where money went -----------------------------------------------------------------------


def spending_by_team(c: Ctx) -> list[dict]:
    """Marketing spending by the team that asked, as the old dashboard counts it: accepted receipts in
    categories the company covers, on liquidations already reviewed."""
    def read():
        teams: dict[str, dict] = {}
        for r in c.db.scalars(select(FundRequest).where(FundRequest.checked_at.is_not(None))):
            here = [e for e in r.expenses if e.accepted is True and e.category is not None and e.category.covered and c.within(e.spent_on)]
            if not here:
                continue
            name = r.team_name or "No team"
            t = teams.setdefault(name, {"label": name, "amountCentavos": 0, "count": 0, "href": link("/finance/funds", stage="history")})
            t["amountCentavos"] += sum(e.amount_centavos for e in here)
            t["count"] += 1
        return sorted(teams.values(), key=lambda t: -t["amountCentavos"])

    return c.once("teams", read)


def went_card(c: Ctx) -> dict:
    slices, hidden = [], []
    if c.can("bills.view"):
        count, total = c.db.execute(select(func.count(), func.coalesce(func.sum(Bill.total_centavos), 0))
                                    .where(Bill.status == "recorded", Bill.bill_date >= c.start, Bill.bill_date <= c.end)).one()
        slices.append({"key": "bills", "label": "Supplier bills", "short": "Bills", "amountCentavos": int(total), "count": count, "noun": "bill", "href": link("/finance/bills", show="ready")})
    else:
        hidden.append("supplier bills")
    if c.can("petty_cash.view"):
        count, total = c.db.execute(select(func.count(), func.coalesce(func.sum(PettyCashVoucher.total_centavos), 0))
                                    .where(PettyCashVoucher.status == "posted", PettyCashVoucher.voucher_date >= c.start, PettyCashVoucher.voucher_date <= c.end)).one()
        slices.append({"key": "petty", "label": "Petty cash", "short": "Petty cash", "amountCentavos": int(total), "count": count, "noun": "voucher", "href": link("/finance/petty-cash", show="posted")})
        count, total = c.db.execute(select(func.count(), func.coalesce(func.sum(ImportedExpense.total_centavos), 0))
                                    .where(ImportedExpense.status == "posted", ImportedExpense.expense_date >= c.start, ImportedExpense.expense_date <= c.end)).one()
        if count:  # Zoho history: shown only where the period has some
            slices.append({"key": "imported_expenses", "label": "Imported expenses", "short": "Imported", "amountCentavos": int(total), "count": count, "noun": "expense", "href": link("/finance/petty-cash/imported")})
    else:
        hidden.append("petty cash")
    if c.can("funds.view"):
        teams = spending_by_team(c)
        slices.append({"key": "marketing", "label": "Marketing", "short": "Marketing", "amountCentavos": sum(t["amountCentavos"] for t in teams),
                       "count": sum(t["count"] for t in teams), "noun": "liquidation", "href": link("/finance/funds", stage="history")})
    else:
        hidden.append("marketing")
    return {"slices": slices, "hidden": hidden, "totalCentavos": sum(s["amountCentavos"] for s in slices)}


def mkt_card(c: Ctx) -> dict:
    teams = spending_by_team(c)
    return {"teams": teams[:RANKED], "teamCount": len(teams), "totalCentavos": sum(t["amountCentavos"] for t in teams), "href": link("/finance/funds", stage="history")}


# ---- Owed by customers, owed to suppliers ------------------------------------------------------


def blank_buckets() -> dict[str, dict]:
    from app.routers.receivables import BUCKETS

    return {k: {"key": k, "label": label, "amountCentavos": 0, "count": 0} for k, label, _ in BUCKETS}


def receivables(c: Ctx) -> dict:
    from app.routers.receivables import ageing

    return c.once("ar", lambda: ageing(None, c.db, c.settings, c.on))


def ar_card(c: Ctx) -> dict:
    found = receivables(c)
    buckets = blank_buckets()
    unpaid = 0
    for customer in found["customers"]:
        for inv in customer["invoices"]:
            unpaid += 1
            if c.within(date.fromisoformat(inv["date"])):
                b = buckets[inv["bucket"]]
                b["amountCentavos"] += inv["owedCentavos"]
                b["count"] += 1
    for b in buckets.values():
        b["href"] = "/finance/invoices/receivables"
    whole = {b["key"]: b["amountCentavos"] for b in found["buckets"]}
    return {"wholeCentavos": found["totalCentavos"], "wholeInvoices": unpaid, "customers": len(found["customers"]),
            "over60Centavos": whole["d61_90"] + whole["over_90"], "buckets": list(buckets.values()),
            "periodCentavos": sum(b["amountCentavos"] for b in buckets.values()), "periodInvoices": sum(b["count"] for b in buckets.values()),
            "href": "/finance/invoices/receivables"}


def od_card(c: Ctx) -> dict:
    late = [x for x in receivables(c)["customers"] if x["oldestDaysLate"] > 0]
    return {"total": len(late), "href": "/finance/invoices/receivables", "rows": [
        row(x["name"], f"{len(x['invoices'])} unpaid · oldest {x['oldestDaysLate']} days late", link("/finance/invoices", q=x["name"]), x["totalCentavos"],
            (f"{x['oldestDaysLate']} days late", "bad"), rank=i + 1)
        for i, x in enumerate(late[:RANKED])]}


def coll_card(c: Ctx) -> dict:
    """Payments received: the Cash Receipts Journal for the period, by bar."""
    found = bir.cash_receipts(c.db, c.start, c.end)
    amounts = [[0, 0] for _ in c.spans]
    for r in found["rows"]:
        i = c.span_of(date.fromisoformat(r["date"]))
        amounts[i][0] += r["cashCentavos"]
        amounts[i][1] += 1
    hrefs = [link("/finance/bir", book="cash-receipts", start=s.start.isoformat(), end=s.end.isoformat()) if c.can("bir.view") else "/finance/invoices/receivables" for s in c.spans]
    return {"totalCentavos": found["totals"]["cashCentavos"], "count": len(found["rows"]),
            "points": [{"label": s.label, "amountCentavos": a, "count": n, "href": h} for s, (a, n), h in zip(c.spans, amounts, hrefs)]}


def ap_report(c: Ctx) -> dict:
    from app.payables_work import aging

    return c.once("ap", lambda: aging(c.db, c.on))


def ap_card(c: Ctx) -> dict:
    report = ap_report(c)
    dated = set(c.db.scalars(select(Bill.id).where(Bill.bill_date >= c.start, Bill.bill_date <= c.end)))
    buckets = blank_buckets()
    week_end = c.on + timedelta(days=WEEK - 1)
    week_amount = week_count = 0
    for supplier in report["suppliers"]:
        for b in supplier["bills"]:
            if b["id"] in dated:
                buckets[b["bucket"]]["amountCentavos"] += b["owedCentavos"]
                buckets[b["bucket"]]["count"] += 1
            if c.on <= date.fromisoformat(b["dueDate"]) <= week_end:
                week_amount += b["owedCentavos"]
                week_count += 1
    for key, b in buckets.items():
        b["href"] = link("/finance/bills", queue="outstanding", bucket=key)
    whole = {b["key"]: b["amountCentavos"] for b in report["buckets"]}
    return {"wholeCentavos": report["totals"]["owedCentavos"], "wholeBills": report["billCount"], "over60Centavos": whole["d61_90"] + whole["over_90"],
            "buckets": list(buckets.values()), "periodCentavos": sum(b["amountCentavos"] for b in buckets.values()),
            "periodBills": sum(b["count"] for b in buckets.values()), "dueThisWeekCentavos": week_amount, "dueThisWeek": week_count,
            "href": "/finance/bills/aging"}


# ---- The saved Zoho copies ----------------------------------------------------------------------


def zoho_saved(c: Ctx) -> list[dict] | None:
    """The saved Zoho invoices of the connected organisation; None when no organisation is confirmed here."""
    def read():
        from app.routers.zoho_source import organization

        try:
            org = organization(c.settings)
        except HTTPException:
            return None
        return [r.data for r in c.db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id == org, ZohoSourceDocument.kind == "invoice"))]

    return c.once("zoho", read)


def zoho_unpaid(saved: list[dict]) -> tuple[list[dict], int]:
    """Saved invoices in pesos with a balance left, and how many can't be counted here (no saved balance, or not in pesos)."""
    out, skipped = [], 0
    for r in saved:
        if r.get("status") in ZOHO_UNPAID_NOT:
            continue
        if r.get("balanceCentavos") is None or r.get("currency") != "PHP":
            skipped += 1
        elif r["balanceCentavos"] > 0:
            out.append(r)
    return out, skipped


def zoho_card(c: Ctx) -> dict:
    from app.routers.receivables import bucket_of

    saved = zoho_saved(c)
    if saved is None:
        return {"available": False}
    unpaid, skipped = zoho_unpaid(saved)
    list_period = "month" if c.key == "month" else "all"
    buckets = blank_buckets() | {"no_due": {"key": "no_due", "label": "No due date saved", "amountCentavos": 0, "count": 0}}
    companies = {k: {"key": k, "label": label, "amountCentavos": 0, "count": 0, "href": link("/finance/invoices/zoho", company="2mg" if k == "2mg" else "all", period=list_period)}
                 for k, label in ZOHO_COMPANIES.items()}
    for r in unpaid:
        if not c.within(date.fromisoformat(r["date"])):
            continue
        due = date.fromisoformat(r["dueDate"]) if r.get("dueDate") else None
        b = buckets[bucket_of(max((c.on - due).days, 0)) if due else "no_due"]
        b["amountCentavos"] += r["balanceCentavos"]
        b["count"] += 1
        company = companies[r.get("company") if r.get("company") in companies else "unknown"]
        company["amountCentavos"] += r["balanceCentavos"]
        company["count"] += 1
    for b in buckets.values():
        b["href"] = link("/finance/invoices/zoho", company="all", period=list_period)
    return {"available": True, "buckets": [b for b in buckets.values() if b["key"] != "no_due" or b["count"]],
            "companies": [x for x in companies.values() if x["key"] != "unknown" or x["count"]],
            "totalCentavos": sum(b["amountCentavos"] for b in buckets.values()), "count": sum(b["count"] for b in buckets.values()),
            "notCounted": skipped, "href": link("/finance/invoices/zoho", company="all", period=list_period)}


def due_card(c: Ctx) -> dict:
    saved = zoho_saved(c)
    if saved is None:
        return {"available": False, "rows": [], "total": 0}
    unpaid, _ = zoho_unpaid(saved)
    until = c.on + timedelta(days=WEEK - 1)
    due = sorted((r for r in unpaid if r.get("dueDate") and c.on <= date.fromisoformat(r["dueDate"]) <= until), key=lambda r: (r["dueDate"], r["number"]))
    return {"available": True, "total": len(due), "href": link("/finance/invoices/zoho", company="all", period="all"), "rows": [
        row(f"{r['number']} · {r['customerName']}", ZOHO_COMPANIES.get(r.get("company"), ZOHO_COMPANIES["unknown"]), f"/finance/invoices/zoho/{r['id']}",
            r["balanceCentavos"], ("Due today", "warn") if r["dueDate"] == c.on.isoformat() else None, date.fromisoformat(r["dueDate"]))
        for r in due[:RANKED]]}


# ---- Petty cash ----------------------------------------------------------------------------------


def petty_card(c: Ctx) -> dict:
    from app.routers.petty_cash import funds_out

    waiting = dict(c.db.execute(select(PettyCashVoucher.fund_account_id, func.count()).where(PettyCashVoucher.status == "to_check").group_by(PettyCashVoucher.fund_account_id)).all())
    funds = [{"name": f["name"], "balanceCentavos": f["balanceCentavos"], "waiting": waiting.get(f["id"], 0),
              "href": link("/finance/petty-cash", show="to_check" if waiting.get(f["id"]) else None)}
             for f in funds_out(c.db) if f["active"]]
    funds.sort(key=lambda f: (-f["waiting"], -f["balanceCentavos"], f["name"]))
    used = c.db.scalar(select(func.count()).select_from(PettyCashVoucher).where(
        PettyCashVoucher.status == "posted", PettyCashVoucher.voucher_date >= c.start, PettyCashVoucher.voucher_date <= c.end)) or 0
    return {"funds": funds[:3], "fundCount": len(funds), "balanceCentavos": sum(f["balanceCentavos"] for f in funds), "postedInPeriod": used, "href": "/finance/petty-cash"}


# ---- Tax -------------------------------------------------------------------------------------------


def purchases(c: Ctx) -> list:
    return c.once("purchases", lambda: bir.bills_between(c.db, c.start, c.end))


def book_link(c: Ctx, book: str, s: Span) -> str:
    return link("/finance/bir", book=book, start=s.start.isoformat(), end=s.end.isoformat())


def vat_card(c: Ctx) -> dict:
    """Output and input VAT, read as the VAT return reads them (bir.vat_return). A non-VAT company's return is percentage tax."""
    regime = bir.taxpayer(c.db)["regime"]
    output = [[0, 0] for _ in c.spans]
    input_ = [[0, 0] for _ in c.spans]
    for inv in bir.issued_between(c.db, c.start, c.end):
        i = c.span_of(inv.invoice_date)
        output[i][0] += bir.amounts_of(inv)["tax"]
        output[i][1] += 1
    for pu in purchases(c):
        i = c.span_of(pu.on)
        input_[i][0] += pu.vat
        input_[i][1] += 1
    out_total, in_total = sum(a for a, _ in output), sum(a for a, _ in input_)
    return {"vatRegistered": regime != "non_vat", "outputCentavos": out_total, "inputCentavos": in_total, "payableCentavos": out_total - in_total,
            "output": [{"label": s.label, "amountCentavos": a, "count": n, "href": book_link(c, "sales-journal", s)} for s, (a, n) in zip(c.spans, output)],
            "input": [{"label": s.label, "amountCentavos": a, "count": n, "href": book_link(c, "purchase-journal", s)} for s, (a, n) in zip(c.spans, input_)],
            "href": link("/finance/bir/vat", year=c.fiscal_year, quarter=c.fiscal_quarter)}


def ewt_card(c: Ctx) -> dict:
    """Tax withheld from suppliers: what the 0619-E, QAP and 2307s read (bir.withheld_bills)."""
    amounts = [[0, 0] for _ in c.spans]
    payees = set()
    for pu in purchases(c):
        if pu.held:
            i = c.span_of(pu.on)
            amounts[i][0] += sum(h[3] for h in pu.held)
            amounts[i][1] += 1
            payees.add(pu.supplier_id)
    return {"totalCentavos": sum(a for a, _ in amounts), "payees": len(payees),
            "points": [{"label": s.label, "amountCentavos": a, "count": n,
                        "href": link("/finance/bir/withholding", form="0619e", year=s.start.year, month=s.start.month)} for s, (a, n) in zip(c.spans, amounts)],
            "href": link("/finance/bir/withholding", form="2307", year=c.fiscal_year, quarter=c.fiscal_quarter)}


def ready_card(c: Ctx) -> dict:
    from app.bir_readiness import readiness

    end = min(c.end, c.on)
    found = readiness(c.db, c.start, end, c.zone)
    href = link("/finance/bir/readiness", start=c.start.isoformat(), end=end.isoformat())
    rank = {"differs": 0, "not_set": 1, "agrees": 2}
    checks = sorted(found["checks"], key=lambda x: rank[x["status"]])
    return {"counts": found["counts"], "href": href, "checks": [
        {"key": x["key"], "title": x["title"], "status": x["status"], "listCentavos": x["listCentavos"], "booksCentavos": x["booksCentavos"],
         "differenceCentavos": x["differenceCentavos"], "href": href} for x in checks]}


def books_card(c: Ctx) -> dict:
    rows = c.db.execute(
        select(JournalEntry.source, func.count(func.distinct(JournalEntry.id)), func.coalesce(func.sum(JournalLine.debit_centavos), 0))
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(JournalEntry.status == "approved", JournalEntry.entry_date >= c.start, JournalEntry.entry_date <= c.end)
        .group_by(JournalEntry.source)
    ).all()
    found = {s: (n, int(a)) for s, n, a in rows}
    span = {"from": c.start.isoformat(), "to": c.end.isoformat()}
    out = []
    for source in ("bill", "voucher", "petty_cash", "invoice", "fund", "manual"):
        n, amount = found.pop(source, (0, 0))
        # The journal page offers no petty cash filter yet: the period's entries are the closest list.
        out.append({"key": source, "label": SOURCE_NAMES[source], "amountCentavos": amount, "count": n,
                    "href": link("/finance/ledger", **span) if source == "petty_cash" else link("/finance/ledger", source=source, **span)})
    if found:
        out.append({"key": "other", "label": "Other sources", "amountCentavos": sum(a for _, a in found.values()), "count": sum(n for n, _ in found.values()), "href": link("/finance/ledger", **span)})
    # What happened, and typed by hand always; zero rows keep the picture's shape when little has, and
    # the smallest sources join "Other sources" when more happened than a card can show.
    shown = [r for r in out if r["count"] or r["key"] == "manual"]
    if len(shown) > BOOK_ROWS:
        largest = sorted((r for r in shown if r["key"] not in ("manual", "other")), key=lambda r: -r["amountCentavos"])[:BOOK_ROWS - 2]
        rest = [r for r in shown if r not in largest and r["key"] != "manual"]
        shown = [r for r in shown if r in largest or r["key"] == "manual"] + [
            {"key": "other", "label": "Other sources", "amountCentavos": sum(r["amountCentavos"] for r in rest), "count": sum(r["count"] for r in rest), "href": link("/finance/ledger", **span)}]
    else:
        shown += [r for r in out if r not in shown][:BOOK_ROWS - len(shown)]
    return {"sources": shown, "entries": sum(r["count"] for r in out), "totalCentavos": sum(r["amountCentavos"] for r in out), "href": link("/finance/ledger", **span)}


# ---- Coming up, and the Zoho link ------------------------------------------------------------------


def soon_card(c: Ctx) -> dict:
    from app.calendar_events import is_done, occurrence_link, occurrences, visible
    from app.payables_asof import owed_on
    from app.workdays import holidays_between

    until = c.on + timedelta(days=SOON_DAYS)
    rows = []
    if c.can("bills.view"):
        for o in owed_on(c.db, c.on):
            b = o.bill
            if c.on <= b.due_date <= until:
                rows.append(row(f"Bill {b.no} · {(b.supplier.company_name or b.supplier.name).strip()}", "Supplier bill falls due", f"/finance/bills/{b.id}", o.owed_centavos,
                                ("Due today", "warn") if b.due_date == c.on else None, b.due_date))
    can_calendar = c.can("calendar.use")
    if can_calendar:
        for e in visible(c.db, c.access.user):
            for d in occurrences(e, c.on, until):
                if not is_done(e, d):
                    rows.append(row(e.title, "Your calendar" if e.owner_id == c.access.user.id else f"Shared by {e.owner.full_name}", f"/finance{occurrence_link(e, d)}", None, None, d))
    for d, name in holidays_between(c.on, until):
        rows.append(row(name, "Day off", link("/finance/calendar", on=d.isoformat()) if can_calendar else None, None, ("Holiday", "plain"), d, holiday=True))
    rows.sort(key=lambda r: (r["on"], r["title"]))
    return {"rows": rows[:LISTED], "total": len(rows), "href": "/finance/calendar" if can_calendar else link("/finance/bills", queue="month_end")}


def link_card(c: Ctx) -> dict:
    """How the Zoho reader stands, from its own run records. Zoho itself isn't asked."""
    from app.routers.zoho_source import organization
    from app.zoho_month_sync import usage_today, zoho_day_limit_hit

    try:
        org = organization(c.settings)
    except HTTPException:
        return {"connected": False, "href": "/finance/integrations/zoho"}
    last = c.db.scalar(select(ZohoSourceRun).where(ZohoSourceRun.organization_id == org).order_by(ZohoSourceRun.started_at.desc()).limit(1))
    return {"connected": True, "href": "/finance/integrations/zoho", "lastUpdate": last.finished_at.isoformat() if last else None,
            "usedToday": usage_today(c.db, org), "dailyLimit": (last.coverage.get("dailyLimit") if last else None) or c.settings.zoho_daily_limit,
            "stoppedForToday": zoho_day_limit_hit(c.db, org), "error": bool(last and last.coverage.get("error"))}


# ---- The hand-offs ----------------------------------------------------------------------------------


def supplier_of(b: Bill) -> str:
    return (b.supplier.company_name or b.supplier.name).strip()


def bill_title(b: Bill) -> str:
    return f"Bill {b.no} · {supplier_of(b)}" if b.no else f"Draft bill · {supplier_of(b)}"


def last_event(record, *kinds):
    return next((e for e in reversed(record.events) if e.kind in kinds), None)


def waited(c: Ctx, at: datetime | None, label: str) -> tuple[str, str]:
    days = c.days_since(at) if at else 0
    return (f"Waiting {days} days", "warn") if days >= STALE_DAYS else (label, "plain")


def bill_lists(c: Ctx) -> dict:
    """The Payables queues, by the rules `filter_bills` keeps (app/payables_work.py)."""
    from app.payables_work import bill_rows, filter_bills
    from app.routers.payables import set_aside

    def read():
        rows = bill_rows(c.db)
        held = set_aside(c.db, [b.id for b in rows])
        return {q: filter_bills(rows, c.access.user, c.on, held, queue=q)
                for q in ("drafts", "returned", "approve", "check", "prepare", "sent_approve", "sent_check")} | {"all": rows, "held": held}

    return c.once("bills", read)


def petty_lists(c: Ctx) -> dict:
    from app.routers.petty_cash import may, preparers

    def read():
        me = c.access.user.id
        open_ = list(c.db.scalars(select(PettyCashVoucher).where(PettyCashVoucher.status.in_(("draft", "to_check", "returned")))
                                  .order_by(PettyCashVoucher.voucher_date, PettyCashVoucher.number)))
        return {"check": [v for v in open_ if may(c.access.user, v)["canCheck"]],
                "returned": [v for v in open_ if v.status == "returned" and me in preparers(v)],
                "drafts": [v for v in open_ if v.status == "draft" and me in preparers(v) and c.can("petty_cash.create")],
                "sent": [v for v in open_ if v.status == "to_check" and me in preparers(v)]}

    return c.once("petty", read)


def voucher_lists(c: Ctx) -> dict:
    from app.payables_work import filter_vouchers

    def read():
        rows = list(c.db.scalars(select(PaymentVoucher).order_by(PaymentVoucher.updated_at)))
        me = c.access.user.id
        lists = {q: filter_vouchers(rows, c.access.user, q) for q in ("drafts", "returned", "release")}
        lists["sent"] = [v for v in rows if v.status == "to_release" and v.prepared_by_id == me and v not in lists["release"]]
        return lists

    return c.once("vouchers", read)


def for_you(c: Ctx) -> list[dict]:
    return c.once("for_you", lambda: read_for_you(c))


def read_for_you(c: Ctx) -> list[dict]:
    """What's waiting for this person, oldest first. Each row opens its record; nothing is approved from here."""
    from app.payables_work import balance

    items: list[dict] = []

    def add(area: str, group: int, at, *args, **kwargs) -> None:
        items.append(row(*args, area=area, group=group, sort=(at.replace(tzinfo=None) if at else datetime.max).isoformat(), **kwargs))

    if c.can("bills.view"):
        lists = bill_lists(c)
        for b in lists["returned"]:
            e = last_event(b, "returned")
            add("payables", 0, e.at if e else None, bill_title(b), f"{e.who}: {e.text or 'Returned for correction'}" if e else "Returned for correction",
                f"/finance/bills/{b.id}", b.payable_centavos, ("Returned", "warn"), kind="returned", queue=link("/finance/bills", queue="returned"))
        for b in lists["approve"]:
            e = last_event(b, "submitted", "resubmitted")
            add("payables", 1, e.at if e else None, bill_title(b), f"Sent by {e.who}" if e else "To approve", f"/finance/bills/{b.id}", b.payable_centavos,
                waited(c, e.at if e else None, "To approve"), kind="approve", queue=link("/finance/bills", queue="approve"))
        for b in lists["check"]:
            e = last_event(b, "approved")
            add("payables", 1, e.at if e else None, bill_title(b), f"Approved by {b.approved_by} · check the tax withheld", f"/finance/bills/{b.id}", b.payable_centavos,
                waited(c, e.at if e else None, "Your check"), kind="check", queue=link("/finance/bills", queue="check"))
        for b in lists["drafts"]:
            add("payables", 2, b.created_at, bill_title(b), "Draft, not yet sent", f"/finance/bills/{b.id}", b.payable_centavos, ("Draft", "plain"), kind="draft", queue=link("/finance/bills", queue="drafts"))
        ready = lists["prepare"]
        if ready:
            add("payables", 3, None, f"{len(ready)} {'bill' if len(ready) == 1 else 'bills'} ready for a payment voucher", "Money available to prepare",
                link("/finance/bills", queue="prepare"), sum(balance(b, lists["held"])["availableCentavos"] for b in ready), ("To prepare", "plain"), kind="prepare", records=len(ready), queue=link("/finance/bills", queue="prepare"))
    if c.can("vouchers.view"):
        lists = voucher_lists(c)
        for v in lists["returned"]:
            e = last_event(v, "returned")
            add("payables", 0, e.at if e else None, f"{v.number} · {v.supplier.name}", f"{e.who}: {e.text or 'Returned for correction'}" if e else "Returned for correction",
                f"/finance/vouchers/{v.id}", v.total_centavos, ("Returned", "warn"), kind="returned", queue=link("/finance/vouchers", queue="returned"))
        for v in lists["release"]:
            add("payables", 1, v.updated_at, f"{v.number} · {v.supplier.name}", "Payment voucher to release", f"/finance/vouchers/{v.id}", v.total_centavos,
                waited(c, v.updated_at, "To release"), kind="release", queue=link("/finance/vouchers", queue="release"))
        for v in lists["drafts"]:
            add("payables", 2, v.updated_at, f"{v.number} · {v.supplier.name}", "Draft payment voucher", f"/finance/vouchers/{v.id}", v.total_centavos, ("Draft", "plain"), kind="draft", queue=link("/finance/vouchers", queue="drafts"))
    if c.can("petty_cash.view"):
        lists = petty_lists(c)
        for v in lists["returned"]:
            e = last_event(v, "returned")
            add("cash", 0, e.at if e else None, f"{v.number} · {v.fund.name}", f"{e.who}: {e.text or 'Returned for correction'}" if e else "Returned for correction",
                f"/finance/petty-cash/{v.id}", v.total_centavos, ("Returned", "warn"), kind="returned", queue=link("/finance/petty-cash", show="returned"))
        for v in lists["check"]:
            add("cash", 1, v.submitted_at, f"{v.number} · {v.fund.name}", f"Petty cash voucher from {v.created_by}", f"/finance/petty-cash/{v.id}", v.total_centavos,
                waited(c, v.submitted_at, "To check"), kind="check", queue=link("/finance/petty-cash", show="to_check"))
        for v in lists["drafts"]:
            add("cash", 2, v.created_at, f"{v.number} · {v.fund.name}", "Draft, not yet sent", f"/finance/petty-cash/{v.id}", v.total_centavos, ("Draft", "plain"), kind="draft", queue=link("/finance/petty-cash", show="draft"))
    if c.can("journal.view") and c.can("journal.approve"):
        me = c.access.user.id
        waiting = c.db.scalars(select(JournalEntry).where(JournalEntry.status == "waiting", (JournalEntry.posted_by_id.is_(None)) | (JournalEntry.posted_by_id != me)).order_by(JournalEntry.created_at))
        for e in waiting:
            add("cash", 1, e.created_at, f"{e.number} · {e.memo}", f"Journal entry from {e.posted_by}", link("/finance/ledger", q=e.number), sum(ln.debit_centavos for ln in e.lines),
                waited(c, e.created_at, "To approve"), kind="approve", queue=link("/finance/ledger", status="waiting"))
    if c.can("funds.view") and (c.can("funds.release") or c.can("funds.check") or c.can("funds.settle")):
        from app.routers.funds import check_hold

        rows = c.db.scalars(select(FundRequest).where(FundRequest.status.in_(("to_release", "to_check", "to_return", "to_reimburse"))).order_by(FundRequest.approved_at))
        for r in rows:
            who = r.team_name or r.requester_name
            if r.status == "to_release" and c.can("funds.release"):
                add("payables", 1, r.approved_at, f"{r.number} · {who}", "Marketing request to release", f"/finance/funds/{r.id}", r.approved_centavos,
                    waited(c, r.approved_at, "To release"), kind="release", queue=link("/finance/funds", stage="to_release"))
            elif r.status == "to_check" and c.can("funds.check") and check_hold(r, c.access.user) is None:
                add("payables", 1, r.liquidated_at or r.approved_at, f"{r.number} · {who}", "Marketing liquidation to review", f"/finance/funds/{r.id}", r.released_centavos,
                    waited(c, r.liquidated_at, "To review"), kind="review", queue=link("/finance/funds", stage="to_check"))
            elif r.status in ("to_return", "to_reimburse") and c.can("funds.settle"):
                due = r.return_due_centavos - r.returned_centavos if r.status == "to_return" else r.reimburse_due_centavos - r.reimbursed_centavos
                add("payables", 1, r.updated_at, f"{r.number} · {who}", "Refund to record" if r.status == "to_return" else "Reimbursement to record", f"/finance/funds/{r.id}", due,
                    ("To settle", "plain"), kind="settle", queue=link("/finance/funds", stage="to_settle"))
    if c.can("sales_orders.view"):
        from app.routers.sales_orders import permissions, prepared

        for o in c.db.scalars(select(SalesOrder).where(SalesOrder.status.in_(("submitted", "returned"))).order_by(SalesOrder.updated_at)):
            if permissions(o, c.access.user)["canApprove"]:
                add("receivables", 1, o.updated_at, f"{o.number} · {o.customer_name}", "Sales order to approve", f"/finance/sales-orders/{o.id}", o.total_centavos,
                    waited(c, o.updated_at, "To approve"), kind="approve", queue=link("/finance/sales-orders/local", queue="to_approve"))
            elif o.status == "returned" and prepared(o, c.access.user) and c.can("sales_orders.create"):
                add("receivables", 0, o.updated_at, f"{o.number} · {o.customer_name}", "Sales order returned to you", f"/finance/sales-orders/{o.id}", o.total_centavos, ("Returned", "warn"), kind="returned", queue=link("/finance/sales-orders/local", queue="returned"))
    items.sort(key=lambda i: (i.pop("group"), i.pop("sort")))
    return items


def on_others(c: Ctx) -> list[dict]:
    """The sender's side: what this person passed on and is still with someone else, a row per step."""
    rows: list[dict] = []

    def add(found: list, noun: str, plural: str, step: str, href: str, amount, oldest) -> None:
        if not found:
            return
        at = [x for x in (oldest(r) for r in found) if x]
        meta = f"Oldest {max(c.days_since(x) for x in at)} days" if at else ""
        rows.append(row(f"{len(found)} {noun if len(found) == 1 else plural} {step}", meta, href, sum(amount(r) for r in found), None, None, records=len(found)))

    def submitted(b):
        e = last_event(b, "submitted", "resubmitted", "approved")
        return e.at if e else None

    if c.can("bills.view"):
        lists = bill_lists(c)
        me = c.access.user.id
        add(lists["sent_approve"], "bill", "bills", "waiting for approval", link("/finance/bills", queue="sent_approve"), lambda b: b.payable_centavos, submitted)
        add(lists["sent_check"], "bill", "bills", "waiting for the tax check", link("/finance/bills", queue="sent_check"), lambda b: b.payable_centavos, submitted)
        approved = [b for b in lists["all"] if b.status == "draft" and b.stage == "to_check" and b.approved_by_id == me and b.submitted_by_id != me]
        add(approved, "bill you approved", "bills you approved", "waiting for the tax check", link("/finance/bills", show="to_check"), lambda b: b.payable_centavos, submitted)
        sent_back = [b for b in lists["all"] if b.status == "draft" and b.stage == "returned" and (e := last_event(b, "returned")) is not None and e.who_id == me]
        add(sent_back, "bill you returned", "bills you returned", "being corrected", link("/finance/bills", show="returned"), lambda b: b.payable_centavos, lambda b: last_event(b, "returned").at)
    if c.can("vouchers.view"):
        add(voucher_lists(c)["sent"], "payment voucher", "payment vouchers", "waiting to be released", link("/finance/vouchers", show="to_release"), lambda v: v.total_centavos, lambda v: v.updated_at)
    if c.can("petty_cash.view"):
        add(petty_lists(c)["sent"], "petty cash voucher", "petty cash vouchers", "waiting to be checked", link("/finance/petty-cash", show="to_check"), lambda v: v.total_centavos, lambda v: v.submitted_at)
    if c.can("journal.view") and c.can("journal.post"):
        mine = list(c.db.scalars(select(JournalEntry).where(JournalEntry.status == "waiting", JournalEntry.posted_by_id == c.access.user.id)))
        add(mine, "journal entry", "journal entries", "waiting for approval", link("/finance/ledger", status="waiting"), lambda e: sum(ln.debit_centavos for ln in e.lines), lambda e: e.created_at)
    if c.can("sales_orders.view"):
        from app.routers.sales_orders import prepared

        orders = [o for o in c.db.scalars(select(SalesOrder).where(SalesOrder.status == "submitted")) if prepared(o, c.access.user)]
        add(orders, "sales order", "sales orders", "waiting for approval", link("/finance/sales-orders/local", queue="waiting"), lambda o: o.total_centavos, lambda o: o.updated_at)
    return rows


def wait_card(c: Ctx) -> dict:
    items = for_you(c)
    areas = {"payables": 0, "receivables": 0, "cash": 0}
    for i in items:
        areas[i["area"]] += i.get("records", 1)
    others = on_others(c)
    first = next((i for i in items if i["kind"] != "draft"), items[0] if items else None)
    return {"forYou": items[:LISTED], "forYouTotal": sum(i.get("records", 1) for i in items), "byArea": areas, "seeAll": first["queue"] if first else None,
            "others": others[:LISTED], "othersTotal": sum(r["records"] for r in others),
            "prices": c.can("prices.approve") and c.can("prices.view")}


# ---- The leads ---------------------------------------------------------------------------------------


def action(label: str, href: str, primary: bool = False, title: str | None = None) -> dict:
    return {"label": label, "href": href, "primary": primary, "title": title}


def primary_first(actions: list[dict]) -> list[dict]:
    return [a | {"primary": i == 0} for i, a in enumerate(actions)]


def released(c: Ctx) -> tuple[int, int]:
    """Money released in the period: payment vouchers by their paid-on date, marketing requests by the day they were released."""
    amount = count = 0
    if c.can("vouchers.view"):
        n, total = c.db.execute(select(func.count(), func.coalesce(func.sum(PaymentVoucher.total_centavos), 0))
                                .where(PaymentVoucher.status == "released", PaymentVoucher.paid_on >= c.start, PaymentVoucher.paid_on <= c.end)).one()
        amount, count = int(total), n
    if c.can("funds.view"):
        for r in c.db.scalars(select(FundRequest).where(FundRequest.released_at.is_not(None), FundRequest.status != "cancelled")):
            if c.within(c.local_day(r.released_at)):
                amount += r.released_centavos or 0
                count += 1
    return amount, count


def lead_release(c: Ctx) -> dict:
    rows, oldest = [], []
    if c.can("vouchers.view") and c.can("vouchers.release"):
        found = voucher_lists(c)["release"]
        rows.append({"key": "vouchers", "label": "Supplier payments", "amountCentavos": sum(v.total_centavos for v in found), "count": len(found), "noun": "voucher", "href": link("/finance/vouchers", queue="release")})
        oldest += [v.updated_at for v in found]
    if c.can("funds.view") and c.can("funds.release"):
        found = list(c.db.scalars(select(FundRequest).where(FundRequest.status == "to_release")))
        rows.append({"key": "funds", "label": "Marketing requests", "amountCentavos": sum(r.approved_centavos for r in found), "count": len(found), "noun": "request", "href": link("/finance/funds", stage="to_release")})
        oldest += [r.approved_at for r in found]
    amount, count = released(c)
    actions = [action("Open payments to release", link("/finance/vouchers", queue="release"))] if c.can("vouchers.view") and c.can("vouchers.release") else []
    if c.can("funds.view"):
        actions.append(action("Open marketing requests", link("/finance/funds", stage="to_release")))
    return {"key": "release", "rows": rows, "totalCentavos": sum(r["amountCentavos"] for r in rows), "count": sum(r["count"] for r in rows),
            "oldestDays": max((c.days_since(x) for x in oldest), default=0), "releasedCentavos": amount, "releasedCount": count, "actions": primary_first(actions)}


def lead_cash(c: Ctx) -> dict:
    head = (c.can("bills.first") or c.can("journal.first")) and c.can("bills.view") and c.can("bills.approve")
    actions = [action("Open my approvals", link("/finance/bills", queue="approve"))] if head else []
    actions.append(action("Open cash accounts", "/finance/ledger/accounts"))
    if not head and c.can("bank.view"):
        actions.append(action("Open bank reconciliation", "/finance/bank"))
    return {"key": "cash", "actions": primary_first(actions)}


def lead_vat(c: Ctx) -> dict:
    return {"key": "vat", "actions": primary_first([
        action("Open VAT summary (2550Q)", link("/finance/bir/vat", year=c.fiscal_year, quarter=c.fiscal_quarter), title="2550Q: the quarterly VAT return"),
        action("Open BIR readiness", link("/finance/bir/readiness", start=c.start.isoformat(), end=min(c.end, c.on).isoformat()))])}


def lead_recv(c: Ctx) -> dict:
    return {"key": "recv", "viewOnly": not c.can("invoices.collect"), "actions": primary_first([
        action("Open customer aging", "/finance/invoices/receivables"), action("Open Zoho invoices", link("/finance/invoices/zoho", company="all", period="all"))])}


def lead_sup(c: Ctx) -> dict:
    actions = [action("Open bills by how late", "/finance/bills/aging")]
    if c.can("bills.approve"):
        actions.append(action("Open my approvals", link("/finance/bills", queue="approve")))
    return {"key": "sup", "actions": primary_first(actions)}


def lead_check(c: Ctx) -> dict:
    found = [i for i in for_you(c) if i["kind"] == "check" and i["href"].startswith("/finance/bills/")]
    actions = [action("Open my tax checks", link("/finance/bills", queue="check"))]
    if c.can("bir.view"):
        actions.append(action("Open the SLP", link("/finance/bir/lists", list="slp", year=c.fiscal_year, quarter=c.fiscal_quarter), title="SLP: the BIR's list of purchases per supplier"))
    return {"key": "check", "rows": found[:LISTED], "count": len(found), "totalCentavos": sum(i["amountCentavos"] for i in found), "actions": primary_first(actions)}


def lead_mine(c: Ctx) -> dict:
    me = c.access.user.id
    bills = bill_lists(c) if c.can("bills.view") else {k: [] for k in ("returned", "drafts", "sent_approve", "sent_check", "all")}
    petty = petty_lists(c) if c.can("petty_cash.view") else {k: [] for k in ("returned", "drafts", "sent")}

    def stage(key: str, label: str, found_bills: list, found_petty: list, bill_href: str, petty_href: str, noun: str = "record") -> dict:
        return {"key": key, "label": label, "count": len(found_bills) + len(found_petty), "noun": noun,
                "amountCentavos": sum(b.payable_centavos for b in found_bills) + sum(v.total_centavos for v in found_petty),
                "href": bill_href if found_bills or not found_petty and c.can("bills.view") else petty_href}

    posted_bills = [b for b in bills["all"] if b.status == "recorded" and b.submitted_by_id == me and c.within(b.bill_date)]
    posted_petty: list = []
    if c.can("petty_cash.view"):
        from app.routers.petty_cash import preparers

        posted_petty = [v for v in c.db.scalars(select(PettyCashVoucher).where(PettyCashVoucher.status == "posted", PettyCashVoucher.voucher_date >= c.start, PettyCashVoucher.voucher_date <= c.end)) if me in preparers(v)]
    stages = [
        stage("returned", "Returned to you", bills["returned"], petty["returned"], link("/finance/bills", queue="returned"), link("/finance/petty-cash", show="returned")),
        stage("drafts", "Drafts", bills["drafts"], petty["drafts"], link("/finance/bills", queue="drafts"), link("/finance/petty-cash", show="draft")),
        stage("approve", "Waiting for approval", bills["sent_approve"], [], link("/finance/bills", queue="sent_approve"), link("/finance/bills", queue="sent_approve"), "bill"),
        stage("check", "Waiting for a check", bills["sent_check"], petty["sent"], link("/finance/bills", queue="sent_check"), link("/finance/petty-cash", show="to_check")),
        stage("posted", "Posted", posted_bills, posted_petty, link("/finance/bills", show="ready"), link("/finance/petty-cash", show="posted")),
    ]
    progress = stages[:4]
    actions = []
    if c.can("bills.create") and c.can("bills.view"):
        actions.append(action("Record a new bill", "/finance/bills/new"))
    if c.can("petty_cash.create") and c.can("petty_cash.view"):
        actions.append(action("New petty cash voucher", "/finance/petty-cash/new"))
    first = [i for i in for_you(c) if i["kind"] in ("returned", "draft")]
    return {"key": "mine", "stages": stages, "totalCentavos": sum(s["amountCentavos"] for s in progress), "count": sum(s["count"] for s in progress),
            "returned": stages[0]["count"], "rows": first[:LISTED], "rowsTotal": len(first), "actions": primary_first(actions)}


def lead_petty(c: Ctx) -> dict:
    actions = [action("New petty cash voucher", "/finance/petty-cash/new")] if c.can("petty_cash.create") else []
    actions.append(action("Open petty cash", "/finance/petty-cash"))
    return {"key": "petty", "actions": primary_first(actions)}


LEADS = {"release": lead_release, "cash": lead_cash, "vat": lead_vat, "recv": lead_recv, "sup": lead_sup, "check": lead_check, "mine": lead_mine, "petty": lead_petty}


def may_lead(c: Ctx) -> dict[str, bool]:
    return {
        "release": (c.can("vouchers.view") and c.can("vouchers.release")) or (c.can("funds.view") and c.can("funds.release")),
        "cash": c.has("cash"),
        "vat": c.can("bir.view"),
        "recv": c.can("invoices.view"),
        "sup": c.can("bills.view"),
        "check": c.can("bills.view") and c.can("bills.check"),
        "mine": (c.can("bills.create") and c.can("bills.view")) or (c.can("petty_cash.create") and c.can("petty_cash.view")),
        "petty": c.can("petty_cash.view"),
    }


def main_lead(c: Ctx, may: dict[str, bool]) -> str:
    """Each person's hero, from what they do, never their role's name. Whoever approves first (the main approver)
    leads with cash, whoever releases money with what's to release, so the two who can also read BIR reports keep
    the heroes the approved mock-up gave them; then BIR work, collections read but not posted, recording bills, cash."""
    posts = c.can("invoices.collect") or c.can("journal.post") or c.can("bills.create")
    if may["cash"] and (c.can("bills.first") or c.can("journal.first")):
        return "cash"
    if may["release"]:
        return "release"
    if may["vat"] and (c.can("tax.view") or c.can("tax.manage")):
        return "vat"
    if may["recv"] and not posts:
        return "recv"
    return next((k for k in ("mine", "cash", "vat", "recv", "sup", "petty") if may[k]), "none")


def area_lead(area: str, may: dict[str, bool]) -> str | None:
    picks = {"payables": ("release", "check", "mine", "sup"), "receivables": ("recv",), "cash": ("cash", "petty"), "tax": ("vat",)}[area]
    return next((k for k in picks if may[k]), None)


def views_for(c: Ctx, cards: dict, may: dict[str, bool]) -> tuple[dict, list[str]]:
    views, used = {}, set()

    def view(lead: str, keys) -> dict:
        used.add(lead)
        return {"lead": lead, "cards": [k for k in keys if k in cards and k != LEAD_CARD.get(lead)][:MOST_CARDS],
                # These leads already list what's waiting for this person: the hand-offs card shows the other side.
                "othersOnly": lead in ("mine", "check")}

    lead = main_lead(c, may)
    suggested = [k for k in SUGGESTED.get(lead, ()) if k in cards]
    if len(suggested) < 3:
        suggested += [k for k in CARD_ORDER if k in cards and k not in suggested and k != LEAD_CARD.get(lead) and k not in ("link", "dl")]
    views["overview"] = view(lead, suggested)
    for area, keys in AREA_CARDS.items():
        if chosen := area_lead(area, may):
            views[area] = view(chosen, keys)
    return views, sorted(used)


BUILDERS = {"cash": cash_card, "inout": inout_card, "went": went_card, "ar": ar_card, "od": od_card, "coll": coll_card, "due": due_card, "zoho": zoho_card,
            "ap": ap_card, "petty": petty_card, "mkt": mkt_card, "vat": vat_card, "ewt": ewt_card, "ready": ready_card, "books": books_card,
            "dl": lambda c: {"listed": False}, "soon": soon_card, "link": link_card}


def build(access, db, settings, key: str) -> dict:
    from app.routers.funds import today

    on = today(settings)
    start, end, spans, year, q = period_of(key, on, bir.taxpayer(db)["fiscalMonthEnd"])
    c = Ctx(access, db, settings, key, on, ZoneInfo(settings.org_timezone), start, end, spans, year, q)
    cards = {k: make(c) for k, make in BUILDERS.items() if c.has(k)}
    if any(c.can(doing) and c.can(view) for doing, view in DOING):
        cards["wait"] = wait_card(c)
    may = may_lead(c)
    views, used = views_for(c, cards, may)
    leads = {k: LEADS[k](c) if k in LEADS else {"key": k, "actions": []} for k in used}
    counts = dict(cards["wait"]["byArea"]) if "wait" in cards else {"payables": 0, "receivables": 0, "cash": 0}
    # BIR lists that disagree with the books are this person's to clear if they prepare the BIR files.
    counts["tax"] = cards["ready"]["counts"]["differs"] if "ready" in cards and c.can("bir.prepare") else 0
    shown = {k: counts[k] for k in ("payables", "receivables", "cash", "tax") if k in views}
    return {
        "on": on.isoformat(),
        "period": {"key": key, "start": start.isoformat(), "end": end.isoformat(), "byUnit": "by week" if key == "month" else "by month"},
        "cards": cards, "leads": leads, "views": views,
        "counts": shown | {"overview": sum(shown.values())},
        # What the person may choose for their Overview: everything they can see, except what their hero already shows.
        "pickable": [{"key": k, "area": CARD_AREAS[k]} for k in CARD_ORDER if k in cards and k != LEAD_CARD.get(views["overview"]["lead"])],
    }


@router.get("/overview")
def overview(access: CurrentAccess, db: DB, settings: SettingsDep, period: Period = "month") -> dict:
    """The Living Overview for whoever asks (top of this file). Nothing is asked of another app."""
    return build(access, db, settings, period)
