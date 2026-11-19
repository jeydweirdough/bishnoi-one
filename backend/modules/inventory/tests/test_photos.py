"""Optional photos on deliveries and packages (2026-11-18, Step 4B, routers/photos.py)."""

import io

from modules.inventory.tests.conftest import receive, sold

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def upload(client, headers, target_type, target_id, data=JPEG, name="photo.jpg"):
    return client.post("/inventory/photos", headers=headers, data={"targetType": target_type, "targetId": target_id},
                       files={"file": (name, io.BytesIO(data), "image/jpeg")})


def delivery(ana, world):
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 20}])
    return sold(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 5}])


def test_photos_of_a_delivery_are_added_listed_shown_and_removed(client, ana, world, people):
    o = delivery(ana, world)
    for data in (PNG, JPEG, WEBP):
        assert upload(client, ana.h, "delivery", o["id"], data).status_code == 201
    listed = ana.get("/inventory/photos", targetType="delivery", targetId=o["id"])
    assert [p["contentType"] for p in listed] == ["image/png", "image/jpeg", "image/webp"]
    assert listed[0]["takenBy"]["name"] == "Ana" and listed[0]["canRemove"]
    image = client.get(f"/inventory/photos/{listed[1]['id']}", headers=people["aud"])
    assert image.status_code == 200 and image.content == JPEG and image.headers["content-type"] == "image/jpeg"
    assert client.delete(f"/inventory/photos/{listed[0]['id']}", headers=ana.h).status_code == 204
    assert len(ana.get("/inventory/photos", targetType="delivery", targetId=o["id"])) == 2


def test_only_pictures_are_taken(client, ana, world):
    o = delivery(ana, world)
    r = upload(client, ana.h, "delivery", o["id"], b"%PDF-1.4 not a photo", "x.jpg")
    assert r.status_code == 415
    assert upload(client, ana.h, "delivery", o["id"], b"\xff\xd8\xff" + b"\x00" * 3_000_001).status_code == 413
    assert upload(client, ana.h, "delivery", "no-such-delivery").status_code == 404
    assert client.post("/inventory/photos", headers=ana.h, data={"targetType": "visit", "targetId": o["id"]},
                       files={"file": ("p.jpg", io.BytesIO(JPEG), "image/jpeg")}).status_code == 422


def test_who_may_add_and_remove(client, ana, world, people):
    o = delivery(ana, world)
    assert upload(client, people["aud"], "delivery", o["id"]).status_code == 403  # sees, changes nothing
    wes = upload(client, people["wes"], "delivery", o["id"])  # issues deliveries
    assert wes.status_code == 201
    mine = upload(client, ana.h, "delivery", o["id"]).json()
    assert not next(p for p in client.get("/inventory/photos", headers=people["wes"], params={"targetType": "delivery", "targetId": o["id"]}).json()
                    if p["id"] == mine["id"])["canRemove"]
    assert client.delete(f"/inventory/photos/{mine['id']}", headers=people["wes"]).status_code == 403
    assert client.delete(f"/inventory/photos/{wes.json()['id']}", headers=people["aud"]).status_code == 403
    assert client.delete(f"/inventory/photos/{wes.json()['id']}", headers=people["wes"]).status_code == 204  # their own


def test_a_package_has_its_photos_and_they_go_when_it_is_unpacked(client, ana, world):
    o = delivery(ana, world)
    ana.post(f"/inventory/orders/{o['id']}/confirm")
    box = ana.post(f"/inventory/orders/{o['id']}/packages", {})["packages"][0]
    assert upload(client, ana.h, "package", box["id"]).status_code == 201
    assert len(ana.get(f"/inventory/orders/{o['id']}/packages")["packages"][0]["photos"]) == 1
    assert client.delete(f"/inventory/orders/{o['id']}/packages/{box['id']}", headers=ana.h).status_code == 200
    assert client.get("/inventory/photos", headers=ana.h, params={"targetType": "package", "targetId": box["id"]}).status_code == 404


def test_deleting_a_delivery_takes_its_photos_and_restore_brings_them_back(client, ana, world):
    o = delivery(ana, world)
    assert upload(client, ana.h, "delivery", o["id"]).status_code == 201
    r = client.post("/data-cleanup/kinds/deliveries/delete", json={"ids": [o["id"]]}, headers=ana.h)
    assert r.status_code == 200, r.text
    entry = client.get("/data-cleanup/bin", headers=ana.h).json()["items"][0]
    assert client.post(f"/data-cleanup/bin/{entry['id']}/restore", headers=ana.h).status_code == 200
    photo = ana.get("/inventory/photos", targetType="delivery", targetId=o["id"])[0]
    assert client.get(f"/inventory/photos/{photo['id']}", headers=ana.h).content == JPEG
