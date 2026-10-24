"""Supplier bills (decided 2026-10-24, BIR features from Oojeema): made out to
Inventory's suppliers, recorded with their input VAT and the expanded
withholding, paid; and the BIR's purchase side read from them (Purchase
Journal, 2550Q input VAT, SLP, 0619E, 1601EQ with QAP, 2307, 1604E)."""

from datetime import date

import pytest

from app.routers import bills as bills_router
from .test_invoices import TODAY, issued, ready
from .test_ledger import balances
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)

YEAR = date.today().year
QUARTER = (date.today().month - 1) // 3 + 1
SUPPLIERS = {
    "sup-abc": {"id": "sup-abc", "code": "ABC", "name": "ABC Medical Supply", "address": "Pasig City", "tin": "111-222-333-000", "vatStatus": "vat", "defaultAtc": "WC158"},
    "sup-joe": {"id": "sup-joe", "code": "JOE", "name": "Joe's Repairs", "address": "Makati", "tin": "444-555-666-000", "vatStatus": "non_vat", "defaultAtc": "WI160"},
}


@pytest.fixture(autouse=True)
def inventory(monkeypatch):
    """Inventory's suppliers, without Inventory."""
    def read(_settings, supplier_id):
        if supplier_id not in SUPPLIERS:
            raise bills_router.InventoryUnavailable("Inventory has no such supplier.")
        return SUPPLIERS[supplier_id]

    monkeypatch.setattr(bills_router, "read_supplier", read)
    monkeypatch.setattr(bills_router, "find_suppliers", lambda _s, q=None: list(SUPPLIERS.values()))
    monkeypatch.setattr(bills_router, "supplier_deliveries", lambda _s, sid: [{"id": "r1", "number": "RCV-1", "lines": [], "totalCost": 100000}])


def account_id(client, who, code):
    return next(a["id"] for a in client.get("/finance/ledger/accounts", headers=who).json()["items"] if a["code"] == code)


def bill(client, who, **extra) -> dict:
    """1,120.00 of supplies with VAT in (1,000.00 + 120.00 VAT), 1% withheld (WC158): 1,110.00 to pay."""
    body = {
        "supplierId": "sup-abc", "supplierInvoiceNo": "SI-77", "billDate": TODAY, "termsDays": 30,
        "lines": [{"description": "Gloves, 10 boxes", "accountId": account_id(client, who, "6500"), "kind": "vatable", "amountCentavos": 112000}],
        "atc": "WC158", **extra,
    }
    r = client.post("/finance/bills", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_bill_works_out_its_vat_and_withholding_and_posts(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    b = bill(client, ben)
    assert (b["status"], b["totalCentavos"], b["inputTaxCentavos"], b["ewtCentavos"], b["payableCentavos"]) == ("draft", 112000, 12000, 1000, 111000)
    assert b["supplier"]["tin"] == "111-222-333-000" and b["ewtRateBp"] == 100  # the ATC's usual rate
    recorded = client.post(f"/finance/bills/{b['id']}/record", headers=ben)
    assert recorded.status_code == 200, recorded.text
    # The purchase, its input VAT, what ABC is owed, and the 1% held for the BIR.
    assert balances(client, ana) == {"6500": 100000, "1300": 12000, "2000": 111000, "2300": 1000}
    # Recorded, it's not changed; the same supplier invoice isn't recorded twice.
    assert client.put(f"/finance/bills/{b['id']}", json={"supplierId": "sup-abc", "supplierInvoiceNo": "X", "billDate": TODAY, "lines": [{"description": "x", "accountId": account_id(client, ben, "6500"), "amountCentavos": 1}]}, headers=ben).status_code == 409
    again = client.post("/finance/bills", json={"supplierId": "sup-abc", "supplierInvoiceNo": "si-77", "billDate": TODAY, "lines": [{"description": "x", "accountId": account_id(client, ben, "6500"), "amountCentavos": 1}]}, headers=ben)
    assert again.status_code == 422 and "already recorded" in again.text


def test_paying_and_what_is_owed(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    b = client.post(f"/finance/bills/{bill(client, ben)['id']}/record", headers=ben).json()
    owed = client.get("/finance/bills/payables", headers=ben).json()
    assert owed["totals"]["owedCentavos"] == 111000 and owed["items"][0]["supplier"]["name"] == "ABC Medical Supply"
    pay = lambda amount: client.post(f"/finance/bills/{b['id']}/payments", json={"paidOn": TODAY, "amountCentavos": amount, "method": "bank"}, headers=ben)  # noqa: E731
    assert pay(200000).status_code == 422
    paid = pay(111000).json()
    assert paid["balanceCentavos"] == 0
    assert balances(client, ana)["2000"] == 0 and balances(client, ana)["1010"] == -111000
    # Paid, it can't be voided until the payment is taken off.
    assert client.post(f"/finance/bills/{b['id']}/void", json={"reason": "Wrong supplier"}, headers=ana).status_code == 409


def test_a_non_vat_supplier_has_no_input_vat(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    lines = [{"description": "Aircon repair", "accountId": account_id(client, ben, "6900"), "kind": "vatable", "amountCentavos": 50000}]
    r = client.post("/finance/bills", json={"supplierId": "sup-joe", "supplierInvoiceNo": "OR-5", "billDate": TODAY, "lines": lines}, headers=ben)
    assert r.status_code == 422 and "VAT-registered" in r.text
    ok = client.post("/finance/bills", json={"supplierId": "sup-joe", "supplierInvoiceNo": "OR-5", "billDate": TODAY, "lines": [{**lines[0], "kind": "non_vat"}], "atc": "WI160"}, headers=ben).json()
    assert (ok["inputTaxCentavos"], ok["ewtCentavos"], ok["payableCentavos"]) == (0, 1000, 49000)  # 2% of 500.00


def test_the_bir_purchase_side(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    issued(client, ana)  # a sale of 2,240.00: 240.00 output VAT
    b = client.post(f"/finance/bills/{bill(client, ben)['id']}/record", headers=ben).json()
    pj = client.get("/finance/bir/books/purchase-journal", headers=ben).json()
    assert (pj["totals"]["vatableCentavos"], pj["totals"]["inputTaxCentavos"], pj["totals"]["ewtCentavos"]) == (100000, 12000, 1000)
    vat = {line["key"]: line["amountCentavos"] for line in client.get(f"/finance/bir/returns/vat?year={YEAR}&quarter={QUARTER}", headers=ben).json()["lines"]}
    assert (vat["output"], vat["input"], vat["payable"]) == (24000, 12000, 12000)
    slp = client.get(f"/finance/bir/lists/slp?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    assert [(r["tin"], r["taxableCentavos"], r["inputTaxCentavos"]) for r in slp["rows"]] == [("111-222-333-000", 100000, 12000)]
    qap = client.get(f"/finance/bir/lists/qap?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    assert [(r["payee"], r["atc"], r["baseCentavos"], r["taxCentavos"]) for r in qap["rows"]] == [("ABC Medical Supply", "WC158", 100000, 1000)]
    eq = client.get(f"/finance/bir/withholding/1601eq?year={YEAR}&quarter={QUARTER}", headers=ben).json()
    assert eq["totalCentavos"] == 1000 and len(eq["remitted"]) == 2
    month = client.get(f"/finance/bir/withholding/0619e?year={YEAR}&month={date.today().month}", headers=ben).json()
    assert month["totalCentavos"] == 1000
    cert = client.get(f"/finance/bir/withholding/2307?year={YEAR}&quarter={QUARTER}&supplierId=sup-abc", headers=ben).json()
    assert [s["name"] for s in cert["suppliers"]] == ["ABC Medical Supply"]
    row = cert["certificate"]["rows"][0]
    assert (row["atc"], sum(row["months"]), row["taxCentavos"]) == ("WC158", 100000, 1000)
    annual = client.get(f"/finance/bir/withholding/1604e?year={YEAR}", headers=ben).json()
    assert annual["totals"] == {"baseCentavos": 100000, "taxCentavos": 1000}
    assert "WC158" in client.get(f"/finance/bir/withholding/1604e?year={YEAR}&format=csv", headers=ben).text
    # Voided, it leaves the lists.
    client.post(f"/finance/bills/{b['id']}/void", json={"reason": "Entered twice"}, headers=ana)
    assert client.get(f"/finance/bir/lists/qap?year={YEAR}&quarter={QUARTER}", headers=ben).json()["rows"] == []


def test_suppliers_come_from_inventory(client, ana, ben):  # noqa: F811 (fixtures)
    assert [s["code"] for s in client.get("/finance/bills/suppliers", headers=ben).json()["items"]] == ["ABC", "JOE"]
    setup = client.get("/finance/bills/setup", headers=ben).json()
    assert {"code": "WC158", "nature": "Purchases of goods by top withholding agents, corporate supplier", "rateBp": 100} in setup["atcs"]
    gone = client.post("/finance/bills", json={"supplierId": "nobody", "supplierInvoiceNo": "1", "billDate": TODAY, "lines": [{"description": "x", "accountId": account_id(client, ben, "6500"), "amountCentavos": 1}]}, headers=ben)
    assert gone.status_code == 503
