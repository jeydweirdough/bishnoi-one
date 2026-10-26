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
