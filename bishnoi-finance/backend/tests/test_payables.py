"""Suppliers and their bills (built 2026-10-23 from Aubrey's answers): the usual tax withheld
filled in, VAT and withholding worked out, recorded straight into the books, voided rather
than changed, no supplier or bill twice, and the supplier's invoice attached."""

import base64

from .test_dashboard import VIEW, person
from .test_ledger import balances
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

PDF = base64.b64encode(b"%PDF-1.4 the supplier's invoice").decode()
SUPPLIER = {"name": "Sample Pharma Distribution Inc.", "tin": "123456789", "address": "Mandaluyong", "vatRegistered": True, "withholding": "WC158", "termsDays": 30}


def account(client, who, code: str) -> str:
    return next(a["id"] for a in client.get("/finance/ledger/accounts", headers=who).json()["items"] if a["code"] == code)


def supplier(client, who, **extra) -> dict:
    r = client.post("/finance/suppliers", json=SUPPLIER | extra, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def bill(client, who, supplier_id: str, amount=1_120_000, number="SI-0001", **extra) -> dict:
    line = {"accountId": account(client, who, "6500"), "description": "Packaging materials", "amountCentavos": amount, "vat": "vat", "withholding": "WC158"}
    body = {"supplierId": supplier_id, "billNumber": number, "billDate": "2026-10-01", "lines": [line]} | extra
    r = client.post("/finance/bills", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_suppliers_keep_their_usual_withholding_and_are_never_twice(client, ben):
    s = supplier(client, ben)
    assert (s["tin"], s["branchCode"], s["withholding"]["code"], s["withholding"]["rateBp"]) == ("123-456-789", "00000", "WC158", 100)
    twin = client.post("/finance/suppliers", json=SUPPLIER | {"name": "Sample Pharma (other spelling)"}, headers=ben)
    assert twin.status_code == 422 and "Sample Pharma Distribution Inc. already has this TIN" in twin.text
    same_name = client.post("/finance/suppliers", json=SUPPLIER | {"tin": None, "name": "sample pharma distribution inc."}, headers=ben)
    assert same_name.status_code == 422 and "already a supplier called" in same_name.text
    unknown = client.post("/finance/suppliers", json=SUPPLIER | {"name": "X", "tin": None, "withholding": "WX999"}, headers=ben)
    assert unknown.status_code == 422


def test_a_bill_takes_vat_out_withholds_on_the_rest_and_posts_when_recorded(client, ana, ben):
    s = supplier(client, ben)
    b = bill(client, ben, s["id"])
    # ₱11,200 with VAT: ₱10,000 and ₱1,200 VAT; 1% of ₱10,000 withheld; ₱11,100 to pay.
    assert (b["status"], b["netCentavos"], b["vatCentavos"], b["withheldCentavos"], b["payableCentavos"]) == ("draft", 1_000_000, 120_000, 10_000, 1_110_000)
    assert b["dueDate"] == "2026-10-31" and b["documentMissing"] is True
    assert balances(client, ana) == {}  # a draft posts nothing
    recorded = client.post(f"/finance/bills/{b['id']}/record", headers=ben)
    assert recorded.status_code == 200, recorded.text
    assert recorded.json()["status"] == "recorded" and recorded.json()["recordedBy"] == "Ben Cruz"
    # Counts at once (no approval wait): the expense and input VAT, against payables and EWT payable.
    assert balances(client, ana) == {"6500": 1_000_000, "1300": 120_000, "2000": 1_110_000, "2300": 10_000}
    entries = client.get("/finance/ledger/entries?source=bill", headers=ana).json()["items"]
    assert len(entries) == 1 and entries[0]["status"] == "approved"
    # Recorded, it's never changed or deleted, nor recorded twice.
    line = {"accountId": account(client, ben, "6500"), "amountCentavos": 100}
    assert client.put(f"/finance/bills/{b['id']}", json={"supplierId": s["id"], "billNumber": "X", "billDate": "2026-10-01", "lines": [line]}, headers=ben).status_code == 409
    assert client.delete(f"/finance/bills/{b['id']}", headers=ben).status_code == 409
    assert client.post(f"/finance/bills/{b['id']}/record", headers=ben).status_code == 409


def test_amounts_without_vat_add_it_and_a_non_vat_line_has_none(client, ben):
    s = supplier(client, ben)
    b = bill(client, ben, s["id"], amount=1_000_000, amountsIncludeVat=False)
    assert (b["netCentavos"], b["vatCentavos"], b["totalCentavos"]) == (1_000_000, 120_000, 1_120_000)
    plain = {"accountId": account(client, ben, "6500"), "amountCentavos": 500_000, "vat": "none"}
    r = client.post("/finance/bills", json={"supplierId": s["id"], "billNumber": "SI-0002", "billDate": "2026-10-01", "lines": [plain]}, headers=ben).json()
    assert (r["vatCentavos"], r["withheldCentavos"], r["payableCentavos"]) == (0, 0, 500_000)


def test_the_same_invoice_from_a_supplier_is_entered_once_and_voiding_frees_it(client, ana, ben):
    s = supplier(client, ben)
    first = bill(client, ben, s["id"])
    twice = client.post("/finance/bills", json={"supplierId": s["id"], "billNumber": "si-0001", "billDate": "2026-10-01",
                                                  "lines": [{"accountId": account(client, ben, "6500"), "amountCentavos": 100}]}, headers=ben)
    assert twice.status_code == 422 and f"bill {first['no']}" in twice.text
    client.post(f"/finance/bills/{first['id']}/record", headers=ben)
    # Ben (Finance Staff) records bills but doesn't void them; Ana does, with a reason.
    assert client.post(f"/finance/bills/{first['id']}/void", json={"reason": "Wrong amount"}, headers=ben).status_code == 403
    voided = client.post(f"/finance/bills/{first['id']}/void", json={"reason": "Wrong amount"}, headers=ana)
    assert voided.status_code == 200 and voided.json()["status"] == "void" and voided.json()["voidReason"] == "Wrong amount"
    assert set(balances(client, ana).values()) == {0}  # reversed in full
    bill(client, ben, s["id"])  # entered again, corrected


def test_the_suppliers_invoice_is_attached_opened_and_removed(client, ana, ben):
    s = supplier(client, ben)
    b = bill(client, ben, s["id"])
    added = client.post(f"/finance/bills/{b['id']}/files", json={"name": "SI-0001.pdf", "contentType": "application/pdf", "data": PDF}, headers=ben)
    assert added.status_code == 201, added.text
    f = added.json()["files"][0]
    assert added.json()["documentMissing"] is False and f["name"] == "SI-0001.pdf" and f["uploadedBy"] == "Ben Cruz"
    opened = client.get(f"/finance/bills/{b['id']}/files/{f['id']}", headers=ana)
    assert opened.status_code == 200 and opened.content.startswith(b"%PDF") and opened.headers["content-type"] == "application/pdf"
    assert client.get("/finance/bills?missing=true", headers=ana).json()["items"] == []
    wrong = client.post(f"/finance/bills/{b['id']}/files", json={"name": "a.exe", "contentType": "application/x-msdownload", "data": PDF}, headers=ben)
    assert wrong.status_code == 422
    big = base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode()
    assert client.post(f"/finance/bills/{b['id']}/files", json={"name": "big.pdf", "contentType": "application/pdf", "data": big}, headers=ben).status_code == 422
    removed = client.delete(f"/finance/bills/{b['id']}/files/{f['id']}", headers=ben)
    assert removed.status_code == 200 and removed.json()["documentMissing"] is True


def test_bills_are_ticks_any_role_can_have(client, ana):
    # Like Ms. Cristal's, who sometimes makes bills (you, 2026-10-23); each step its own tick (split 2026-10-23).
    viewer = person(client, ana, "Looks only", VIEW + ["bills.view", "suppliers.view"])
    drafter = person(client, ana, "Drafts bills", VIEW + ["bills.view", "bills.create", "suppliers.view"])
    s = supplier(client, ana)
    assert client.post("/finance/bills", json={"supplierId": s["id"], "billNumber": "1", "billDate": "2026-10-01", "lines": []}, headers=viewer).status_code == 403
    b = bill(client, drafter, s["id"])
    assert client.post(f"/finance/bills/{b['id']}/files", json={"name": "a.pdf", "contentType": "application/pdf", "data": PDF}, headers=drafter).status_code == 201
    assert client.post(f"/finance/bills/{b['id']}/record", headers=drafter).status_code == 403  # drafts, but doesn't post
    assert client.post("/finance/suppliers", json=SUPPLIER | {"name": "Y", "tin": None}, headers=drafter).status_code == 403
    catalogue = client.get("/admin/roles", headers=ana).json()
    labels = {a["key"]: [x["label"] for x in a["actions"]] for a in catalogue["catalogue"]}
    assert labels["bills"] == ["View", "Make drafts", "Record (post to the books)", "Void"]
    assert labels["suppliers"] == ["View", "Add", "Edit", "Switch off"]


def test_a_supplier_has_zohos_details_and_its_own_payables_account(client, ana, ben):
    trade = client.post("/finance/ledger/accounts", json={"code": "2101-000", "name": "Accounts Payable - Trade", "type": "liability"}, headers=ana).json()
    s = supplier(client, ben, companyName="Sample Pharma Distribution Incorporated", salutation="Ms.", firstName="Ana", lastName="Lim", mobile="0917 000 0000",
                 payablesAccountId=trade["id"], contacts=[{"firstName": "Jo", "lastName": "Tan", "designation": "Billing", "email": "jo@example.com"}, {}])
    assert (s["companyName"], s["firstName"], s["mobile"], s["payablesAccount"]["code"]) == ("Sample Pharma Distribution Incorporated", "Ana", "0917 000 0000", "2101-000")
    assert s["contacts"] == [{"salutation": None, "firstName": "Jo", "lastName": "Tan", "email": "jo@example.com", "phone": None, "mobile": None, "designation": "Billing"}]
    expense = client.post("/finance/suppliers", json=SUPPLIER | {"name": "X", "tin": None, "payablesAccountId": account(client, ana, "6500")}, headers=ben)
    assert expense.status_code == 422  # a payables account is a liability
    b = bill(client, ben, s["id"])
    client.post(f"/finance/bills/{b['id']}/record", headers=ben)
    # Its bills post to its own payables account, and the list says what's owed it.
    assert balances(client, ana)["2101-000"] == 1_110_000 and "2000" not in balances(client, ana)
    listed = next(x for x in client.get("/finance/suppliers", headers=ben).json()["items"] if x["id"] == s["id"])
    assert listed["owedCentavos"] == 1_110_000


def test_switching_off_is_its_own_tick_and_documents_go_with_edit(client, ana):
    editor = person(client, ana, "Edits suppliers", VIEW + ["suppliers.view", "suppliers.edit"])
    s = supplier(client, ana)
    assert client.post(f"/finance/suppliers/{s['id']}/active", json={"isActive": False}, headers=editor).status_code == 403
    off = client.post(f"/finance/suppliers/{s['id']}/active", json={"isActive": False}, headers=ana)
    assert off.status_code == 200 and off.json()["isActive"] is False
    assert all(x["id"] != s["id"] for x in client.get("/finance/bills/choices", headers=ana).json()["suppliers"])  # not offered on new bills
    doc = client.post(f"/finance/suppliers/{s['id']}/files", json={"name": "BIR 2303.pdf", "contentType": "application/pdf", "data": PDF}, headers=editor)
    assert doc.status_code == 201 and doc.json()["files"][0]["name"] == "BIR 2303.pdf"
    f = doc.json()["files"][0]
    assert client.get(f"/finance/suppliers/{s['id']}/files/{f['id']}", headers=ana).content.startswith(b"%PDF")
    assert client.delete(f"/finance/suppliers/{s['id']}/files/{f['id']}", headers=editor).json()["files"] == []
