"""The sidebar's red counts: what isn't set up yet, for the admins who can fix it."""

from .test_ledger import accounts
from .test_tax_api import REGISTRATION, ana, app, ben, client  # noqa: F401 (fixtures)


def test_setup_an_admin_owes(client, ana, ben):  # noqa: F811 (fixtures)
    # Fresh from the migration the default accounts are set; the tax registration isn't.
    assert client.get("/finance/unset", headers=ana).json() == {"taxProfile": 1}
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    assert client.get("/finance/unset", headers=ana).json() == {}
    # A default account cleared, and one switched off: two to fix.
    acc = accounts(client, ana)
    client.put("/finance/ledger/posting", json={"accounts": {"cash_account_id": None}}, headers=ana)
    bank = acc["1010"]
    r = client.put(f"/finance/ledger/accounts/{bank['id']}", json={"code": bank["code"], "name": bank["name"], "type": bank["type"], "isActive": False}, headers=ana)
    assert r.status_code == 200, r.text
    assert client.get("/finance/unset", headers=ana).json()["postingAccounts"] >= 2
    # Only admins can fix these, so nobody else is shown them.
    assert client.get("/finance/unset", headers=ben).json() == {}


def test_an_expense_category_with_no_account(client, ana):  # noqa: F811 (fixtures)
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    food = next(c for c in client.get("/finance/funds/categories", headers=ana).json()["items"] if c["label"] == "Food")
    account = accounts(client, ana)[food["account"]["code"]]
    client.put(f"/finance/ledger/accounts/{account['id']}", json={"code": account["code"], "name": account["name"], "type": account["type"], "isActive": False}, headers=ana)
    assert client.get("/finance/unset", headers=ana).json()["categoryAccounts"] >= 1
