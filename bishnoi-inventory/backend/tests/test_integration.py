"""The CRM reads the product list and stock levels with its key."""

from fastapi.testclient import TestClient

from tests.conftest import INTEGRATION_KEY, receive

KEY = {"X-Bishnoi-Key": INTEGRATION_KEY}


def test_only_an_app_with_its_key_reads(client: TestClient, people):
    assert client.get("/integration/products").status_code == 401
    assert client.get("/integration/products", headers={"X-Bishnoi-Key": "wrong" * 8}).status_code == 401
    # A person's sign-in isn't a key.
    assert client.get("/integration/products", headers=people["ana"]).status_code == 401


def test_products_carry_the_srp_and_status(client: TestClient, ana, world):
    ana.patch(f"/inventory/products/{world['pump']}", {"status": "discontinued"})
    by_sku = {p["sku"]: p for p in client.get("/integration/products", headers=KEY).json()["items"]}
    assert set(by_sku) == {"GLV-M", "PCM-500", "PUMP"}
    assert by_sku["GLV-M"]["sellingPrice"] == 32000 and by_sku["GLV-M"]["unit"]["code"] == "box"
    assert by_sku["PUMP"]["status"] == "discontinued"


def test_stock_overall_and_per_warehouse(client: TestClient, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    receive(ana, world["ceb"], [{"productId": world["gloves"], "quantity": 100}])
    items = client.get("/integration/stock", params={"skus": "glv-m,PUMP,NOPE"}, headers=KEY).json()["items"]
    by_sku = {s["sku"]: s for s in items}
    assert set(by_sku) == {"GLV-M", "PUMP"}
    gloves = by_sku["GLV-M"]
    assert gloves["available"] == 130 and gloves["state"] == "ok"
    assert sorted((w["code"], w["available"]) for w in gloves["warehouses"]) == [("CEB", 100), ("MNL", 30)]
    assert by_sku["PUMP"]["state"] == "out" and by_sku["PUMP"]["warehouses"] == []


def test_finance_reads_suppliers_with_their_tax_registration_and_deliveries(client: TestClient, ana, world):
    """Suppliers stay here; Finance makes out bills to them (decided 2026-10-24)."""
    ana.patch(f"/inventory/suppliers/{world['supplier']}", {"tin": "123456789000", "vatStatus": "vat", "defaultAtc": "wc158"})
    found = client.get("/integration/suppliers?q=abc", headers=KEY).json()["items"]
    assert [(s["name"], s["tin"], s["vatStatus"], s["defaultAtc"]) for s in found] == [("ABC Medical Supply", "123-456-789-000", "vat", "WC158")]
    # A TIN that isn't one, or an ATC that isn't one, is refused.
    assert ana.patch(f"/inventory/suppliers/{world['supplier']}", {"tin": "12345"}, expect=422)
    assert ana.patch(f"/inventory/suppliers/{world['supplier']}", {"defaultAtc": "XX1"}, expect=422)
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10, "unitCost": 18500}], supplierId=world["supplier"], deliveryRef="DR-77")
    got = client.get(f"/integration/suppliers/{world['supplier']}/receipts", headers=KEY).json()["items"]
    assert [(r["deliveryRef"], r["totalCost"], r["lines"][0]["quantity"]) for r in got] == [("DR-77", 185000, 10)]
