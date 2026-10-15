"""Lists cut into pages by the database (app/paging.py): `limit` and `offset`
give one page and the total; without them a route answers as it always has."""

from datetime import date, timedelta

from tests.conftest import receive
from tests.test_graphql import gql

LATER = (date.today() + timedelta(days=400)).isoformat()


def every_page(api, path, size, **params):
    """All the pages of a list, one after another, and the totals each one gave."""
    rows, totals, offset = [], set(), 0
    while True:
        page = api.get(path, limit=size, offset=offset, **params)
        totals.add(page["count"] if "count" in page else page["total"])  # the stock list's total is its sums
        rows += page["items"]
        if len(page["items"]) < size:
            return rows, totals
        offset += size


def busy_world(ana, world, products=7):
    """Stock in two warehouses, some held for an order, some on its way, some low and some out."""
    ids = []
    for i in range(products):
        ids.append(ana.post("/inventory/products", {"sku": f"ITEM-{i}", "name": f"Item {i:02d}", "unitCode": "box", "costPrice": 100 * (i + 1), "reorderPoint": 20})["id"])
    for i, pid in enumerate(ids[:5]):
        receive(ana, world["mnl"], [{"productId": pid, "quantity": 10 * (i + 1)}])
    receive(ana, world["ceb"], [{"productId": ids[0], "quantity": 5}, {"productId": world["gloves"], "quantity": 80}])
    order = ana.post("/inventory/orders", {"recipient": "Ward 3", "warehouseId": world["mnl"], "lines": [{"productId": ids[4], "quantity": 50}]})
    ana.post(f"/inventory/orders/{order['id']}/confirm")
    t = ana.post("/inventory/transfers", {"fromWarehouseId": world["mnl"], "toWarehouseId": world["ceb"], "lines": [{"productId": ids[3], "quantity": 15}]})
    ana.post(f"/inventory/transfers/{t['id']}/approve")
    ana.post(f"/inventory/transfers/{t['id']}/dispatch", {})
    return ids


def test_products_page_in_the_database_with_their_filters(ana, world):
    busy_world(ana, world)
    whole = ana.get("/inventory/products")
    assert isinstance(whole, list) and len(whole) == 10  # unpaged: the old answer, every product

    page = ana.get("/inventory/products", limit=4, offset=0)
    assert page["total"] == 10 and [p["id"] for p in page["items"]] == [p["id"] for p in whole[:4]]
    assert ana.get("/inventory/products", limit=4, offset=8)["items"] == whole[8:]
    assert ana.get("/inventory/products", limit=4, offset=40) == {"items": [], "total": 10}

    # Every filter, the stock state among them, is applied before the page is cut.
    for params in ({"stock": "low"}, {"stock": "out"}, {"stock": "over"}, {"q": "item"}, {"supplier": world["supplier"]}, {"status": "all", "stock": "out"}):
        rows, totals = every_page(ana, "/inventory/products", 3, **params)
        expected = ana.get("/inventory/products", **params)
        assert rows == expected, params
        assert totals == {len(expected)}, params


def test_purchase_orders_page_newest_first(ana, world):
    ids = []
    for i in range(6):
        ids.append(ana.post("/inventory/purchase-orders", {"supplierId": world["supplier"], "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": i + 1, "unitCost": 100}]})["id"])
    for po in ids[:2]:
        ana.post(f"/inventory/purchase-orders/{po}/place")
    whole = ana.get("/inventory/purchase-orders")
    assert isinstance(whole, list) and len(whole) == 6

    rows, totals = every_page(ana, "/inventory/purchase-orders", 4)
    assert {r["id"] for r in rows} == set(ids) and len(rows) == 6 and totals == {6}
    ordered = ana.get("/inventory/purchase-orders", status="ordered", limit=1)
    assert ordered["total"] == 2 and ordered["items"][0]["status"] == "ordered"
    assert ana.get("/inventory/purchase-orders", q="abc medical", limit=25)["total"] == 6
    assert ana.get("/inventory/purchase-orders", q="nobody", limit=25) == {"items": [], "total": 0}

    # The backorders the two placed orders leave behind, paged too.
    back = ana.get("/inventory/backorders", limit=1)
    assert back["total"] == 2 and len(back["items"]) == 1
    assert isinstance(ana.get("/inventory/backorders"), list)


def test_stock_pages_and_its_totals_stay_whole(ana, world):
    busy_world(ana, world)
    whole = ana.get("/inventory/stock")
    assert set(whole) == {"items", "total"}  # unpaged: the old answer

    for params in ({}, {"state": "low"}, {"state": "out"}, {"state": "ok"}, {"warehouse": world["ceb"]}, {"q": "item 0"}, {"warehouse": world["mnl"], "state": "low"}):
        expected = ana.get("/inventory/stock", **params)
        rows, counts = every_page(ana, "/inventory/stock", 2, **params)
        assert rows == expected["items"], params
        assert counts == {len(expected["items"])}, params
        # The total row sums every matching row, whichever page is shown.
        page = ana.get("/inventory/stock", limit=2, offset=0, **params)
        assert page["total"] == expected["total"], params


def test_the_other_lists_page_too(ana, world):
    for i in range(3):
        receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 10, "batchNo": f"B{i}", "expiresOn": LATER}])
    for name, path in (("batches", "/inventory/batches"), ("receipts", "/inventory/receipts")):
        whole = ana.get(path)
        rows, totals = every_page(ana, path, 2)
        assert rows == whole and totals == {3}, name
    for path in ("/inventory/suppliers", "/inventory/orders", "/inventory/reservations", "/inventory/transfers", "/inventory/adjustments", "/inventory/counts"):
        assert isinstance(ana.get(path), list), path
        page = ana.get(path, limit=5)
        assert set(page) == {"items", "total"} and page["total"] == len(ana.get(path)), path
    assert ana.c.get("/inventory/products", headers=ana.h, params={"limit": 201}).status_code == 422
    assert ana.c.get("/inventory/products", headers=ana.h, params={"limit": 0}).status_code == 422


def test_graphql_pages_as_rest_does(ana, world):
    busy_world(ana, world)
    got = gql(ana, "{ products(limit: 3, offset: 3) stock(limit: 2) purchaseOrders(limit: 5) }")
    assert "errors" not in got, got
    assert got["data"]["products"] == ana.get("/inventory/products", limit=3, offset=3)
    assert got["data"]["stock"] == ana.get("/inventory/stock", limit=2)
    assert got["data"]["purchaseOrders"] == {"items": [], "total": 0}
    # Unpaged, the same lists as before.
    assert gql(ana, "{ products }")["data"]["products"] == ana.get("/inventory/products")
    assert gql(ana, "{ products(limit: 500) }")["errors"][0]["extensions"]["code"] == "BAD_INPUT"
