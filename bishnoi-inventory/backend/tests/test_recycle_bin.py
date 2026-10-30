"""Data clean-up and the recycle bin in Inventory (2026-10-30, app/recycle_bin.py): a posted receipt goes with
its stock movements and the stock it added; restore brings both back. A product still used refuses."""

from tests.conftest import level, receive


def test_only_administrators_clean_up(client, people):
    assert client.get("/data-cleanup/kinds", headers=people["wes"]).status_code == 403
    keys = {k["key"] for k in client.get("/data-cleanup/kinds", headers=people["ana"]).json()["kinds"]}
    assert {"receipts", "products", "vendors", "warehouses"} <= keys and "users" not in keys


def test_a_posted_receipt_takes_its_stock_with_it_and_restore_brings_it_back(client, ana, world):
    r = receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 40}])
    assert level(ana, world["gloves"], world["mnl"])["onHand"] == 40
    h = ana.h
    # posted: a second confirmation
    first = client.post("/data-cleanup/kinds/receipts/delete", json={"ids": [r["id"]]}, headers=h)
    assert first.status_code == 409 and "posted" in first.text
    done = client.post("/data-cleanup/kinds/receipts/delete", json={"ids": [r["id"]], "confirmPosted": True}, headers=h)
    assert done.status_code == 200, done.text
    assert level(ana, world["gloves"], world["mnl"])["onHand"] == 0
    entry = client.get("/data-cleanup/bin", headers=h).json()["items"][0]
    assert entry["kindName"] == "Receipts"
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=h).status_code == 200
    assert level(ana, world["gloves"], world["mnl"])["onHand"] == 40


def test_a_product_still_used_refuses(client, ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])
    r = client.post("/data-cleanup/kinds/products/delete", json={"ids": [world["gloves"]]}, headers=ana.h)
    assert r.status_code == 409 and "still used" in r.text
    # one nothing uses goes, with its own rows
    r = client.post("/data-cleanup/kinds/products/delete", json={"ids": [world["pump"]]}, headers=ana.h)
    assert r.status_code == 200, r.text
