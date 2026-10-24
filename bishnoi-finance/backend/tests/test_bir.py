"""The BIR's books, statements, VAT return and summary lists, read from what
Finance posts (app/bir.py), and the creditable withholding customers deduct
from what they pay (their Form 2307)."""

from datetime import date

from app import bir
from .test_invoices import TODAY, issued, ready
from .test_ledger import balances
from .test_tax_api import REGISTRATION, ana, app, ben, client  # noqa: F401 (fixtures)

QUARTER = (date.today().month - 1) // 3 + 1
YEAR = date.today().year


def paid_with_withholding(client, who):
    """An invoice of 2,240.00 (2,000.00 VATable, 240.00 VAT), paid 2,200.00 by bank with 40.00 withheld (2% of 2,000.00, WC158)."""
    inv = issued(client, who)
    r = client.post(f"/finance/invoices/{inv['id']}/payments", json={
        "paidOn": TODAY, "amountCentavos": 220000, "method": "bank", "reference": "DEP-9",
        "cwtCentavos": 4000, "cwtAtc": "wc158", "cwtCertificate": "2307 no. 0001",
    }, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_tax_withheld_by_the_customer_settles_the_invoice_and_is_kept_to_claim(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    inv = paid_with_withholding(client, ben)
    assert (inv["paidCentavos"], inv["balanceCentavos"]) == (224000, 0)
    assert inv["payments"][0]["cwtAtc"] == "WC158" and inv["payments"][0]["cwtCertificate"] == "2307 no. 0001"
    # The bank got the money; 1210 holds what the customer paid the BIR for us; nothing is owed.
    assert balances(client, ana) == {"1010": 220000, "1210": 4000, "1100": 0, "4000": 200000, "2200": 24000}
    # Withholding needs its ATC, as the 2307 shows it.
    other = issued(client, ana)
    no_atc = client.post(f"/finance/invoices/{other['id']}/payments", json={"paidOn": TODAY, "amountCentavos": 1000, "method": "cash", "cwtCentavos": 100}, headers=ben)
    assert no_atc.status_code == 422 and "ATC" in no_atc.text


def test_the_books_of_accounts(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    paid_with_withholding(client, ben)
    sj = client.get("/finance/bir/books/sales-journal", headers=ben).json()
    assert sj["title"] == "Sales Journal" and sj["taxpayer"]["tin"] == "123-456-789"
    assert sj["totals"] == {"grossCentavos": 224000, "taxableSalesCentavos": 200000, "taxCentavos": 24000, "zeroRatedSalesCentavos": 0, "exemptSalesCentavos": 0, "nonTaxableSalesCentavos": 0}
    cr = client.get("/finance/bir/books/cash-receipts", headers=ben).json()
    assert cr["totals"] == {"cashCentavos": 220000, "cwtCentavos": 4000, "receivablesCentavos": 224000}
    gj = client.get("/finance/bir/books/general-journal", headers=ben).json()
    assert gj["totals"]["debitCentavos"] == gj["totals"]["creditCentavos"] == 224000 + 224000
    gl = {a["code"]: a for a in client.get("/finance/bir/books/general-ledger", headers=ben).json()["accounts"]}
    assert gl["1100"]["closingCentavos"] == 0 and gl["1210"]["closingCentavos"] == 4000
    # Each book also comes as a file, in its columns.
    csv = client.get("/finance/bir/books/sales-journal?format=csv", headers=ben)
    assert csv.headers["content-type"].startswith("text/csv") and "Invoice no.,Customer,TIN" in csv.text and "2240.00" in csv.text
    assert client.get("/finance/bir/books/nonsense", headers=ben).status_code == 404


def test_the_statements_balance(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    paid_with_withholding(client, ben)
    inc = client.get("/finance/bir/statements/income", headers=ben).json()
    assert inc["totals"] == {"incomeCentavos": 200000, "expensesCentavos": 0, "netCentavos": 200000}
    bs = client.get("/finance/bir/statements/balance", headers=ben).json()
    assert bs["totals"]["balanced"] is True and bs["totals"]["assetsCentavos"] == 224000
    assert {"code": "", "account": "Net income, not yet closed", "amountCentavos": 200000} in bs["equity"]


def test_the_quarters_vat_return(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    paid_with_withholding(client, ben)
    vat = client.get(f"/finance/bir/returns/vat?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    lines = {line["key"]: line for line in vat["lines"]}
    assert vat["form"] == "2550Q" and len(vat["months"]) == 3
    assert (lines["taxable"]["amountCentavos"], lines["output"]["amountCentavos"], lines["payable"]["amountCentavos"]) == (200000, 24000, 24000)
    assert lines["input"]["amountCentavos"] == 0  # no supplier bills recorded (tests/test_bills.py)
    # A non-VAT company files the percentage tax return instead.
    client.put("/tax/profile", json={**REGISTRATION, "regime": "non_vat"}, headers=ana)
    assert client.get("/finance/bir/returns/vat", headers=ben).json()["form"] == "2551Q"


def test_the_summary_lists(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    paid_with_withholding(client, ben)
    sls = client.get(f"/finance/bir/lists/sls?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    assert [(r["name"], r["taxableCentavos"], r["outputTaxCentavos"]) for r in sls["rows"]] == [("Mercury Drug Makati", 200000, 24000)]
    assert sls["missingTin"] == 1  # the customer's TIN isn't on the invoice
    sawt = client.get(f"/finance/bir/lists/sawt?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    assert [(r["payor"], r["atc"], r["incomePaymentCentavos"], r["withheldCentavos"], r["rateBp"]) for r in sawt["rows"]] == [("Mercury Drug Makati", "WC158", 200000, 4000, 200)]
    csv = client.get(f"/finance/bir/lists/sawt?year={YEAR}&quarter={QUARTER}&format=csv", headers=ben).text
    assert "ATC,Amount of income payment" in csv and "WC158,2000.00,2.00%,40.00" in csv


def test_the_rdo_and_fiscal_year_go_on_the_forms(client, ana):  # noqa: F811 (a fixture)
    r = client.put("/tax/profile", json={**REGISTRATION, "rdoCode": "050", "fiscalMonthEnd": 6}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.put("/tax/profile", json={**REGISTRATION, "rdoCode": "5"}, headers=ana).status_code == 422
    who = client.get("/finance/bir/lists/sls", headers=ana).json()["taxpayer"]
    assert (who["rdoCode"], who["fiscalMonthEnd"]) == ("050", 6)


def test_quarters_follow_the_fiscal_year():
    assert (bir.quarter(2026, 1).start, bir.quarter(2026, 1).end) == (date(2026, 1, 1), date(2026, 3, 31))
    # A year ending in June: its first quarter is July to September of the year before.
    assert (bir.quarter(2026, 1, 6).start, bir.quarter(2026, 1, 6).end) == (date(2025, 7, 1), date(2025, 9, 30))
    assert (bir.quarter(2026, 4, 6).start, bir.quarter(2026, 4, 6).end) == (date(2026, 4, 1), date(2026, 6, 30))
