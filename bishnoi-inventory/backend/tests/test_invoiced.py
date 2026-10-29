"""Automatic invoicing (feature plan step 13), the Sales app's side: the delivery tells Finance what was sold;
Finance's invoice.issued and invoice.paid close the order's chain, and the order-to-cash report counts the days."""

from tests.conftest import receive
from tests.test_platform_roles import note
from tests.test_platform_sign_in import linked  # noqa: F401 (fixture)
from tests.test_sales import outbox
from tests.test_shipping import a_delivery


def test_the_delivery_carries_the_sale_and_finance_closes_the_chain(app, client, ana, world, linked):  # noqa: F811
    d = a_delivery(ana, world, quantity=3)
    so = d["salesOrder"]
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    done = [e for e in outbox(app, "delivery.done") if e["orderId"] == d["id"]][0]
    sale = done["salesOrder"]
    assert sale["number"] == so["number"] and sale["customer"]["name"] == "PGH"
    assert sale["lines"] == [{"sku": sale["lines"][0]["sku"], "name": sale["lines"][0]["name"], "quantity": 3, "freeQuantity": 0,
                              "unitPriceCentavos": 32000, "discountCentavos": 0, "vatCategory": "standard"}]

    issued = {"id": "ev-inv-1", "kind": "invoice.issued", "source": "finance", "occurredAt": "2026-10-29T00:00:00+00:00",
              "data": {"id": "inv-1", "number": "SI-000101", "totalCentavos": 96000, "deliveryId": d["id"], "salesOrderId": so["id"]}}
    assert client.post("/platform/events", json={"pass": note("event", event=issued)}).status_code == 204
    order = ana.get(f"/inventory/sales-orders/{so['id']}")
    assert order["invoice"]["number"] == "SI-000101" and order["invoice"]["paidAt"] is None

    paid = {"id": "ev-inv-2", "kind": "invoice.paid", "source": "finance", "occurredAt": "2026-10-29T00:00:00+00:00",
            "data": {"id": "inv-1", "number": "SI-000101", "salesOrderId": so["id"], "paidAt": "2026-10-30T02:00:00+00:00"}}
    assert client.post("/platform/events", json={"pass": note("event", event=paid)}).status_code == 204
    assert ana.get(f"/inventory/sales-orders/{so['id']}")["invoice"]["paidAt"].startswith("2026-10-30")

    report = ana.get("/inventory/reports/order-to-cash")
    row = next(r for r in report["rows"] if r["order"] == so["number"])
    assert row["stage"] == "Paid" and row["invoice"] == "SI-000101" and row["orderToCash"] is not None


def test_an_order_not_yet_invoiced_shows_where_it_waits(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}])
    d = a_delivery(ana, world, quantity=1)
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    row = next(r for r in ana.get("/inventory/reports/order-to-cash")["rows"] if r["order"] == d["salesOrder"]["number"])
    assert row["stage"] == "Delivered" and row["toInvoice"] is None
