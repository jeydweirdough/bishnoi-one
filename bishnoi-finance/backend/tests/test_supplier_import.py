"""Importing suppliers from Zoho's vendor export (2026-10-23): each row checked first (new,
already here, or needing a look), Zoho's Company ID as the TIN when it is one, terms as days,
inactive vendors switched off, and the chosen rows added all or none. Made-up vendors."""

from .test_dashboard import VIEW, person
from .test_payables import SUPPLIER, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

ROWS = [
    {"name": "Sample Printing", "companyName": "Sample Printing Services Inc.", "email": "printing@example.com", "terms": "Net 15", "companyId": "123-456-789-000"},
    {"name": "Sample Kitchen", "companyName": "Sample Kitchen Corporation", "companyId": "SEC-CS2019-001", "terms": "Due on Receipt", "currency": "USD"},
    {"name": "Old Vendor", "status": "Inactive"},
    {"name": "Sample Pharma Distribution Inc."},  # already in Finance (by name)
    {"companyName": "Only A Company Name"},
    {"name": "SAMPLE PRINTING"},  # the same as line 1
    {"name": ""},
]


def test_each_vendor_is_checked_before_anything_is_added(client, ana):
    supplier(client, ana)
    out = client.post("/finance/suppliers/import/check", json={"rows": ROWS}, headers=ana)
    assert out.status_code == 200, out.text
    rows = out.json()["rows"]
    printing, kitchen, old, sample_pharma, company_only, twin, blank = rows
    assert printing["status"] == "new" and (printing["supplier"]["tin"], printing["supplier"]["branchCode"], printing["supplier"]["termsDays"]) == ("123-456-789", "000", 15)
    assert kitchen["supplier"]["tin"] is None and "Company ID in Zoho: SEC-CS2019-001" in kitchen["supplier"]["notes"]
    assert kitchen["supplier"]["termsDays"] == 0 and "pesos only" in kitchen["note"]
    assert old["supplier"]["isActive"] is False and "switched off" in old["note"]
    assert sample_pharma["status"] == "here" and "Already in Finance" in sample_pharma["note"]
    assert company_only["supplier"]["name"] == "Only A Company Name"
    assert twin["status"] == "problem" and "line 1" in twin["note"]
    assert blank["status"] == "problem"
    assert out.json()["counts"] == {"new": 4, "here": 1, "problem": 2}
    assert len(client.get("/finance/suppliers", headers=ana).json()["items"]) == 1  # checking adds nothing


def test_the_chosen_vendors_are_added_all_or_none(client, ana):
    rows = client.post("/finance/suppliers/import/check", json={"rows": ROWS[:3]}, headers=ana).json()["rows"]
    chosen = [r["supplier"] for r in rows]
    adder = person(client, ana, "Adds suppliers", VIEW + ["suppliers.view", "suppliers.add"])
    viewer = person(client, ana, "Sees suppliers", VIEW + ["suppliers.view"])
    assert client.post("/finance/suppliers/import", json={"suppliers": chosen}, headers=viewer).status_code == 403
    done = client.post("/finance/suppliers/import", json={"suppliers": chosen}, headers=adder)
    assert done.status_code == 201 and done.json() == {"added": 3}
    listed = {s["name"]: s for s in client.get("/finance/suppliers", headers=ana).json()["items"]}
    assert listed["Old Vendor"]["isActive"] is False and listed["Sample Printing"]["email"] == "printing@example.com"
    # One already here refuses the lot, naming its line.
    again = client.post("/finance/suppliers/import", json={"suppliers": [{"name": "Brand New Co."}, chosen[0]]}, headers=ana)
    assert again.status_code == 409 and again.json()["detail"].startswith("Line 2 (Sample Printing)")
    assert "Brand New Co." not in {s["name"] for s in client.get("/finance/suppliers", headers=ana).json()["items"]}


def test_two_rows_for_one_supplier_in_the_same_import_are_refused(client, ana):
    same = [{"name": "Twin Supply"}, {"name": "TWIN SUPPLY", "tin": None}]
    out = client.post("/finance/suppliers/import", json={"suppliers": same}, headers=ana)
    assert out.status_code == 409 and "Line 2" in out.json()["detail"]
    assert client.get("/finance/suppliers", headers=ana).json()["items"] == []
    assert SUPPLIER  # the shared made-up supplier stays as it is for the other tests
