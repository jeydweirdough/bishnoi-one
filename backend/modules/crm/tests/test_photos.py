"""Optional photos on visits (2026-11-18, Step 4B, routers/photos.py): only on a visit within reach."""

import io

from modules.crm.tests.test_field import doctor, field, visit  # noqa: F401  (the fixture)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def upload(client, headers, visit_id, data=JPEG):
    return client.post("/photos", headers=headers, data={"targetType": "visit", "targetId": visit_id},
                       files={"file": ("photo.jpg", io.BytesIO(data), "image/jpeg")})


def test_an_agent_adds_photos_to_their_visit_and_their_lead_sees_them(client, field):  # noqa: F811
    v = visit(client, field["fay"], doctor(client, field, "Dr. Reyes", "fay"))
    assert upload(client, field["fay"], v["id"]).status_code == 201
    assert upload(client, field["fay"], v["id"], WEBP).status_code == 201
    listed = client.get("/photos", headers=field["lia"], params={"targetType": "visit", "targetId": v["id"]}).json()
    assert [p["contentType"] for p in listed] == ["image/jpeg", "image/webp"] and listed[0]["takenBy"]["name"] == "Fay"
    image = client.get(f"/photos/{listed[0]['id']}", headers=field["lia"])
    assert image.status_code == 200 and image.content == JPEG
    # The visit list carries them.
    assert len(client.get("/visits", headers=field["fay"]).json()["items"][0]["photos"]) == 2
    assert client.delete(f"/photos/{listed[1]['id']}", headers=field["fay"]).status_code == 204


def test_only_pictures_and_only_within_reach(client, field):  # noqa: F811
    v = visit(client, field["fay"], doctor(client, field, "Dr. Santos", "fay"))
    assert upload(client, field["fay"], v["id"], b"%PDF-1.4 not a photo").status_code == 415
    assert upload(client, field["fay"], v["id"], b"\xff\xd8\xff" + b"\x00" * 3_000_001).status_code == 413
    # Sol is on another team: the visit isn't there for him, nor its photos.
    assert upload(client, field["sol"], v["id"]).status_code == 404
    shot = upload(client, field["fay"], v["id"]).json()
    assert client.get(f"/photos/{shot['id']}", headers=field["sol"]).status_code == 404
    assert client.get("/photos", headers=field["sol"], params={"targetType": "visit", "targetId": v["id"]}).status_code == 404
    # Finn, on her team, sees only his own visits.
    assert client.delete(f"/photos/{shot['id']}", headers=field["finn"]).status_code == 404


def test_a_role_without_visits_adds_none(client, field, ben):  # noqa: F811
    v = visit(client, field["fay"], doctor(client, field, "Dr. Tan", "fay"))
    assert upload(client, ben, v["id"]).status_code == 403
    assert client.get("/photos", headers=ben, params={"targetType": "visit", "targetId": v["id"]}).status_code == 403


def test_deleting_a_visit_takes_its_photos(client, field, app):  # noqa: F811
    v = visit(client, field["fay"], doctor(client, field, "Dr. Lim", "fay"))
    shot = upload(client, field["fay"], v["id"]).json()
    assert client.delete(f"/visits/{v['id']}", headers=field["lia"]).status_code == 204
    from modules.crm.models import Photo
    with app.state.sessions() as db:
        assert db.get(Photo, shot["id"]) is None
