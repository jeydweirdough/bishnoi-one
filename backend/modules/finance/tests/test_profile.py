"""A person's own profile: their name in parts and contact details, their password, and their activity."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .test_auth import PASSWORD, bearer, sign_in
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)

PROFILE = {"firstName": "Ana", "middleInitial": "m.", "lastName": "Reyes", "suffix": "Jr.", "gender": "female", "phone": "+63 917 123 4567", "email": "ana@example.com", "birthday": "1990-04-02"}


def test_the_name_in_parts_makes_the_full_name(client, ana):
    first = client.get("/auth/profile", headers=ana).json()
    assert first["email"] == "ana@example.com" and (first["firstName"], first["lastName"]) == ("Ana", "Reyes")
    saved = client.put("/auth/profile", json=PROFILE, headers=ana).json()
    assert saved["middleInitial"] == "M" and saved["fullName"] == "Ana M. Reyes Jr."
    assert client.get("/auth/me", headers=ana).json()["user"]["fullName"] == "Ana M. Reyes Jr."
    for change in ({"phone": "call me"}, {"middleInitial": "Maria"}, {"birthday": "2999-01-01"}, {"gender": "x"}):
        assert client.put("/auth/profile", json={**PROFILE, **change}, headers=ana).status_code == 422


def test_a_new_email_asks_for_the_password(client, ana):
    moved = {**PROFILE, "email": "ana.reyes@example.com"}
    assert client.put("/auth/profile", json=moved, headers=ana).status_code == 422
    taken = client.put("/auth/profile", json={**moved, "email": "ben@example.com", "currentPassword": PASSWORD}, headers=ana)
    assert taken.status_code == 422
    assert client.put("/auth/profile", json={**moved, "currentPassword": PASSWORD}, headers=ana).json()["email"] == "ana.reyes@example.com"


def test_changing_the_password_keeps_this_session_and_ends_the_others(client, ana):
    other = bearer(sign_in(client))
    assert client.post("/auth/password", json={"currentPassword": "wrong", "newPassword": "a brand new phrase"}, headers=ana).status_code == 422
    r = client.post("/auth/password", json={"currentPassword": PASSWORD, "newPassword": "a brand new phrase"}, headers=ana)
    assert r.status_code == 200
    assert client.get("/auth/me", headers=bearer(r)).status_code == 200
    assert client.get("/auth/me", headers=other).status_code == 401
    assert sign_in(client, password="a brand new phrase").status_code == 200


def test_my_activity_by_day(client, ana, ben):
    client.put("/auth/profile", json=PROFILE, headers=ana)
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    window = {"from": (today - timedelta(days=7)).isoformat(), "to": (today + timedelta(days=1)).isoformat()}
    mine = client.get("/auth/activity", params=window, headers=ana).json()
    assert mine["days"].get(today.isoformat(), 0) >= 1 and mine["recent"][0]["action"] == "user.profile_changed"
    assert client.get("/auth/activity", params=window, headers=ben).json()["days"] == {}
