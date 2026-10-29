"""Shipping with couriers (feature plan step 12, app/shipping.py): a delivery's courier, tracking number and fee;
out for delivery once issued, then delivered (signed for, or the courier's photo) or failed and sent again."""

import base64
from datetime import date, timedelta

from tests.conftest import receive
from tests.test_sales import outbox

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64).decode()


def courier(ana, code: str) -> dict:
    return next(c for c in ana.get("/inventory/couriers") if c["code"] == code)


def a_delivery(ana, world, quantity=2, scheduled: date | None = None) -> dict:
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    made = ana.post("/inventory/sales-orders", {"customerName": "PGH", "lines": [{"productId": world["gloves"], "quantity": quantity}],
                                                 **({"scheduledOn": scheduled.isoformat()} if scheduled else {})})
    ana.post(f"/inventory/sales-orders/{made['id']}/submit")
    return {**ana.post(f"/inventory/sales-orders/{made['id']}/approve")["delivery"], "salesOrder": made}


def test_every_company_has_the_three_couriers_and_adds_its_own(ana):
    assert [c["code"] for c in ana.get("/inventory/couriers")] == ["LBC", "JNT", "LALAMOVE"]
    assert ana.c.post("/inventory/couriers", headers=ana.h, json={"code": "grab", "name": "Grab Express", "trackingUrl": "grab.com"}).status_code == 422
    made = ana.post("/inventory/couriers", {"code": "grab", "name": "Grab Express"})
    assert made["code"] == "GRAB" and made["isActive"]
    assert ana.patch(f"/inventory/couriers/{made['id']}", {"isActive": False})["isActive"] is False


def test_a_delivery_goes_by_courier_and_is_delivered_with_the_couriers_photo(app, ana, world):
    d = a_delivery(ana, world, scheduled=date.today() + timedelta(days=3))
    lbc = courier(ana, "LBC")
    ship = ana.put(f"/inventory/orders/{d['id']}/shipping", {"method": "courier", "courierId": lbc["id"], "trackingNumber": "LBC123", "fee": 15000, "feeCharged": True})
    assert ship["courier"]["name"] == "LBC Express" and ship["trackingUrl"].endswith("LBC123") and ship["fee"] == 15000 and ship["status"] is None
    # Nothing is delivered before it leaves the warehouse.
    assert ana.c.post(f"/inventory/orders/{d['id']}/delivered", headers=ana.h, json={"receivedBy": "Nurse Cruz"}).status_code == 409
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    order = ana.get(f"/inventory/orders/{d['id']}")
    assert order["shipping"]["status"] == "out" and order["shipping"]["attempts"] == 1
    done = [e for e in outbox(app, "delivery.done") if e["orderId"] == d["id"]][0]
    assert done["shipping"] == {"method": "courier", "courier": "LBC Express", "trackingNumber": "LBC123", "fee": 15000, "feeCharged": True}
    # The courier's proof: who received it, and their photo.
    got = ana.post(f"/inventory/orders/{d['id']}/delivered", {"receivedBy": "Nurse Cruz", "photo": PNG})
    assert got["status"] == "delivered" and got["onTime"] is True and got["hasPhoto"]
    assert ana.c.get(f"/inventory/orders/{d['id']}/delivery-photo", headers=ana.h).headers["content-type"] == "image/png"
    so = ana.get(f"/inventory/sales-orders/{d['salesOrder']['id']}")
    assert so["deliveries"][0]["shipping"]["status"] == "delivered"
    # Delivered stays delivered.
    assert ana.c.put(f"/inventory/orders/{d['id']}/shipping", headers=ana.h, json={"method": "own"}).status_code == 409


def test_a_failed_delivery_goes_out_again_and_signing_for_it_delivers_it(ana, world):
    d = a_delivery(ana, world)
    ana.put(f"/inventory/orders/{d['id']}/shipping", {"method": "own"})
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    assert ana.c.post(f"/inventory/orders/{d['id']}/failed", headers=ana.h, json={"reason": ""}).status_code == 422
    failed = ana.post(f"/inventory/orders/{d['id']}/failed", {"reason": "Nobody at the receiving area"})
    assert failed["status"] == "failed" and failed["failedReason"] == "Nobody at the receiving area"
    again = ana.post(f"/inventory/orders/{d['id']}/send-again", {})
    assert again["status"] == "out" and again["attempts"] == 2
    signed = ana.post(f"/inventory/orders/{d['id']}/received", {"name": "Dr. Santos", "signature": PNG_SIGNATURE})
    assert signed["receivedBy"] == "Dr. Santos"
    assert ana.get(f"/inventory/orders/{d['id']}")["shipping"]["status"] == "delivered"


def test_the_shipping_reports(ana, world):
    d = a_delivery(ana, world, scheduled=date.today() - timedelta(days=1))  # promised yesterday: late
    ana.put(f"/inventory/orders/{d['id']}/shipping", {"method": "courier", "courierId": courier(ana, "JNT")["id"], "fee": 9000})
    ana.post(f"/inventory/orders/{d['id']}/confirm")
    ana.post(f"/inventory/orders/{d['id']}/issue", {})
    ana.post(f"/inventory/orders/{d['id']}/delivered", {"receivedBy": "Front desk"})
    report = ana.get("/inventory/reports/deliveries-by-courier")
    row = next(r for r in report["rows"] if r["name"] == "J&T Express")
    assert (row["deliveries"], row["delivered"], row["late"], row["onTimeRate"], row["fees"]) == (1, 1, 1, 0, 9000)
    assert next(c for c in report["columns"] if c["key"] == "onTimeRate")["ratio"] == ["onTime", "promised"]
    assert ana.get("/inventory/reports/on-time-delivery")["rows"][0]["late"] == 1
    assert ana.get("/inventory/orders?delivery=delivered")[0]["id"] == d["id"]


# A real (tiny) PNG, as the signature pad sends it: 20 × 20 pixels.
def _png(width: int, height: int) -> str:
    import struct
    import zlib

    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    body = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + body).decode()


PNG_SIGNATURE = _png(40, 20)
