"""Your own profile: your name in parts and contact details, and your activity.
(Changing your password is in test_auth.py: POST /auth/password.)"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import PASSWORD

PROFILE = {"firstName": "Ana", "middleInitial": "m.", "lastName": "Reyes", "suffix": "Jr.", "gender": "female", "phone": "+63 917 123 4567", "email": "ana@example.com", "birthday": "1990-04-02"}


def test_the_name_in_parts_makes_the_full_name(client, ana):
    assert client.get("/auth/account", headers=ana).json()["role"]["name"] == "Platform Admin"
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


def test_a_name_typed_in_one_piece_fills_its_parts(client, ana):
    client.patch("/auth/me", json={"fullName": "Ana Maria Santos"}, headers=ana)
    profile = client.get("/auth/profile", headers=ana).json()
    assert (profile["firstName"], profile["lastName"]) == ("Ana Maria", "Santos")


def test_my_activity_by_day(client, ana, ben):
    client.put("/auth/profile", json=PROFILE, headers=ana)
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    window = {"from": (today - timedelta(days=7)).isoformat(), "to": (today + timedelta(days=1)).isoformat()}
    mine = client.get("/auth/activity", params=window, headers=ana).json()
    assert mine["days"].get(today.isoformat(), 0) >= 1 and mine["recent"][0]["action"] == "staff.profile_changed"
    # Ben has only signed in.
    assert [e["action"] for e in client.get("/auth/activity", params=window, headers=ben).json()["recent"]] == ["auth.signed_in"]
