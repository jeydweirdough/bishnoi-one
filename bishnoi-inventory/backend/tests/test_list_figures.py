"""The list layout's data (decided 2026-10-25): purchase orders and orders carry their lines for a
row that opens in place, and each list has its headline figures beside it."""

from tests.conftest import receive


def test_purchase_orders_carry_their_lines_and_the_figures_add_up(ana, world):
    po = ana.post("/inventory/purchase-orders", {"supplierId": world["supplier"], "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 100, "unitCost": 18000}]})
    ana.post(f"/inventory/purchase-orders/{po['id']}/place")
    receive(ana, None, [{"productId": world["gloves"], "quantity": 60}], orderId=po["id"])
    row = ana.get("/inventory/purchase-orders", limit=10)["items"][0]
    assert row["items"] == [{"sku": "GLV-M", "product": "Gloves M", "quantity": 100, "received": 60, "unitCost": 18000}]
    f = ana.get("/inventory/purchase-order-figures")
    # 40 still to come at 180.00, and 60 received this month.
    assert (f["pendingCount"], f["pendingValue"], f["lateCount"], f["receivedThisMonth"], f["receivedLastMonth"]) == (1, 40 * 18000, 0, 60 * 18000, 0)


def test_orders_carry_their_lines_and_the_figures_add_up(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    order = ana.post("/inventory/orders", {"recipient": "Mercury Drug", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 5, "unitPrice": 32000}]})
    row = ana.get("/inventory/orders", limit=10)["items"][0]
    assert row["items"] == [{"sku": "GLV-M", "product": "Gloves M", "quantity": 5, "unitPrice": 32000}]
    f = ana.get("/inventory/order-figures")
    assert (f["openCount"], f["issuedThisMonth"]) == (1, 0)
    assert order
