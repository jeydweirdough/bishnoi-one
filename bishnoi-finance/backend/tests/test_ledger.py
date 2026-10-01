"""The ledger: each fund step posts its balanced entry, manual journals and
reversals, and what the accounts add up to."""

from datetime import date

from .test_funds import KEY, approved, categories, release, spend
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def accounts(client, who) -> dict[str, dict]:
    return {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=who).json()["items"]}


def balances(client, who) -> dict[str, int]:
    tb = client.get("/finance/ledger/trial-balance", headers=who).json()
    assert tb["debitCentavos"] == tb["creditCentavos"]  # the books balance
    return {r["account"]["code"]: r["balanceCentavos"] for r in tb["rows"]}


def test_a_fund_posts_at_each_step_and_advances_clear(client, ben):
    req = release(client, ben, approved(client)["id"])  # 5,000 in cash
    assert balances(client, ben) == {"1000": -500000, "1200": 500000}
    cats = categories(client)
    dining = next(c for c in client.get("/integration/funds/categories", headers=KEY).json()["items"] if c["label"] == "Food › Dining")
    spend(client, 320000, dining)
    spend(client, 50000, cats["Personal"], receipt=False)
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY).json()
    for e in sent["expenses"]:
        client.patch(f"/finance/funds/{req['id']}/expenses/{e['id']}", json={"accepted": True}, headers=ben)
    done = client.post(f"/finance/funds/{req['id']}/finish-check", headers=ben).json()
    # Only the covered receipt is expensed, to its category's account (Food).
    assert balances(client, ben) == {"1000": -500000, "1200": 180000, "6100": 320000}
    client.post(f"/finance/funds/{req['id']}/returned", json={"amountCentavos": 180000, "method": "bank", "reference": "DEP-9"}, headers=ben)
    assert balances(client, ben) == {"1000": -500000, "1010": 180000, "1200": 0, "6100": 320000}  # advances back to nothing
    closed = client.get(f"/finance/funds/{req['id']}", headers=ben).json()
    assert closed["status"] == "closed" and len(closed["entries"]) == 3
    assert done["entries"][1]["totalCentavos"] == 320000


def test_spending_over_is_owed_then_paid(client, ben):
    req = release(client, ben, approved(client, amount=200000)["id"], amount=200000)
    spend(client, 250000, categories(client)["Food"])
    sent = client.post("/integration/funds/requests/req-1/submit", json={"by": "Rico"}, headers=KEY).json()
    client.patch(f"/finance/funds/{req['id']}/expenses/{sent['expenses'][0]['id']}", json={"accepted": True}, headers=ben)
    client.post(f"/finance/funds/{req['id']}/finish-check", headers=ben)
    assert balances(client, ben) == {"1000": -200000, "1200": 0, "2100": 50000, "6100": 250000}
    client.post(f"/finance/funds/{req['id']}/reimbursed", json={"amountCentavos": 50000, "method": "ewallet"}, headers=ben)
    assert balances(client, ben) == {"1000": -200000, "1020": -50000, "1200": 0, "2100": 0, "6100": 250000}


def test_manual_journals_balance_and_are_reversed_not_edited(client, ana, ben):
    acc = accounts(client, ben)
    body = {"date": date.today().isoformat(), "memo": "Owner puts in capital", "lines": [
        {"accountId": acc["1010"]["id"], "debitCentavos": 10000000},
        {"accountId": acc["3000"]["id"], "creditCentavos": 9000000},
    ]}
    assert client.post("/finance/ledger/entries", json=body, headers=ben).status_code == 422  # not balanced
    body["lines"][1]["creditCentavos"] = 10000000
    entry = client.post("/finance/ledger/entries", json=body, headers=ben).json()
    assert entry["number"].startswith("JE-") and entry["totalCentavos"] == 10000000
    both = {**body, "lines": [{"accountId": acc["1010"]["id"], "debitCentavos": 5, "creditCentavos": 5}, body["lines"][1]]}
    assert client.post("/finance/ledger/entries", json=both, headers=ben).status_code == 422
    back = client.post(f"/finance/ledger/entries/{entry['id']}/reverse", json={}, headers=ben).json()
    assert back["reversesId"] == entry["id"] and back["lines"][0]["creditCentavos"] == 10000000
    assert client.post(f"/finance/ledger/entries/{entry['id']}/reverse", json={}, headers=ben).status_code == 409
    assert balances(client, ben) == {"1010": 0, "3000": 0}
    ledger = client.get(f"/finance/ledger/accounts/{acc['1010']['id']}", headers=ben).json()
    assert [ln["balanceCentavos"] for ln in ledger["lines"]] == [10000000, 0]


def test_the_chart_and_posting_accounts_are_the_admins(client, ana, ben):
    assert client.post("/finance/ledger/accounts", json={"code": "6150", "name": "Representation", "type": "expense"}, headers=ben).status_code == 403
    made = client.post("/finance/ledger/accounts", json={"code": "6150", "name": "Representation", "type": "expense"}, headers=ana)
    assert made.status_code == 201
    assert client.post("/finance/ledger/accounts", json={"code": "6150", "name": "Again", "type": "expense"}, headers=ana).status_code == 422
    acc = accounts(client, ana)
    wrong = client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": acc["6100"]["id"]}}, headers=ana)
    assert wrong.status_code == 422  # cash is an asset
    posting = client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": acc["1010"]["id"]}}, headers=ana).json()
    assert next(i for i in posting["items"] if i["key"] == "cash_account_id")["account"]["code"] == "1010"
