"""Profile pictures: a person sets their own, admins set their company's, and
everyone in the company can see them. No picture means initials on the screens."""

from io import BytesIO

import pytest
from PIL import Image

from app.photos import MAX_UPLOAD_BYTES


def png(size=(900, 600), colour=(40, 90, 140)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, colour).save(buf, "PNG")
    return buf.getvalue()


def upload(client, path: str, headers: dict, data: bytes = None, name: str = "me.png", kind: str = "image/png"):
    return client.put(path, files={"photo": (name, png() if data is None else data, kind)}, headers=headers)


def ids(client, headers) -> dict[str, str]:
    return {u["email"].split("@")[0]: u["id"] for u in client.get("/admin/users", headers=headers).json()}


def test_a_person_sets_and_removes_their_own(client, as_):
    ana = as_("ana")
    assert client.get("/auth/me", headers=ana).json()["user"]["photoAt"] is None

    r = upload(client, "/me/photo", ana)
    assert r.status_code == 200, r.text
    when = r.json()["photoAt"]
    assert client.get("/auth/me", headers=ana).json()["user"]["photoAt"] == when

    me = client.get("/auth/me", headers=ana).json()["user"]
    picture = client.get(f"/people/{me['id']}/photo", headers=ana)
    assert picture.status_code == 200
    assert picture.headers["content-type"] == "image/webp"
    assert picture.headers["cache-control"] == "private, max-age=300"
    assert Image.open(BytesIO(picture.content)).size == (256, 256)  # cropped square, whatever went in

    # Asking again with the tag we were given costs nothing.
    again = client.get(f"/people/{me['id']}/photo", headers={**ana, "If-None-Match": picture.headers["etag"]})
    assert again.status_code == 304

    assert client.delete("/me/photo", headers=ana).status_code == 204
    assert client.get("/auth/me", headers=ana).json()["user"]["photoAt"] is None
    assert client.get(f"/people/{me['id']}/photo", headers=ana).status_code == 404


def test_colleagues_can_see_it_and_outsiders_cannot(client, as_, acme):
    ana = as_("ana")
    upload(client, "/me/photo", ana)
    ana_id = client.get("/auth/me", headers=ana).json()["user"]["id"]

    assert client.get(f"/people/{ana_id}/photo", headers=as_("carmen")).status_code == 200  # same company
    assert client.get(f"/people/{ana_id}/photo", headers=acme).status_code == 404  # another company
    assert client.get(f"/people/{ana_id}/photo").status_code == 401  # signed out


def test_only_pictures_and_only_small_ones(client, as_):
    ana = as_("ana")
    r = upload(client, "/me/photo", ana, data=b"this is not a picture", name="notes.txt", kind="text/plain")
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["body", "photo"]

    too_big = b"\x89PNG\r\n\x1a\n" + b"x" * MAX_UPLOAD_BYTES
    r = upload(client, "/me/photo", ana, data=too_big)
    assert r.status_code == 422 and "MB" in r.json()["detail"][0]["msg"]


def test_admins_manage_their_own_companys_people(client, as_):
    carmen = as_("carmen")
    ben = ids(client, carmen)["ben"]

    r = upload(client, f"/admin/users/{ben}/photo", carmen)
    assert r.status_code == 200, r.text
    listed = {u["id"]: u["photoAt"] for u in client.get("/admin/users", headers=carmen).json()}
    assert listed[ben] == r.json()["photoAt"]
    assert client.get(f"/admin/users/{ben}", headers=carmen).json()["photoAt"] == r.json()["photoAt"]

    assert client.delete(f"/admin/users/{ben}/photo", headers=carmen).status_code == 204
    assert client.get(f"/admin/users/{ben}", headers=carmen).json()["photoAt"] is None

    # A rep can't set someone else's.
    assert upload(client, f"/admin/users/{ben}/photo", as_("ana")).status_code == 403


def test_someone_who_works_in_two_companies_keeps_their_own_picture(client, as_, acme, app):
    from app.seed import add_person
    from app.tenancy import set_company
    from tests.test_tenancy import ACME

    with app.state.sessions() as db:
        set_company(db, ACME)
        add_person(db, "ana@pharmacrm.test", "Ana Reyes", "ignored", [("rep", "bnb", "bnb", "general")])

    carmen = as_("carmen")
    ana_id = ids(client, carmen)["ana"]
    r = upload(client, f"/admin/users/{ana_id}/photo", carmen)
    assert r.status_code == 409 and "another company" in r.json()["detail"]
    # She still can herself.
    assert upload(client, "/me/photo", as_("ana")).status_code == 200


def test_the_change_is_audited_without_the_picture(client, as_):
    ana = as_("ana")
    upload(client, "/me/photo", ana)
    entries = client.get("/admin/audit", headers=as_("carmen")).json()["items"]
    assert entries[0]["action"] == "person.photo_changed" and entries[0]["target"] == "ana@pharmacrm.test"
    assert entries[0]["fields"] == []


@pytest.mark.parametrize("shape", [(1200, 400), (400, 1200), (64, 64)])
def test_any_shape_comes_out_square(client, as_, shape):
    ana = as_("ana")
    assert upload(client, "/me/photo", ana, data=png(shape)).status_code == 200
    me = client.get("/auth/me", headers=ana).json()["user"]
    picture = client.get(f"/people/{me['id']}/photo", headers=ana)
    assert Image.open(BytesIO(picture.content)).size == (256, 256)
