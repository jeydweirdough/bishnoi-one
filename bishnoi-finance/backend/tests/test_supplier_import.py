"""Supplier CSV reviews and all-or-none writes, isolated fictional records only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from sqlalchemy import func, select
from app.models import Account, Bill, PaymentVoucher, JournalEntry
from .test_dashboard import VIEW, person
from .test_payables import account, supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401


def reviewed(name="Fictional Supply", **source):
    return {"name": name, "terms": "30", **source, "review": {"vatRegistered": False, "withholding": None, "taxConfirmed": True, "missingTinAccepted": True, "termsConfirmed": True}}


def preview(client, ana, rows):
    response = client.post("/finance/suppliers/import/check", json={"rows": rows, "mode": "review"}, headers=ana)
    assert response.status_code == 200, response.text
    return response.json()


def run(client, ana, rows, confirmed=True):
    return client.post("/finance/suppliers/import", json={"rows": rows, "confirmed": confirmed, "mode": "review"}, headers=ana)


def test_preview_requires_explicit_tax_and_missing_tin_choices_without_writes(client, ana):
    out = preview(client, ana, [{"name": "Example", "terms": "30", "taxName": "No Tax", "taxPercentage": "0", "taxable": "true", "trackTds": "true"}])
    row = out["rows"][0]
    assert row["status"] == "review" and row["supplier"]["vatRegistered"] is None
    assert row["supplier"]["withholding"] is None
    assert any("Missing TIN" in v for v in row["reviews"])
    assert run(client, ana, [{"name": "Example"}]).status_code == 409
    assert client.get("/finance/suppliers", headers=ana).json()["items"] == []
    assert client.post("/finance/suppliers/import", json={"suppliers": [{"name": "Bypass"}]}, headers=ana).status_code == 422


def test_tin_conflict_invalid_and_company_fallback(client, ana):
    row = reviewed(tinSources=[{"heading": "CF.TIN", "value": "123-456-789-000"}, {"heading": "TIN", "value": "98765432100000"}])
    assert preview(client, ana, [row])["rows"][0]["status"] == "review"
    row["review"].update(tin="123456789000", tinConfirmed=True)
    checked = preview(client, ana, [row])["rows"][0]
    assert checked["status"] == "new" and checked["supplier"]["branchCode"] == "000"
    row["review"]["tin"] = "12"
    assert preview(client, ana, [row])["rows"][0]["status"] == "problem"
    row["review"]["tin"] = None
    assert preview(client, ana, [row])["rows"][0]["status"] == "problem"
    explicit = reviewed(tin="bad", companyId="12345678900000")
    assert preview(client, ana, [explicit])["rows"][0]["status"] == "problem"
    legacy = preview(client, ana, [reviewed(companyId="SEC-EXAMPLE")])["rows"][0]
    assert legacy["supplier"]["tin"] is None and "Company ID in Zoho" in legacy["supplier"]["notes"]
    assert preview(client, ana, [reviewed(companyId="123456789")])["rows"][0]["supplier"]["branchCode"] == "00000"


def test_extra_numbers_labels_and_inactive_currency_survive(client, ana, app):
    row = reviewed(phone="02 8000 0000", mobile="09170000000", contactNumber="09990000000", billingPhone="02 8000 0000", termsLabel="Paid", status="Inactive", currency="USD", billingAttention="Example purchasing", website="https://example.invalid", designation="Purchasing")
    row["review"]["termsDays"] = 0
    value = preview(client, ana, [row])["rows"][0]["supplier"]
    assert value["contacts"] == [{"phone": "09990000000", "designation": "Zoho custom contact number"}]
    assert "Zoho terms: Paid" in value["notes"] and "Billing attention" in value["notes"]
    assert value["phone"] == "02 8000 0000" and value["mobile"] == "09170000000"
    assert not value["isActive"] and "pesos only" in value["notes"]
    assert run(client, ana, [row], False).status_code == 422
    assert run(client, ana, [row]).status_code == 201
    saved = client.get("/finance/suppliers", headers=ana).json()["items"][0]
    assert saved["vatRegistered"] is False and saved["withholding"] is None and saved["contacts"][0]["phone"] == "09990000000"
    with app.state.sessions() as db:
        for model in (Bill, PaymentVoucher, JournalEntry):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_overflow_and_bad_codes_are_never_silently_truncated(client, ana):
    for fields in ({"phone": "1"*41}, {"contactNumber": "1"*41}, {"notes": "x"*501}, {"address": "x"*301}, {"name": "x"*201}):
        row = reviewed(**fields)
        assert preview(client, ana, [row])["rows"][0]["status"] == "problem"
        assert run(client, ana, [row]).status_code == 409
    row = reviewed(notes="x"*500)
    assert preview(client, ana, [row])["rows"][0]["supplier"]["notes"] == "x"*500
    row["review"]["withholding"] = "WX999"
    assert run(client, ana, [row]).status_code == 409


def test_terms_shipping_and_accounts_require_resolution(client, ana):
    row = reviewed(terms="120", termsLabel="COD", shippingAddress="Test shipping address", accountsPayable="Unknown account")
    row["review"]["termsConfirmed"] = False
    result = preview(client, ana, [row])["rows"][0]
    assert len(result["reviews"]) == 3
    row["review"].update(termsDays=0, termsConfirmed=True, addressChoice="shipping", accountConfirmed=True)
    result = preview(client, ana, [row])["rows"][0]
    assert result["status"] == "new" and result["supplier"]["address"] == "Test shipping address"
    row["review"]["payablesAccountId"] = account(client, ana, "6500")
    assert preview(client, ana, [row])["rows"][0]["status"] == "problem"
    liability = client.get("/finance/suppliers", headers=ana).json()["payablesAccounts"][0]
    row["accountsPayable"] = liability["code"]
    row["review"]["payablesAccountId"] = liability["id"]
    result = preview(client, ana, [row])["rows"][0]
    assert result["accountMatches"][0]["id"] == liability["id"] and result["status"] == "new"
    assert run(client, ana, [row]).status_code == 201


def test_duplicates_existing_branch_and_all_or_none(client, ana):
    original = supplier(client, ana)
    good = reviewed("New fictional supplier", tin="99988877700000", record=12)
    same = reviewed("NEW FICTIONAL SUPPLIER", record=18)
    existing = reviewed(original["name"], record=20)
    rows = preview(client, ana, [good, same, existing])["rows"]
    assert [r["status"] for r in rows] == ["new", "duplicate", "here"]
    assert "record 12" in rows[1]["note"]
    assert run(client, ana, [good, existing]).status_code == 409
    assert len(client.get("/finance/suppliers", headers=ana).json()["items"]) == 1
    assert run(client, ana, [good]).status_code == 201
    assert run(client, ana, [good]).status_code == 409
    branch = reviewed("Separate example branch", tin="999888777000")
    assert preview(client, ana, [branch])["rows"][0]["status"] == "review"
    branch["review"]["branchConfirmed"] = True
    assert preview(client, ana, [branch])["rows"][0]["status"] == "new"


def test_import_permission_and_concurrent_identity_recheck(client, ana):
    viewer = person(client, ana, "Views vendors", VIEW + ["suppliers.view"])
    row = reviewed()
    assert run(client, viewer, [row]).status_code == 403
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: run(client, ana, [deepcopy(row)]).status_code, range(2)))
    assert sorted(outcomes) == [201, 409]
    assert len(client.get("/finance/suppliers", headers=ana).json()["items"]) == 1


def test_confirmed_tax_persists_and_stale_account_mapping_is_rejected(client, ana, app):
    row = reviewed("Confirmed tax example", tin="88877766600000")
    row["review"].update(vatRegistered=True, withholding="WC158")
    assert run(client, ana, [row]).status_code == 201
    saved = client.get("/finance/suppliers", headers=ana).json()["items"][0]
    assert saved["vatRegistered"] is True and saved["withholding"]["code"] == "WC158"
    liability = client.get("/finance/suppliers", headers=ana).json()["payablesAccounts"][0]
    other = reviewed("Stale account example", accountsPayable=liability["code"])
    other["review"].update(payablesAccountId=liability["id"], accountConfirmed=True)
    assert preview(client, ana, [other])["rows"][0]["status"] == "new"
    with app.state.sessions() as db:
        db.get(Account, liability["id"]).is_active = False
        db.commit()
    assert run(client, ana, [other]).status_code == 409
    assert len(client.get("/finance/suppliers", headers=ana).json()["items"]) == 1
