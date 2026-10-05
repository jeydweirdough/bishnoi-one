"""Sales invoices: drafted, issued with the next number of the BIR's series,
posted to the ledger, and voided (never edited) once issued."""

from datetime import date, timedelta

from .test_ledger import balances
from .test_tax_api import REGISTRATION, ana, app, ben, client  # noqa: F401 (fixtures)

TODAY = date.today().isoformat()
SERIES = {"name": "Sales invoices", "prefix": "SI-", "digits": 6, "firstNumber": 101, "lastNumber": 102, "atpNumber": "OCN-2026-0001", "atpDate": "2026-01-05"}


def draft(client, who, **extra) -> dict:
    body = {
        "customerName": "Mercury Drug Makati", "customerAddress": "Ayala Ave, Makati", "invoiceDate": TODAY, "termsDays": 30,
        "lines": [{"description": "Amoxicillin 500 mg, box of 100", "quantity": 2, "unitPriceCentavos": 112000}],
        **extra,
    }
    r = client.post("/finance/invoices", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def ready(client, ana):  # noqa: F811 (a fixture)
    client.put("/tax/profile", json=REGISTRATION, headers=ana)
    assert client.post("/finance/invoices/series", json=SERIES, headers=ana).status_code == 201


def test_a_draft_is_worked_out_then_issued_numbered_and_posted(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    inv = draft(client, ben)
    # A draft has no number yet, and is worked out each time it's read (prices include VAT: 2,240.00).
    assert inv["status"] == "draft" and inv["number"] is None and inv["computed"]["totalDueCentavos"] == 224000
    assert inv["dueDate"] == (date.today() + timedelta(days=30)).isoformat()
    issued = client.post(f"/finance/invoices/{inv['id']}/issue", json={}, headers=ben)
    assert issued.status_code == 200, issued.text
    issued = issued.json()
    assert (issued["status"], issued["number"], issued["totalCentavos"], issued["taxCentavos"]) == ("issued", "SI-000101", 224000, 24000)
    assert issued["series"]["atpNumber"] == "OCN-2026-0001" and issued["balanceCentavos"] == 224000
    # Owed by the customer, against the sale and its VAT.
    assert balances(client, ana) == {"1100": 224000, "4000": 200000, "2200": 24000}
    # Issued, it isn't changed or deleted.
    assert client.put(f"/finance/invoices/{inv['id']}", json={"customerName": "X", "invoiceDate": TODAY, "lines": [{"quantity": 1, "unitPriceCentavos": 1}]}, headers=ben).status_code == 409
    assert client.delete(f"/finance/invoices/{inv['id']}", headers=ben).status_code == 409


def test_numbers_are_used_in_order_and_never_past_the_last(client, ana):  # noqa: F811 (a fixture)
    ready(client, ana)
    numbers = [client.post(f"/finance/invoices/{draft(client, ana)['id']}/issue", json={}, headers=ana).json()["number"] for _ in range(2)]
    assert numbers == ["SI-000101", "SI-000102"]
    third = client.post(f"/finance/invoices/{draft(client, ana)['id']}/issue", json={}, headers=ana)
    assert third.status_code == 409 and "Authority to Print" in third.json()["detail"]
    assert client.get("/finance/unset", headers=ana).json()["invoiceSeries"] == 1
    # A new series can't reuse numbers another already prints.
    clash = client.post("/finance/invoices/series", json={**SERIES, "firstNumber": 102, "lastNumber": 500}, headers=ana)
    assert clash.status_code == 422


def test_voiding_keeps_the_number_and_reverses_the_entry(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    inv = client.post(f"/finance/invoices/{draft(client, ana)['id']}/issue", json={}, headers=ana).json()
    # Staff issue invoices, but don't void them.
    assert client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong customer"}, headers=ben).status_code == 403
    voided = client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong customer"}, headers=ana).json()
    assert (voided["status"], voided["number"], voided["voidReason"]) == ("void", "SI-000101", "Wrong customer")
    assert balances(client, ana) == {"1100": 0, "4000": 0, "2200": 0}
    assert client.get("/finance/invoices?status=void", headers=ana).json()["counts"] == {"draft": 0, "issued": 0, "void": 1}


def test_what_stops_an_invoice(client, ana, ben):  # noqa: F811 (fixtures)
    # No company registration yet: an invoice can't be issued without it.
    assert client.post("/finance/invoices/series", json=SERIES, headers=ben).status_code == 403  # the series are the admin's
    client.post("/finance/invoices/series", json=SERIES, headers=ana)
    inv = draft(client, ana)
    unregistered = client.post(f"/finance/invoices/{inv['id']}/issue", json={}, headers=ana)
    assert unregistered.status_code == 409 and "TIN" in unregistered.json()["detail"]
    # Not dated in the future; a bad VAT category is caught on the draft.
    later = (date.today() + timedelta(days=1)).isoformat()
    assert client.post("/finance/invoices", json={"customerName": "X", "invoiceDate": later, "lines": [{"quantity": 1, "unitPriceCentavos": 1}]}, headers=ana).status_code == 422
    odd = draft(client, ana, lines=[{"quantity": 1, "unitPriceCentavos": 100, "category": "nonsense"}])
    assert odd["computed"] is None and odd["problem"]
    # Without the CRM linked, customers are typed in; a draft can still be deleted.
    assert client.get("/finance/invoices/customers?q=mer", headers=ana).status_code == 409
    assert client.delete(f"/finance/invoices/{inv['id']}", headers=ana).status_code == 204


def issued(client, who, **extra) -> dict:
    return client.post(f"/finance/invoices/{draft(client, who, **extra)['id']}/issue", json={}, headers=who).json()


def test_payments_bring_what_is_owed_down_and_post(client, ana, ben):  # noqa: F811 (fixtures)
    ready(client, ana)
    inv = issued(client, ana)  # 2,240.00
    pay = lambda amount, **extra: client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": TODAY, "amountCentavos": amount, "method": "bank", **extra}, headers=ben)  # noqa: E731
    assert pay(300000).status_code == 422  # more than is owed
    part = pay(100000, reference="DEP-1").json()
    assert (part["paidCentavos"], part["balanceCentavos"]) == (100000, 124000)
    assert [p["methodLabel"] for p in part["payments"]] == ["Bank transfer"]
    assert balances(client, ana) == {"1010": 100000, "1100": 124000, "4000": 200000, "2200": 24000}
    # Paid, it can't be voided until the payment is taken off; only who may void takes it off.
    assert client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong"}, headers=ana).status_code == 409
    payment = part["payments"][0]["id"]
    assert client.delete(f"/finance/invoices/{inv['id']}/payments/{payment}", headers=ben).status_code == 403
    back = client.delete(f"/finance/invoices/{inv['id']}/payments/{payment}", headers=ana).json()
    assert back["paidCentavos"] == 0 and back["payments"][0]["removedBy"] == "Ana Reyes"
    assert balances(client, ana)["1100"] == 224000


def test_receivables_age_by_how_late_they_are(client, ana):  # noqa: F811 (a fixture)
    ready(client, ana)
    old = (date.today() - timedelta(days=75)).isoformat()
    late = issued(client, ana, invoiceDate=old, termsDays=30)  # 45 days late
    fresh = issued(client, ana, customerName="Watsons BGC")  # not yet due
    client.post(f"/finance/invoices/{fresh['id']}/payments", json={"paidOn": TODAY, "amountCentavos": 24000, "method": "cash"}, headers=ana)
    got = client.get("/finance/receivables", headers=ana).json()
    buckets = {b["key"]: b["amountCentavos"] for b in got["buckets"]}
    assert buckets == {"current": 200000, "d1_30": 0, "d31_60": 224000, "d61_90": 0, "over_90": 0}
    assert got["totalCentavos"] == 424000
    # The latest first.
    assert [c["name"] for c in got["customers"]] == ["Mercury Drug Makati", "Watsons BGC"]
    assert got["customers"][0]["invoices"][0] == {**got["customers"][0]["invoices"][0], "number": late["number"], "daysLate": 45, "bucket": "d31_60"}
