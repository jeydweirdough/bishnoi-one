"""Packages (feature plan step 14d, app/routers/packing.py): pick → pack → ship. Wave picking was removed 2026-11-17."""

from modules.inventory.tests.conftest import receive, sold


def delivery(ana, world, quantity, recipient="PGH"):
    o = sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": quantity}], recipient)
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
