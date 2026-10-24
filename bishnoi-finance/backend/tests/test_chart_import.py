"""Importing a chart of accounts (2026-10-23): each row checked first (new, already here,
or needing a look), the type from Oojeema's class, parents by name, and the chosen rows
added all or none. Rows like Oojeema's own (made up where they'd be sensitive)."""

from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

ROWS = [
    {"code": "6915-000", "name": "Loss on Expired Medicines", "kind": "Other Expenses", "nature": "Debit", "statement": "Income Statement"},
    {"code": "6915-001", "name": "Provision for Expired Medicines", "kind": "Other Expenses", "nature": "Debit", "parent": "Loss on Expired Medicines"},
    {"code": "2334-000", "name": "Final VAT Withholding Payable", "kind": "Current Liabilities", "nature": "Credit", "parent": "Taxes & Government Contributions"},
    {"code": "7002-000", "name": "Packaging Charges", "kind": "Other Income", "nature": "Credit"},
    {"code": "1000", "name": "Cash on hand (already here)", "kind": "Cash"},
    {"code": "9999-000", "name": "Something", "kind": "Mystery", "statement": "Balance Sheet"},
    {"code": "", "name": "No code"},
]


def test_each_row_is_checked_before_anything_is_added(client, ana):
    out = client.post("/finance/ledger/accounts/import/check", json={"rows": ROWS}, headers=ana)
    assert out.status_code == 200, out.text
    rows = {r["code"] or r["name"]: r for r in out.json()["rows"]}
    assert rows["6915-000"]["status"] == "new" and rows["6915-000"]["type"] == "expense"
    assert rows["6915-001"]["parentFound"] == "file"
    assert rows["2334-000"]["type"] == "liability" and "imported without one" in rows["2334-000"]["note"]
    assert rows["7002-000"]["type"] == "income"
    assert rows["1000"]["status"] == "here" and "Cash on hand" in rows["1000"]["note"]
    assert rows["9999-000"]["status"] == "problem" and "pick one" in rows["9999-000"]["note"]
    assert rows["No code"]["status"] == "problem"
    assert out.json()["counts"] == {"new": 4, "here": 1, "problem": 2}
    # Checking adds nothing.
    assert not any(a["code"] == "6915-000" for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"])


def test_the_chosen_rows_are_added_with_their_parents_all_or_none(client, ana, ben):
    chosen = [
        {"code": "6915-001", "name": "Provision for Expired Medicines", "type": "expense", "parent": "Loss on Expired Medicines"},
        {"code": "6915-000", "name": "Loss on Expired Medicines", "type": "expense"},
        {"code": "2334-000", "name": "Final VAT Withholding Payable", "type": "liability", "parent": "Taxes & Government Contributions"},
    ]
    assert client.post("/finance/ledger/accounts/import", json={"accounts": chosen}, headers=ben).status_code == 403  # the chart is the setup's
    done = client.post("/finance/ledger/accounts/import", json={"accounts": chosen}, headers=ana)
    assert done.status_code == 201 and done.json() == {"added": 3, "withParent": 1}
    chart = {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    assert chart["6915-001"]["parentId"] == chart["6915-000"]["id"] and chart["2334-000"]["parentId"] is None
    # A code already used refuses the lot.
    again = client.post("/finance/ledger/accounts/import", json={"accounts": [{"code": "7002-000", "name": "Packaging Charges", "type": "income"}, chosen[0]]}, headers=ana)
    assert again.status_code == 409 and "6915-001" in again.json()["detail"]
    assert "7002-000" not in {a["code"] for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}


def test_an_account_cant_sit_under_itself(client, ana):
    chart = {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    cash = chart["1000"]
    body = {"code": "1000", "name": cash["name"], "type": "asset", "parentId": cash["id"]}
    assert client.put(f"/finance/ledger/accounts/{cash['id']}", json=body, headers=ana).status_code == 422
    under = client.put(f"/finance/ledger/accounts/{chart['1010']['id']}", json={"code": "1010", "name": chart["1010"]["name"], "type": "asset", "parentId": cash["id"]}, headers=ana)
    assert under.status_code == 200 and under.json()["parentId"] == cash["id"]
