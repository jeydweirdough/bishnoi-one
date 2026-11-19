"""Bank reconciliation (decided 2026-10-24, from Oojeema): a statement matched
against the books, line by line, until the cleared balance is the statement's."""

from datetime import date, timedelta

from .test_invoices import TODAY, issued, ready
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def bank_id(client, who):
    return next(a["id"] for a in client.get("/finance/bank/accounts", headers=who).json()["accounts"] if a["code"] == "1010")


def test_a_statement_is_matched_against_the_books(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    for amount in (100000, 50000):  # two deposits from customers
        inv = issued(client, ana)
        client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": TODAY, "amountCentavos": amount, "method": "bank"}, headers=ben)
    bank = bank_id(client, ben)
    start = client.post("/finance/bank/reconciliations", json={"accountId": bank, "statementDate": TODAY, "statementBalanceCentavos": 100000}, headers=ben)
    assert start.status_code == 201, start.text
    rec = client.get(f"/finance/bank/reconciliations/{start.json()['id']}", headers=ben).json()
    assert [ln["inCentavos"] for ln in rec["lines"]] == [100000, 50000] and rec["differenceCentavos"] == 100000
    # Only one in progress per account.
    assert client.post("/finance/bank/reconciliations", json={"accountId": bank, "statementDate": TODAY, "statementBalanceCentavos": 1}, headers=ben).status_code == 422
    # The bank shows only the first deposit: tick it, and it balances.
    first = rec["lines"][0]["id"]
    rec = client.put(f"/finance/bank/reconciliations/{rec['id']}/cleared", json={"lineIds": [first]}, headers=ben).json()
    assert rec["differenceCentavos"] == 0
    done = client.post(f"/finance/bank/reconciliations/{rec['id']}/finish", headers=ben).json()
    assert done["status"] == "done"
    # The next statement starts from this one's balance, with only the deposit not yet cleared.
    later = (date.today() + timedelta(days=0)).isoformat()
    again = client.post("/finance/bank/reconciliations", json={"accountId": bank, "statementDate": later, "statementBalanceCentavos": 150000}, headers=ben)
    assert again.status_code == 422  # not after the last statement
    accounts = client.get("/finance/bank/accounts", headers=ben).json()["accounts"]
    assert next(a for a in accounts if a["id"] == bank)["lastStatementBalanceCentavos"] == 100000


def test_it_wont_finish_until_it_balances(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    bank = bank_id(client, ben)
    rec = client.post("/finance/bank/reconciliations", json={"accountId": bank, "statementDate": TODAY, "statementBalanceCentavos": 5000}, headers=ben).json()
    stuck = client.post(f"/finance/bank/reconciliations/{rec['id']}/finish", headers=ben)
    assert stuck.status_code == 409 and "journal entries" in stuck.json()["detail"]
    assert client.delete(f"/finance/bank/reconciliations/{rec['id']}", headers=ben).status_code == 204
