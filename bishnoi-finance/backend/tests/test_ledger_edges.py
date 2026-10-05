"""The ledger's rules at their edges: numbering by month, what a manual
journal can't do, an account's type once it's used, balances brought
forward, finding entries, and who sets the default accounts."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .test_funds import approved, release
from .test_ledger import accounts, balances
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def manila_today() -> date:
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def journal(client, who, on: date, amount: int, debit: dict, credit: dict, memo: str = "Owner puts in capital"):
    body = {"date": on.isoformat(), "memo": memo, "lines": [
        {"accountId": debit["id"], "debitCentavos": amount},
        {"accountId": credit["id"], "creditCentavos": amount},
    ]}
    return client.post("/finance/ledger/entries", json=body, headers=who)


def test_entries_are_numbered_by_the_month_of_their_date(client, ben):
    acc = accounts(client, ben)
    this_month = manila_today().replace(day=1)
    last_month = this_month - timedelta(days=1)
    numbers = [
        journal(client, ben, on, 100, acc["1010"], acc["3000"]).json()["number"]
        for on in (last_month, last_month.replace(day=1), this_month)
    ]
    assert numbers == [f"JE-{last_month:%Y%m}-0001", f"JE-{last_month:%Y%m}-0002", f"JE-{this_month:%Y%m}-0001"]


def test_what_a_manual_journal_cannot_do(client, ana, ben):
    acc = accounts(client, ben)
    later = manila_today() + timedelta(days=2)
    future = journal(client, ben, later, 100, acc["1010"], acc["3000"])
    assert future.status_code == 422 and future.json()["detail"][0]["loc"][-1] == "date"
    one_line = {"date": manila_today().isoformat(), "memo": "Half an entry", "lines": [{"accountId": acc["1010"]["id"], "debitCentavos": 100}]}
    assert client.post("/finance/ledger/entries", json=one_line, headers=ben).status_code == 422
    # A switched-off account takes no new entries.
    equity = acc["3000"]
    off = client.put(
        f"/finance/ledger/accounts/{equity['id']}",
        json={"code": equity["code"], "name": equity["name"], "type": equity["type"], "isActive": False},
        headers=ana,
    )
    assert off.status_code == 200
    refused = journal(client, ben, manila_today(), 100, acc["1010"], equity)
    assert refused.status_code == 422 and refused.json()["detail"][0]["loc"][-1] == "accountId"
    assert client.get("/finance/ledger/entries", headers=ben).json()["items"] == []


def test_a_reversal_cannot_itself_be_reversed(client, ben):
    acc = accounts(client, ben)
    entry = journal(client, ben, manila_today(), 5000, acc["1010"], acc["3000"]).json()
    back = client.post(f"/finance/ledger/entries/{entry['id']}/reverse", json={}, headers=ben).json()
    assert back["memo"] == f"Reversal of {entry['number']}: Owner puts in capital"
    assert client.post(f"/finance/ledger/entries/{back['id']}/reverse", json={}, headers=ben).status_code == 409


def test_an_account_keeps_its_type_once_it_has_entries(client, ana, ben):
    made = client.post("/finance/ledger/accounts", json={"code": "1300", "name": "Deposits", "type": "asset"}, headers=ana).json()
    changed = client.put(f"/finance/ledger/accounts/{made['id']}", json={"code": "1300", "name": "Deposits", "type": "expense"}, headers=ana)
    assert changed.status_code == 200 and changed.json()["type"] == "expense"  # nothing posted to it yet
    acc = accounts(client, ben)
    journal(client, ben, manila_today(), 1000, acc["1300"], acc["1010"])
    locked = client.put(f"/finance/ledger/accounts/{made['id']}", json={"code": "1300", "name": "Deposits", "type": "asset"}, headers=ana)
    assert locked.status_code == 422 and locked.json()["detail"][0]["loc"][-1] == "type"
    # Its name can still change.
    renamed = client.put(f"/finance/ledger/accounts/{made['id']}", json={"code": "1300", "name": "Security deposits", "type": "expense"}, headers=ana)
    assert renamed.status_code == 200


def test_a_statement_from_a_date_brings_the_balance_forward(client, ben):
    acc = accounts(client, ben)
    earlier, today = manila_today() - timedelta(days=10), manila_today()
    journal(client, ben, earlier, 100000, acc["1010"], acc["3000"])
    journal(client, ben, today, 50000, acc["1010"], acc["3000"])
    statement = client.get(f"/finance/ledger/accounts/{acc['1010']['id']}", params={"from": today.isoformat()}, headers=ben).json()
    assert statement["openingCentavos"] == 100000
    assert [ln["balanceCentavos"] for ln in statement["lines"]] == [150000]
    assert statement["closingCentavos"] == 150000
    # The trial balance on the earlier day leaves out what came after it.
    before = client.get("/finance/ledger/trial-balance", params={"to": earlier.isoformat()}, headers=ben).json()
    assert {r["account"]["code"]: r["balanceCentavos"] for r in before["rows"]} == {"1010": 100000, "3000": 100000}
    assert before["debitCentavos"] == before["creditCentavos"] == 100000
    assert balances(client, ben) == {"1010": 150000, "3000": 150000}


def test_finding_entries_by_source_words_and_dates(client, ben):
    acc = accounts(client, ben)
    req = release(client, ben, approved(client)["id"])
    journal(client, ben, manila_today() - timedelta(days=3), 1000, acc["1010"], acc["3000"])

    def memos(**params):
        return [e["memo"] for e in client.get("/finance/ledger/entries", params=params, headers=ben).json()["items"]]

    assert memos(source="fund") == [f"{req['number']}: cash advance to Rico Santos (Partnership dinner)"]
    assert memos(source="manual") == ["Owner puts in capital"]
    assert memos(q="CAPITAL") == ["Owner puts in capital"]
    assert memos(q=req["number"]) == [f"{req['number']}: cash advance to Rico Santos (Partnership dinner)"]
    assert memos(to=(manila_today() - timedelta(days=1)).isoformat()) == ["Owner puts in capital"]
    assert len(memos()) == 2


def test_only_admins_set_the_default_accounts(client, ana, ben):
    acc = accounts(client, ben)
    assert client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": acc["1010"]["id"]}}, headers=ben).status_code == 403
    unknown = client.put("/finance/ledger/posting", json={"accounts": {"petty_cash": acc["1010"]["id"]}}, headers=ana)
    assert unknown.status_code == 422
    posting = client.get("/finance/ledger/posting", headers=ben).json()
    assert posting["canEdit"] is False
    assert {i["key"]: i["account"]["code"] for i in posting["items"]} == {
        "advances_account_id": "1200", "due_to_employees_account_id": "2100", "cash_account_id": "1000",
        "bank_account_id": "1010", "ewallet_account_id": "1020", "check_account_id": "1010",
        "receivables_account_id": "1100", "sales_account_id": "4000", "output_tax_account_id": "2200",
    }
