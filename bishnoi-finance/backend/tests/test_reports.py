"""Finance's reports (app/routers/reports.py): each needs the permission for its data, and every
report answers in the report kit's shape."""

from .test_dashboard import VIEW, person
from .test_invoices import issued, ready
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)


def test_every_report_answers_and_sales_add_up(client, ana):  # noqa: F811
    ready(client, ana)
    issued(client, ana)  # 2,240.00
    listed = client.get("/finance/reports", headers=ana).json()
    assert {"Sales", "Expenses", "Purchases", "Accounting"} <= {r["group"] for r in listed}
    for r in listed:
        body = client.get(f"/finance/reports/{r['key']}", headers=ana)
        assert body.status_code == 200, (r["key"], body.text)
        assert body.json()["columns"], r["key"]
    register = client.get("/finance/reports/sales-register", headers=ana).json()
    assert [row["total"] for row in register["rows"]] == [224000] and register["summary"][1]["value"] == 224000
    ageing = client.get("/finance/reports/receivables-ageing", headers=ana).json()
    assert ageing["rows"][0]["current"] == 224000  # not due yet


def test_a_role_sees_only_the_reports_for_its_data(client, ana):  # noqa: F811
    seller = person(client, ana, "Invoices only", VIEW)
    keys = {r["key"] for r in client.get("/finance/reports", headers=seller).json()}
    assert "sales-register" in keys and "bills-by-supplier" not in keys
    assert client.get("/finance/reports/bills-by-supplier", headers=seller).status_code == 404


def test_the_accounting_statements_are_fixed_reports(client, ana):  # noqa: F811
    """Profit and loss, balance sheet, cash flow, trial balance and general ledger: in the Reports Center, fixed."""
    listed = {r["key"]: r for r in client.get("/finance/reports", headers=ana).json()}
    for key in ("profit-and-loss", "balance-sheet", "cash-flow", "trial-balance", "general-ledger"):
        assert listed[key]["fixed"] is True, key
        body = client.get(f"/finance/reports/{key}", headers=ana)
        assert body.status_code == 200, (key, body.text)
        assert body.json()["fixed"] is True
    assert listed["sales-register"]["fixed"] is False  # a template: may be customised
    tb = client.get("/finance/reports/trial-balance", headers=ana).json()
    debits, credits = (f["value"] for f in tb["summary"][:2])
    assert debits == credits  # the trial balance agrees


def test_management_figures_come_from_the_books(client, ana):  # noqa: F811
    """Key figures, revenue growth and the cash forecast (decided 2026-10-28): fixed, from invoices and the books."""
    from datetime import date, timedelta

    ready(client, ana)
    inv = issued(client, ana)  # 2,240.00 with VAT: 2,000.00 of revenue
    client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": date.today().isoformat(), "amountCentavos": 100000, "method": "bank"}, headers=ana)
    listed = {r["key"]: r for r in client.get("/finance/reports", headers=ana).json()}
    assert all(listed[k]["fixed"] and listed[k]["group"] == "Management" for k in ("key-figures", "revenue-growth", "cash-forecast"))

    key = client.get("/finance/reports/key-figures", headers=ana).json()
    figures = {f["label"]: f["value"] for f in key["summary"]}
    assert figures["Revenue"] == 200000
    # Owed 1,240 + 1,000 in the bank, against 240 of output VAT: all current.
    assert figures["Working capital"] == 224000 - 24000
    assert figures["Accounts judged by name"] >= 1  # nobody has said which accounts are current yet
    rows = {r["figure"]: r for r in key["rows"]}
    assert rows["Revenue"]["now"] == "₱2K" and rows["Current ratio"]["reading"] == "Healthy"

    # Saying it on each account: none judged by name any more.
    chart = {a["code"]: a for a in client.get("/finance/ledger/accounts", headers=ana).json()["items"]}
    for code in ("1010", "1100", "2200"):
        a = chart[code]
        body = {"code": a["code"], "name": a["name"], "type": a["type"], "description": a["description"], "isActive": a["isActive"], "parentId": a["parentId"], "term": "current"}
        saved = client.put(f"/finance/ledger/accounts/{a['id']}", json=body, headers=ana)
        assert saved.status_code == 200 and saved.json()["term"] == "current", saved.text
    again = client.get("/finance/reports/key-figures", headers=ana).json()
    assert "Accounts judged by name" not in {f["label"] for f in again["summary"]}

    growth = client.get("/finance/reports/revenue-growth", headers=ana).json()
    assert growth["rows"][-1]["revenue"] == 200000 and growth["summary"][0]["value"] == 200000

    # The 1,240 still owed is due in 30 days: it lands in that week, after the cash in the bank.
    forecast = client.get("/finance/reports/cash-forecast", headers=ana).json()
    due = date.today() + timedelta(days=30)
    monday = (due - timedelta(days=due.weekday())).isoformat()
    week = next(r for r in forecast["rows"] if r["week"] == f"Week of {monday}")
    assert week["inflow"] == 124000
    assert forecast["summary"][0]["label"] == "Cash now"


def test_only_assets_and_liabilities_are_current_or_long_term(client, ana):  # noqa: F811
    made = client.post("/finance/ledger/accounts", json={"code": "6150", "name": "Representation", "type": "expense", "term": "current"}, headers=ana)
    assert made.status_code == 201 and made.json()["term"] is None and made.json()["termShown"] is None
    building = client.post("/finance/ledger/accounts", json={"code": "1600", "name": "Building and equipment", "type": "asset"}, headers=ana).json()
    assert building["term"] is None and building["termShown"] == "non_current"  # worked out from its name


def test_an_invoice_books_its_cost_of_goods_sold_from_inventory(client, ana, monkeypatch):  # noqa: F811
    """Feature plan step 3 (2026-10-28): issuing books what the goods cost (Inventory's cost by item
    code) in the same entry as the sale, a void reverses both, and the margin reports read it."""
    from app import inventory

    from .test_invoices import draft
    from .test_ledger import balances

    ready(client, ana)
    asked = []
    monkeypatch.setattr(inventory, "unit_costs", lambda settings, skus: asked.append(skus) or {"AMX-500": 70000})
    made = {code: client.post("/finance/ledger/accounts", json={"code": code, "name": name, "type": kind}, headers=ana).json()["id"]
            for code, name, kind in (("5000", "Cost of goods sold", "expense"), ("1400", "Merchandise inventory", "asset"))}
    client.put("/finance/ledger/posting", json={"accounts": {"cogs_account_id": made["5000"], "inventory_account_id": made["1400"]}}, headers=ana)

    lines = [{"ref": "AMX-500", "description": "Amoxicillin 500 mg", "quantity": 2, "unitPriceCentavos": 112000},
             {"ref": "NOPE-1", "description": "Not in Inventory", "quantity": 1, "unitPriceCentavos": 11200}]
    inv = client.post(f"/finance/invoices/{draft(client, ana, lines=lines)['id']}/issue", json={}, headers=ana).json()
    assert asked == [["AMX-500", "NOPE-1"]]
    books = balances(client, ana)
    assert (books["5000"], books["1400"]) == (140000, -140000)  # 2 × 700.00, out of the stock

    by_product = {r["name"]: r for r in client.get("/finance/reports/gross-margin-by-product", headers=ana).json()["rows"]}
    assert (by_product["AMX-500"]["revenue"], by_product["AMX-500"]["cost"], by_product["AMX-500"]["profit"]) == (200000, 140000, 60000)
    assert by_product["NOPE-1"]["cost"] == 0
    by_customer = client.get("/finance/reports/gross-margin-by-customer", headers=ana).json()
    assert by_customer["rows"][0]["cost"] == 140000 and by_customer["summary"][-1]["value"] == 1  # one invoice with a line of unknown cost
    key = {f["label"]: f["value"] for f in client.get("/finance/reports/key-figures", headers=ana).json()["summary"]}
    assert key["Gross profit"] == 210000 - 140000

    # A void takes the sale and its cost off together.
    client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong customer"}, headers=ana)
    after = balances(client, ana)
    assert after.get("5000", 0) == 0 and after.get("1400", 0) == 0


def test_revenue_by_division_follows_the_salesperson_when_each_invoice_was_made(client, ana):  # noqa: F811
    """Feature plan step 4: each invoice keeps its salesperson's division and team (migration 0025)."""
    ready(client, ana)
    hos = issued(client, ana, salespersonName="Ben Cruz", divisionId="d1", divisionName="HOS", teamId="t1", teamName="Field NCR 1")
    assert hos["division"] == {"id": "d1", "name": "HOS"} and hos["team"]["name"] == "Field NCR 1"
    issued(client, ana)
    rows = {r["name"]: r for r in client.get("/finance/reports/revenue-by-division", headers=ana).json()["rows"]}
    assert set(rows) == {"HOS", "Not in a division"} and rows["HOS"]["revenue"] == 200000  # 2,240.00 with VAT
    teams = {r["name"] for r in client.get("/finance/reports/revenue-by-team", headers=ana).json()["rows"]}
    assert teams == {"Field NCR 1", "Not in a team"}
