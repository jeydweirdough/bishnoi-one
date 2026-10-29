"""Automatic invoicing (app/delivery_invoices.py, feature plan step 13): a customer's delivery leaving the
warehouse (delivery.done) becomes its invoice, issued at once or waiting as a draft with why."""

from sqlalchemy import select

from app.business_events import OutboxEvent
from .test_invoices import ready
from .test_platform_roles import note
from .test_platform_sign_in import PUBLIC
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


def delivery(n: int = 1, fee_charged: bool = True) -> dict:
    return {
        "id": f"ev-delivery-{n:04d}", "kind": "delivery.done", "source": "inventory", "occurredAt": "2026-10-29T00:00:00+00:00",
        "data": {
            "orderId": f"order-{n}", "number": f"DR-{n:05d}", "recipient": "Mercury Drug Makati", "issuedAt": "2026-10-29T01:00:00+00:00",
            "shipping": {"method": "courier", "courier": "LBC Express", "trackingNumber": "LBC123", "fee": 15000, "feeCharged": fee_charged},
            "salesOrder": {
                "id": f"so-{n}", "number": f"SO-{n:05d}", "quote": {"id": "q-1", "number": "Q-2026-0001"},
                "customer": {"id": "c-1", "name": "Mercury Drug Makati", "address": "Ayala Ave, Makati", "tin": None},
                "salesperson": {"id": "u-1", "name": "Ria Santos"}, "division": {"id": "d-1", "name": "B2B"}, "team": {"id": "t-1", "name": "B2B NBD"},
                "payer": {"kind": "customer"}, "currency": "PHP", "pricesIncludeTax": None,
                "lines": [{"sku": "AMX-500", "name": "Amoxicillin 500 mg", "quantity": 2, "freeQuantity": 1, "unitPriceCentavos": 112000,
                           "discountCentavos": 4000, "vatCategory": "standard"}],
            },
        },
    }


def send(client, event):
    r = client.post("/platform/events", json={"pass": note("event", event=event)})
    assert r.status_code == 204, r.text


def outbox(app, kind):
    with app.state.sessions() as db:
        return [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == kind).order_by(OutboxEvent.occurred_at))]


def test_a_delivery_becomes_its_invoice_issued_once(app, client, ana):  # noqa: F811
    app.state.settings.platform_public_key = PUBLIC
    ready(client, ana)
    for _ in range(2):
        send(client, delivery())
    send(client, {**delivery(), "id": "ev-delivery-again"})  # the same delivery told twice: one invoice
    items = client.get("/finance/invoices", headers=ana).json()["items"]
    assert len(items) == 1
    inv = client.get(f"/finance/invoices/{items[0]['id']}", headers=ana).json()
    assert inv["status"] == "issued" and inv["number"] and inv["attention"] is None
    assert inv["delivery"] == {"id": "order-1", "number": "DR-00001"} and inv["salesOrder"]["number"] == "SO-00001"
    assert (inv["customer"]["name"], inv["salesperson"]["name"], inv["division"]["name"]) == ("Mercury Drug Makati", "Ria Santos", "B2B")
    assert [(l["description"], l["quantity"], l["unitPriceCentavos"], l["discountCentavos"]) for l in inv["lines"]] == [
        ("Amoxicillin 500 mg", 2, 112000, 4000), ("Amoxicillin 500 mg (free)", 1, 0, 0), ("Shipping fee (LBC Express · LBC123)", 1, 15000, 0)]
    assert inv["issuedBy"] == "Bishnoi One"
    told = outbox(app, "invoice.issued")[-1]
    assert told["deliveryId"] == "order-1" and told["salesOrderId"] == "so-1"
    link = outbox(app, "document.linked")[-1]
    assert link["from"]["app"] == "inventory" and link["to"] == {"app": "finance", "kind": "invoice", "id": inv["id"], "number": inv["number"]}

    # Paid in full: the chain is closed.
    client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": inv["totalCentavos"] - 1, "method": "bank"}, headers=ana)
    assert outbox(app, "invoice.paid") == []
    client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 1, "method": "bank"}, headers=ana)
    paid = outbox(app, "invoice.paid")
    assert len(paid) == 1 and paid[0]["salesOrderId"] == "so-1"


def test_when_it_cant_be_issued_it_waits_as_a_draft_with_why(app, client, ana):  # noqa: F811
    app.state.settings.platform_public_key = PUBLIC
    # No invoice numbers yet (no BIR series): made, not issued.
    send(client, delivery(2, fee_charged=False))
    listed = client.get("/finance/invoices?attention=true", headers=ana).json()
    assert listed["counts"]["attention"] == 1
    inv = listed["items"][0]
    assert inv["status"] == "draft" and inv["attention"] and inv["number"] is None
    assert all("Shipping" not in l["description"] for l in client.get(f"/finance/invoices/{inv['id']}", headers=ana).json()["lines"])
    # Fixed: Finance issues it; it's no longer waiting.
    ready(client, ana)
    r = client.post(f"/finance/invoices/{inv['id']}/issue", json={}, headers=ana)
    assert r.status_code == 200, r.text
    assert r.json()["attention"] is None and client.get("/finance/invoices?attention=true", headers=ana).json()["counts"]["attention"] == 0


def test_the_company_can_have_them_wait_for_finance(app, client, ana):  # noqa: F811
    app.state.settings.platform_public_key = PUBLIC
    ready(client, ana)
    assert client.get("/finance/invoices/automatic", headers=ana).json() == {"autoInvoice": "issue"}
    assert client.put("/finance/invoices/automatic", json={"autoInvoice": "draft"}, headers=ana).json() == {"autoInvoice": "draft"}
    send(client, delivery(3))
    inv = client.get("/finance/invoices", headers=ana).json()["items"][0]
    assert inv["status"] == "draft" and "wait" in inv["attention"]


def test_an_issue_to_a_department_isnt_invoiced(app, client, ana):  # noqa: F811
    app.state.settings.platform_public_key = PUBLIC
    send(client, {**delivery(4), "data": {**delivery(4)["data"], "salesOrder": None}})
    assert client.get("/finance/invoices", headers=ana).json()["items"] == []


def test_a_consignment_settlement_becomes_a_draft_vendor_bill(app, client, ana):  # noqa: F811
    """Step 15d: what sold from a vendor's consignment, settled in Inventory, waits here as a draft bill."""
    app.state.settings.platform_public_key = PUBLIC
    event = {"id": "ev-consign-1", "kind": "consignment.billed", "source": "inventory", "occurredAt": "2026-10-29T00:00:00+00:00",
             "data": {"settlementId": "cs-1", "number": "CS-00001", "supplier": {"id": "s-1", "code": "GC045604", "name": "ABC Medical Supply", "tin": None},
                      "lines": [{"productId": "p-1", "sku": "GLV-M", "name": "Gloves M", "quantity": 4, "unitCost": 18500, "total": 74000}], "totalCentavos": 74000}}
    for _ in range(2):
        send(client, event)
    from app.models import Bill, Supplier

    with app.state.sessions() as db:
        bills = db.scalars(select(Bill)).all()
        assert len(bills) == 1 and bills[0].status == "draft" and bills[0].bill_number == "CS-00001"
        assert bills[0].total_centavos == 74000 and "Gloves M" in bills[0].lines[0]["description"]
        assert db.scalar(select(Supplier).where(Supplier.name == "ABC Medical Supply")) is not None
