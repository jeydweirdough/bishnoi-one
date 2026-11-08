"""Petty cash (2026-10-30, Plans/Plan - Petty cash and receipts): a voucher with its receipts, every receipt
attached before it's submitted, checked and posted by someone who didn't make it, voided with a reversal,
and its receipts in the BIR purchase lists like bill lines."""

import base64
from datetime import date

from app import bir_reports as bir
from app.bir_readiness import readiness
from app.models import Account, JournalEntry
from zoneinfo import ZoneInfo

from .test_dashboard import VIEW, person
from .test_ledger import balances
from .test_payables import account
from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_tax_api import ana, ben, client  # noqa: F401 (fixtures)

RECEIPT = {"name": "receipt.pdf", "contentType": "application/pdf", "data": base64.b64encode(b"%PDF-1.4 store receipt").decode()}
MAKER = VIEW + ["petty_cash.view", "petty_cash.create"]
CHECKER = VIEW + ["petty_cash.view", "petty_cash.check"]


def fund(app) -> str:
    """A petty cash fund under CASH, as in the company's chart."""
    with app.state.sessions() as db:
        cash = Account(code="1100-T", name="CASH", type="asset")
        db.add(cash)
        db.flush()
        f = Account(code="1110-T", name="Petty Cash Fund - Finance", type="asset", parent_id=cash.id)
        db.add(f)
        db.commit()
        return f.id


def line(client, who, **extra) -> dict:
    return {"spentOn": "2026-10-05", "store": "Corner Hardware", "storeTin": "123-456-789-00000", "receiptNumber": "OR 1001",
            "accountId": account(client, who, "6500"), "description": "Cleaning materials", "purchaseType": "other_goods",
            "vat": "vat", "withholding": None, "amountCentavos": 112_000} | extra


def voucher(client, who, fund_id, number="2MG PCV 01682", lines=None) -> dict:
    body = {"number": number, "fundAccountId": fund_id, "voucherDate": "2026-10-06", "personInCharge": "Aubrey", "department": "Finance",
            "lines": lines or [line(client, who)]}
    r = client.post("/finance/petty-cash", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def attach_all(client, who, v) -> dict:
    for ln in v["lines"]:
        r = client.post(f"/finance/petty-cash/{v['id']}/lines/{ln['id']}/file", json=RECEIPT, headers=who)
        assert r.status_code == 201, r.text
    return r.json()


def test_a_voucher_needs_every_receipt_and_someone_else_checks_and_posts_it(app, client, ana):
    f = fund(app)
    aubrey = person(client, ana, "Aubrey Petty", MAKER)
    cristal = person(client, ana, "Cristal Petty", CHECKER)
    v = voucher(client, aubrey, f, lines=[line(client, aubrey), line(client, aubrey, receiptNumber="OR 1002", amountCentavos=50_000, vat="none")])
    assert v["status"] == "draft" and v["missingReceipts"] == 2 and not v["canSubmit"]
    # VAT taken out of the VAT-inclusive receipt; none on the non-VAT store's.
    assert (v["netCentavos"], v["vatCentavos"], v["totalCentavos"]) == (100_000 + 50_000, 12_000, 162_000)
    refused = client.post(f"/finance/petty-cash/{v['id']}/submit", headers=aubrey)
    assert refused.status_code == 409 and "Attach the receipt for line 1, 2" in refused.text
    v = attach_all(client, aubrey, v)
    assert v["missingReceipts"] == 0 and v["canSubmit"]
    opened = client.get(f"/finance/petty-cash/{v['id']}/lines/{v['lines'][0]['id']}/file", headers=cristal)
    assert opened.status_code == 200 and opened.content.startswith(b"%PDF")
    v = client.post(f"/finance/petty-cash/{v['id']}/submit", headers=aubrey).json()
    assert v["status"] == "to_check" and not v["canEdit"]
    # The maker never checks it, even with the permission.
    both = person(client, ana, "Maker Checker", MAKER + ["petty_cash.check"])
    own = voucher(client, both, f, number="2MG PCV 01683")
    attach_all(client, both, own)
    client.post(f"/finance/petty-cash/{own['id']}/submit", headers=both)
    assert client.post(f"/finance/petty-cash/{own['id']}/check", headers=both).status_code == 403
    listed = client.get("/finance/petty-cash?show=to_check", headers=cristal).json()
    assert listed["counts"]["to_check"] == 2 and listed["waitingForYou"] == 2
    assert client.get("/finance/petty-cash", headers=aubrey).json()["waitingOnOthers"] == 1
    before = balances(client, ana)
    v = client.post(f"/finance/petty-cash/{v['id']}/check", headers=cristal).json()
    assert v["status"] == "posted" and v["checkedBy"] == "Cristal Petty" and v["entryId"]
    with app.state.sessions() as db:
        e = db.get(JournalEntry, v["entryId"])
        assert e.source == "petty_cash" and e.entry_date == date(2026, 10, 6)
        legs = {(ln.account.code, ln.debit_centavos, ln.credit_centavos) for ln in e.lines}
        assert ("1110-T", 0, 162_000) in legs and ("6500", 100_000, 0) in legs and ("6500", 50_000, 0) in legs
        assert sum(ln.debit_centavos for ln in e.lines) == sum(ln.credit_centavos for ln in e.lines) == 162_000
    assert balances(client, ana) != before
    signed = client.get(f"/finance/signatures/petty_cash/{v['id']}", headers=cristal).json()["steps"]
    assert [s["step"] for s in signed] == ["prepared", "checked"]


def test_returned_vouchers_are_corrected_and_voids_reverse_the_entry(app, client, ana):
    f = fund(app)
    aubrey = person(client, ana, "Aubrey Return", MAKER)
    malou = person(client, ana, "Malou Return", CHECKER + ["petty_cash.void"])
    v = attach_all(client, aubrey, voucher(client, aubrey, f))
    client.post(f"/finance/petty-cash/{v['id']}/submit", headers=aubrey)
    v = client.post(f"/finance/petty-cash/{v['id']}/return", json={"reason": "The receipt is for October 4"}, headers=malou).json()
    assert v["status"] == "returned" and v["events"][-1]["text"] == "The receipt is for October 4"
    fixed = [line(client, aubrey, id=v["lines"][0]["id"], spentOn="2026-10-04")]
    r = client.put(f"/finance/petty-cash/{v['id']}", json={"number": v["number"], "fundAccountId": f, "voucherDate": "2026-10-06", "lines": fixed}, headers=aubrey)
    assert r.status_code == 200 and r.json()["lines"][0]["file"]  # the corrected line keeps its receipt
    client.post(f"/finance/petty-cash/{v['id']}/submit", headers=aubrey)
    v = client.post(f"/finance/petty-cash/{v['id']}/check", headers=malou).json()
    assert client.post(f"/finance/petty-cash/{v['id']}/void", json={"reason": "Entered twice"}, headers=aubrey).status_code == 403
    v = client.post(f"/finance/petty-cash/{v['id']}/void", json={"reason": "Entered twice"}, headers=malou).json()
    assert v["status"] == "void"
    with app.state.sessions() as db:
        assert db.get(JournalEntry, v["entryId"]).reversed_by_id
    # A voided voucher's number can be used again.
    assert voucher(client, aubrey, f)["number"] == "2MG PCV 01682"


def test_the_same_number_once_no_receipt_no_entry_and_only_petty_cash_funds(app, client, ana):
    f = fund(app)
    aubrey = person(client, ana, "Aubrey Rules", MAKER)
    voucher(client, aubrey, f)
    body = {"number": "2mg  pcv 01682", "fundAccountId": f, "voucherDate": "2026-10-06", "lines": [line(client, aubrey)]}
    twin = client.post("/finance/petty-cash", json=body, headers=aubrey)
    assert twin.status_code == 422 and "already here" in twin.text
    no_or = client.post("/finance/petty-cash", json=body | {"number": "X1", "lines": [line(client, aubrey, receiptNumber="")]}, headers=aubrey)
    assert no_or.status_code == 422
    bank = account(client, ana, "1010") if any(a["code"] == "1010" for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]) else None
    if bank:
        assert client.post("/finance/petty-cash", json=body | {"number": "X2", "fundAccountId": bank}, headers=aubrey).status_code == 422
    late = client.post("/finance/petty-cash", json=body | {"number": "X3", "lines": [line(client, aubrey, spentOn="2026-10-07")]}, headers=aubrey)
    assert late.status_code == 422 and "after its voucher" in late.text
    bad_tin = client.post("/finance/petty-cash", json=body | {"number": "X4", "lines": [line(client, aubrey, storeTin="12345")]}, headers=aubrey)
    assert bad_tin.status_code == 422
    viewer = person(client, ana, "Views Petty", VIEW + ["petty_cash.view"])
    assert client.post("/finance/petty-cash", json=body | {"number": "X5"}, headers=viewer).status_code == 403
    assert client.get("/finance/petty-cash", headers=person(client, ana, "No Petty", VIEW)).status_code == 403


def test_posted_receipts_reach_the_purchase_lists_and_readiness_agrees(app, client, ana):
    f = fund(app)
    aubrey = person(client, ana, "Aubrey BIR", MAKER)
    cristal = person(client, ana, "Cristal BIR", CHECKER)
    lines = [line(client, aubrey, purchaseType="services", withholding="WI160", store="Juan Dela Cruz Services", storeTin="111-222-333"),
             line(client, aubrey, receiptNumber="OR 2", amountCentavos=56_000)]
    v = attach_all(client, aubrey, voucher(client, aubrey, f, lines=lines))
    client.post(f"/finance/petty-cash/{v['id']}/submit", headers=aubrey)
    draft_only = voucher(client, aubrey, f, number="DRAFT 1")  # never posted: not in any list
    v = client.post(f"/finance/petty-cash/{v['id']}/check", headers=cristal).json()
    assert v["withheldCentavos"] == 2_000 and v["paidOutCentavos"] == v["totalCentavos"] - 2_000
    with app.state.sessions() as db:
        pj = bir.purchase_journal(db, date(2026, 10, 1), date(2026, 10, 31))
        rows = [r for r in pj["rows"] if r["source"] == "petty_cash"]
        assert len(rows) == 2 and {r["supplierInvoiceNo"] for r in rows} == {"OR 1001", "OR 2"}
        assert all(r["no"] != draft_only["number"] for r in pj["rows"])
        p = bir.quarter(2026, 4)
        slp = {r["name"]: r for r in bir.slp(db, p)["rows"]}
        assert slp["Juan Dela Cruz Services"]["servicesCentavos"] == 100_000 and slp["Juan Dela Cruz Services"]["tin"] == "111-222-333"
        qap = bir.qap(db, p)["rows"]
        assert [(r["payee"], r["atc"], r["taxCentavos"]) for r in qap] == [("Juan Dela Cruz Services", "WI160", 2_000)]
        payee = bir.withheld_suppliers(db, p)[0]
        assert payee["id"] == "store:111-222-333"
        cert = bir.form_2307(db, p, payee["id"])
        assert cert["payee"]["name"] == "Juan Dela Cruz Services" and cert["totals"]["taxCentavos"] == 2_000
        checks = {c["key"]: c for c in readiness(db, date(2026, 10, 1), date(2026, 10, 31), ZoneInfo("Asia/Manila"))["checks"]}
        for key in ("input_vat", "ewt"):
            if checks[key]["status"] != "not_set":
                assert checks[key]["status"] == "agrees", checks[key]
        assert {checks[k]["status"] for k in ("input_vat", "ewt")} == {"agrees"}  # both accounts are set in the test chart
