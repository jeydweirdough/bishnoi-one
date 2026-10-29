"""The Sales app's sales orders (app/sales.py, feature plan step 11): from a CRM quote or typed here, every
order waits for approval; approving makes its delivery; the delivery issued delivers the order."""

from sqlalchemy import select

from app.business_events import OutboxEvent
from tests.conftest import Api, receive
from tests.test_platform_roles import database, note
from tests.test_platform_sign_in import linked  # noqa: F401 (fixture)


def outbox(app, kind: str) -> list[dict]:
    with database(app)() as db:
        return [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == kind).order_by(OutboxEvent.occurred_at))]


def test_a_typed_order_waits_for_approval_then_its_delivery_is_made(app, client, people, ana, world):
    sal = Api(client, people["sal"])
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    made = sal.post("/inventory/sales-orders", {"customerName": "St. Luke's Medical Center", "lines": [{"productId": world["gloves"], "quantity": 4}]})
    order = sal.get(f"/inventory/sales-orders/{made['id']}")
    assert made["number"].startswith("SO-") and order["status"] == "draft"
    assert order["lines"][0]["unitPrice"] == 32000 and order["totalCentavos"] == 128000  # the price list's price, nobody typed it
    assert order["warehouse"]["code"] == "MNL"  # the company's first warehouse
    sal.post(f"/inventory/sales-orders/{made['id']}/submit")
    # A Sales role writes orders up but doesn't approve them.
    assert sal.c.post(f"/inventory/sales-orders/{made['id']}/approve", headers=sal.h).status_code == 403
    approved = ana.post(f"/inventory/sales-orders/{made['id']}/approve")
    assert approved["status"] == "confirmed" and approved["delivery"]["number"].startswith("DR-")
    delivery = ana.get(f"/inventory/orders/{approved['delivery']['id']}")
    assert delivery["header"]["sourceDocument"] == made["number"] and delivery["recipient"] == "St. Luke's Medical Center"
    # The warehouse reserves and issues it: the order is delivered.
    ana.post(f"/inventory/orders/{delivery['id']}/confirm")
    ana.post(f"/inventory/orders/{delivery['id']}/issue", {})
    done = ana.get(f"/inventory/sales-orders/{made['id']}")
    assert done["status"] == "delivered" and done["lines"][0]["delivered"] == 4
    assert done["deliveries"][0]["status"] == "issued"
    links = outbox(app, "document.linked")
    assert links[-1]["from"] == {"app": "inventory", "kind": "sales_order", "id": made["id"], "number": made["number"]}


def test_a_crm_quote_becomes_an_order_once_and_the_quote_hears_back(app, client, ana, world, linked):  # noqa: F811
    quote = {"quote": {"id": "q-1", "number": "Q-2026-0001", "notes": "Deliver before noon"},
             "customer": {"kind": "company", "id": "c-1", "name": "Mercury Drug Makati", "address": "Ayala Ave, Makati"},
             "salesperson": {"id": "u-1", "name": "Ria Santos"}, "team": {"id": "t-1", "name": "B2B NBD"}, "division": {"id": "d-1", "name": "B2B"},
             "payer": {"kind": "customer"}, "raisedBy": {"name": "Ria Santos"}, "currency": "PHP",
             "lines": [{"inventoryId": world["gloves"], "code": "GLV-M", "name": "Gloves M", "quantity": 3, "freeQuantity": 1, "unitPriceCentavos": 30000,
                        "discountCentavos": 0, "totalCentavos": 90000},
                       {"inventoryId": None, "code": "NOPE", "name": "Something we don't stock", "quantity": 1, "unitPriceCentavos": 100, "totalCentavos": 100}]}
    event = {"id": "ev-quote-0001", "kind": "quote.ordered", "source": "crm", "data": quote, "occurredAt": "2026-10-29T00:00:00+00:00"}
    for _ in range(2):  # delivered twice: one order
        r = client.post("/platform/events", json={"pass": note("event", event=event)})
        assert r.status_code == 204, r.text
    orders = ana.get("/inventory/sales-orders")
    assert len(orders) == 1
    o = ana.get(f"/inventory/sales-orders/{orders[0]['id']}")
    assert o["status"] == "pending" and o["quote"] == {"id": "q-1", "number": "Q-2026-0001"}
    assert o["salesperson"]["name"] == "Ria Santos" and o["division"] == "B2B" and o["team"] == "B2B NBD"
    assert o["lines"][0]["unitPrice"] == 30000 and o["lines"][0]["freeQuantity"] == 1 and o["totalCentavos"] == 90000
    assert "Something we don't stock" in o["notes"]  # left out, and said so
    assert outbox(app, "sales_order.updated")[-1] == {"quoteId": "q-1", "id": o["id"], "number": o["number"], "status": "pending", "note": None, "deliveredAt": None, "delivery": None, "invoice": None}
    assert outbox(app, "document.linked")[0]["from"]["app"] == "crm"
    # Rejected, with the reason: the quote hears it.
    assert ana.c.post(f"/inventory/sales-orders/{o['id']}/reject", headers=ana.h, json={}).status_code == 422
    ana.post(f"/inventory/sales-orders/{o['id']}/reject", {"note": "Customer is over their credit limit"})
    told = outbox(app, "sales_order.updated")[-1]
    assert told["status"] == "rejected" and told["note"] == "Customer is over their credit limit"
    # An order from a quote isn't changed here.
    assert ana.c.put(f"/inventory/sales-orders/{o['id']}", headers=ana.h, json={"customerName": "X", "lines": [{"productId": world["gloves"], "quantity": 1}]}).status_code == 409


def test_an_order_is_cancelled_only_while_nothing_has_left(app, client, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["gloves"], "quantity": 2}]})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    delivery = ana.post(f"/inventory/sales-orders/{made['id']}/approve")["delivery"]
    ana.post(f"/inventory/orders/{delivery['id']}/confirm")  # the warehouse reserved it
    assert ana.c.post(f"/inventory/sales-orders/{made['id']}/cancel", headers=ana.h).status_code == 409
    ana.post(f"/inventory/orders/{delivery['id']}/cancel")
    assert ana.post(f"/inventory/sales-orders/{made['id']}/cancel")["status"] == "cancelled"


def test_the_sales_order_reports(app, client, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["gloves"], "quantity": 5}]})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    ana.post(f"/inventory/sales-orders/{made['id']}/approve")
    status = {r["name"]: r for r in ana.get("/inventory/reports/sales-orders-by-status")["rows"]}
    assert status["Confirmed"]["orders"] == 1 and status["Confirmed"]["value"] == 160000
    fill = ana.get("/inventory/reports/fill-rate")
    row = fill["rows"][0]
    assert (row["ordered"], row["delivered"], row["fillRate"]) == (5, 0, 0)
    assert next(c for c in fill["columns"] if c["key"] == "fillRate")["ratio"] == ["delivered", "ordered"]
