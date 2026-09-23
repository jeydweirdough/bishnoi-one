"""Inventory: products, prices, promos and discounts."""

from datetime import date, timedelta

from tests.conftest import field_messages, price_list_in

CEFALEXIN = {"code": "cef-250", "name": "Cefalexin 250 mg", "unit": "Box of 100", "prices": {"srp": 98000, "patient": 90000}}


def test_inventory_staff_keep_products_and_prices(client, as_):
    iris = as_("iris")
    products = client.get("/inventory/products", headers=iris).json()
    assert {p["code"] for p in products} == {"AMOX-500", "PARA-SYR", "ASC-500", "MET-500", "PNV-30"}

    r = client.post("/inventory/products", json=CEFALEXIN, headers=iris)
    assert r.status_code == 201 and r.json()["code"] == "CEF-250"
    product_id = r.json()["id"]
    assert client.post("/inventory/products", json=CEFALEXIN, headers=iris).status_code == 409

    # Special Price is typed per quote; it isn't kept on the price list.
    r = client.put(f"/inventory/products/{product_id}/prices", json={"prices": {"special": 100}}, headers=iris)
    assert r.status_code == 422
    r = client.put(f"/inventory/products/{product_id}/prices", json={"prices": {"patient": None, "doctor": 85000}}, headers=iris)
    assert r.json()["prices"] == {"srp": 98000, "doctor": 85000}

    b2c_codes = lambda: {p["code"] for p in price_list_in(client, as_("ana"), "b2c")["products"]}  # noqa: E731
    assert "CEF-250" in b2c_codes()
    assert client.patch(f"/inventory/products/{product_id}", json={"isActive": False}, headers=iris).status_code == 200
    assert "CEF-250" not in b2c_codes()
    assert "CEF-250" not in {p["code"] for p in client.get("/inventory/products", headers=iris).json()}


def test_who_can_touch_inventory(client, as_):
    assert client.get("/inventory/products", headers=as_("ana")).status_code == 403
    assert client.get("/inventory/products", headers=as_("joy")).status_code == 403  # Finance, not Inventory
    ramon = as_("ramon")
    assert client.get("/inventory/products", headers=ramon).status_code == 200
    assert client.post("/inventory/products", json=CEFALEXIN, headers=ramon).status_code == 403


def test_the_summary_counts_missing_prices(client, as_):
    counts = client.get("/inventory/summary", headers=as_("iris")).json()["counts"]
    assert counts == {"products": 5, "missingPrices": 1, "runningPromos": 4}


def test_promos(client, as_):
    iris = as_("iris")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    start = (date.today() - timedelta(days=2)).isoformat()

    r = client.post("/inventory/promos", json={"name": "Half off", "kind": "percent", "startsOn": start, "divisionCodes": ["b2c"]}, headers=iris)
    assert r.status_code == 422 and field_messages(r) == {"percentBp": "Enter the percent off."}
    tiers = [{"minQty": 5, "percentBp": 300}, {"minQty": 5, "percentBp": 500}]
    r = client.post("/inventory/promos", json={"name": "Tiers", "kind": "tiered", "tiers": tiers, "startsOn": start, "divisionCodes": ["hos"]}, headers=iris)
    assert field_messages(r) == {"tiers": "Each tier needs its own minimum quantity."}

    promo = {"name": "Metformin 5% off", "kind": "percent", "percentBp": 500, "startsOn": start, "productIds": [ids["MET-500"]], "divisionCodes": ["b2c"]}
    r = client.post("/inventory/promos", json=promo, headers=iris)
    assert r.status_code == 201 and r.json()["state"] == "running"
    promo_id = r.json()["id"]

    promos_in = lambda module, who: {p["name"] for p in price_list_in(client, as_(who), module)["promos"]}  # noqa: E731
    assert "Metformin 5% off" in promos_in("b2c", "ana")
    assert "Metformin 5% off" not in promos_in("hos", "grace")

    r = client.put(f"/inventory/promos/{promo_id}", json={**promo, "divisionCodes": ["b2c", "hos"]}, headers=iris)
    assert r.json()["divisionCodes"] == ["b2c", "hos"]
    assert "Metformin 5% off" in promos_in("hos", "grace")

    assert client.patch(f"/inventory/promos/{promo_id}", json={"isActive": False}, headers=iris).json()["state"] == "off"
    assert "Metformin 5% off" not in promos_in("b2c", "ana")
    assert [p["id"] for p in client.get("/inventory/promos", params={"state": "off"}, headers=iris).json()] == [promo_id]
