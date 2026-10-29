"""Packages and wave picking (feature plan step 14d, app/routers/packing.py): pick → pack → ship."""

from tests.conftest import receive


def delivery(ana, world, quantity, recipient="PGH"):
    o = ana.post("/inventory/orders", {"recipient": recipient, "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": quantity}]})
    ana.post(f"/inventory/orders/{o['id']}/confirm")
    return o


def test_a_delivery_is_packed_into_numbered_boxes(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    o = delivery(ana, world, 10)
    line = ana.get(f"/inventory/orders/{o['id']}")["lines"][0]["id"]
    one = ana.post(f"/inventory/orders/{o['id']}/packages", {"lines": [{"lineId": line, "quantity": 4}], "weightKg": 2.5})
    assert one["packages"][0]["weightGrams"] == 2500 and not one["allPacked"]
    assert ana.c.post(f"/inventory/orders/{o['id']}/packages", headers=ana.h, json={"lines": [{"lineId": line, "quantity": 7}]}).status_code == 422
    two = ana.post(f"/inventory/orders/{o['id']}/packages", {})  # everything left
    assert two["allPacked"] and [(p["index"], p["of"], p["lines"][0]["quantity"]) for p in two["packages"]] == [(1, 2, 4), (2, 2, 6)]
    assert ana.c.post(f"/inventory/orders/{o['id']}/packages", headers=ana.h, json={}).status_code == 409
    after = ana.c.delete(f"/inventory/orders/{o['id']}/packages/{two['packages'][1]['id']}", headers=ana.h).json()
    assert not after["allPacked"] and after["lines"][0]["packed"] == 4


def test_a_wave_picks_several_deliveries_from_one_list(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 30}])
    a, b = delivery(ana, world, 5, "PGH"), delivery(ana, world, 7, "St. Luke's")
    w = ana.post("/inventory/waves", {"orderIds": [a["id"], b["id"]]})
    assert w["number"].startswith("WV-") and w["units"] == 12
    row = w["pickList"][0]
    assert row["total"] == 12 and row["short"] == 0 and sum(x["quantity"] for x in row["from"]) == 12
    assert {x["number"] for x in row["orders"]} == {a["number"], b["number"]}
    assert ana.get(f"/inventory/orders/{a['id']}")["status"] == "picking"
    # In one open wave at a time.
    assert ana.c.post("/inventory/waves", headers=ana.h, json={"orderIds": [a["id"]]}).status_code == 422
    assert ana.post(f"/inventory/waves/{w['id']}/done")["status"] == "done"
    ana.post(f"/inventory/orders/{a['id']}/issue", {})
    assert ana.get(f"/inventory/orders/{a['id']}")["status"] == "issued"
