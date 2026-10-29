"""Quality checks on receipt (feature plan step 14a, app/quality.py): a warehouse that checks what it receives
holds it until its check; passed is released for use, failed is put aside as damaged with why."""

from tests.conftest import level, receive


def test_goods_wait_for_their_check_then_pass_or_fail(ana, world):
    ana.patch(f"/inventory/warehouses/{world['mnl']}", {"qualityCheck": True})
    r = receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    check_id = r["qualityCheck"]["id"]
    held = level(ana, world["gloves"], world["mnl"])
    assert (held["onHand"], held["onHold"], held["available"]) == (50, 50, 0)  # on hand, not usable yet
    # Nothing on hold can be reserved.
    order = ana.post("/inventory/orders", {"recipient": "PGH", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 5}]})
    assert ana.c.post(f"/inventory/orders/{order['id']}/confirm", headers=ana.h).status_code == 409

    checks = ana.get("/inventory/quality-checks")
    assert checks["waiting"] == 1 and checks["items"][0]["receipt"]["number"] == r["number"]
    check = ana.get(f"/inventory/quality-checks/{check_id}")
    line = check["lines"][0]
    # Passed and failed add up to what was received; a failure says why.
    assert ana.c.post(f"/inventory/quality-checks/{check_id}/done", headers=ana.h, json={"lines": [{"lineId": line["id"], "passed": 40, "failed": 5}]}).status_code == 422
    assert ana.c.post(f"/inventory/quality-checks/{check_id}/done", headers=ana.h, json={"lines": [{"lineId": line["id"], "passed": 45, "failed": 5}]}).status_code == 422
    done = ana.post(f"/inventory/quality-checks/{check_id}/done", {"lines": [{"lineId": line["id"], "passed": 45, "failed": 5, "reason": "damaged", "note": "Crushed carton"}]})
    assert (done["status"], done["passed"], done["failed"]) == ("done", 45, 5)
    after = level(ana, world["gloves"], world["mnl"])
    assert (after["onHand"], after["onHold"], after["damaged"], after["available"]) == (50, 0, 5, 45)
    ana.post(f"/inventory/orders/{order['id']}/confirm")  # now there's stock for it
    assert ana.c.post(f"/inventory/quality-checks/{check_id}/done", headers=ana.h, json={"lines": [{"lineId": line["id"], "passed": 50}]}).status_code == 409


def test_a_warehouse_that_doesnt_check_takes_goods_in_at_once(ana, world):
    r = receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}])
    assert r["qualityCheck"] is None
    assert level(ana, world["gloves"], world["mnl"])["available"] == 10
