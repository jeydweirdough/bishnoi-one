"""The BIR's books and returns, from what Finance already keeps (decided
2026-10-24, part one of the BIR features taken from Oojeema).

Everything here is read from posted records, never typed in again:
- the books of accounts the BIR asks a company to keep: the Sales Journal
  (issued invoices), the Cash Receipts Journal (payments received), the Cash
  Disbursements Journal (entries paying money out), the General Journal (every
  entry) and the General Ledger (each account's movement);
- the income statement and the balance sheet, from the chart's account types;
- the quarterly VAT return (2550Q) for a VAT-registered company, or the
  percentage tax return (2551Q) for a non-VAT one, sales side: the purchases
  side (input VAT) comes with supplier bills, part two;
- the Summary List of Sales (SLS, for the RELIEF submission) and the Summary
  Alphalist of Withholding Taxes (SAWT): the tax customers withheld from what
  they paid, from their Forms 2307.

The summary lists come out as tables and CSV in the BIR templates' columns;
the BIR's DAT files follow once their official layout is confirmed (a DAT file
with a field out of place fails the BIR's validation module).

Amounts are in centavos throughout, as everywhere in Finance.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Bill, Invoice, InvoicePayment, JournalEntry, JournalLine, PettyCashLine, PettyCashVoucher, Supplier, TaxProfile
from app import payables
from app.tax.packs.ph import PERCENTAGE
from app.tax.rates import lookup

SALES_KEYS = ("taxable_sales", "tax", "zero_rated_sales", "exempt_sales", "non_taxable_sales")


# ---- Periods --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    label: str


def month_end(year: int, month: int) -> date:
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def quarter(year: int, q: int, fiscal_month_end: int = 12) -> Period:
    """Quarter q (1 to 4) of the fiscal year that ends in fiscal_month_end of `year`."""
    if q not in (1, 2, 3, 4):
        raise ValueError("A quarter is 1, 2, 3 or 4.")
    end_index = year * 12 + (fiscal_month_end - 1) - 3 * (4 - q)  # months since year 0, 0-based
    end_y, end_m = divmod(end_index, 12)
    start_y, start_m = divmod(end_index - 2, 12)
    ordinal = ("1st", "2nd", "3rd", "4th")[q - 1]
    return Period(date(start_y, start_m + 1, 1), month_end(end_y, end_m + 1), f"{ordinal} quarter, {'calendar' if fiscal_month_end == 12 else 'fiscal'} year {year}")


def months_of(p: Period) -> list[Period]:
    out, d = [], p.start
    while d <= p.end:
        out.append(Period(d, month_end(d.year, d.month), d.strftime("%B %Y")))
        d = month_end(d.year, d.month) + timedelta(days=1)
    return out


# ---- Who files ------------------------------------------------------------------------------


def taxpayer(db: Session) -> dict:
    p = db.get(TaxProfile, 1)
    return {
        "registeredName": p.registered_name if p else None,
        "tradeName": p.trade_name if p else None,
        "tin": p.tin if p else None,
        "branchCode": p.branch_code if p else "00000",
        "rdoCode": p.rdo_code if p else None,
        "address": p.registered_address if p else None,
        "regime": p.regime if p else "vat",
        "fiscalMonthEnd": p.fiscal_month_end if p else 12,
    }


# ---- Sales --------------------------------------------------------------------------------


def amounts_of(inv: Invoice) -> dict[str, int]:
    """An issued invoice's sales, by the BIR's kinds (its summary as printed)."""
    got = {k: 0 for k in SALES_KEYS}
    for line in (inv.computed or {}).get("summary", []):
        if line.get("key") in got:
            got[line["key"]] = int(line.get("amountCentavos") or 0)
    return got


def issued_between(db: Session, start: date, end: date, *, with_void: bool = False) -> list[Invoice]:
    statuses = ("issued", "void") if with_void else ("issued",)
    return list(db.scalars(
        select(Invoice).where(Invoice.status.in_(statuses), Invoice.invoice_date >= start, Invoice.invoice_date <= end)
        .order_by(Invoice.invoice_date, Invoice.number)
    ))


def sales_journal(db: Session, start: date, end: date) -> dict:
    rows, totals = [], {"gross": 0, **{k: 0 for k in SALES_KEYS}}
    for inv in issued_between(db, start, end, with_void=True):
        void = inv.status == "void"
        a = {k: 0 for k in SALES_KEYS} if void else amounts_of(inv)
        gross = 0 if void else inv.total_centavos
        rows.append({
            "date": inv.invoice_date.isoformat(), "number": inv.number, "customer": inv.customer_name, "tin": inv.customer_tin,
            "address": inv.customer_address, "void": void, "grossCentavos": gross,
            **{f"{camel(k)}Centavos": v for k, v in a.items()},
        })
        totals["gross"] += gross
        for k, v in a.items():
            totals[k] += v
    return {"rows": rows, "totals": {("grossCentavos" if k == "gross" else f"{camel(k)}Centavos"): v for k, v in totals.items()}}


def cash_receipts(db: Session, start: date, end: date) -> dict:
    payments = db.scalars(
        select(InvoicePayment).join(Invoice).where(InvoicePayment.removed_at.is_(None), InvoicePayment.paid_on >= start, InvoicePayment.paid_on <= end)
        .order_by(InvoicePayment.paid_on, InvoicePayment.recorded_at)
    ).all()
    rows, cash, cwt = [], 0, 0
    for p in payments:
        rows.append({
            "date": p.paid_on.isoformat(), "invoice": p.invoice.number, "customer": p.invoice.customer_name, "tin": p.invoice.customer_tin,
            "method": p.method, "reference": p.reference, "cashCentavos": p.amount_centavos, "cwtCentavos": p.cwt_centavos,
            "atc": p.cwt_atc, "receivablesCentavos": p.amount_centavos + p.cwt_centavos,
        })
        cash += p.amount_centavos
        cwt += p.cwt_centavos
    return {"rows": rows, "totals": {"cashCentavos": cash, "cwtCentavos": cwt, "receivablesCentavos": cash + cwt}}


# ---- The journal --------------------------------------------------------------------------


def entries_between(db: Session, start: date, end: date) -> list[JournalEntry]:
    return list(db.scalars(select(JournalEntry).where(JournalEntry.entry_date >= start, JournalEntry.entry_date <= end).order_by(JournalEntry.entry_date, JournalEntry.number)))


def entry_out(e: JournalEntry) -> dict:
    return {
        "date": e.entry_date.isoformat(), "number": e.number, "memo": e.memo, "reference": e.reference, "source": e.source,
        "lines": [
            {"code": ln.account.code, "account": ln.account.name, "debitCentavos": ln.debit_centavos, "creditCentavos": ln.credit_centavos, "description": ln.description}
            for ln in e.lines
        ],
    }


def general_journal(db: Session, start: date, end: date) -> dict:
    entries = entries_between(db, start, end)
    debit = sum(ln.debit_centavos for e in entries for ln in e.lines)
    credit = sum(ln.credit_centavos for e in entries for ln in e.lines)
    return {"entries": [entry_out(e) for e in entries], "totals": {"debitCentavos": debit, "creditCentavos": credit}}


def money_accounts(db: Session) -> set[str]:
    from app.money_accounts import money_account_ids

    return money_account_ids(db)


def cash_disbursements(db: Session, start: date, end: date) -> dict:
    """Every entry that pays money out of cash, the bank, an e-wallet or by check."""
    money = money_accounts(db)
    rows, total = [], 0
    for e in entries_between(db, start, end):
        out = sum(ln.credit_centavos for ln in e.lines if ln.account_id in money)
        if not out:
            continue
        rows.append({
            "date": e.entry_date.isoformat(), "number": e.number, "memo": e.memo, "reference": e.reference, "amountCentavos": out,
            "from": ", ".join(sorted({ln.account.name for ln in e.lines if ln.account_id in money and ln.credit_centavos})),
            "charged": [{"code": ln.account.code, "account": ln.account.name, "debitCentavos": ln.debit_centavos} for ln in e.lines if ln.debit_centavos],
        })
        total += out
    return {"rows": rows, "totals": {"amountCentavos": total}}


def balances(db: Session, *, before: date | None = None, start: date | None = None, end: date | None = None) -> dict[str, tuple[int, int]]:
    """By account: (debits, credits) of the lines dated in the range."""
    q = select(JournalLine.account_id, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos)).join(JournalEntry)
    if before is not None:
        q = q.where(JournalEntry.entry_date < before)
    if start is not None:
        q = q.where(JournalEntry.entry_date >= start)
    if end is not None:
        q = q.where(JournalEntry.entry_date <= end)
    return {a: (int(d or 0), int(c or 0)) for a, d, c in db.execute(q.group_by(JournalLine.account_id))}


NORMAL_DEBIT = {"asset", "expense"}


def signed(account: Account, debit: int, credit: int) -> int:
    """A balance the way the account normally carries it: debits for assets and expenses, credits for the rest."""
    return debit - credit if account.type in NORMAL_DEBIT else credit - debit


def general_ledger(db: Session, start: date, end: date) -> dict:
    opening = balances(db, before=start)
    accounts = db.scalars(select(Account).order_by(Account.code)).all()
    lines = db.execute(
        select(JournalLine, JournalEntry).join(JournalEntry).where(JournalEntry.entry_date >= start, JournalEntry.entry_date <= end)
        .order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.position)
    ).all()
    by_account: dict[str, list] = {}
    for ln, e in lines:
        by_account.setdefault(ln.account_id, []).append((ln, e))
    out = []
    for a in accounts:
        moves = by_account.get(a.id, [])
        o = opening.get(a.id, (0, 0))
        if not moves and o == (0, 0):
            continue
        running = signed(a, *o)
        rows = []
        for ln, e in moves:
            running += signed(a, ln.debit_centavos, ln.credit_centavos)
            rows.append({"date": e.entry_date.isoformat(), "number": e.number, "memo": ln.description or e.memo, "debitCentavos": ln.debit_centavos, "creditCentavos": ln.credit_centavos, "balanceCentavos": running})
        out.append({"code": a.code, "account": a.name, "type": a.type, "openingCentavos": signed(a, *o), "rows": rows, "closingCentavos": running})
    return {"accounts": out}


# ---- Statements -----------------------------------------------------------------------------


def income_statement(db: Session, start: date, end: date) -> dict:
    moves = balances(db, start=start, end=end)
    accounts = db.scalars(select(Account).where(Account.type.in_(("income", "expense"))).order_by(Account.code)).all()
    income = [{"code": a.code, "account": a.name, "amountCentavos": signed(a, *moves.get(a.id, (0, 0)))} for a in accounts if a.type == "income"]
    expenses = [{"code": a.code, "account": a.name, "amountCentavos": signed(a, *moves.get(a.id, (0, 0)))} for a in accounts if a.type == "expense"]
    income = [r for r in income if r["amountCentavos"]]
    expenses = [r for r in expenses if r["amountCentavos"]]
    total_in, total_out = sum(r["amountCentavos"] for r in income), sum(r["amountCentavos"] for r in expenses)
    return {"income": income, "expenses": expenses, "totals": {"incomeCentavos": total_in, "expensesCentavos": total_out, "netCentavos": total_in - total_out}}


def balance_sheet(db: Session, as_of: date) -> dict:
    upto = balances(db, end=as_of)
    accounts = db.scalars(select(Account).order_by(Account.code)).all()
    group = {"asset": [], "liability": [], "equity": []}
    earnings = 0
    for a in accounts:
        amount = signed(a, *upto.get(a.id, (0, 0)))
        if a.type in group:
            if amount:
                group[a.type].append({"code": a.code, "account": a.name, "amountCentavos": amount})
        elif a.type == "income":
            earnings += amount
        else:
            earnings -= amount
    if earnings:
        # Income less expenses not yet closed to equity: shown under equity, so the sheet balances.
        group["equity"].append({"code": "", "account": "Net income, not yet closed", "amountCentavos": earnings})
    totals = {k: sum(r["amountCentavos"] for r in v) for k, v in group.items()}
    return {
        "assets": group["asset"], "liabilities": group["liability"], "equity": group["equity"],
        "totals": {"assetsCentavos": totals["asset"], "liabilitiesCentavos": totals["liability"], "equityCentavos": totals["equity"],
                   "balanced": totals["asset"] == totals["liability"] + totals["equity"]},
    }


# ---- Returns -----------------------------------------------------------------------------


def sales_totals(invoices: list[Invoice]) -> dict[str, int]:
    t = {k: 0 for k in SALES_KEYS}
    for inv in invoices:
        for k, v in amounts_of(inv).items():
            t[k] += v
    return t


def vat_return(db: Session, p: Period) -> dict:
    """2550Q for a VAT-registered company; 2551Q (percentage tax) for a non-VAT one. Sales side; input VAT with supplier bills."""
    who = taxpayer(db)
    months = []
    for m in months_of(p):
        t = sales_totals(issued_between(db, m.start, m.end))
        months.append({"label": m.label, "start": m.start.isoformat(), "end": m.end.isoformat(), **{f"{camel(k)}Centavos": v for k, v in t.items()}})
    t = sales_totals(issued_between(db, p.start, p.end))
    if who["regime"] == "non_vat":
        rate = lookup(db, "PH")(PERCENTAGE, p.end) or 0
        gross = t["non_taxable_sales"]
        return {
            "form": "2551Q", "title": "Quarterly percentage tax return", "months": months,
            "lines": [
                {"key": "gross", "label": "Gross sales or receipts", "amountCentavos": gross},
                {"key": "rate", "label": "Tax rate", "rateBp": rate},
                {"key": "due", "label": "Percentage tax due", "amountCentavos": round(gross * rate / 10_000)},
            ],
            "notes": ["The rate is the one in force on the quarter's last day (Tax setup, rates)."],
        }
    output = t["tax"]
    bills = bills_between(db, p.start, p.end)
    purchases = {k: sum(b.by_kind[k] for b in bills) for k in ("vatable", "zero_rated", "exempt", "non_vat")}
    input_tax = sum(b.vat for b in bills)
    for m in months:
        mb = bills_between(db, date.fromisoformat(m["start"]), date.fromisoformat(m["end"]))
        m["purchasesCentavos"] = sum(b.net for b in mb)
        m["inputTaxCentavos"] = sum(b.vat for b in mb)
    return {
        "form": "2550Q", "title": "Quarterly value-added tax return", "months": months,
        "lines": [
            {"key": "taxable", "label": "VATable sales", "amountCentavos": t["taxable_sales"]},
            {"key": "zero_rated", "label": "Zero-rated sales", "amountCentavos": t["zero_rated_sales"]},
            {"key": "exempt", "label": "VAT-exempt sales", "amountCentavos": t["exempt_sales"]},
            {"key": "total_sales", "label": "Total sales", "amountCentavos": t["taxable_sales"] + t["zero_rated_sales"] + t["exempt_sales"]},
            {"key": "output", "label": "Output VAT", "amountCentavos": output},
            {"key": "purchases", "label": "VATable purchases (net of VAT)", "amountCentavos": purchases["vatable"]},
            {"key": "purchases_other", "label": "Zero-rated, exempt and non-VAT purchases", "amountCentavos": purchases["zero_rated"] + purchases["exempt"] + purchases["non_vat"]},
            {"key": "input", "label": "Input VAT on purchases", "amountCentavos": input_tax},
            *[
                {"key": f"{kind}_{part}", "label": f"{label}: {description}",
                 "amountCentavos": sum(b.by_type[kind][field] for b in bills)}
                for kind, label in payables.PURCHASE_TYPES.items()
                for part, description, field in (("purchases", "purchases before VAT", "netCentavos"), ("input", "input VAT", "vatCentavos"))
            ],
            {"key": "payable", "label": "VAT payable" if output >= input_tax else "Excess input VAT, carried over", "amountCentavos": abs(output - input_tax)},
        ],
        "notes": ["Input VAT is from recorded supplier bills and posted petty cash receipts dated in the quarter. Taxes customers withheld (the SAWT) are credited on the income tax return, not here."],
    }


# ---- Summary lists -----------------------------------------------------------------------


def sls(db: Session, p: Period) -> dict:
    """Summary List of Sales: by customer (TIN), the quarter's sales by kind."""
    by: dict[tuple, dict] = {}
    for inv in issued_between(db, p.start, p.end):
        key = ((inv.customer_tin or "").strip(), inv.customer_name.strip().upper())
        row = by.setdefault(key, {"tin": inv.customer_tin, "name": inv.customer_name, "address": inv.customer_address,
                                   "exemptCentavos": 0, "zeroRatedCentavos": 0, "taxableCentavos": 0, "outputTaxCentavos": 0, "grossTaxableCentavos": 0})
        a = amounts_of(inv)
        row["exemptCentavos"] += a["exempt_sales"] + a["non_taxable_sales"]
        row["zeroRatedCentavos"] += a["zero_rated_sales"]
        row["taxableCentavos"] += a["taxable_sales"]
        row["outputTaxCentavos"] += a["tax"]
        row["grossTaxableCentavos"] += a["taxable_sales"] + a["tax"]
    rows = sorted(by.values(), key=lambda r: r["name"].upper())
    totals = {k: sum(r[k] for r in rows) for k in ("exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "outputTaxCentavos", "grossTaxableCentavos")}
    return {"rows": rows, "totals": totals, "missingTin": sum(1 for r in rows if not r["tin"])}


def sawt(db: Session, p: Period) -> dict:
    """Summary Alphalist of Withholding Taxes: tax customers withheld from what they paid us (their Forms 2307), by customer and ATC."""
    payments = db.scalars(
        select(InvoicePayment).join(Invoice).where(InvoicePayment.removed_at.is_(None), InvoicePayment.cwt_centavos > 0,
                                                   InvoicePayment.paid_on >= p.start, InvoicePayment.paid_on <= p.end)
        .order_by(InvoicePayment.paid_on)
    ).all()
    by: dict[tuple, dict] = {}
    for pay in payments:
        inv = pay.invoice
        # The income payment the tax was withheld on: what this payment settled, net of VAT, in the invoice's own proportion.
        settled = pay.amount_centavos + pay.cwt_centavos
        base = round(settled * (inv.total_centavos - inv.tax_centavos) / inv.total_centavos) if inv.total_centavos else settled
        key = ((inv.customer_tin or "").strip(), inv.customer_name.strip().upper(), pay.cwt_atc)
        row = by.setdefault(key, {"tin": inv.customer_tin, "payor": inv.customer_name, "atc": pay.cwt_atc, "incomePaymentCentavos": 0, "withheldCentavos": 0, "certificates": []})
        row["incomePaymentCentavos"] += base
        row["withheldCentavos"] += pay.cwt_centavos
        if pay.cwt_certificate:
            row["certificates"].append(pay.cwt_certificate)
    rows = sorted(by.values(), key=lambda r: (r["payor"].upper(), r["atc"] or ""))
    for r in rows:
        r["rateBp"] = round(r["withheldCentavos"] * 10_000 / r["incomePaymentCentavos"]) if r["incomePaymentCentavos"] else None
    return {"rows": rows, "totals": {"incomePaymentCentavos": sum(r["incomePaymentCentavos"] for r in rows), "withheldCentavos": sum(r["withheldCentavos"] for r in rows)},
            "missingTin": sum(1 for r in rows if not r["tin"])}


def camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(w.title() for w in rest)



# ---- Purchases (supplier bills, the Finance team's payables: app/payables.py) -----------------


@dataclass
class Purchase:
    """A purchase as the BIR reports read it: a recorded (or voided) supplier bill, or one receipt on a posted
    (or voided) petty cash voucher (added 2026-10-30). Its amounts by VAT kind and purchase type, and what
    was withheld from it, by ATC and rate, worked out line by line exactly as it was posted."""

    source: str  # bill or petty_cash
    on: date
    no: str | int | None  # the bill's number, or the petty cash voucher's
    reference: str  # the supplier's invoice number, or the store's receipt number
    payee_id: str  # a supplier's id, or "store:" and the store's TIN (else its name) for petty cash
    name: str
    tin: str | None
    address: str | None
    void: bool
    net: int
    vat: int
    withheld: int
    by_kind: dict[str, int]
    by_type: dict[str, dict[str, int]]
    held: list[tuple[str, int, int, int]]  # (ATC, rate in basis points, base, tax withheld)

    @property
    def total(self) -> int:
        return self.net + self.vat

    @property
    def payable(self) -> int:
        return self.net + self.vat - self.withheld

    @property
    def supplier_id(self) -> str:
        return self.payee_id


def classify(lines: list[dict]) -> tuple[dict, dict, list]:
    kinds = {"vatable": 0, "zero_rated": 0, "exempt": 0, "non_vat": 0}
    types = {k: {"netCentavos": 0, "vatCentavos": 0} for k in payables.PURCHASE_TYPES}
    held: dict[tuple[str, int], list[int]] = {}
    for line in lines:
        group = types[line.get("purchaseType", "other_goods")]
        group["netCentavos"] += line["netCentavos"]
        group["vatCentavos"] += line["vatCentavos"]
        kinds[{"vat": "vatable", "zero": "zero_rated", "exempt": "exempt"}.get(line["vat"], "non_vat")] += line["netCentavos"]
        code = line.get("withholding")
        if code and line["withheldCentavos"]:
            row = held.setdefault((code, payables.WITHHOLDING[code][1]), [0, 0])
            row[0] += line["netCentavos"]
            row[1] += line["withheldCentavos"]
    return kinds, types, [(code, bp, base, tax) for (code, bp), (base, tax) in held.items()]


def purchase(db: Session, bill: Bill) -> Purchase:
    worked = payables.work_out(db, bill.lines or [], bill.bill_date, bill.amounts_include_vat)
    kinds, types, held = classify(worked.lines)
    return Purchase("bill", bill.bill_date, bill.no, bill.bill_number, bill.supplier_id,
                    (bill.supplier.company_name or bill.supplier.name).strip(), bill.supplier.tin, bill.supplier.address,
                    bill.status == "void", bill.net_centavos, bill.vat_centavos, bill.withheld_centavos, kinds, types, held)


def store_key(line: PettyCashLine) -> str:
    return "store:" + (line.store_tin or " ".join(line.store.split()).upper())


def receipts(db: Session, v: PettyCashVoucher) -> list[Purchase]:
    """Each receipt on a petty cash voucher, as its own purchase from its store, worked out as it was posted."""
    worked = payables.work_out(db, [{"accountId": ln.account_id, "amountCentavos": ln.amount_centavos, "vat": ln.vat,
                                     "withholding": ln.withholding, "purchaseType": ln.purchase_type} for ln in v.lines],
                               v.voucher_date, v.amounts_include_vat)
    out = []
    for ln, w in zip(v.lines, worked.lines):
        kinds, types, held = classify([w])
        out.append(Purchase("petty_cash", v.voucher_date, v.number, ln.receipt_number, store_key(ln), ln.store.strip(), ln.store_tin, None,
                            v.status == "void", w["netCentavos"], w["vatCentavos"], w["withheldCentavos"], kinds, types, held))
    return out


def bills_between(db: Session, start: date, end: date, *, with_void: bool = False, supplier_id: str | None = None) -> list[Purchase]:
    """Every purchase dated in the period: supplier bills and petty cash receipts, in date order."""
    statuses = ("recorded", "void") if with_void else ("recorded",)
    out: list[Purchase] = []
    if not supplier_id or not supplier_id.startswith("store:"):
        q = select(Bill).where(Bill.status.in_(statuses), Bill.bill_date >= start, Bill.bill_date <= end)
        if supplier_id:
            q = q.where(Bill.supplier_id == supplier_id)
        out += [purchase(db, b) for b in db.scalars(q.order_by(Bill.bill_date, Bill.no))]
    if not supplier_id or supplier_id.startswith("store:"):
        q = select(PettyCashVoucher).where(PettyCashVoucher.status.in_(("posted", "void") if with_void else ("posted",)),
                                          PettyCashVoucher.voucher_date >= start, PettyCashVoucher.voucher_date <= end)
        for v in db.scalars(q.order_by(PettyCashVoucher.voucher_date, PettyCashVoucher.number)):
            out += [pu for pu in receipts(db, v) if not supplier_id or pu.payee_id == supplier_id]
    return sorted(out, key=lambda pu: pu.on)


PURCHASE_KEYS = ("totalCentavos", "vatableCentavos", "inputTaxCentavos", "zeroRatedCentavos", "exemptCentavos", "ewtCentavos", "payableCentavos")


def purchase_journal(db: Session, start: date, end: date) -> dict:
    rows = []
    totals = {k: 0 for k in PURCHASE_KEYS}
    for pu in bills_between(db, start, end, with_void=True):
        k, void = pu.by_kind, pu.void
        row = {
            "date": pu.on.isoformat(), "no": pu.no, "source": pu.source, "supplierInvoiceNo": pu.reference, "supplier": pu.name, "tin": pu.tin, "void": void,
            "atc": ", ".join(sorted({h[0] for h in pu.held})) or None,
            "totalCentavos": 0 if void else pu.total,
            "vatableCentavos": 0 if void else k["vatable"],
            "inputTaxCentavos": 0 if void else pu.vat,
            "zeroRatedCentavos": 0 if void else k["zero_rated"],
            "exemptCentavos": 0 if void else k["exempt"] + k["non_vat"],
            "ewtCentavos": 0 if void else pu.withheld,
            "payableCentavos": 0 if void else pu.payable,
        }
        rows.append(row)
        for key in PURCHASE_KEYS:
            totals[key] += row[key]
    return {"rows": rows, "totals": totals}


def slp(db: Session, p: Period) -> dict:
    """Summary List of Purchases: by supplier (TIN), the quarter's purchases by kind and the input tax."""
    by: dict[tuple, dict] = {}
    for pu in bills_between(db, p.start, p.end):
        key = ((pu.tin or "").strip(), pu.name.upper())
        row = by.setdefault(key, {"tin": pu.tin, "name": pu.name, "address": pu.address,
                                   "exemptCentavos": 0, "zeroRatedCentavos": 0, "taxableCentavos": 0, "inputTaxCentavos": 0, "grossTaxableCentavos": 0})
        k = pu.by_kind
        row["exemptCentavos"] += k["exempt"] + k["non_vat"]
        row["zeroRatedCentavos"] += k["zero_rated"]
        row["taxableCentavos"] += k["vatable"]
        row["inputTaxCentavos"] += pu.vat
        row["grossTaxableCentavos"] += k["vatable"] + pu.vat
        for kind, amounts in pu.by_type.items():
            row[f"{camel(kind)}Centavos"] = row.get(f"{camel(kind)}Centavos", 0) + amounts["netCentavos"]
            row[f"{camel(kind)}InputTaxCentavos"] = row.get(f"{camel(kind)}InputTaxCentavos", 0) + amounts["vatCentavos"]
    rows = sorted(by.values(), key=lambda r: r["name"].upper())
    totals = {k: sum(r[k] for r in rows) for k in ("exemptCentavos", "zeroRatedCentavos", "taxableCentavos", "inputTaxCentavos", "grossTaxableCentavos")}
    for kind in payables.PURCHASE_TYPES:
        for suffix in ("Centavos", "InputTaxCentavos"):
            key = f"{camel(kind)}{suffix}"
            totals[key] = sum(r[key] for r in rows)
    return {"rows": rows, "totals": totals, "missingTin": sum(1 for r in rows if not r["tin"])}


# ---- Expanded withholding: what the company withheld from its suppliers ---------------------


def withheld_bills(db: Session, start: date, end: date, supplier_id: str | None = None) -> list[Purchase]:
    return [pu for pu in bills_between(db, start, end, supplier_id=supplier_id) if pu.held]


def nature(atc: str | None) -> str | None:
    return payables.WITHHOLDING[atc][0] if atc in payables.WITHHOLDING else None


def by_atc(bills: list[Purchase]) -> list[dict]:
    rows: dict[tuple, dict] = {}
    for pu in bills:
        for atc, bp, base, tax in pu.held:
            row = rows.setdefault((atc, bp), {"atc": atc, "nature": nature(atc), "rateBp": bp, "baseCentavos": 0, "taxCentavos": 0})
            row["baseCentavos"] += base
            row["taxCentavos"] += tax
    return sorted(rows.values(), key=lambda r: (r["atc"] or "", r["rateBp"]))


def by_payee(bills: list[Purchase]) -> list[dict]:
    """Each supplier and ATC: the income payments and the tax withheld (the QAP's and 1604E's lines)."""
    rows: dict[tuple, dict] = {}
    for pu in bills:
        for atc, bp, base, tax in pu.held:
            row = rows.setdefault((pu.supplier_id, atc, bp), {
                "supplierId": pu.supplier_id, "tin": pu.tin, "payee": pu.name, "address": pu.address,
                "atc": atc, "nature": nature(atc), "rateBp": bp, "baseCentavos": 0, "taxCentavos": 0,
            })
            row["baseCentavos"] += base
            row["taxCentavos"] += tax
    return sorted(rows.values(), key=lambda r: (r["payee"].upper(), r["atc"] or ""))


def form_0619e(db: Session, m: Period) -> dict:
    """Monthly remittance of expanded withholding (the quarter's first two months; the third is on the 1601EQ)."""
    rows = by_atc(withheld_bills(db, m.start, m.end))
    return {"form": "0619E", "title": "Monthly remittance of expanded withholding tax", "rows": rows, "totalCentavos": sum(r["taxCentavos"] for r in rows)}


def form_1601eq(db: Session, p: Period) -> dict:
    """Quarterly return of expanded withholding: by ATC, less what the 0619Es remitted for the first two months."""
    rows = by_atc(withheld_bills(db, p.start, p.end))
    months = months_of(p)
    remitted = [{"label": m.label, "amountCentavos": form_0619e(db, m)["totalCentavos"]} for m in months[:2]]
    total = sum(r["taxCentavos"] for r in rows)
    paid = sum(r["amountCentavos"] for r in remitted)
    return {
        "form": "1601EQ", "title": "Quarterly remittance return of creditable income taxes withheld (expanded)",
        "rows": rows, "totalCentavos": total, "remitted": remitted, "dueCentavos": total - paid,
        "notes": ["The 0619E amounts are what the books show withheld in each month. If what was actually remitted differs, use the remitted amounts."],
    }


def qap(db: Session, p: Period) -> dict:
    """Quarterly Alphalist of Payees: attached to the 1601EQ."""
    rows = by_payee(withheld_bills(db, p.start, p.end))
    return {"rows": rows, "totals": {"baseCentavos": sum(r["baseCentavos"] for r in rows), "taxCentavos": sum(r["taxCentavos"] for r in rows)},
            "missingTin": sum(1 for r in rows if not r["tin"])}


def form_1604e(db: Session, year: int, fiscal_month_end: int = 12) -> dict:
    """Annual information return of expanded withholding: the year's payees (its alphalist) and the totals by ATC."""
    start = quarter(year, 1, fiscal_month_end).start
    end = quarter(year, 4, fiscal_month_end).end
    bills = withheld_bills(db, start, end)
    payees = by_payee(bills)
    return {
        "form": "1604E", "title": "Annual information return of creditable income taxes withheld (expanded)",
        "period": {"start": start.isoformat(), "end": end.isoformat(), "label": f"Year {year}"},
        "payees": payees, "byAtc": by_atc(bills),
        "totals": {"baseCentavos": sum(r["baseCentavos"] for r in payees), "taxCentavos": sum(r["taxCentavos"] for r in payees)},
    }


def form_2307(db: Session, p: Period, supplier_id: str) -> dict:
    """Certificate of creditable tax withheld at source, for one supplier and quarter: by ATC, each month's income payments, and the tax withheld."""
    bills = withheld_bills(db, p.start, p.end, supplier_id)
    months = months_of(p)
    rows: dict[tuple, dict] = {}
    for pu in bills:
        i = next(n for n, m in enumerate(months) if m.start <= pu.on <= m.end)
        for atc, bp, base, tax in pu.held:
            row = rows.setdefault((atc, bp), {"atc": atc, "nature": nature(atc), "rateBp": bp, "months": [0, 0, 0], "baseCentavos": 0, "taxCentavos": 0})
            row["months"][i] += base
            row["baseCentavos"] += base
            row["taxCentavos"] += tax
    if supplier_id.startswith("store:"):  # a store paid from petty cash: as its receipts name it
        payee = {"id": supplier_id, "name": bills[0].name if bills else None, "tin": bills[0].tin if bills else None, "address": None}
    else:
        supplier = db.get(Supplier, supplier_id)
        payee = {"id": supplier_id, "name": (supplier.company_name or supplier.name) if supplier else None,
                 "tin": supplier.tin if supplier else None, "address": supplier.address if supplier else None}
    return {
        "form": "2307", "title": "Certificate of creditable tax withheld at source",
        "payee": payee,
        "monthLabels": [m.label for m in months],
        "rows": sorted(rows.values(), key=lambda r: r["atc"] or ""),
        "totals": {"baseCentavos": sum(r["baseCentavos"] for r in rows.values()), "taxCentavos": sum(r["taxCentavos"] for r in rows.values())},
    }


def withheld_suppliers(db: Session, p: Period) -> list[dict]:
    """The suppliers the company withheld from in the quarter: each gets a 2307."""
    seen: dict[str, dict] = {}
    for pu in withheld_bills(db, p.start, p.end):
        row = seen.setdefault(pu.supplier_id, {"id": pu.supplier_id, "name": pu.name, "tin": pu.tin, "taxCentavos": 0})
        row["taxCentavos"] += sum(h[3] for h in pu.held)
    return sorted(seen.values(), key=lambda r: r["name"].upper())
