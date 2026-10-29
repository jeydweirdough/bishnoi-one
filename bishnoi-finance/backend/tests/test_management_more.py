"""The last management reports (feature plan step 17): fixed assets and depreciation, budgets against actual, and EBITDA,
return on equity, debt to equity, break-even and customer acquisition cost in the key figures."""

from datetime import date, timedelta

from .test_banking import account
from .test_invoices import TODAY, issued, ready
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


def accounts(client, ana):  # noqa: F811
    return {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}


def retag(client, ana, a, **tags):  # noqa: F811
    r = client.put(f"/finance/ledger/accounts/{a['id']}", json={"code": a["code"], "name": a["name"], "type": a["type"], "isActive": True, **tags}, headers=ana)
    assert r.status_code == 200, r.text
    return r.json()


def entry(client, ana, on, legs):  # noqa: F811
    """A journal entry by hand, approved by someone else is how the books work; posted straight for the test."""
    from app.models import Account, User
    from app.ledger import Leg, post

    app_ = client.app
    with app_.state.sessions() as db:
        post(db, date.fromisoformat(on), "Test", [Leg(db.get(Account, a), debit=d, credit=c) for a, d, c in legs], "Test", source="manual")
        db.commit()


def test_a_fixed_asset_is_depreciated_month_by_month_once(app, client, ana):  # noqa: F811
    equipment = account(client, ana, "1597", "Equipment (test)", "asset")
    accumulated = account(client, ana, "1598", "Accumulated depreciation, equipment", "asset")
    expense = account(client, ana, "6991", "Depreciation (test)", "expense")
    bought = (date.fromisoformat(TODAY).replace(day=1) - timedelta(days=70)).replace(day=15)
    r = client.post("/finance/fixed-assets", json={"name": "Delivery van", "assetAccountId": equipment, "accumulatedAccountId": accumulated, "expenseAccountId": expense,
                                                   "costCentavos": 120000000, "salvageCentavos": 0, "acquiredOn": bought.isoformat(), "usefulMonths": 60}, headers=ana)
    assert r.status_code == 201, r.text
    assert r.json()["monthlyCentavos"] == 2000000
    run = client.post("/finance/fixed-assets/depreciate", json={"through": TODAY}, headers=ana)
    assert run.status_code == 200, run.text
    months = run.json()["entries"]
    assert len(months) >= 2 and all(m["totalCentavos"] == 2000000 for m in months)
    again = client.post("/finance/fixed-assets/depreciate", json={"through": TODAY}, headers=ana).json()
    assert again["entries"] == []  # never twice
    register = client.get("/finance/fixed-assets", headers=ana).json()
    assert register["totals"]["accumulatedCentavos"] == 2000000 * len(months)
    report = client.get("/finance/reports/fixed-assets", headers=ana)
    assert report.status_code == 200 and report.json()["rows"][0]["bookValue"] == 120000000 - 2000000 * len(months)


def test_budget_against_actual(client, ana):  # noqa: F811
    a = accounts(client, ana)
    other = a["6900"]
    r = client.put("/finance/budgets", json={"yearEnd": f"{date.fromisoformat(TODAY).year}-12-31", "accountId": other["id"], "yearlyCentavos": 1200000}, headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["months"] == [100000] * 12
    entry(client, ana, TODAY, [(other["id"], 150000, 0), (a["1000"]["id"], 0, 150000)])
    first = date.fromisoformat(TODAY).replace(day=1).isoformat()
    rows = client.get(f"/finance/reports/budget-vs-actual?from={first}&to={TODAY}", headers=ana).json()["rows"]
    row = next(x for x in rows if x["code"] == "6900")
    assert (row["budget"], row["actual"], row["variance"]) == (100000, 150000, 50000)


def test_the_key_figures_gain_ebitda_equity_break_even_and_acquisition_cost(client, ana):  # noqa: F811
    a = accounts(client, ana)
    interest = account(client, ana, "6981", "Interest expense (test)", "expense")
    marketing = account(client, ana, "6982", "Advertising (test)", "expense")
    rent = account(client, ana, "6983", "Rent (test)", "expense")
    acc = accounts(client, ana)
    retag(client, ana, acc["6981"], reportTag="interest")
    retag(client, ana, acc["6982"], reportTag="sales_marketing", costBehaviour="variable")
    retag(client, ana, acc["6983"], costBehaviour="fixed")
    ready(client, ana)
    issued(client, ana)  # 2,240 with VAT: 2,000 revenue from a new customer
    cash = a["1000"]["id"]
    entry(client, ana, TODAY, [(interest, 10000, 0), (cash, 0, 10000)])
    entry(client, ana, TODAY, [(marketing, 50000, 0), (cash, 0, 50000)])
    entry(client, ana, TODAY, [(rent, 60000, 0), (cash, 0, 60000)])
    first = date.fromisoformat(TODAY).replace(day=1).isoformat()
    body = client.get(f"/finance/reports/key-figures?from={first}&to={TODAY}", headers=ana).json()
    rows = {r["figure"]: r for r in body["rows"]}
    assert rows["EBITDA"]["reading"] in ("Positive", "Negative")
    assert rows["Customer acquisition cost"]["now"] == "₱500.00" and rows["Customer acquisition cost"]["reading"] == "1 new customer"
    # Revenue 2,000; variable 500 (advertising): contribution 75%; fixed 600 (rent) ÷ 0.75 = 800.
    assert rows["Break-even revenue"]["now"] == "₱800.00" and rows["Break-even revenue"]["reading"] == "Above it"
    assert "Debt to equity" in rows and "Return on equity" in rows
