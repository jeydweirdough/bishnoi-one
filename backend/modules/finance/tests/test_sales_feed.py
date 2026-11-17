"""What the CRM reads to score its people: a month's invoices with whose sale
each is, each customer's first sale ever, and what each salesperson's
customers still owe."""

from datetime import date, timedelta

from .test_customer_standing import KEY, issue
from .test_invoices import REGISTRATION, SERIES, draft
from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)

LINE = [{"description": "Amoxicillin 500 mg", "quantity": 1, "unitPriceCentavos": 100000}]


def test_the_crm_reads_a_months_sales_by_salesperson(client, ana):  # noqa: F811 (fixtures)
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    client.post("/finance/invoices/series", json={**SERIES, "lastNumber": 199}, headers=ana)
    today = date.today()
    old = (today - timedelta(days=200)).isoformat()
    issue(client, ana, customerId="crm-1", invoiceDate=old, salespersonId="rep-1", salespersonName="Rina", lines=LINE)
    sale = issue(client, ana, customerId="crm-1", salespersonId="rep-1", salespersonName="Rina", lines=LINE)
    assert sale["salesperson"] == {"id": "rep-1", "name": "Rina"}
    issue(client, ana, customerId="crm-2", salespersonId="rep-1", salespersonName="Rina", lines=LINE)
    voided = issue(client, ana, customerId="crm-3", salespersonId="rep-2", salespersonName="Sam", lines=LINE)
    client.post(f"/finance/invoices/{voided['id']}/void", json={"reason": "Ordered twice"}, headers=ana)
    draft(client, ana, customerId="crm-4", salespersonId="rep-2", lines=LINE)  # a draft isn't a sale

    span = f"from={(today - timedelta(days=5)).isoformat()}&to={(today + timedelta(days=1)).isoformat()}"
    assert client.get(f"/integration/sales?{span}").status_code == 401
    r = client.get(f"/integration/sales?{span}", headers=KEY)
    assert r.status_code == 200, r.text
    got = r.json()
    assert sorted((i["customerId"], i["status"]) for i in got["invoices"]) == [("crm-1", "issued"), ("crm-2", "issued"), ("crm-3", "void")]
    assert got["firstSale"]["crm-1"] == old and got["firstSale"]["crm-2"] == today.isoformat()  # crm-1 is an old customer
    assert got["owed"]["rep-1"] == 3 * sale["totalCentavos"] and "rep-2" not in got["owed"]  # nothing paid; a voided invoice isn't owed
