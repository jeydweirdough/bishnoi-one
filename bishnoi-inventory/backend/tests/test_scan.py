"""Barcode and QR scanning (feature plan step 14c, app/routers/scan.py): one lookup for any code, and counting by scanning."""

from tests.conftest import receive


def test_a_code_is_an_item_a_batch_or_a_document(ana, world):
    ana.patch(f"/inventory/products/{world['gloves']}", {"barcode": "4800016644290"})
    assert ana.get("/inventory/scan", code=" 4800016644290 ")["product"]["id"] == world["gloves"]
    sku = ana.get(f"/inventory/products/{world['gloves']}")["sku"]
    assert ana.get("/inventory/scan", code=sku.lower())["kind"] == "product"
    r = receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])
    doc = ana.get("/inventory/scan", code=r["number"])
    assert doc["kind"] == "document" and doc["href"] == f"/inventory/receipts/{r['id']}"
    assert ana.get("/inventory/scan", code="NOTHING-123")["kind"] == "unknown"


def test_counting_by_scanning_adds_up(ana, world):
    ana.patch(f"/inventory/products/{world['gloves']}", {"barcode": "4800016644290"})
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])
    c = ana.post("/inventory/counts", {"warehouseId": world["mnl"]})
    for _ in range(3):
        last = ana.post(f"/inventory/counts/{c['id']}/scan", {"code": "4800016644290"})
    assert (last["counted"], last["expected"], last["new"]) == (3, 5, False)
    assert ana.post(f"/inventory/counts/{c['id']}/scan", {"code": "4800016644290", "quantity": 2})["counted"] == 5
    assert ana.c.post(f"/inventory/counts/{c['id']}/scan", headers=ana.h, json={"code": "NOTHING"}).status_code == 422
    ana.post(f"/inventory/counts/{c['id']}/submit")
    assert ana.c.post(f"/inventory/counts/{c['id']}/scan", headers=ana.h, json={"code": "4800016644290"}).status_code == 409


def test_packs_convert_to_the_base_unit(ana, world):
    """Units with conversions (step 14e): a pack's barcode counts the whole pack; stock stays in the base unit."""
    packs = ana.post(f"/inventory/products/{world['gloves']}/packagings", {"name": "Case", "quantity": 10, "barcode": "CASE-GLV"})
    assert packs == [{"id": packs[0]["id"], "name": "Case", "quantity": 10, "barcode": "CASE-GLV"}]
    assert ana.c.post(f"/inventory/products/{world['gloves']}/packagings", headers=ana.h, json={"name": "case", "quantity": 5}).status_code == 422
    assert ana.c.post(f"/inventory/products/{world['gloves']}/packagings", headers=ana.h, json={"name": "Pallet", "quantity": 1}).status_code == 422
    assert ana.get(f"/inventory/products/{world['gloves']}")["packagings"][0]["name"] == "Case"
    assert ana.get("/inventory/scan", code="case-glv")["pack"] == {"name": "Case", "quantity": 10}
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 25}])
    c = ana.post("/inventory/counts", {"warehouseId": world["mnl"]})
    ana.post(f"/inventory/counts/{c['id']}/scan", {"code": "CASE-GLV", "quantity": 2})
    assert ana.post(f"/inventory/counts/{c['id']}/scan", {"code": ana.get(f"/inventory/products/{world['gloves']}")["sku"]})["counted"] == 21
