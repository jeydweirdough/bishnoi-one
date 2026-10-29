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
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from app import bir_reports as bir
from app.access import permitted
from app.deps import DB, SettingsDep
from app.routers.funds import today

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
    return f"{(centavos or 0) / 100:.2f}"


def as_csv(name: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
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
def income(_: Viewer, db: DB, settings: SettingsDep, start: date | None = None, end: date | None = None) -> dict:
    end = end or today(settings)
    start = start or end.replace(month=1, day=1)
    start, end = span(start, end, settings)
    return {"title": "Income statement", "taxpayer": bir.taxpayer(db), "period": period_out(start, end), **bir.income_statement(db, start, end)}


@router.get("/statements/balance")
def balance(_: Viewer, db: DB, settings: SettingsDep, as_of: date | None = Query(None, alias="asOf")) -> dict:
    as_of = as_of or today(settings)
    return {"title": "Balance sheet", "taxpayer": bir.taxpayer(db), "asOf": as_of.isoformat(), **bir.balance_sheet(db, as_of)}


def default_quarter(settings) -> tuple[int, int]:
    d = today(settings)
    return d.year, (d.month - 1) // 3 + 1


@router.get("/returns/vat")
def vat(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None) -> dict:
    y, q = default_quarter(settings)
    p = the_quarter(db, year or y, quarter or q)
    return {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year or y, "quarter": quarter or q, **bir.vat_return(db, p)}


@router.get("/lists/{which}")
def summary_list(which: Literal["sls", "slp", "sawt", "qap"], _: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None, format: Literal["json", "csv"] = "json"):
    y, q = default_quarter(settings)
    year, quarter = year or y, quarter or q
    p = the_quarter(db, year, quarter)
    who = bir.taxpayer(db)
    if which == "sls":
        data = bir.sls(db, p)
        if format == "csv":
            return as_csv(f"Summary List of Sales {year} Q{quarter}", ["TIN", "Registered name", "Address", "Exempt sales", "Zero-rated sales", "Taxable sales", "Output tax", "Gross taxable sales"],
                          [[r["tin"] or "", r["name"], r["address"] or "", pesos(r["exemptCentavos"]), pesos(r["zeroRatedCentavos"]), pesos(r["taxableCentavos"]), pesos(r["outputTaxCentavos"]), pesos(r["grossTaxableCentavos"])] for r in data["rows"]])
        title = "Summary List of Sales"
    elif which == "slp":
        data = bir.slp(db, p)
        if format == "csv":
            return as_csv(f"Summary List of Purchases {year} Q{quarter}", ["TIN", "Registered name", "Address", "Exempt purchases", "Zero-rated purchases", "Taxable purchases", "Input tax", "Gross taxable purchases", *[f"{label}: {part}" for label in bir.payables.PURCHASE_TYPES.values() for part in ("Purchases before VAT", "Input VAT")]],
                          [[r["tin"] or "", r["name"], r["address"] or "", pesos(r["exemptCentavos"]), pesos(r["zeroRatedCentavos"]), pesos(r["taxableCentavos"]), pesos(r["inputTaxCentavos"]), pesos(r["grossTaxableCentavos"]), *[pesos(r[f"{bir.camel(kind)}{suffix}"]) for kind in bir.payables.PURCHASE_TYPES for suffix in ("Centavos", "InputTaxCentavos")]] for r in data["rows"]])
        title = "Summary List of Purchases"
    elif which == "qap":
        data = bir.qap(db, p)
        if format == "csv":
            return as_csv(f"QAP {year} Q{quarter}", ["TIN of payee", "Registered name of payee", "ATC", "Nature of income payment", "Amount of income payment", "Rate of tax", "Amount of tax withheld"],
                          [[r["tin"] or "", r["payee"], r["atc"] or "", r["nature"] or "", pesos(r["baseCentavos"]), f"{r['rateBp'] / 100:.2f}%", pesos(r["taxCentavos"])] for r in data["rows"]])
        title = "Quarterly Alphalist of Payees (QAP)"
    else:
        data = bir.sawt(db, p)
        if format == "csv":
            return as_csv(f"SAWT {year} Q{quarter}", ["TIN of payor", "Registered name of payor", "ATC", "Amount of income payment", "Rate of tax", "Amount of tax withheld", "Forms 2307"],
                          [[r["tin"] or "", r["payor"], r["atc"] or "", pesos(r["incomePaymentCentavos"]), f"{(r['rateBp'] or 0) / 100:.2f}%", pesos(r["withheldCentavos"]), "; ".join(r["certificates"])] for r in data["rows"]])
        title = "Summary Alphalist of Withholding Taxes (SAWT)"
    return {"list": which, "title": title, "taxpayer": who, "period": period_out(p.start, p.end, p.label), "year": year, "quarter": quarter, **data}



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
    p = the_quarter(db, year or y, quarter or q)
    return {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year or y, "quarter": quarter or q, **bir.form_1601eq(db, p)}


@router.get("/withholding/1604e")
def withholding_1604e(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, format: Literal["json", "csv"] = "json"):
    who = bir.taxpayer(db)
    year = year or today(settings).year - 1
    data = bir.form_1604e(db, year, who["fiscalMonthEnd"])
    if format == "csv":
        return as_csv(f"1604E alphalist {year}", ["TIN of payee", "Registered name of payee", "ATC", "Nature of income payment", "Amount of income payment", "Rate of tax", "Amount of tax withheld"],
                      [[r["tin"] or "", r["payee"], r["atc"] or "", r["nature"] or "", pesos(r["baseCentavos"]), f"{r['rateBp'] / 100:.2f}%", pesos(r["taxCentavos"])] for r in data["payees"]])
    return {"taxpayer": who, "year": year, **data}


@router.get("/withholding/2307")
def withholding_2307(_: Viewer, db: DB, settings: SettingsDep, year: int | None = None, quarter: int | None = None, supplier_id: str | None = Query(None, alias="supplierId")) -> dict:
    """With a supplier: its certificate for the quarter. Without: the suppliers withheld from, each due one."""
    y, q = default_quarter(settings)
    year, quarter = year or y, quarter or q
    p = the_quarter(db, year, quarter)
    out = {"taxpayer": bir.taxpayer(db), "period": period_out(p.start, p.end, p.label), "year": year, "quarter": quarter, "suppliers": bir.withheld_suppliers(db, p)}
    if supplier_id:
        out["certificate"] = bir.form_2307(db, p, supplier_id)
    return out


@router.get("/readiness")
def readiness(_: Viewer, db: DB, settings: SettingsDep, start: date | None = None, end: date | None = None) -> dict:
    """Each tax list against the books for the same period (app/bir_readiness.py). Read-only."""
    from zoneinfo import ZoneInfo

    from app.bir_readiness import readiness as compare

    start, end = span(start, end, settings)
    return {**compare(db, start, end, ZoneInfo(settings.org_timezone)), "period": period_out(start, end)}
