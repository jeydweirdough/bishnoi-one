"""Finance's reports (decided 2026-10-25, benchmarks/surpass.md §11): one registry, each report in
a group (Sales, Expenses, Purchases, Accounting, Management) and needing the permission for its data, drawn by
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
from app.receivables_asof import owed_on
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
    zone: ZoneInfo


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
    for o in owed_on(c.db, on, c.zone):  # rebuilt for that day, not from what's paid now
        i, owed = o.invoice, o.owed_centavos
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
    from app.payables_asof import owed_on

    names = supplier_names(c)
    on = c.last
    by: dict[str, dict] = {}
    for o in owed_on(c.db, on):
        b, owed = o.bill, o.owed_centavos
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


# --- Management: the figures a business manager reads (app/management.py, decided 2026-10-28) ------


def _reading(value, good, watch, *, low_is_good: bool = False) -> str:
    """Healthy / Watch / Low (or Slow) against two thresholds."""
    if value is None:
        return "Not enough data"
    if low_is_good:
        return "Healthy" if value <= good else "Watch" if value <= watch else "Slow"
    return "Healthy" if value >= good else "Watch" if value >= watch else "Low"


def _pct(v) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _times(v) -> str:
    return "—" if v is None else f"{v:.2f}×"


def _days(v) -> str:
    return "—" if v is None else f"{v:.0f} days"


def _change(a, b) -> str:
    if a is None or b is None or b == 0:
        return "—"
    d = (a - b) / abs(b)
    return f"{'+' if d >= 0 else '−'}{abs(d) * 100:.0f}%"


def key_figures(c: Ctx):
    """Each figure for the period, the same-length period before, and how it reads."""
    from app import management as m

    now = m.figures(c.db, c.first, c.last, c.zone)
    then = m.figures(c.db, *m.previous(c.first, c.last), c.zone)
    margin = now.net_margin
    roa = now.return_on_assets
    rows = [
        ("Revenue", "Invoiced sales, without VAT", m.peso(now.revenue), m.peso(then.revenue), _change(now.revenue, then.revenue),
         "Growing" if now.revenue > then.revenue else "Flat" if now.revenue == then.revenue else "Down"),
        ("Net profit", "Income − expenses (profit and loss)", m.peso(now.net_profit), m.peso(then.net_profit), _change(now.net_profit, then.net_profit),
         "Profit" if now.net_profit > 0 else "Break-even" if now.net_profit == 0 else "Loss"),
        ("Gross profit", "Revenue − cost of goods sold", m.peso(now.gross_profit) if now.cogs else "—", m.peso(then.gross_profit) if then.cogs else "—",
         _change(now.gross_profit, then.gross_profit) if now.cogs and then.cogs else "—", "Not enough data" if not now.cogs else "Profit" if now.gross_profit > 0 else "Loss"),
        ("Gross margin", "Gross profit ÷ revenue", _pct(now.gross_margin), _pct(then.gross_margin), "—",
         "Not enough data" if now.gross_margin is None else "Healthy" if now.gross_margin >= 0.2 else "Watch" if now.gross_margin >= 0.1 else "Low"),
        ("Net margin", "Net profit ÷ income", _pct(margin), _pct(then.net_margin), "—",
         "Not enough data" if margin is None else "Healthy" if margin >= 0.1 else "Watch" if margin >= 0 else "Loss"),
        ("Return on assets", "Net profit ÷ total assets, for the period", _pct(roa), _pct(then.return_on_assets), "—",
         "Not enough data" if roa is None else "Positive" if roa > 0 else "Negative"),
        ("Working capital", "Current assets − current liabilities", m.peso(now.working_capital), m.peso(then.working_capital), _change(now.working_capital, then.working_capital),
         "Healthy" if now.working_capital > 0 else "Short"),
        ("Current ratio", "Current assets ÷ current liabilities", _times(now.current_ratio), _times(then.current_ratio), "—", _reading(now.current_ratio, 1.5, 1.0)),
        ("Quick ratio", "(Current assets − inventory) ÷ current liabilities", _times(now.quick_ratio), _times(then.quick_ratio), "—", _reading(now.quick_ratio, 1.0, 0.7)),
        ("Days to collect (DSO)", "Receivables ÷ revenue × days in the period", _days(now.days_to_collect), _days(then.days_to_collect), "—",
         _reading(now.days_to_collect, 45, 60, low_is_good=True)),
        ("Days to pay (DPO)", "Payables ÷ purchases × days in the period", _days(now.days_to_pay), _days(then.days_to_pay), "—",
         "Not enough data" if now.days_to_pay is None else "—"),
        ("Days stock sits (DIO)", "Inventory ÷ cost of goods sold × days in the period", _days(now.days_stock_sits), _days(then.days_stock_sits), "—",
         _reading(now.days_stock_sits, 60, 90, low_is_good=True)),
        ("Inventory turnover", "Cost of goods sold ÷ inventory, a year at this pace", _times(now.inventory_turnover), _times(then.inventory_turnover), "—",
         _reading(now.inventory_turnover, 6, 4)),
        ("Cash conversion cycle", "Days to collect + days stock sits − days to pay", _days(now.cash_cycle), _days(then.cash_cycle), "—",
         _reading(now.cash_cycle, 60, 90, low_is_good=True)),
        ("Cash", "Cash, bank, e-wallet and checks on the last day", m.peso(now.position.cash), m.peso(then.position.cash), _change(now.position.cash, then.position.cash),
         "Healthy" if now.position.cash > 0 else "None"),
    ]
    summary = [
        fig("Revenue", now.revenue, "money"),
        *([fig("Gross profit", now.gross_profit, "money", "good" if now.gross_profit >= 0 else "bad")] if now.cogs else []),
        fig("Net profit", now.net_profit, "money", "good" if now.net_profit >= 0 else "bad"),
        fig("Working capital", now.working_capital, "money", "good" if now.working_capital >= 0 else "bad"),
        fig("Cash", now.position.cash, "money"),
    ]
    if now.position.guessed:
        summary.append(fig("Accounts judged by name", now.position.guessed, tone="warn"))
    return (
        [col("figure", "Figure"), col("how", "How it's worked out"), col("now", "This period"), col("before", "Period before"), col("change", "Change"), col("reading", "Reading")],
        [{"figure": f, "how": h, "now": n, "before": b, "change": ch, "reading": rd} for f, h, n, b, ch, rd in rows],
        summary,
        None,
    )


NONE_FOR = {"customer": "No customer", "salesperson": "No salesperson", "division": "Not in a division", "team": "Not in a team"}


def gross_margin_by(key: str, label: str):
    """Revenue (without VAT), the cost of goods sold and the gross profit, by product, customer,
    salesperson, division or team, from the period's issued invoices and the costs booked with them.
    Division and team are the salesperson's when the invoice was made (migration 0025)."""

    def build(c: Ctx):
        by: dict[str, dict] = {}
        unknown = 0
        for inv in c.db.scalars(issued_in(c)):
            costs = inv.line_costs or []
            worked = (inv.computed or {}).get("lines") or []
            if key == "product":
                for i, line in enumerate(inv.lines or []):
                    out = worked[i] if i < len(worked) else {}
                    name = str(line.get("ref") or line.get("description") or "No item code")
                    unit = costs[i] if i < len(costs) else None
                    if unit is None:
                        unknown += 1
                    r = by.setdefault(name, {"name": name, "revenue": 0, "cost": 0})
                    r["revenue"] += int(out.get("totalCentavos", 0)) - int(out.get("taxCentavos", 0))
                    r["cost"] += (unit or 0) * int(line.get("quantity") or 0)
            else:
                name = {"customer": inv.customer_name, "salesperson": inv.salesperson_name, "division": inv.division_name,
                        "team": inv.team_name}[key] or NONE_FOR[key]
                if inv.line_costs is None or any(x is None for x in inv.line_costs):
                    unknown += 1
                r = by.setdefault(name, {"name": name, "revenue": 0, "cost": 0})
                r["revenue"] += inv.total_centavos - inv.tax_centavos
                r["cost"] += inv.cost_centavos
        rows = []
        for r in by.values():
            r["profit"] = r["revenue"] - r["cost"]
            r["margin"] = r["profit"] / r["revenue"] if r["revenue"] else None
            rows.append(r)
        rows.sort(key=lambda r: -r["profit"])
        revenue, cost = sum(r["revenue"] for r in rows), sum(r["cost"] for r in rows)
        margin = (revenue - cost) / revenue if revenue else None
        what = "lines" if key == "product" else "invoices"
        return (
            [col("name", label), col("revenue", "Revenue", "money"), col("cost", "Cost of goods sold", "money"), col("profit", "Gross profit", "money"), col("margin", "Gross margin", "percent")],
            rows,
            [fig("Revenue", revenue, "money"), fig("Gross profit", revenue - cost, "money", "good" if revenue >= cost else "bad"),
             fig("Gross margin", margin, "percent"), fig(f"{what.capitalize()} without a known cost", unknown, tone="warn" if unknown else "good")],
            bar("name", "revenue", "profit") if rows else None,
        )

    return build


def _month(y: int, mo: int) -> tuple[date, date]:
    first = date(y, mo, 1)
    nxt = date(y + (mo == 12), mo % 12 + 1, 1)
    return first, nxt - timedelta(days=1)


def _shift(y: int, mo: int, by: int) -> tuple[int, int]:
    n = y * 12 + (mo - 1) + by
    return n // 12, n % 12 + 1


def _year_earlier(d: date) -> date:
    return d.replace(year=d.year - 1, day=28) if (d.month, d.day) == (2, 29) else d.replace(year=d.year - 1)


def revenue_growth(c: Ctx):
    """Revenue month by month, against the month before and the same month a year earlier."""
    from app import management as m

    rows = []
    y, mo = c.first.year, c.first.month
    while (y, mo) <= (c.last.year, c.last.month):
        first, last = _month(y, mo)
        now = m.revenue(c.db, max(first, c.first), min(last, c.last))
        before = m.revenue(c.db, *_month(*_shift(y, mo, -1)))
        year_ago = m.revenue(c.db, *_month(*_shift(y, mo, -12)))
        rows.append({
            "month": f"{y}-{mo:02d}", "revenue": now, "previous": before, "vsPrevious": (now - before) / before if before else None,
            "yearAgo": year_ago, "vsYearAgo": (now - year_ago) / year_ago if year_ago else None,
        })
        y, mo = _shift(y, mo, 1)
    total = m.revenue(c.db, c.first, c.last)
    earlier = m.revenue(c.db, *m.previous(c.first, c.last))
    last_year = m.revenue(c.db, _year_earlier(c.first), _year_earlier(c.last))
    growth = (total - earlier) / earlier if earlier else None
    yoy = (total - last_year) / last_year if last_year else None
    return (
        [col("month", "Month"), col("revenue", "Revenue", "money"), col("previous", "Month before", "money"), col("vsPrevious", "Change", "percent"),
         col("yearAgo", "Same month last year", "money"), col("vsYearAgo", "Change on last year", "percent")],
        rows,
        [fig("Revenue", total, "money"), fig("Period before", earlier, "money"),
         fig("Growth", growth, "percent", None if growth is None else "good" if growth >= 0 else "bad"),
         fig("On last year", yoy, "percent", None if yoy is None else "good" if yoy >= 0 else "bad")],
        {"kind": "line", "x": "month", "series": ["revenue", "yearAgo"]} if rows else None,
    )


def cash_forecast(c: Ctx):
    """The next 12 weeks from the day: cash now, what customers owe by when it's due, what's owed
    to suppliers by when it's due, and the cash that leaves."""
    from app import management as m

    today = c.last
    weeks = 12
    start = today - timedelta(days=today.weekday())  # this week's Monday
    horizon = start + timedelta(weeks=weeks)
    late = {"week": "Already late", "inflow": 0, "outflow": 0}
    ahead = [{"week": f"Week of {(start + timedelta(weeks=i)).isoformat()}", "inflow": 0, "outflow": 0} for i in range(weeks)]

    def place(due: date, amount: int, key: str) -> None:
        if due < today:
            late[key] += amount
        elif due < horizon:
            ahead[(due - start).days // 7][key] += amount

    for i in c.db.scalars(select(Invoice).where(Invoice.status == "issued", Invoice.paid_centavos < Invoice.total_centavos)):
        place(i.invoice_date + timedelta(days=i.terms_days), i.total_centavos - i.paid_centavos, "inflow")
    for b in c.db.scalars(select(Bill).where(Bill.status == "recorded", Bill.paid_centavos < Bill.payable_centavos)):
        place(b.due_date, b.payable_centavos - b.paid_centavos, "outflow")

    cash = m.position(c.db, today).cash
    rows = ([late] if late["inflow"] or late["outflow"] else []) + ahead
    running = lowest = cash
    for row in rows:
        row["net"] = row["inflow"] - row["outflow"]
        running += row["net"]
        row["projected"] = running
        lowest = min(lowest, running)
    return (
        [col("week", "When"), col("inflow", "Expected in", "money"), col("outflow", "Expected out", "money"), col("net", "Net", "money"), col("projected", "Cash after", "money")],
        rows,
        [fig("Cash now", cash, "money"), fig("Expected in", sum(r["inflow"] for r in rows), "money", "good"),
         fig("Expected out", sum(r["outflow"] for r in rows), "money"), fig("Lowest cash ahead", lowest, "money", "good" if lowest >= 0 else "bad")],
        {"kind": "line", "x": "week", "series": ["projected"]},
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
    Report("key-figures", "Key figures", "Management", "Revenue, profit, margin, return on assets, working capital, current and quick ratios, days to collect and pay, and cash, against the period before.", key_figures, "journal.view", fixed=True),
    Report("revenue-growth", "Revenue growth", "Management", "Revenue month by month, against the month before and the same month last year.", revenue_growth, "invoices.view", fixed=True),
    Report("gross-margin-by-product", "Gross margin by product", "Management", "Revenue, cost of goods sold and gross profit for each product sold in the period.", gross_margin_by("product", "Product"), "invoices.view", fixed=True),
    Report("gross-margin-by-customer", "Gross margin by customer", "Management", "Revenue, cost of goods sold and gross profit for each customer in the period.", gross_margin_by("customer", "Customer"), "invoices.view", fixed=True),
    Report("gross-margin-by-salesperson", "Gross margin by salesperson", "Management", "Revenue, cost of goods sold and gross profit for each salesperson in the period.", gross_margin_by("salesperson", "Salesperson"), "invoices.view", fixed=True),
    Report("revenue-by-division", "Revenue and margin by division", "Management", "Revenue, cost of goods sold and gross profit for each division in the period, by the salesperson's division when each invoice was made.", gross_margin_by("division", "Division"), "invoices.view", fixed=True),
    Report("revenue-by-team", "Revenue and margin by team", "Management", "Revenue, cost of goods sold and gross profit for each team in the period, by the salesperson's team when each invoice was made.", gross_margin_by("team", "Team"), "invoices.view", fixed=True),
    Report("cash-forecast", "Cash forecast", "Management", "Cash now, and what customers and suppliers are due to pay and be paid over the next 12 weeks.", cash_forecast, "journal.view", dated=False, fixed=True),
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
    ctx = Ctx(db=db, first=start, last=end, start=datetime.combine(start, time.min, zone), end=datetime.combine(end + timedelta(days=1), time.min, zone), zone=zone)
    columns, rows, summary, chart = r.build(ctx)
    return {"key": r.key, "title": r.title, "group": r.group, "about": r.about, "dated": r.dated, "fixed": r.fixed, "from": start.isoformat(), "to": end.isoformat(),
            "filters": [], "columns": columns, "rows": rows, "summary": summary, "chart": chart}


