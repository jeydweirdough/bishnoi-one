"""The BIR's books of accounts, statements, VAT return and summary lists
(app/bir_reports.py works them out). Each answers as data for the screens, or with
?format=csv as a file in the BIR templates' columns.

- GET /finance/bir/books/{book}?start=&end=: sales-journal, cash-receipts,
  cash-disbursements, general-journal, general-ledger
- GET /finance/bir/statements/income?start=&end=, /statements/balance?asOf=
- GET /finance/bir/returns/vat?year=&quarter=: 2550Q (VAT) or 2551Q (non-VAT)
- GET /finance/bir/lists/sls?year=&quarter=, /lists/sawt?year=&quarter=
"""

import csv
import io
from decimal import Decimal
import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from modules.finance import bir_dat, bir_reports as bir
from modules.finance.access import permitted
from modules.finance.deps import DB, SettingsDep
from modules.finance.routers.funds import today

router = APIRouter(prefix="/finance/bir", tags=["bir"])

Viewer = permitted("bir.view")
BOOKS = {
    "sales-journal": "Sales Journal",
    "purchase-journal": "Purchase Journal",
    "cash-receipts": "Cash Receipts Journal",
    "cash-disbursements": "Cash Disbursements Journal",
    "general-journal": "General Journal",
    "general-ledger": "General Ledger",
}


def pesos(centavos: int | None) -> str:
    return f"{Decimal(centavos or 0) / 100:.2f}"


def as_csv(name: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    # Protect text cells while preserving exact numeric amounts, including negatives.
    from modules.finance.routers.exports import text
    writer.writerows([[text(v) if isinstance(v, str) and not re.fullmatch(r"-?\d+(?:\.\d+)?", v) else v for v in row] for row in rows])
    # A byte-order mark, so Excel reads the names' ñ and accents right.
    return Response("﻿" + buffer.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})


def span(start: date | None, end: date | None, settings) -> tuple[date, date]:
    end = end or today(settings)
    start = start or end.replace(day=1)
    if start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The start date is after the end date.")
    return start, end


def the_quarter(db, year: int, q: int) -> bir.Period:
    try:
        return bir.quarter(year, q, bir.taxpayer(db)["fiscalMonthEnd"])
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None


def calendar_quarter(year: int, q: int) -> bir.Period:
    """Withholding returns (1601-EQ, QAP, 2307, SAWT, 1604-E) follow BIR calendar quarters regardless of fiscal year."""
    try:
        return bir.quarter(year, q, 12)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None


def period_out(start: date, end: date, label: str | None = None) -> dict:
    return {"start": start.isoformat(), "end": end.isoformat(), "label": label or f"{start:%b %d, %Y} to {end:%b %d, %Y}"}


@router.get("/books/{book}")
def book(book: str, _: Viewer, db: DB, settings: SettingsDep, start: date | None = None, end: date | None = None, format: Literal["json", "csv"] = "json"):
    if book not in BOOKS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such book.")
    start, end = span(start, end, settings)
    name = f"{BOOKS[book]} {start:%Y-%m-%d} to {end:%Y-%m-%d}"
    if book == "sales-journal":
        data = bir.sales_journal(db, start, end)
        if format == "csv":
            return as_csv(name, ["Date", "Invoice no.", "Customer", "TIN", "Address", "Gross sales", "VATable sales", "Output VAT", "Zero-rated", "VAT-exempt", "Non-VAT sales", "Void"],
                          [[r["date"], r["number"], r["customer"], r["tin"] or "", r["address"] or "", pesos(r["grossCentavos"]), pesos(r["taxableSalesCentavos"]), pesos(r["taxCentavos"]),
                            pesos(r["zeroRatedSalesCentavos"]), pesos(r["exemptSalesCentavos"]), pesos(r["nonTaxableSalesCentavos"]), "VOID" if r["void"] else ""] for r in data["rows"]])
    elif book == "purchase-journal":
        data = bir.purchase_journal(db, start, end)
        if format == "csv":
            return as_csv(name, ["Date", "Bill no.", "Supplier invoice no.", "Supplier", "TIN", "Total", "VATable purchases", "Input VAT", "Zero-rated", "Exempt and non-VAT", "ATC", "Tax withheld", "Payable", "Void"],
                          [[r["date"], r["no"], r["supplierInvoiceNo"], r["supplier"], r["tin"] or "", pesos(r["totalCentavos"]), pesos(r["vatableCentavos"]), pesos(r["inputTaxCentavos"]),
                            pesos(r["zeroRatedCentavos"]), pesos(r["exemptCentavos"]), r["atc"] or "", pesos(r["ewtCentavos"]), pesos(r["payableCentavos"]), "VOID" if r["void"] else ""] for r in data["rows"]])
    elif book == "cash-receipts":
        data = bir.cash_receipts(db, start, end)
        if format == "csv":
            return as_csv(name, ["Date", "Invoice no.", "Customer", "TIN", "How paid", "Reference", "Cash received", "Tax withheld (2307)", "ATC", "Accounts receivable"],
                          [[r["date"], r["invoice"], r["customer"], r["tin"] or "", r["method"], r["reference"] or "", pesos(r["cashCentavos"]), pesos(r["cwtCentavos"]), r["atc"] or "", pesos(r["receivablesCentavos"])] for r in data["rows"]])
    elif book == "cash-disbursements":
        data = bir.cash_disbursements(db, start, end)
        if format == "csv":
            return as_csv(name, ["Date", "Entry no.", "Particulars", "Reference", "Paid from", "Amount", "Charged to"],
                          [[r["date"], r["number"], r["memo"], r["reference"] or "", r["from"], pesos(r["amountCentavos"]), "; ".join(f"{c['code']} {c['account']} {pesos(c['debitCentavos'])}" for c in r["charged"])] for r in data["rows"]])
    elif book == "general-journal":
        data = bir.general_journal(db, start, end)
        if format == "csv":
            return as_csv(name, ["Date", "Entry no.", "Particulars", "Reference", "Account code", "Account", "Debit", "Credit"],
                          [[e["date"], e["number"], e["memo"], e["reference"] or "", ln["code"], ln["account"], pesos(ln["debitCentavos"]), pesos(ln["creditCentavos"])] for e in data["entries"] for ln in e["lines"]])
    else:
        data = bir.general_ledger(db, start, end)
        if format == "csv":
            rows = []
            for a in data["accounts"]:
                rows.append(["", "", f"{a['code']} {a['account']}: balance brought forward", "", "", pesos(a["openingCentavos"])])
                rows += [[r["date"], r["number"], r["memo"], pesos(r["debitCentavos"]), pesos(r["creditCentavos"]), pesos(r["balanceCentavos"])] for r in a["rows"]]
            return as_csv(name, ["Date", "Entry no.", "Particulars", "Debit", "Credit", "Balance"], rows)
    return {"book": book, "title": BOOKS[book], "taxpayer": bir.taxpayer(db), "period": period_out(start, end), **data}


@router.get("/statements/income")
def income(_: Viewer, db: DB, settings: SettingsDep, start: date | None = None, end: date | None = None, format: Literal["json", "csv"] = "json"):
    end = end or today(settings)
    start = start or end.replace(month=1, day=1)
    start, end = span(start, end, settings)
    data = bir.income_statement(db, start, end)
    if format == "csv":
        rows = [["Income", r["code"], r["account"], pesos(r["amountCentavos"])] for r in data["income"]]
        rows += [["Expenses", r["code"], r["account"], pesos(r["amountCentavos"])] for r in data["expenses"]]
        rows.append(["Total", "", "Total income", pesos(data["totals"]["incomeCentavos"])])
        rows.append(["Total", "", "Total expenses", pesos(data["totals"]["expensesCentavos"])])
        rows.append(["Total", "", "Net income" if data["totals"]["netCentavos"] >= 0 else "Net loss", pesos(data["totals"]["netCentavos"])])
        return as_csv(f"Income statement {start:%Y-%m-%d} to {end:%Y-%m-%d}", ["Section", "Code", "Account", "Amount"], rows)
    return {"title": "Income statement", "taxpayer": bir.taxpayer(db), "period": period_out(start, end), **data}


@router.get("/statements/balance")
def balance(_: Viewer, db: DB, settings: SettingsDep, as_of: date | None = Query(None, alias="asOf"), format: Literal["json", "csv"] = "json"):
    as_of = as_of or today(settings)
    data = bir.balance_sheet(db, as_of)
    if format == "csv":
        rows = []
        for label, key, total_key in (("Assets", "assets", "assetsCentavos"), ("Liabilities", "liabilities", "liabilitiesCentavos"), ("Equity", "equity", "equityCentavos")):
            rows += [[label, r["code"], r["account"], pesos(r["amountCentavos"])] for r in data[key]]
            rows.append(["Total", "", f"Total {label.lower()}", pesos(data["totals"][total_key])])
        rows.append(["Total", "", "Total liabilities and equity", pesos(data["totals"]["liabilitiesCentavos"] + data["totals"]["equityCentavos"])])
        return as_csv(f"Balance sheet as of {as_of:%Y-%m-%d}", ["Section", "Code", "Account", "Amount"], rows)
    return {"title": "Balance sheet", "taxpayer": bir.taxpayer(db), "asOf": as_of.isoformat(), **data}


def default_quarter(settings) -> tuple[int, int]:
    d = today(settings)
    return d.year, (d.month - 1) // 3 + 1


@router.get("/returns/vat")
def vat(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None) -> dict:
    y, q = default_quarter(settings)
    p = the_quarter(db, year or y, quarter or q)
    return {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year or y, "quarter": quarter or q, **bir.vat_return(db, p)}


@router.get("/lists/{which}")
def summary_list(
    which: Literal["sls", "slp", "sawt", "qap"],
    _: Viewer,
    db: DB,
    settings: SettingsDep,
    year: int | None = None,
    quarter: int | None = Query(None, ge=1, le=4),
    month: int | None = Query(None, ge=1, le=12),
    sawt_form: Literal["all", "1702Q", "2550Q"] = Query("all", alias="form"),
    format: Literal["json", "csv", "dat"] = "json",
):
    y, q = default_quarter(settings)
    year = year or y
    if month is not None:
        derived_q = (month - 1) // 3 + 1
        if quarter is not None and quarter != derived_q:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Selected month does not belong to that quarter.")
        quarter = derived_q
        p = bir.Period(date(year, month, 1), bir.month_end(year, month), date(year, month, 1).strftime("%B %Y"))
    else:
        quarter = quarter or q
        p = calendar_quarter(year, quarter) if which in ("qap", "sawt") else the_quarter(db, year, quarter)
    who = bir.taxpayer(db)
    period_tag = f"{year} M{month:02d}" if month is not None else f"{year} Q{quarter}"
    if which == "sls":
        data = bir.sls(db, p)
        if format == "csv":
            return as_csv(f"Summary List of Sales {period_tag}", ["TIN", "Registered name", "Address", "Exempt sales", "Zero-rated sales", "Taxable sales", "Output tax", "Gross taxable sales"],
                          [[r["tin"] or "", r["name"], r["address"] or "", pesos(r["exemptCentavos"]), pesos(r["zeroRatedCentavos"]), pesos(r["taxableCentavos"]), pesos(r["outputTaxCentavos"]), pesos(r["grossTaxableCentavos"])] for r in data["rows"]])
        title = "Summary List of Sales"
    elif which == "slp":
        data = bir.slp(db, p)
        if format == "csv":
            return as_csv(f"Summary List of Purchases {period_tag}", ["TIN", "Registered name", "Address", "Exempt purchases", "Zero-rated purchases", "Taxable purchases", "Input tax", "Gross taxable purchases", *[f"{label}: {part}" for label in bir.payables.PURCHASE_TYPES.values() for part in ("Purchases before VAT", "Input VAT")]],
                          [[r["tin"] or "", r["name"], r["address"] or "", pesos(r["exemptCentavos"]), pesos(r["zeroRatedCentavos"]), pesos(r["taxableCentavos"]), pesos(r["inputTaxCentavos"]), pesos(r["grossTaxableCentavos"]), *[pesos(r[f"{bir.camel(kind)}{suffix}"]) for kind in bir.payables.PURCHASE_TYPES for suffix in ("Centavos", "InputTaxCentavos")]] for r in data["rows"]])
        title = "Summary List of Purchases"
    elif which == "qap":
        data = bir.qap(db, p)
        if format == "csv":
            return as_csv(f"QAP {period_tag}", ["TIN of payee", "Registered name of payee", "ATC", "Nature of income payment", "Amount of income payment", "Rate of tax", "Amount of tax withheld"],
                          [[r["tin"] or "", r["payee"], r["atc"] or "", r["nature"] or "", pesos(r["baseCentavos"]), f"{r['rateBp'] / 100:.2f}%", pesos(r["taxCentavos"])] for r in data["rows"]])
        title = "Quarterly Alphalist of Payees (QAP)"
    else:
        data = bir.sawt(db, p, form=sawt_form)
        if format == "csv":
            sawt_name = f"SAWT {period_tag}" if sawt_form == "all" else f"SAWT {sawt_form} {period_tag}"
            return as_csv(sawt_name, ["TIN of payor", "Registered name of payor", "ATC", "Amount of income payment", "Rate of tax", "Amount of tax withheld", "Forms 2307"],
                          [[r["tin"] or "", r["payor"], r["atc"] or "", pesos(r["incomePaymentCentavos"]), f"{(r['rateBp'] or 0) / 100:.2f}%", pesos(r["withheldCentavos"]), "; ".join(r["certificates"])] for r in data["rows"]])
        title = "Summary Alphalist of Withholding Taxes (SAWT)"
    if format == "dat":
        dat_sawt_form = "2550Q" if sawt_form == "2550Q" else "1702Q"
        dat_text, filename = bir_dat.build_list_dat(which, who, p.end, data, sawt_form=dat_sawt_form)
        return Response(dat_text, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    return {"list": which, "title": title, "taxpayer": who, "period": period_out(p.start, p.end, p.label), "year": year, "quarter": quarter, "month": month, **({"form": sawt_form} if which == "sawt" else {}), **data}


@router.get("/returns/income-tax")
def income_tax(
    _: Viewer,
    db: DB,
    settings: SettingsDep,
    year: int | None = None,
    quarter: int | None = None,
    rate_bp: int = Query(2500, alias="rateBp"),
    format: Literal["json", "csv"] = "json",
):
    if rate_bp not in (2000, 2500):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Corporate income tax rate must be 20% (2000 bp) or 25% (2500 bp).")
    y, q = default_quarter(settings)
    year, quarter = year or y, quarter or q
    p = the_quarter(db, year, quarter)
    data = bir.income_tax_1702q(db, p, rate_bp)
    if format == "csv":
        return as_csv(f"1702Q draft {year} Q{quarter}", ["Item", "Amount"], [[ln["label"], pesos(ln["amountCentavos"])] for ln in data["lines"]])
    return {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year, "quarter": quarter, **data}


@router.get("/returns/income-tax/draft.pdf")
def income_tax_draft_pdf(
    _: Viewer,
    db: DB,
    settings: SettingsDep,
    year: int | None = None,
    quarter: int | None = None,
    rate_bp: int = Query(2500, alias="rateBp"),
) -> Response:
    from modules.finance.bir_form_1702q import prepare, render

    report = income_tax(_, db, settings, year, quarter, rate_bp, "json")
    try:
        document = render(prepare(report))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return Response(
        document,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="1702Q-review-draft-{report["year"]}-Q{report["quarter"]}.pdf"',
            "Cache-Control": "no-store",
        },
    )



# --- expanded withholding: what the company withheld from its suppliers -----------------------


@router.get("/withholding/0619e")
def withholding_0619e(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, month: int | None = None) -> dict:
    d = today(settings)
    year, month = year or d.year, month or d.month
    if not 1 <= month <= 12:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A month is 1 to 12.")
    m = bir.Period(date(year, month, 1), bir.month_end(year, month), date(year, month, 1).strftime("%B %Y"))
    return {"taxpayer": bir.taxpayer(db), "period": period_out(m.start, m.end, m.label), "year": year, "month": month, **bir.form_0619e(db, m)}


@router.get("/withholding/1601eq")
def withholding_1601eq(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None) -> dict:
    y, q = default_quarter(settings)
    p = calendar_quarter(year or y, quarter or q)
    return {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year or y, "quarter": quarter or q, **bir.form_1601eq(db, p)}


@router.get("/withholding/1604e")
def withholding_1604e(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, format: Literal["json", "csv"] = "json"):
    who = bir.taxpayer(db)
    year = year or today(settings).year - 1
    data = bir.form_1604e(db, year, 12)
    if format == "csv":
        return as_csv(f"1604E alphalist {year}", ["TIN of payee", "Registered name of payee", "ATC", "Nature of income payment", "Amount of income payment", "Rate of tax", "Amount of tax withheld"],
                      [[r["tin"] or "", r["payee"], r["atc"] or "", r["nature"] or "", pesos(r["baseCentavos"]), f"{r['rateBp'] / 100:.2f}%", pesos(r["taxCentavos"])] for r in data["payees"]])
    return {"taxpayer": who, "year": year, **data}


def _resolve_2307_scope(
    db: DB,
    settings: SettingsDep,
    year: int | None,
    quarter: int | None,
    month: int | None,
    supplier_id: str | None,
    bill_id: str | None,
    voucher_id: str | None,
):
    from modules.finance.models import Bill, PaymentVoucher

    if bill_id and voucher_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose either a bill or a payment voucher, not both.")
    anchor_date: date | None = None
    if bill_id:
        b = db.get(Bill, bill_id)
        if b is None or b.status != "recorded":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Recorded bill not found.")
        if supplier_id and supplier_id != b.supplier_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Bill belongs to a different supplier.")
        supplier_id = b.supplier_id
        anchor_date = b.bill_date
    elif voucher_id:
        v = db.get(PaymentVoucher, voucher_id)
        if v is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment voucher not found.")
        if supplier_id and supplier_id != v.supplier_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Payment voucher belongs to a different supplier.")
        supplier_id = v.supplier_id
        bill_dates = sorted(ln.bill.bill_date for ln in v.lines if ln.bill and ln.bill.status == "recorded")
        anchor_date = bill_dates[0] if bill_dates else v.paid_on
    dy, dq = default_quarter(settings)
    if anchor_date is not None:
        dy, dq = anchor_date.year, (anchor_date.month - 1) // 3 + 1
    y = year or dy
    if month is not None:
        if not 1 <= month <= 12:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A month is 1 to 12.")
        derived_q = (month - 1) // 3 + 1
        if quarter is not None and quarter != derived_q:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Selected month does not belong to that quarter.")
        q = derived_q
        scope_p = bir.Period(date(y, month, 1), bir.month_end(y, month), date(y, month, 1).strftime("%B %Y"))
    else:
        q = quarter or dq
        scope_p = calendar_quarter(y, q)
    return y, q, month, calendar_quarter(y, q), scope_p, supplier_id


@router.get("/withholding/2307")
def withholding_2307(
    _: Viewer,
    db: DB,
    settings: SettingsDep,
    year: int | None = None,
    quarter: int | None = Query(None, ge=1, le=4),
    month: int | None = Query(None, ge=1, le=12),
    supplier_id: str | None = Query(None, alias="supplierId"),
    bill_id: str | None = Query(None, alias="billId"),
    voucher_id: str | None = Query(None, alias="voucherId"),
) -> dict:
    """With a supplier (or billId/voucherId): its certificate for the quarter (or single month). Without: the suppliers withheld from, each due one."""
    year, quarter, month, quarter_p, scope_p, supplier_id = _resolve_2307_scope(db, settings, year, quarter, month, supplier_id, bill_id, voucher_id)
    out = {
        "taxpayer": bir.taxpayer(db),
        "period": period_out(scope_p.start, scope_p.end, scope_p.label),
        "year": year,
        "quarter": quarter,
        "month": month,
        "suppliers": bir.withheld_suppliers(db, scope_p),
    }
    if supplier_id:
        out["certificate"] = bir.form_2307(db, quarter_p, supplier_id, bill_id=bill_id, voucher_id=voucher_id, month=month)
    return out


@router.get("/readiness")
def readiness(_: Viewer, db: DB, settings: SettingsDep, start: date | None = None, end: date | None = None) -> dict:
    """Each tax list against the books for the same period (app/bir_readiness.py). Read-only."""
    from zoneinfo import ZoneInfo

    from modules.finance.bir_readiness import readiness as compare

    start, end = span(start, end, settings)
    return {**compare(db, start, end, ZoneInfo(settings.org_timezone)), "period": period_out(start, end)}


@router.get("/returns/vat/draft")
def vat_draft(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None) -> dict:
    from modules.finance.bir_form_2550q import build_draft
    try:
        return build_draft(vat(_, db, settings, year, quarter))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/returns/vat/draft.pdf")
def vat_draft_pdf(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None) -> Response:
    from modules.finance.bir_pdf import render_draft
    try:
        document = render_draft(vat_draft(_, db, settings, year, quarter))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return Response(document, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="2550Q-review-draft.pdf"', "Cache-Control": "no-store"})


@router.get("/withholding/2307/draft.pdf")
def certificate_draft_pdf(
    user: Viewer,
    db: DB,
    settings: SettingsDep,
    supplier_id: str | None = Query(None, alias="supplierId"),
    bill_id: str | None = Query(None, alias="billId"),
    voucher_id: str | None = Query(None, alias="voucherId"),
    year: int | None = None,
    quarter: int | None = Query(None, ge=1, le=4),
    month: int | None = Query(None, ge=1, le=12),
) -> Response:
    from modules.finance.bir_form_2307 import prepare, render
    if not (supplier_id or bill_id or voucher_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a supplier, bill, or payment voucher first.")
    try:
        report=withholding_2307(user,db,settings,year,quarter,month,supplier_id,bill_id,voucher_id)
        if not report.get('certificate',{}).get('rows'):
            raise HTTPException(404,'No withholding certificate records for this payee and period.')
        document=render(prepare(report))
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    return Response(document,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="2307-review-certificate.pdf"','Cache-Control':'no-store'})


@router.get("/withholding/{form}/draft.pdf")
def withholding_draft_pdf(form: Literal["0619e", "1601eq", "1604e"], user: Viewer, db: DB, settings: SettingsDep, year: int | None = Query(None, ge=1900, le=9998), month: int | None = Query(None, ge=1, le=12), quarter: int | None = Query(None, ge=1, le=4)) -> Response:
    from modules.finance.bir_withholding_pdf import prepare, render
    if form=='0619e':report=withholding_0619e(user,db,settings,year,month)
    elif form=='1601eq':report=withholding_1601eq(user,db,settings,year,quarter)
    else:report=withholding_1604e(user,db,settings,year,'json')
    try:document=render(prepare(report))
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    return Response(document,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{form}-review-draft.pdf"','Cache-Control':'no-store'})


@router.get("/filing-guidance")
def filing_guidance(_: Viewer, form: Literal["2550Q", "2307", "0619E", "1601EQ", "1604E", "1702Q"]) -> dict:
    from modules.finance.bir_filing import guidance
    return guidance(form)
