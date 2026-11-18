"""Packs that can be broken (owner's Step 4A, app/packs.py): which levels sell and at what price, stock written
in packs, the unit sold on the sales order and its delivery, an opened pack picked first."""

from datetime import date, timedelta

from modules.inventory.packs import in_packs, sold_as
from modules.inventory.tests.conftest import receive
from modules.inventory.tests.test_sales import outbox

LATER = (date.today() + timedelta(days=400)).isoformat()


def packs(ana, product: str, *rows: dict) -> list[dict]:
    out = []
    for r in rows:
        out = ana.post(f"/inventory/products/{product}/packagings", r)
    return out


def test_a_quantity_reads_in_packs_largest_first():
    levels = [{"name": "Strip", "quantity": 10}, {"name": "Box", "quantity": 70}]
    assert in_packs(180, levels, "tablet") == "2 Boxes + 4 Strips"
    assert in_packs(73, levels, "tablet") == "1 Box + 3 tablets"
    assert in_packs(5, levels, "tablet") is None and in_packs(0, levels, "tablet") is None and in_packs(50, [], "tablet") is None
    assert sold_as(20, "Box", 10) == "2 Boxes of 10" and sold_as(3, None, 1) is None and sold_as(15, "Box", 10) is None


def test_packs_carry_whether_they_sell_and_their_price(ana, world):
    rows = packs(ana, world["gloves"], {"name": "Case", "quantity": 10, "price": 300000}, {"name": "Pallet", "quantity": 100, "sellable": False})
    assert [(p["name"], p["sellable"], p["price"]) for p in rows] == [("Pallet", False, None), ("Case", True, 300000)]
    # A price must split evenly over the pack, so the lines stay per base unit to the centavo.
    r = ana.c.post(f"/inventory/products/{world['gloves']}/packagings", headers=ana.h, json={"name": "Half", "quantity": 3, "price": 1000})
    assert r.status_code == 422
    case = next(p for p in rows if p["name"] == "Case")
    changed = ana.patch(f"/inventory/products/{world['gloves']}/packagings/{case['id']}", {"price": None})
    assert next(p for p in changed if p["name"] == "Case")["price"] is None


def test_stock_shows_in_packs_without_changing_quantities(ana, world):
    packs(ana, world["gloves"], {"name": "Case", "quantity": 10})
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 34}])
    p = ana.get(f"/inventory/products/{world['gloves']}")
    assert p["level"]["onHand"] == 34 and p["inPacks"]["onHand"] == "3 Cases + 4 Boxes"
    assert p["warehouses"][0]["inPacks"] == "3 Cases + 4 Boxes"
    for page in (ana.get("/inventory/stock"), ana.get("/inventory/stock", limit=10)):
        row = next(r for r in page["items"] if r["product"]["id"] == world["gloves"])
        assert row["onHand"] == 34 and row["inPacks"] == "3 Cases + 4 Boxes"


def test_a_typed_order_sells_in_a_pack_at_its_price(app, client, ana, world):
    rows = packs(ana, world["gloves"], {"name": "Case", "quantity": 10, "price": 300000}, {"name": "Pallet", "quantity": 100, "sellable": False})
    case, pallet = (next(p for p in rows if p["name"] == n) for n in ("Case", "Pallet"))
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["gloves"], "quantity": 20, "packagingId": case["id"]}]})
    o = ana.get(f"/inventory/sales-orders/{made['id']}")
    line = o["lines"][0]
    assert line["quantity"] == 20 and line["unitPrice"] == 30000 and o["totalCentavos"] == 600000  # 2 cases at ₱3,000
    assert line["unit"] == {"packagingId": case["id"], "name": "Case", "per": 10, "soldAs": "2 Cases of 10"}
    # A pack that isn't sold, part of a pack, or the base unit when it isn't sold on its own: refused.
    bad = lambda lines: ana.c.post("/inventory/sales-orders", headers=ana.h, json={"customerName": "PGH", "lines": lines}).status_code  # noqa: E731
    assert bad([{"productId": world["gloves"], "quantity": 100, "packagingId": pallet["id"]}]) == 422
    assert bad([{"productId": world["gloves"], "quantity": 15, "packagingId": case["id"]}]) == 422
    ana.patch(f"/inventory/products/{world['gloves']}", {"baseSellable": False})
    assert bad([{"productId": world["gloves"], "quantity": 3}]) == 422
    # The delivery and the invoice's line say the unit sold; quantities stay in the base unit.
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    delivery = ana.post(f"/inventory/sales-orders/{made['id']}/approve")["delivery"]
    assert ana.get(f"/inventory/orders/{delivery['id']}")["lines"][0]["soldAs"] == "2 Cases of 10"
    ana.post(f"/inventory/orders/{delivery['id']}/confirm")
    ana.post(f"/inventory/orders/{delivery['id']}/issue", {})
    sale = outbox(app, "delivery.done")[-1]["salesOrder"]["lines"][0]
    assert sale["quantity"] == 20 and sale["unitPriceCentavos"] == 30000 and sale["soldAs"] == "2 Cases of 10"


def test_a_line_in_the_base_unit_stays_as_it_was(ana, world):
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["gloves"], "quantity": 4}]})
    line = ana.get(f"/inventory/sales-orders/{made['id']}")["lines"][0]
    assert line["unitPrice"] == 32000 and line["unit"]["packagingId"] is None and line["unit"]["per"] == 1 and line["unit"]["soldAs"] is None


def test_picking_takes_from_an_opened_pack_first(ana, world):
    packs(ana, world["pcm"], {"name": "Case", "quantity": 10})
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 30, "batchNo": "FULL", "expiresOn": LATER}])
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 25, "batchNo": "OPEN", "expiresOn": LATER}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["pcm"], "quantity": 5}]})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    delivery = ana.post(f"/inventory/sales-orders/{made['id']}/approve")["delivery"]
    ana.post(f"/inventory/orders/{delivery['id']}/confirm")
    ana.post(f"/inventory/orders/{delivery['id']}/issue", {})
    picks = ana.get(f"/inventory/orders/{delivery['id']}")["lines"][0]["picks"]
    assert [(p["batchNo"], p["quantity"]) for p in picks] == [("OPEN", 5)]


def test_an_earlier_expiry_still_goes_first(ana, world):
    packs(ana, world["pcm"], {"name": "Case", "quantity": 10})
    soon = (date.today() + timedelta(days=60)).isoformat()
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 30, "batchNo": "SOON", "expiresOn": soon}])
    receive(ana, world["mnl"], [{"productId": world["pcm"], "quantity": 25, "batchNo": "OPEN", "expiresOn": LATER}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["pcm"], "quantity": 5}]})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    delivery = ana.post(f"/inventory/sales-orders/{made['id']}/approve")["delivery"]
    ana.post(f"/inventory/orders/{delivery['id']}/confirm")
    ana.post(f"/inventory/orders/{delivery['id']}/issue", {})
    assert ana.get(f"/inventory/orders/{delivery['id']}")["lines"][0]["picks"][0]["batchNo"] == "SOON"

