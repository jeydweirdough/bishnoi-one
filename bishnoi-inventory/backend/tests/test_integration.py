"""The CRM reads the product list and stock levels with its key."""

from fastapi.testclient import TestClient

from tests.conftest import INTEGRATION_KEY, receive

KEY = {"X-Nabhi-Key": INTEGRATION_KEY}


def test_only_an_app_with_its_key_reads(client: TestClient, people):
    assert client.get("/integration/products").status_code == 401
    assert client.get("/integration/products", headers={"X-Nabhi-Key": "wrong" * 8}).status_code == 401
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
