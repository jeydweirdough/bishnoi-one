"""One document header on every stock document (app/documents.py, feature plan step 8): operation type,
scheduled date, done date, source document and responsible person, the same on every kind, with lists
filtered by type and by late or on time."""

from datetime import date, timedelta

from tests.conftest import receive

from app.documents import today  # noqa: E402 (the company's day, not the computer's or UTC's)

YESTERDAY = (today() - timedelta(days=1)).isoformat()
TOMORROW = (today() + timedelta(days=1)).isoformat()


def types(ana) -> dict:
    return {t["kind"]: t for t in ana.get("/inventory/operation-types") if t["isDefault"]}


def test_every_kind_has_a_default_operation_type(ana):
    assert set(types(ana)) == {"receipt", "delivery", "issue", "internal", "adjustment", "count", "return"}


def test_a_receipt_names_its_purchase_order_and_whether_it_came_late(ana, world):
    po = ana.post("/inventory/purchase-orders", {"supplierId": world["supplier"], "warehouseId": world["mnl"], "expectedOn": YESTERDAY,
                                                  "lines": [{"productId": world["gloves"], "quantity": 10, "unitCost": 18000}]})
    ana.post(f"/inventory/purchase-orders/{po['id']}/place")
    got = receive(ana, None, [{"productId": world["gloves"], "quantity": 10}], orderId=po["id"])
    header = ana.get(f"/inventory/receipts/{got['id']}")["header"]
    assert header["operationType"]["kind"] == "receipt" and header["sourceDocument"] == po["number"]
    assert header["scheduledOn"] == YESTERDAY and header["doneAt"] and header["timing"] == "late"
    assert header["responsible"]["name"] == "Ana"
    late = ana.get("/inventory/receipts", timing="late")
    assert [r["id"] for r in late] == [got["id"]]
    assert ana.get("/inventory/receipts", timing="on_time") == []


def test_an_order_is_overdue_until_issued_and_its_type_can_be_chosen(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 100}])
    sale = ana.post("/inventory/orders", {"recipient": "St. Luke's", "warehouseId": world["mnl"], "neededOn": YESTERDAY, "sourceDocument": "Customer PO 7781",
                                          "lines": [{"productId": world["gloves"], "quantity": 5}]})
    order = ana.get(f"/inventory/orders/{sale['id']}")
    assert order["header"]["operationType"]["kind"] == "delivery" and order["header"]["timing"] == "overdue"
    assert order["header"]["sourceDocument"] == "Customer PO 7781"
    assert [o["id"] for o in ana.get("/inventory/orders", timing="overdue")] == [sale["id"]]
    ana.post(f"/inventory/orders/{sale['id']}/confirm")
    ana.post(f"/inventory/orders/{sale['id']}/issue", {})
    assert ana.get(f"/inventory/orders/{sale['id']}")["header"]["timing"] == "late"
    # A type of the wrong kind is refused; one the company made is taken.
    count_type = types(ana)["count"]["id"]
    r = ana.c.post("/inventory/orders", headers=ana.h, json={"recipient": "X", "warehouseId": world["mnl"], "operationTypeId": count_type,
                                                             "lines": [{"productId": world["gloves"], "quantity": 1}]})
    assert r.status_code == 422
    rush = ana.post("/inventory/operation-types", {"code": "rush", "name": "Rush deliveries", "kind": "delivery"})
    assert rush["code"] == "RUSH"
    fast = ana.post("/inventory/orders", {"recipient": "PGH", "warehouseId": world["mnl"], "operationTypeId": rush["id"], "scheduledOn": TOMORROW,
                                          "lines": [{"productId": world["gloves"], "quantity": 1}]})
    header = ana.get(f"/inventory/orders/{fast['id']}")["header"]
    assert header["operationType"]["name"] == "Rush deliveries" and header["timing"] == "due"
    assert [o["id"] for o in ana.get("/inventory/orders", operationType=rush["id"])] == [fast["id"]]


def test_a_count_and_the_adjustment_it_makes_are_linked(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    count = ana.post("/inventory/counts", {"warehouseId": world["mnl"], "scheduledOn": TOMORROW})
    lines = ana.get(f"/inventory/counts/{count['id']}")["lines"]
    ana.put(f"/inventory/counts/{count['id']}/lines", {"lines": [{"lineId": lines[0]["id"], "counted": 48}]})
    ana.post(f"/inventory/counts/{count['id']}/submit")
    done = ana.post(f"/inventory/counts/{count['id']}/approve")
    assert ana.get(f"/inventory/counts/{count['id']}")["header"]["timing"] == "on_time"
    adjustment = ana.get(f"/inventory/adjustments/{done['adjustmentId']}")
    assert adjustment["header"]["sourceDocument"] == count["number"] and adjustment["header"]["operationType"]["kind"] == "adjustment"


def test_only_one_default_per_kind_and_the_default_stays_on(ana):
    default = types(ana)["receipt"]
    other = ana.post("/inventory/operation-types", {"code": "CONS", "name": "Consignment receipts", "kind": "receipt", "isDefault": True})
    assert types(ana)["receipt"]["id"] == other["id"]
    assert ana.c.patch(f"/inventory/operation-types/{other['id']}", headers=ana.h, json={"isActive": False}).status_code == 409
    ana.patch(f"/inventory/operation-types/{default['id']}", {"isDefault": True})
    assert types(ana)["receipt"]["id"] == default["id"]


def test_the_customer_signs_for_a_delivery(ana, world):
    """Feature plan step 10: proof of delivery, once, on an issued order."""
    import base64
    import struct

    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 200, 60) + b"\x08\x06\x00\x00\x00" + b"\x00" * 40
    signature = "data:image/png;base64," + base64.b64encode(png).decode()
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    sale = ana.post("/inventory/orders", {"recipient": "St. Luke's", "warehouseId": world["mnl"], "lines": [{"productId": world["gloves"], "quantity": 5}]})
    ana.post(f"/inventory/orders/{sale['id']}/confirm")
    early = ana.c.post(f"/inventory/orders/{sale['id']}/received", headers=ana.h, json={"name": "Maria Santos", "signature": signature})
    assert early.status_code == 409  # not issued yet
    ana.post(f"/inventory/orders/{sale['id']}/issue", {})
    bad = ana.c.post(f"/inventory/orders/{sale['id']}/received", headers=ana.h, json={"name": "Maria Santos", "signature": "data:image/png;base64,AAAA"})
    assert bad.status_code == 422
    ana.post(f"/inventory/orders/{sale['id']}/received", {"name": "Maria Santos", "signature": signature})
    got = ana.get(f"/inventory/orders/{sale['id']}")["received"]
    assert got["name"] == "Maria Santos" and got["signature"].startswith("data:image/png") and len(got["fingerprint"]) == 64
    again = ana.c.post(f"/inventory/orders/{sale['id']}/received", headers=ana.h, json={"name": "Someone else", "signature": signature})
    assert again.status_code == 409  # signed once, stays as signed
