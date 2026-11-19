"""Chart clean-up list (Sir Mel, recording 12): accounts with the same name as another, or never used, for Sir Mel
and Malou to choose from. Read-only. Made-up accounts."""

from .test_banking import account
from .test_tax_api import app, ana, client  # noqa: F401 (fixtures)


def test_the_list_shows_twins_and_unused_accounts_and_changes_nothing(client, ana):
    account(client, ana, "6981", "Office Supplies", "expense")
    account(client, ana, "6982", "office  supplies.", "expense")  # same name once spaces, case and dots are set aside
    before = client.get("/finance/ledger/accounts", headers=ana).json()["items"]
    r = client.get("/finance/reports/chart-cleanup", headers=ana)
    assert r.status_code == 200, r.text
    rows = {x["code"]: x for x in r.json()["rows"]}
    assert rows["6981"]["issue"] == "Same name as 6982; Never used" and rows["6982"]["issue"] == "Same name as 6981; Never used"
    assert rows["6981"]["entries"] == 0 and rows["6981"]["lastUsed"] is None
    figures = {f["label"]: f["value"] for f in r.json()["summary"]}
    assert figures["Same name as another"] >= 2 and figures["Accounts"] == len(before)
    # Read-only: the chart is the same afterwards.
    assert client.get("/finance/ledger/accounts", headers=ana).json()["items"] == before
