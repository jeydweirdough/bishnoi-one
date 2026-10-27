"""Finance's reports (decided 2026-10-25, benchmarks/surpass.md §11): one registry, each report in
a group (Sales, Expenses, Purchases, Accounting) and needing the permission for its data, drawn by
the one app's shared report kit (src/platform/reports/). The BIR's books, statements and forms
stay under Taxes (app/routers/bir.py).

- GET /finance/reports: the reports this person may open.
- GET /finance/reports/{key}?from&to: one report: columns, rows, headline figures, chart.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.access import Access, CurrentAccess
from app.deps import DB, SettingsDep
from app.models import (
    Bill,
    ExpenseCategory,
    FundExpense,
    FundRequest,
    Invoice,
    InvoicePayment,
    JournalEntry,
    JournalLine,
    PaymentVoucher,
    Supplier,
)
from app.routers.receivables import BUCKETS, bucket_of

router = APIRouter(prefix="/finance/reports", tags=["reports"])


def col(key: str, label: str, kind: str = "text") -> dict:
    return {"key": key, "label": label, "kind": kind}


def fig(label: str, value, kind: str = "number", tone: str | None = None) -> dict:
    return {"label": label, "value": value, "kind": kind, **({"tone": tone} if tone else {})}


def bar(x: str, *series: str) -> dict:
    return {"kind": "bar", "x": x, "series": list(series)}


@dataclass
class Ctx:
    db: DB
    first: date
    last: date
    start: datetime
    end: datetime


@dataclass
class Report:
    key: str
    title: str
    group: str
    about: str
    build: Callable[[Ctx], tuple]
    needs: str
    dated: bool = True
    # A statement whose working-out is fixed (decided 2026-10-26): filtered and exported, never
    # customised; the report builder offers "Customise" only on the others.
    fixed: bool = False


def issued_in(c: Ctx):
    return select(Invoice).where(Invoice.status == "issued", Invoice.invoice_date >= c.first, Invoice.invoice_date <= c.last)


# --- Sales -----------------------------------------------------------------------------------------


def sales_register(c: Ctx):
    rows = [{"date": i.invoice_date.isoformat(), "number": i.number or "", "customer": i.customer_name, "salesperson": i.salesperson_name or "", "total": i.total_centavos,
             "tax": i.tax_centavos, "paid": i.paid_centavos, "balance": i.total_centavos - i.paid_centavos} for i in c.db.scalars(issued_in(c).order_by(Invoice.invoice_date, Invoice.number))]
    return (
        [col("date", "Date", "date"), col("number", "Invoice"), col("customer", "Customer"), col("salesperson", "Salesperson"), col("total", "Total", "money"), col("tax", "VAT", "money"), col("paid", "Paid", "money"), col("balance", "Balance", "money")],
        rows,
        [fig("Invoices", len(rows)), fig("Invoiced", sum(r["total"] for r in rows), "money"), fig("Collected on them", sum(r["paid"] for r in rows), "money", "good"), fig("Still owed", sum(r["balance"] for r in rows), "money", "warn" if any(r["balance"] for r in rows) else None)],
        None,
    )


def sales_by(key: str, label: str):
    def build(c: Ctx):
        by: dict[str, dict] = {}
        for i in c.db.scalars(issued_in(c)):
            name = (i.customer_name if key == "customer" else i.salesperson_name) or "Not set"
            r = by.setdefault(name, {"name": name, "invoices": 0, "total": 0, "paid": 0})
            r["invoices"] += 1
            r["total"] += i.total_centavos
            r["paid"] += i.paid_centavos
        rows = sorted(by.values(), key=lambda r: -r["total"])
        total = sum(r["total"] for r in rows)
        for r in rows:
            r["share"] = round(r["total"] / total, 3) if total else None
        return (
            [col("name", label), col("invoices", "Invoices", "number"), col("total", "Invoiced", "money"), col("paid", "Collected", "money"), col("share", "Share of sales", "percent")],
            rows,
            [fig("Invoiced", total, "money"), fig(f"{label}s", len(rows)), fig("Top share", rows[0]["share"] if rows else None, "percent")],
            bar("name", "total", "paid"),
        )

    return build


def collections(c: Ctx):
    by: dict[str, dict] = {}
    q = select(InvoicePayment).where(InvoicePayment.removed_at.is_(None), InvoicePayment.paid_on >= c.first, InvoicePayment.paid_on <= c.last)
    for p in c.db.scalars(q):
        r = by.setdefault(p.method, {"method": p.method.replace("_", " ").capitalize(), "payments": 0, "amount": 0, "withheld": 0})
        r["payments"] += 1
        r["amount"] += p.amount_centavos
        r["withheld"] += p.cwt_centavos
    rows = sorted(by.values(), key=lambda r: -r["amount"])
    return (
        [col("method", "How paid"), col("payments", "Payments", "number"), col("amount", "Collected", "money"), col("withheld", "Tax withheld (2307)", "money")],
        rows,
        [fig("Collected", sum(r["amount"] for r in rows), "money", "good"), fig("Payments", sum(r["payments"] for r in rows)), fig("Tax withheld", sum(r["withheld"] for r in rows), "money")],
        bar("method", "amount"),
    )


def receivables_ageing(c: Ctx):
    """As of the period's last day: what each customer still owes, by how late it is."""
    on = c.last
    by: dict[str, dict] = {}
    q = select(Invoice).where(Invoice.status == "issued", Invoice.paid_centavos < Invoice.total_centavos, Invoice.invoice_date <= on)
    for i in c.db.scalars(q):
        owed = i.total_centavos - i.paid_centavos
        late = (on - (i.invoice_date + timedelta(days=i.terms_days))).days
        r = by.setdefault(i.customer_name, {"customer": i.customer_name, **{k: 0 for k, _, _ in BUCKETS}, "total": 0})
        r[bucket_of(max(0, late))] += owed
        r["total"] += owed
    rows = sorted(by.values(), key=lambda r: -r["total"])
    late_total = sum(r["total"] - r["current"] for r in rows)
    return (
        [col("customer", "Customer"), *(col(k, label, "money") for k, label, _ in BUCKETS), col("total", "Total owed", "money")],
        rows,
        [fig("Owed", sum(r["total"] for r in rows), "money"), fig("Late", late_total, "money", "bad" if late_total else None), fig("Over 90 days", sum(r["over_90"] for r in rows), "money", "bad" if any(r["over_90"] for r in rows) else None)],
        bar("customer", "total"),
    )


# --- Expenses (marketing requests) -------------------------------------------------------------------

FUND_LABELS = {"to_release": "To release", "to_liquidate": "To liquidate", "to_check": "To review", "to_return": "Refund due", "to_reimburse": "Reimbursement due", "closed": "Closed", "cancelled": "Cancelled"}


def requests_by_status(c: Ctx):
    by: dict[str, dict] = {}
    q = select(FundRequest).where(FundRequest.approved_at >= c.start, FundRequest.approved_at < c.end)
    for f in c.db.scalars(q):
        r = by.setdefault(f.status, {"status": FUND_LABELS.get(f.status, f.status), "requests": 0, "approved": 0, "released": 0})
        r["requests"] += 1
        r["approved"] += f.approved_centavos
        r["released"] += f.released_centavos or 0
    rows = sorted(by.values(), key=lambda r: -r["requests"])
    return (
        [col("status", "Status"), col("requests", "Requests", "number"), col("approved", "Approved", "money"), col("released", "Released", "money")],
        rows,
        [fig("Requests", sum(r["requests"] for r in rows)), fig("Approved", sum(r["approved"] for r in rows), "money"), fig("Released", sum(r["released"] for r in rows), "money")],
        bar("status", "approved", "released"),
    )


def expenses_by_category(c: Ctx):
    names = {x.id: x.name for x in c.db.scalars(select(ExpenseCategory))}
    by: dict[str, dict] = {}
    q = select(FundExpense).where(FundExpense.spent_on >= c.first, FundExpense.spent_on <= c.last, FundExpense.accepted.is_not(False))
    for e in c.db.scalars(q):
        name = names.get(e.category_id or "", "Not categorised")
        r = by.setdefault(name, {"category": name, "items": 0, "amount": 0, "noReceipt": 0})
        r["items"] += 1
        r["amount"] += e.amount_centavos
        r["noReceipt"] += e.receipt_ref is None
    rows = sorted(by.values(), key=lambda r: -r["amount"])
    return (
        [col("category", "Expense category"), col("items", "Items", "number"), col("amount", "Spent", "money"), col("noReceipt", "Without a receipt", "number")],
        rows,
        [fig("Spent", sum(r["amount"] for r in rows), "money"), fig("Items", sum(r["items"] for r in rows)), fig("Without a receipt", sum(r["noReceipt"] for r in rows), tone="warn" if any(r["noReceipt"] for r in rows) else None)],
        bar("category", "amount"),
    )


def outstanding_advances(c: Ctx):
    today = c.last
    q = select(FundRequest).where(FundRequest.status.in_(("to_liquidate", "to_check", "to_return"))).order_by(FundRequest.liquidate_by.is_(None), FundRequest.liquidate_by)
    rows = []
    for f in c.db.scalars(q):
        late = (today - f.liquidate_by).days if f.liquidate_by else None
        rows.append({"number": f.number, "requester": f.requester_name, "team": f.team_name or "", "purpose": f.purpose, "released": f.released_centavos or 0,
                     "status": FUND_LABELS.get(f.status, f.status), "due": f.liquidate_by.isoformat() if f.liquidate_by else None, "daysLate": max(0, late) if late is not None else None})
    overdue = [r for r in rows if r["daysLate"]]
    return (
        [col("number", "Request"), col("requester", "Requester"), col("team", "Team"), col("purpose", "Purpose"), col("released", "Released", "money"), col("status", "Status"), col("due", "Liquidate by", "date"), col("daysLate", "Days late", "number")],
        rows,
        [fig("Outstanding", sum(r["released"] for r in rows), "money"), fig("Requests", len(rows)), fig("Overdue", len(overdue), tone="bad" if overdue else "good")],
        None,
    )


# --- Purchases (supplier bills) -----------------------------------------------------------------------


def supplier_names(c: Ctx) -> dict[str, str]:
    return {s.id: s.name for s in c.db.scalars(select(Supplier))}


def bills_by_supplier(c: Ctx):
    names = supplier_names(c)
    by: dict[str, dict] = {}
    q = select(Bill).where(Bill.status == "recorded", Bill.bill_date >= c.first, Bill.bill_date <= c.last)
    for b in c.db.scalars(q):
        name = names.get(b.supplier_id, "Supplier")
        r = by.setdefault(name, {"supplier": name, "bills": 0, "net": 0, "vat": 0, "withheld": 0, "payable": 0, "paid": 0})
        r["bills"] += 1
        for k, v in (("net", b.net_centavos), ("vat", b.vat_centavos), ("withheld", b.withheld_centavos), ("payable", b.payable_centavos), ("paid", b.paid_centavos)):
            r[k] += v
    rows = sorted(by.values(), key=lambda r: -r["payable"])
    return (
        [col("supplier", "Supplier"), col("bills", "Bills", "number"), col("net", "Net", "money"), col("vat", "Input VAT", "money"), col("withheld", "Tax withheld", "money"), col("payable", "Payable", "money"), col("paid", "Paid", "money")],
        rows,
        [fig("Bills", sum(r["bills"] for r in rows)), fig("Payable", sum(r["payable"] for r in rows), "money"), fig("Input VAT", sum(r["vat"] for r in rows), "money")],
        bar("supplier", "payable", "paid"),
    )


def payables_ageing(c: Ctx):
    """As of the period's last day: what's still owed to each supplier, by how late it is."""
    names = supplier_names(c)
    on = c.last
    by: dict[str, dict] = {}
    q = select(Bill).where(Bill.status == "recorded", Bill.paid_centavos < Bill.payable_centavos, Bill.bill_date <= on)
    for b in c.db.scalars(q):
        owed = b.payable_centavos - b.paid_centavos
        name = names.get(b.supplier_id, "Supplier")
        r = by.setdefault(name, {"supplier": name, **{k: 0 for k, _, _ in BUCKETS}, "total": 0})
        r[bucket_of(max(0, (on - b.due_date).days))] += owed
        r["total"] += owed
    rows = sorted(by.values(), key=lambda r: -r["total"])
    return (
        [col("supplier", "Supplier"), *(col(k, label, "money") for k, label, _ in BUCKETS), col("total", "Total owed", "money")],
        rows,
        [fig("Owed to suppliers", sum(r["total"] for r in rows), "money"), fig("Late", sum(r["total"] - r["current"] for r in rows), "money", "bad" if any(r["total"] - r["current"] for r in rows) else None)],
        bar("supplier", "total"),
    )


def vouchers_released(c: Ctx):
    names = supplier_names(c)
    q = select(PaymentVoucher).where(PaymentVoucher.status == "released", PaymentVoucher.paid_on >= c.first, PaymentVoucher.paid_on <= c.last).order_by(PaymentVoucher.paid_on)
    rows = [{"paid": v.paid_on.isoformat() if v.paid_on else None, "number": v.number, "supplier": names.get(v.supplier_id, "Supplier"), "method": v.method.replace("_", " ").capitalize(),
             "reference": v.bank_reference or v.check_number or "", "amount": v.total_centavos, "releasedBy": v.released_by or ""} for v in c.db.scalars(q)]
    return (
        [col("paid", "Paid on", "date"), col("number", "Voucher"), col("supplier", "Supplier"), col("method", "Method"), col("reference", "Reference"), col("amount", "Amount", "money"), col("releasedBy", "Released by")],
        rows,
        [fig("Paid out", sum(r["amount"] for r in rows), "money"), fig("Vouchers", len(rows))],
        None,
    )


# --- Accounting ----------------------------------------------------------------------------------------

SOURCES = {"manual": "Manual journals", "fund": "Marketing requests", "invoice": "Invoices", "bill": "Supplier bills", "voucher": "Payment vouchers"}


def journal_by_source(c: Ctx):
    q = (
        select(JournalEntry.source, func.count(func.distinct(JournalEntry.id)), func.coalesce(func.sum(JournalLine.debit_centavos), 0))
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(JournalEntry.entry_date >= c.first, JournalEntry.entry_date <= c.last, JournalEntry.status == "approved")
        .group_by(JournalEntry.source)
    )
    rows = sorted(({"source": SOURCES.get(s, s), "entries": int(n), "amount": int(a)} for s, n, a in c.db.execute(q)), key=lambda r: -r["amount"])
    waiting = c.db.scalar(select(func.count()).select_from(JournalEntry).where(JournalEntry.status == "waiting")) or 0
    return (
        [col("source", "Where entries came from"), col("entries", "Entries", "number"), col("amount", "Amount (debits)", "money")],
        rows,
        [fig("Entries", sum(r["entries"] for r in rows)), fig("Amount", sum(r["amount"] for r in rows), "money"), fig("Waiting for approval", waiting, tone="warn" if waiting else None)],
        bar("source", "amount"),
    )


# --- Accounting statements: fixed (the same working-out as the BIR's books, app/bir_reports.py) ----


def profit_and_loss(c: Ctx):
    from app import bir_reports as bir

    st = bir.income_statement(c.db, c.first, c.last)
    rows = [{"section": "Income", "code": r["code"], "account": r["account"], "amount": r["amountCentavos"]} for r in st["income"]]
    rows += [{"section": "Expenses", "code": r["code"], "account": r["account"], "amount": -r["amountCentavos"]} for r in st["expenses"]]
    t = st["totals"]
    return (
        [col("section", "Section"), col("code", "Code"), col("account", "Account"), col("amount", "Amount", "money")],
        rows,
        [fig("Income", t["incomeCentavos"], "money"), fig("Expenses", t["expensesCentavos"], "money"), fig("Net profit", t["netCentavos"], "money", "good" if t["netCentavos"] >= 0 else "bad")],
        bar("account", "amount") if rows else None,
    )


def balance_sheet(c: Ctx):
    from app import bir_reports as bir

    st = bir.balance_sheet(c.db, c.last)
    rows = [{"section": label, "code": r["code"], "account": r["account"], "amount": r["amountCentavos"]}
            for label, key in (("Assets", "assets"), ("Liabilities", "liabilities"), ("Equity", "equity")) for r in st[key]]
    t = st["totals"]
    return (
        [col("section", "Section"), col("code", "Code"), col("account", "Account"), col("amount", "Amount", "money")],
        rows,
        [fig("Assets", t["assetsCentavos"], "money"), fig("Liabilities", t["liabilitiesCentavos"], "money"), fig("Equity", t["equityCentavos"], "money"),
         fig("Balanced", 1 if t["balanced"] else 0, tone="good" if t["balanced"] else "bad")],
        None,
    )


def trial_balance(c: Ctx):
    from app import bir_reports as bir
    from app.models import Account

    sums = bir.balances(c.db, end=c.last)
    rows = []
    for a in c.db.scalars(select(Account).order_by(Account.code)):
        debit, credit = sums.get(a.id, (0, 0))
        if not debit and not credit:
            continue
        net = debit - credit
        rows.append({"code": a.code, "account": a.name, "type": a.type.capitalize(), "debit": max(net, 0), "credit": max(-net, 0)})
    d, k = sum(r["debit"] for r in rows), sum(r["credit"] for r in rows)
    return (
        [col("code", "Code"), col("account", "Account"), col("type", "Type"), col("debit", "Debit", "money"), col("credit", "Credit", "money")],
        rows,
        [fig("Debits", d, "money"), fig("Credits", k, "money"), fig("Difference", d - k, "money", "good" if d == k else "bad")],
        None,
    )


def general_ledger(c: Ctx):
    from app import bir_reports as bir

    gl = bir.general_ledger(c.db, c.first, c.last)
    rows = []
    for a in gl["accounts"]:
        rows.append({"date": c.first.isoformat(), "code": a["code"], "account": a["account"], "number": "", "memo": "Opening balance", "debit": None, "credit": None, "balance": a["openingCentavos"]})
        for r in a["rows"]:
            rows.append({"date": r["date"], "code": a["code"], "account": a["account"], "number": r["number"], "memo": r["memo"] or "", "debit": r["debitCentavos"], "credit": r["creditCentavos"], "balance": r["balanceCentavos"]})
    return (
        [col("date", "Date", "date"), col("code", "Code"), col("account", "Account"), col("number", "Entry"), col("memo", "Description"),
         col("debit", "Debit", "money"), col("credit", "Credit", "money"), col("balance", "Balance", "money")],
        rows,
        [fig("Accounts", len(gl["accounts"])), fig("Debits", sum(r["debit"] or 0 for r in rows), "money"), fig("Credits", sum(r["credit"] or 0 for r in rows), "money")],
        None,
    )


def cash_flow(c: Ctx):
    """Cash flow, direct: the money accounts (cash, bank, e-wallet, checks) at the start, what came in
    and went out each month, and at the end."""
    from app import bir_reports as bir

    money = bir.money_accounts(c.db)
    if not money:
        return ([col("month", "Month"), col("inflow", "Cash in", "money"), col("outflow", "Cash out", "money"), col("net", "Net", "money")], [],
                [fig("Money accounts set", 0, tone="warn")], None)
    opening = sum(d - k for a, (d, k) in bir.balances(c.db, before=c.first).items() if a in money)
    by_month: dict[str, list[int]] = {}
    for e in bir.entries_between(c.db, c.first, c.last):
        m = by_month.setdefault(e.entry_date.strftime("%Y-%m"), [0, 0])
        for ln in e.lines:
            if ln.account_id in money:
                m[0] += ln.debit_centavos
                m[1] += ln.credit_centavos
    rows, running = [], opening
    for month in sorted(by_month):
        i, o = by_month[month]
        running += i - o
        rows.append({"month": month, "inflow": i, "outflow": o, "net": i - o, "closing": running})
    return (
        [col("month", "Month"), col("inflow", "Cash in", "money"), col("outflow", "Cash out", "money"), col("net", "Net", "money"), col("closing", "Cash at month end", "money")],
        rows,
        [fig("Opening cash", opening, "money"), fig("Cash in", sum(r["inflow"] for r in rows), "money"), fig("Cash out", sum(r["outflow"] for r in rows), "money"),
         fig("Closing cash", running, "money", "good" if running >= 0 else "bad")],
        {"kind": "line", "x": "month", "series": ["closing"]} if rows else None,
    )


REPORTS: tuple[Report, ...] = (
    Report("sales-register", "Sales register", "Sales", "Every invoice issued in the period, with what's been paid and what's still owed.", sales_register, "invoices.view"),
    Report("sales-by-customer", "Sales by customer", "Sales", "What each customer was invoiced in the period, and their share.", sales_by("customer", "Customer"), "invoices.view"),
    Report("sales-by-salesperson", "Sales by salesperson", "Sales", "What each salesperson invoiced in the period (the sale behind every scorecard).", sales_by("salesperson", "Salesperson"), "invoices.view"),
    Report("collections", "Collections", "Sales", "Payments received in the period, by how they were paid.", collections, "invoices.view"),
    Report("receivables-ageing", "Receivables ageing", "Sales", "What each customer owes as of the period's last day, by how late it is.", receivables_ageing, "invoices.view"),
    Report("requests-by-status", "Marketing requests by status", "Expenses", "Requests approved in the period, where each stands now.", requests_by_status, "funds.view"),
    Report("expenses-by-category", "Expenses by category", "Expenses", "What liquidations spent in the period, by expense category.", expenses_by_category, "funds.view"),
    Report("outstanding-advances", "Outstanding advances", "Expenses", "Cash advances released and not yet settled, oldest first.", outstanding_advances, "funds.view", dated=False),
    Report("bills-by-supplier", "Bills by supplier", "Purchases", "Supplier bills recorded in the period, with input VAT and tax withheld.", bills_by_supplier, "bills.view"),
    Report("payables-ageing", "Payables ageing", "Purchases", "What's owed to each supplier as of the period's last day, by how late it is.", payables_ageing, "bills.view"),
    Report("vouchers-released", "Payment vouchers released", "Purchases", "What was paid out to suppliers in the period.", vouchers_released, "vouchers.view"),
    Report("profit-and-loss", "Profit and loss", "Accounting", "Income, expenses and net profit for the period, account by account.", profit_and_loss, "journal.view", fixed=True),
    Report("balance-sheet", "Balance sheet", "Accounting", "Assets, liabilities and equity as of the period's last day.", balance_sheet, "journal.view", fixed=True),
    Report("cash-flow", "Cash flow statement", "Accounting", "Cash at the start, what came in and went out each month, and cash at the end.", cash_flow, "journal.view", fixed=True),
    Report("trial-balance", "Trial balance", "Accounting", "Every account's debit or credit balance as of the period's last day, which must agree.", trial_balance, "journal.view", fixed=True),
    Report("general-ledger", "General ledger", "Accounting", "Every account's opening balance, each entry in the period and the running balance.", general_ledger, "journal.view", fixed=True),
    Report("journal-by-source", "Journal entries by source", "Accounting", "Approved entries in the period, by where they came from.", journal_by_source, "journal.view"),
)
BY_KEY = {r.key: r for r in REPORTS}


def allowed(r: Report, access: Access) -> bool:
    return access.can(r.needs)


@router.get("")
def list_reports(access: CurrentAccess) -> list[dict]:
    return [{"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed} for r in REPORTS if allowed(r, access)]


@router.get("/{key}")
def read_report(access: CurrentAccess, db: DB, settings: SettingsDep, key: str, start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to")) -> dict:
    r = BY_KEY.get(key)
    if r is None or not allowed(r, access):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such report.")
    zone = ZoneInfo(settings.org_timezone)
    today = datetime.now(zone).date()
    end = end or today
    start = start or end.replace(day=1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The period starts after it ends.")
    ctx = Ctx(db=db, first=start, last=end, start=datetime.combine(start, time.min, zone), end=datetime.combine(end + timedelta(days=1), time.min, zone))
    columns, rows, summary, chart = r.build(ctx)
    return {"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed, "from": start.isoformat(), "to": end.isoformat(),
            "filters": [], "columns": columns, "rows": rows, "summary": summary, "chart": chart}


