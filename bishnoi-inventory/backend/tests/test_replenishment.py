"""Replenishment (feature plan step 15a, app/replenishment.py): when to order and how many from use and lead time,
draft purchase orders per vendor, by hand or at night."""

from tests.conftest import receive


def test_what_to_order_and_the_drafts_it_makes(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 60}])
    o = ana.post("/inventory/orders", {"recipient": "PGH", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 45}]})
    ana.post(f"/inventory/orders/{o['id']}/confirm")
    ana.post(f"/inventory/orders/{o['id']}/issue", {})  # 15 left; reorder point 50
    plan = ana.get("/inventory/replenishment", warehouse=world["mnl"])
    gloves = next(r for r in plan["rows"] if r["product"]["id"] == world["gloves"])
    assert gloves["leadDays"] == 5 and gloves["safetyDays"] == 3 and gloves["available"] == 15
    assert gloves["dailyUse"] == 0.5 and gloves["orderPoint"] == 50  # 45 used in 90 days; 4 over 8 days is under the reorder point
    assert gloves["suggested"] == 50 + 1 - 15  # no maximum: the order point plus its reorder quantity (at least one)
    pcm = next(r for r in plan["rows"] if r["product"]["id"] == world["pcm"])
    assert pcm["supplier"] is None  # no usual vendor: left out of the drafts, and said so

    made = ana.post("/inventory/replenishment/drafts", {"warehouseId": world["mnl"]})
    assert len(made["made"]) == 1 and made["made"][0]["supplier"] == "ABC Medical Supply"
    assert world["pcm"] in [p["id"] for p in made["needVendor"]]
    po = ana.get(f"/inventory/purchase-orders/{made['made'][0]['id']}")
    assert po["status"] == "draft" and po["lines"][0]["quantity"] == 36 and po["lines"][0]["unitCost"] == 18500
    # A draft already made counts as on order: nothing more is due for the gloves.
    again = ana.get("/inventory/replenishment", warehouse=world["mnl"])
    assert world["gloves"] not in [r["product"]["id"] for r in again["rows"]]


def test_the_settings_and_the_nightly_run(app, ana, world):
    s = ana.put("/inventory/replenishment/settings", {"safetyDays": 5, "defaultLeadDays": 10, "historyDays": 30, "automatic": True})
    assert s["automatic"] and s["safetyDays"] == 5
    from app.replenishment import nightly
    from tests.test_platform_roles import database

    with database(app)() as db:
        assert nightly(db) == 2  # the gloves are under their reorder point with nothing on hand, in each warehouse
    assert any(p["status"] == "draft" for p in ana.get("/inventory/purchase-orders"))
