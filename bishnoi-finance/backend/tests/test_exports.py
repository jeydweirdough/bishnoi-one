"""The books as spreadsheets: each file says what its screen says, amounts
stay numbers a spreadsheet can add, and words never run as formulas."""

import csv
import io
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .test_funds import KEY, approved, categories, release, spend
from .test_ledger import accounts
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def manila_today() -> date:
    return datetime.now(ZoneInfo("Asia/Manila")).date()


def sheet(response) -> list[list[str]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    body = response.content.decode("utf-8")
    assert body.startswith("﻿")  # so Excel reads it as UTF-8
    return list(csv.reader(io.StringIO(body[1:])))


def capital(client, who, on: date, amount: int, memo: str = "Owner puts in capital"):
    acc = accounts(client, who)
    body = {"date": on.isoformat(), "memo": memo, "lines": [
        {"accountId": acc["1010"]["id"], "debitCentavos": amount},
        {"accountId": acc["3000"]["id"], "creditCentavos": amount},
    ]}
    r = client.post("/finance/ledger/entries", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def test_only_finance_downloads_the_books(client):
    for path in ("/finance/exports/journal.csv", "/finance/exports/trial-balance.csv", "/finance/exports/funds.csv"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=KEY).status_code == 401  # an app's key isn't a Finance sign-in


def test_the_journal_one_line_per_row_oldest_first(client, ben):
    first = capital(client, ben, manila_today() - timedelta(days=5), 123456)
    capital(client, ben, manila_today(), 5000, memo="=HYPERLINK(\"http://example.com\")")
    back = client.post(f"/finance/ledger/entries/{first['id']}/reverse", json={}, headers=ben).json()
    rows = sheet(client.get("/finance/exports/journal.csv", headers=ben))
    assert rows[0][:3] == ["Date", "Entry", "Memo"] and rows[0][-1] == "Reversed by"
    assert len(rows) == 1 + 6  # three entries, two lines each
    assert rows[1][1] == first["number"] and rows[1][8:10] == ["1234.56", ""] and rows[2][8:10] == ["", "1234.56"]
    assert rows[1][-1] == back["number"]  # says which entry reversed it
    # A memo that would run as a formula is shown as typed.
    formula = next(r for r in rows if "HYPERLINK" in r[2])
    assert formula[2].startswith("'=")
    # The same filters as the screen.
    only_today = sheet(client.get("/finance/exports/journal.csv", params={"from": manila_today().isoformat()}, headers=ben))
    assert {r[1] for r in only_today[1:]} == {e["number"] for e in client.get("/finance/ledger/entries", params={"from": manila_today().isoformat()}, headers=ben).json()["items"]}


def test_a_statement_carries_its_balances_and_keeps_negatives_as_numbers(client, ben):
    acc = accounts(client, ben)
    release(client, ben, approved(client)["id"])  # 5,000 out of cash on hand
    rows = sheet(client.get(f"/finance/exports/accounts/{acc['1000']['id']}/statement.csv", headers=ben))
    assert rows[1][2] == "Balance brought forward" and rows[1][-1] == "0.00"
    assert rows[2][5:] == ["5000.00", "-5000.00"]  # a negative balance stays a number
    assert rows[-1][2] == "Closing balance" and rows[-1][-1] == "-5000.00"
    assert client.get("/finance/exports/accounts/no-such-account/statement.csv", headers=ben).status_code == 404


def test_the_trial_balance_adds_up(client, ben):
    capital(client, ben, manila_today(), 1000000)
    release(client, ben, approved(client)["id"])
    rows = sheet(client.get("/finance/exports/trial-balance.csv", headers=ben))
    assert rows[0] == ["Code", "Account", "Type", "Debit", "Credit"]
    total = rows[-1]
    assert total[1] == "Total" and total[3] == total[4] == "15000.00"  # 10,000 capital + 5,000 advance
    screen = client.get("/finance/ledger/trial-balance", headers=ben).json()
    assert [r[0] for r in rows[1:-1]] == [r["account"]["code"] for r in screen["rows"]]


def test_fund_requests_with_what_each_came_to(client, ben):
    req = release(client, ben, approved(client)["id"])
    spend(client, 320000, categories(client)["Food"])
    approved(client, "req-2", amount=100000)
    rows = sheet(client.get("/finance/exports/funds.csv", headers=ben))
    header, by_number = rows[0], {r[0]: dict(zip(rows[0], r)) for r in rows[1:]}
    assert len(by_number) == 2 and header[0] == "Number"
    out = by_number[req["number"]]
    assert (out["Status"], out["Released"], out["Release method"], out["Total expenses"]) == ("Released: pending liquidation", "5000.00", "Cash", "3200.00")
    waiting = by_number["FR-202609-eq-2"]
    assert (waiting["Approved"], waiting["Released"], waiting["Total expenses"]) == ("1000.00", "", "")
    # One list only, like the screen's.
    to_release = sheet(client.get("/finance/exports/funds.csv", params={"task": "to_release"}, headers=ben))
    assert [r[0] for r in to_release[1:]] == ["FR-202609-eq-2"]
