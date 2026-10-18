"""How stock moves: in on purchase orders, out on orders, between warehouses,
corrected by adjustments and counts, and every change on the trail."""

from datetime import date, timedelta

from tests.conftest import Api, level, receive

SOON = (date.today() + timedelta(days=30)).isoformat()
LATER = (date.today() + timedelta(days=400)).isoformat()


def test_a_purchase_order_fills_up_as_deliveries_come(ana, world):
    po = ana.post("/inventory/purchase-orders", {"supplierId": world["supplier"], "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 100, "unitCost": 18000}]})
    assert po["number"].startswith("PO-") and po["number"].endswith("-00001")
    # A draft takes no deliveries.
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"orderId": po["id"], "lines": [{"productId": world["gloves"], "quantity": 10}]})
    assert r.status_code == 409
    ana.post(f"/inventory/purchase-orders/{po['id']}/place")

    first = receive(ana, None, [{"productId": world["gloves"], "quantity": 60}], orderId=po["id"])
    assert first["orderStatus"] == "partial"
    backorders = ana.get("/inventory/backorders")
    assert [(b["product"]["sku"], b["outstanding"]) for b in backorders] == [("GLV-M", 40)]
    # More than is owed is refused.
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"orderId": po["id"], "lines": [{"productId": world["gloves"], "quantity": 41}]})
    assert r.status_code == 422
    assert receive(ana, None, [{"productId": world["gloves"], "quantity": 40}], orderId=po["id"])["orderStatus"] == "received"

    assert level(ana, world["gloves"])["onHand"] == 100
    assert ana.get("/inventory/backorders") == []
    # Received at the order's price, and that price is now the supplier's.
    receipt = ana.get(f"/inventory/receipts/{first['id']}")
    assert receipt["lines"][0]["unitCost"] == 18000
    prices = ana.get(f"/inventory/products/{world['gloves']}")["supplierPrices"]
    assert prices[0]["price"] == 18000


def test_every_change_is_on_the_trail(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 500}])
    trail = ana.get("/inventory/movements", product=world["gloves"])["items"]
    assert len(trail) == 1
    m = trail[0]
    assert (m["kind"], m["quantity"], m["onHandAfter"], m["user"]) == ("receive", 500, 500, "Ana")
    assert m["reference"].startswith("RC-") and m["warehouse"]["code"] == "MNL"


def test_batches_need_their_number_and_expiry(ana, world):
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"warehouseId": world["mnl"], "lines": [{"productId": world["pcm"], "quantity": 10}]})
    assert r.status_code == 409 and "batch number" in r.text
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"warehouseId": world["mnl"], "lines": [{"productId": world["pcm"], "quantity": 10, "batchNo": "A1"}]})
    assert r.status_code == 409 and "expiry" in r.text
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 10, "batchNo": "A1", "expiresOn": LATER}])
    assert ana.get("/inventory/batches", product=world["pcm"])[0]["batchNo"] == "A1"


def test_stock_goes_out_first_expired_first_out(ana, world):
    # The later batch arrives first; the one expiring sooner must still go first.
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 50, "batchNo": "LATE", "expiresOn": LATER}])
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 30, "batchNo": "SOON", "expiresOn": SOON}])
    order = ana.post("/inventory/orders", {"recipient": "St. Luke's", "warehouseId": world["mnl"], "lines": [{"productId": world["pcm"], "quantity": 40}]})
    ana.post(f"/inventory/orders/{order['id']}/confirm")
    ana.post(f"/inventory/orders/{order['id']}/issue", {})
    picks = ana.get(f"/inventory/orders/{order['id']}")["lines"][0]["picks"]
    assert [(p["batchNo"], p["quantity"]) for p in picks] == [("SOON", 30), ("LATE", 10)]
    left = {b["batchNo"]: b["onHand"] for b in ana.get("/inventory/batches", product=world["pcm"], empty=True)}
    assert left == {"SOON": 0, "LATE": 40}


def test_confirming_an_order_reserves_it_and_others_cant_take_it(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    first = ana.post("/inventory/orders", {"recipient": "A", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 20}]})
    ana.post(f"/inventory/orders/{first['id']}/confirm")
    lv = level(ana, world["gloves"])
    assert (lv["onHand"], lv["reserved"], lv["available"]) == (20, 20, 0)
    assert ana.get(f"/inventory/products/{world['gloves']}")["state"] == "out"

    second = ana.post("/inventory/orders", {"recipient": "B", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 1}]})
    r = ana.c.post(f"/inventory/orders/{second['id']}/confirm", headers=ana.h)
    assert r.status_code == 409 and "Not enough" in r.text
    # Nor can a transfer or an adjustment take what's held.
    t = ana.post("/inventory/transfers", {"fromWarehouseId": world["mnl"], "toWarehouseId": world["ceb"], "lines": [{"productId": world["gloves"], "quantity": 5}]})
    ana.post(f"/inventory/transfers/{t['id']}/approve")
    assert ana.c.post(f"/inventory/transfers/{t['id']}/dispatch", headers=ana.h, json={}).status_code == 409
    r = ana.c.post("/inventory/adjustments", headers=ana.h, json={"warehouseId": world["mnl"], "reason": "lost", "lines": [{"productId": world["gloves"], "quantity": 1}]})
    assert r.status_code == 409

    # Picking turns reserved into allocated; cancelling lets it all go.
    ana.post(f"/inventory/orders/{first['id']}/pick")
    assert level(ana, world["gloves"])["allocated"] == 20
    ana.post(f"/inventory/orders/{first['id']}/cancel")
    lv = level(ana, world["gloves"])
    assert (lv["reserved"], lv["allocated"], lv["available"]) == (0, 0, 20)
    kinds = [m["kind"] for m in ana.get("/inventory/movements", reference=first["id"])["items"]]
    assert kinds == ["release", "reserve"]


def test_a_transfer_is_in_transit_then_arrives_with_its_batches(ana, world):
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 100, "batchNo": "B7", "expiresOn": LATER}])
    t = ana.post("/inventory/transfers", {"fromWarehouseId": world["mnl"], "toWarehouseId": world["ceb"], "lines": [{"productId": world["pcm"], "quantity": 40}], "request": True})
    assert ana.get(f"/inventory/transfers/{t['id']}")["status"] == "requested"
    # Not before it's approved.
    assert ana.c.post(f"/inventory/transfers/{t['id']}/dispatch", headers=ana.h, json={}).status_code == 409
    ana.post(f"/inventory/transfers/{t['id']}/approve")
    ana.post(f"/inventory/transfers/{t['id']}/dispatch", {})
    assert level(ana, world["pcm"], world["mnl"])["onHand"] == 60
    assert level(ana, world["pcm"], world["ceb"])["inTransit"] == 40
    assert [a["key"] for a in ana.get("/inventory/alerts")].count("transit") == 1
    ana.post(f"/inventory/transfers/{t['id']}/receive", {})
    ceb = level(ana, world["pcm"], world["ceb"])
    assert (ceb["onHand"], ceb["inTransit"]) == (40, 0)
    balances = ana.get(f"/inventory/products/{world['pcm']}")["balances"]
    assert {(b["warehouse"]["code"], b["batch"]["batchNo"], b["onHand"]) for b in balances} == {("MNL", "B7", 60), ("CEB", "B7", 40)}
    done = ana.get(f"/inventory/transfers/{t['id']}")
    assert done["status"] == "received" and done["approvedBy"]["name"] == "Ana" and done["receivedBy"]["name"] == "Ana"


def test_warehouse_adjustments_wait_for_approval(client, people, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 500}])
    wes = Api(client, people["wes"])
    a = wes.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "lost", "notes": "Shelf short", "lines": [{"productId": world["gloves"], "quantity": 3}]})
    assert a["status"] == "pending"
    assert level(ana, world["gloves"])["onHand"] == 500
    # Wes may not approve his own; Pia (purchasing) may.
    assert client.post(f"/inventory/adjustments/{a['id']}/approve", headers=people["wes"]).status_code == 403
    Api(client, people["pia"]).post(f"/inventory/adjustments/{a['id']}/approve")
    assert level(ana, world["gloves"])["onHand"] == 497
    m = ana.get("/inventory/movements", product=world["gloves"])["items"][0]
    assert (m["kind"], m["quantity"], m["user"]) == ("lost", -3, "Pia")
    # An approver's own adjustment is posted at once.
    b = ana.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "found", "lines": [{"productId": world["gloves"], "quantity": 2}]})
    assert b["status"] == "posted" and level(ana, world["gloves"])["onHand"] == 499


def test_damaged_stock_is_set_aside_then_written_off(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}])
    ana.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "damaged", "lines": [{"productId": world["gloves"], "quantity": 4}]})
    lv = level(ana, world["gloves"])
    assert (lv["onHand"], lv["damaged"], lv["available"]) == (10, 4, 6)
    ana.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "write_off", "lines": [{"productId": world["gloves"], "quantity": 4}]})
    lv = level(ana, world["gloves"])
    assert (lv["onHand"], lv["damaged"], lv["available"]) == (6, 0, 6)


def test_a_count_becomes_an_adjustment_on_approval(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 500}])
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 200, "batchNo": "X", "expiresOn": LATER}])
    count = ana.post("/inventory/counts", {"warehouseId": world["mnl"]})
    lines = ana.get(f"/inventory/counts/{count['id']}")["lines"]
    assert sorted((line["product"]["sku"], line["expected"]) for line in lines) == [("GLV-M", 500), ("PCM-500", 200)]
    # Not every line counted: can't submit.
    ana.put(f"/inventory/counts/{count['id']}/lines", {"lines": [{"lineId": lines[0]["id"], "counted": lines[0]["expected"] - 3}]})
    assert ana.c.post(f"/inventory/counts/{count['id']}/submit", headers=ana.h).status_code == 409
    ana.put(f"/inventory/counts/{count['id']}/lines", {"lines": [{"lineId": lines[1]["id"], "counted": lines[1]["expected"]}]})
    ana.post(f"/inventory/counts/{count['id']}/submit")
    done = ana.post(f"/inventory/counts/{count['id']}/approve")
    adjustment = ana.get(f"/inventory/adjustments/{done['adjustmentId']}")
    assert adjustment["reason"] == "count" and adjustment["status"] == "posted"
    assert [line["quantity"] for line in adjustment["lines"]] == [-3]
    variance = ana.get("/inventory/reports/variance")["rows"]
    assert [r["difference"] for r in variance] == [-3]


def test_serial_numbers_follow_their_units(ana, world):
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"warehouseId": world["mnl"], "lines": [{"productId": world["pump"], "quantity": 2, "serials": ["P-1"]}]})
    assert r.status_code == 409 and "give 2" in r.text
    receive(ana, world["mnl"], [{"productId": world["pump"], "quantity": 2, "serials": ["P-1", "P-2"]}])
    # The same unit can't come in twice.
    r = ana.c.post("/inventory/receipts", headers=ana.h, json={"warehouseId": world["mnl"], "lines": [{"productId": world["pump"], "quantity": 1, "serials": ["P-2"]}]})
    assert r.status_code == 409
    order = ana.post("/inventory/orders", {"recipient": "Ward 3", "kind": "department", "warehouseId": world["mnl"], "lines": [{"productId": world["pump"], "quantity": 1}]})
    ana.post(f"/inventory/orders/{order['id']}/confirm")
    line = ana.get(f"/inventory/orders/{order['id']}")["lines"][0]
    assert ana.c.post(f"/inventory/orders/{order['id']}/issue", headers=ana.h, json={}).status_code == 409
    ana.post(f"/inventory/orders/{order['id']}/issue", {"lines": [{"lineId": line["id"], "serials": ["P-2"]}]})
    found = {s["serialNo"]: s["status"] for s in ana.get("/inventory/serials", q="P-")}
    assert found == {"P-1": "in_stock", "P-2": "issued"}
    assert order["number"].startswith("IS-")  # an issue, not a sale


def test_low_and_expiring_stock_raise_alerts(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])  # reorder point 50
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 20, "batchNo": "S", "expiresOn": SOON}])
    keys = {a["key"]: a for a in ana.get("/inventory/alerts")}
    assert keys["low"]["count"] == 1 and "Gloves M" in keys["low"]["examples"][0]
    assert keys["expiring"]["count"] == 1
    assert keys["out"]["count"] == 1  # the pump: none at all
    totals = ana.get("/inventory/dashboard")["totals"]
    assert (totals["units"], totals["value"], totals["low"], totals["out"], totals["expiring"]) == (50, 30 * 18500 + 20 * 9500, 1, 1, 1)


def test_the_home_page_has_twelve_months_of_movement(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    trend = ana.get("/inventory/dashboard")["trend"]
    assert len(trend) == 12
    assert trend[-1]["received"] == 30 and trend[-1]["issued"] == 0
    assert all(t["received"] == 0 for t in trend[:-1])


def test_the_reports_answer_and_export(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    for report in ana.get("/inventory/reports"):
        body = ana.get(f"/inventory/reports/{report['key']}")
        assert body["columns"], report["key"]
        r = ana.c.get(f"/inventory/reports/{report['key']}/csv", headers=ana.h)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    valuation = ana.get("/inventory/reports/valuation")["rows"]
    assert valuation == [{"sku": "GLV-M", "product": "Gloves M", "category": "—", "onHand": 30, "unitCost": 18500, "value": 555000, "retail": 960000}]


def test_history_is_kept_so_products_with_stock_arent_deleted(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 1}])
    assert ana.c.delete(f"/inventory/products/{world['gloves']}", headers=ana.h).status_code == 409
    assert ana.c.delete(f"/inventory/warehouses/{world['mnl']}", headers=ana.h).status_code == 409
    # How it's tracked can't change under stock kept the other way.
    assert ana.c.patch(f"/inventory/products/{world['gloves']}", headers=ana.h, json={"trackBatches": True}).status_code == 409
    # A product nothing has happened to can go.
    assert ana.c.delete(f"/inventory/products/{world['pump']}", headers=ana.h).status_code == 204


def test_transfers_show_as_routes_between_pinned_warehouses(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    ana.patch(f"/inventory/warehouses/{world['mnl']}", {"latitude": 14.5764, "longitude": 121.0851})
    t = ana.post("/inventory/transfers", {"fromWarehouseId": world["mnl"], "toWarehouseId": world["ceb"], "lines": [{"productId": world["gloves"], "quantity": 5}], "request": True})
    seen = ana.get("/inventory/transfers/map")
    route = next(x for x in seen["transfers"] if x["id"] == t["id"])
    assert route["fromPin"] == {"latitude": 14.5764, "longitude": 121.0851}
    assert route["toPin"] is None  # Cebu has no pin yet: listed, but not drawn
    assert route["firstItem"] == "Gloves M" and route["units"] == 5
    assert {w["code"] for w in seen["warehouses"]} == {"MNL", "CEB"}


def test_setup_counts_what_exists_in_order(ana, world):
    before = ana.get("/inventory/setup")
    assert (before["warehouses"], before["suppliers"], before["products"], before["stocked"], before["receipts"]) == (2, 1, 3, 0, 0)
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    after = ana.get("/inventory/setup")
    assert (after["stocked"], after["receipts"]) == (1, 1)
