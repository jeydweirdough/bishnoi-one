"""What the CRM reads of a customer's standing: owed and how late, the next due
date, what was billed over the year, and the lines billed (for credit status,
the yearly contribution and the products they carry)."""

from datetime import date, timedelta

from .test_invoices import draft, ready
from .test_tax_api import CRM_KEY, ana, app, ben, client  # noqa: F401 (fixtures)

KEY = {"X-Bishnoi-Key": CRM_KEY}


def issue(client, who, **extra) -> dict:  # noqa: F811 (a fixture)
    return client.post(f"/finance/invoices/{draft(client, who, **extra)['id']}/issue", json={}, headers=who).json()


def test_a_customers_standing_is_read_by_the_crm(client, ana):  # noqa: F811 (fixtures)
    ready(client, ana)
    old = (date.today() - timedelta(days=100)).isoformat()
    # 100 days ago on 30-day terms: 70 days late, nothing paid.
    issue(client, ana, customerId="crm-1", invoiceDate=old, termsDays=30, lines=[{"ref": "AMX-500", "description": "Amoxicillin 500 mg", "quantity": 1, "unitPriceCentavos": 100000}])
    # Today on 30-day terms, part paid: owed, not late.
    fresh = issue(client, ana, customerId="crm-1", termsDays=30, lines=[{"ref": "AMX-500", "description": "Amoxicillin 500 mg", "quantity": 2, "unitPriceCentavos": 100000}])
    client.post(f"/finance/invoices/{fresh['id']}/payments", json={"paidOn": date.today().isoformat(), "amountCentavos": 50000, "method": "bank"}, headers=ana)

    assert client.get("/integration/customers?ids=crm-1").status_code == 401  # an app's key is needed
    r = client.get("/integration/customers?ids=crm-1,crm-none", headers=KEY)
    assert r.status_code == 200, r.text
    got = r.json()["customers"]
    assert "crm-none" not in got  # no invoices: left out
    c = got["crm-1"]
    assert c["oldestDaysLate"] == 70 and c["openInvoices"] == 2
    assert c["overdueCentavos"] == 100000
    assert c["owedCentavos"] == c["overdueCentavos"] + fresh["totalCentavos"] - 50000
    assert c["nextDueOn"] == (date.today() + timedelta(days=30)).isoformat() and c["approaching"] is False
    assert c["invoicesYear"] == 2 and c["billedYearCentavos"] > 0
    assert [(x["ref"], x["invoices"]) for x in c["lines"]] == [("AMX-500", 2)]
