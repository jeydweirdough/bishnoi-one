"""Tests for the Zoho-style aggregated reports added to Inventory:
Sales by Customer, Sales by Item, Sales by Salesperson, Purchases by Vendor,
Purchases by Item, Inventory summary, Committed stock, Batch details.
"""

from datetime import date, timedelta
from tests.conftest import Api, receive

LATER = (date.today() + timedelta(days=400)).isoformat()


def test_zoho_aggregated_reports(ana, world):
    # Receive some stock
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 100, "batchNo": "Z1", "expiresOn": LATER}])

    # Create and issue an order
    order = ana.post("/inventory/orders", {"recipient": "Makati Medical Center", "warehouseId": world["mnl"], "lines": [{"productId": world["pcm"], "quantity": 25}]})
    ana.post(f"/inventory/orders/{order['id']}/confirm")
    ana.post(f"/inventory/orders/{order['id']}/issue")

    # 1. Sales by customer
    rep = ana.get("/inventory/reports/sales-by-customer")
    assert rep["title"] == "Sales by customer"
    assert len(rep["rows"]) == 1
    assert rep["rows"][0]["customer"] == "Makati Medical Center"
    assert rep["rows"][0]["quantity"] == 25

    # 2. Sales by item
    rep_item = ana.get("/inventory/reports/sales-by-item")
    assert rep_item["title"] == "Sales by item"
    assert len(rep_item["rows"]) == 1
    assert rep_item["rows"][0]["sku"] == "PCM-500"
    assert rep_item["rows"][0]["quantity"] == 25

    # 3. Sales by salesperson
    rep_sp = ana.get("/inventory/reports/sales-by-salesperson")
    assert rep_sp["title"] == "Sales by salesperson"
    assert len(rep_sp["rows"]) >= 1

    # 4. Purchases by vendor
    rep_v = ana.get("/inventory/reports/purchases-by-vendor")
    assert rep_v["title"] == "Purchases by vendor"

    # 5. Inventory summary
    rep_inv = ana.get("/inventory/reports/inventory-summary")
    assert rep_inv["title"] == "Inventory summary"
    assert any(r["sku"] == "PCM-500" for r in rep_inv["rows"])

    # 6. Batch details
    rep_b = ana.get("/inventory/reports/batch-summary")
    assert rep_b["title"] == "Batch details"
    assert any(r["batch"] == "Z1" for r in rep_b["rows"])
