"""Business events (app/business_events.py, feature plan step 7): issuing a sales order is told to the
other apps as "delivery.done", saved with the change itself (Finance invoices from it in Stage 4)."""

from datetime import date, timedelta

from sqlalchemy import select

from modules.inventory.business_events import OutboxEvent
from modules.inventory.tests.conftest import receive, sold
from modules.inventory.tests.test_platform_roles import database

LATER = (date.today() + timedelta(days=400)).isoformat()


def test_issuing_a_sales_order_is_told_as_a_delivery(app, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 100}])
    sale = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 40}], "St. Luke's")
    ana.post(f"/inventory/orders/{sale['id']}/confirm")
    ana.post(f"/inventory/orders/{sale['id']}/issue", {})
    # Stock sent to a department isn't a sale: not told.
    internal = ana.post("/inventory/orders", {"recipient": "Ward 3", "kind": "department", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 5}]})
    ana.post(f"/inventory/orders/{internal['id']}/confirm")
    ana.post(f"/inventory/orders/{internal['id']}/issue", {})
    with database(app)() as db:
        # The sales order tells its own news too (sales_order.updated, document.linked); one delivery is told.
        out = db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "delivery.done")).all()
        assert len(out) == 1
        assert out[0].data["number"] == sale["number"] and out[0].data["lines"][0]["sku"] == "GLV-M" and out[0].data["lines"][0]["quantity"] == 40
        assert out[0].slug == "getmeds" and out[0].sent_at is None  # not connected here: kept


def test_a_receipt_and_an_adjustment_are_linked_to_where_they_came_from(app, ana, world):
    """Feature plan step 9: the purchase order and its receipt, the count and its adjustment."""
    po = ana.post("/inventory/purchase-orders", {"supplierId": world["supplier"], "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 10, "unitCost": 100}]})
    ana.post(f"/inventory/purchase-orders/{po['id']}/place")
    got = receive(ana, None, [{"productId": world["gloves"], "quantity": 10}], orderId=po["id"])
    count = ana.post("/inventory/counts", {"warehouseId": world["mnl"]})
    lines = ana.get(f"/inventory/counts/{count['id']}")["lines"]
    ana.put(f"/inventory/counts/{count['id']}/lines", {"lines": [{"lineId": lines[0]["id"], "counted": 9}]})
    ana.post(f"/inventory/counts/{count['id']}/submit")
    done = ana.post(f"/inventory/counts/{count['id']}/approve")
    with database(app)() as db:
        links = [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "document.linked").order_by(OutboxEvent.occurred_at))]
    assert links[0] == {"from": {"app": "inventory", "kind": "purchase_order", "id": po["id"], "number": po["number"]},
                        "to": {"app": "inventory", "kind": "receipt", "id": got["id"], "number": got["number"]}}
    assert links[1]["from"]["kind"] == "count" and links[1]["to"] == {"app": "inventory", "kind": "adjustment", "id": done["adjustmentId"], "number": links[1]["to"]["number"]}
