"""A person's own profile: their name in parts and contact details, and their password."""

from tests.conftest import PASSWORD, bearer, sign_in

PROFILE = {"firstName": "Ana", "middleInitial": "m.", "lastName": "Reyes", "suffix": "Jr.", "gender": "female", "phone": "+63 917 123 4567", "email": "ana@example.com", "birthday": "1990-04-02"}


def test_the_name_in_parts_makes_the_full_name(client, ana):
    before = client.get("/auth/profile", headers=ana).json()
    assert before["email"] == "ana@example.com" and before["firstName"]
    saved = client.put("/auth/profile", json=PROFILE, headers=ana).json()
    assert saved["middleInitial"] == "M" and saved["fullName"] == "Ana M. Reyes Jr."
    assert client.get("/auth/me", headers=ana).json()["user"]["fullName"] == "Ana M. Reyes Jr."
    assert (saved["gender"], saved["phone"], saved["birthday"]) == ("female", "+63 917 123 4567", "1990-04-02")


def test_what_wont_do(client, ana):
    for change, field in [({"phone": "call me"}, "phone"), ({"middleInitial": "Maria"}, "middleInitial"), ({"birthday": "2999-01-01"}, "birthday"), ({"gender": "x"}, "gender"), ({"firstName": "  "}, "firstName")]:
        r = client.put("/auth/profile", json={**PROFILE, **change}, headers=ana)
        assert r.status_code == 422, (change, r.text)


def test_a_new_email_asks_for_the_password(client, ana, ben):
    moved = {**PROFILE, "email": "ana.reyes@example.com"}
    assert client.put("/auth/profile", json=moved, headers=ana).status_code == 422
    assert client.put("/auth/profile", json={**moved, "currentPassword": "wrong"}, headers=ana).status_code == 422
    taken = client.put("/auth/profile", json={**moved, "email": "ben@example.com", "currentPassword": PASSWORD}, headers=ana)
    assert taken.status_code == 422 and "already" in taken.text
    assert client.put("/auth/profile", json={**moved, "currentPassword": PASSWORD}, headers=ana).json()["email"] == "ana.reyes@example.com"
    assert sign_in(client, "ana.reyes@example.com").status_code == 200


def test_changing_the_password_keeps_this_session_and_ends_the_others(client, ana):
    other = bearer(sign_in(client))
    assert client.post("/auth/password", json={"currentPassword": "wrong", "newPassword": "a brand new phrase"}, headers=ana).status_code == 422
    assert client.post("/auth/password", json={"currentPassword": PASSWORD, "newPassword": "short"}, headers=ana).status_code == 422
    r = client.post("/auth/password", json={"currentPassword": PASSWORD, "newPassword": "a brand new phrase"}, headers=ana)
    assert r.status_code == 200
    fresh = bearer(r)
    assert client.get("/auth/me", headers=fresh).status_code == 200
    assert client.get("/auth/me", headers=other).status_code == 401
    assert sign_in(client).status_code == 401
    assert sign_in(client, password="a brand new phrase").status_code == 200
