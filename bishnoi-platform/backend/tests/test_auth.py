"""Signing in and out, staff roles, sessions, and the security log."""

from tests.conftest import PASSWORD, bearer, sign_in


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "app": "platform"}


def test_sign_in_and_see_who_you_are(client):
    r = sign_in(client, "ANA@example.com")
    assert r.status_code == 200, r.text
    assert r.json()["expiresIn"] == 10 * 3600
    me = client.get("/auth/me", headers=bearer(r)).json()
    assert me["user"]["email"] == "ana@example.com"
    assert me["isDeveloperAdmin"] is True and me["org"] is None
    assert me["platformRole"] == "admin" and me["canAdminister"] is True


def test_support_sees_but_cannot_change_the_platform(client, ben):
    me = client.get("/auth/me", headers=ben).json()
    assert me["platformRoleName"] == "Support" and me["canAdminister"] is False
    assert client.get("/platform/companies", headers=ben).status_code == 200
    r = client.post("/platform/companies", json={"name": "Nope"}, headers=ben)
    assert r.status_code == 403


def test_wrong_passwords_are_security_events_and_lock_out(client, ana):
    for _ in range(5):
        assert sign_in(client, "ben@example.com", "wrong").status_code == 401
    assert sign_in(client, "ben@example.com").status_code == 429
    events = client.get("/platform/activity?category=security", headers=ana).json()["entries"]
    assert sum(e["action"] == "auth.sign_in_failed" for e in events) == 5
    assert any(e["action"] == "auth.signed_in" for e in events)


def test_session_length_comes_from_settings(client, ana):
    r = client.put("/platform/settings/security", json={"sessionHours": 2, "loginAttempts": 5, "lockoutMinutes": 15}, headers=ana)
    assert r.status_code == 200, r.text
    assert sign_in(client, "ben@example.com").json()["expiresIn"] == 2 * 3600


def test_change_password_keeps_this_session_ends_others(client):
    first = bearer(sign_in(client))
    second = bearer(sign_in(client))
    r = client.post("/auth/password", json={"currentPassword": PASSWORD, "newPassword": "a brand new one"}, headers=first)
    assert r.status_code == 204, r.text
    assert client.get("/auth/me", headers=first).status_code == 200
    assert client.get("/auth/me", headers=second).status_code == 401
    bad = client.post("/auth/password", json={"currentPassword": "nope", "newPassword": "another one!"}, headers=first)
    assert bad.status_code == 422


def test_admin_ends_someone_elses_session_support_cannot(client, ana, ben):
    sessions = client.get("/platform/sessions", headers=ana).json()["sessions"]
    bens = next(s for s in sessions if s["staff"]["name"] == "Ben Cruz")
    anas = next(s for s in sessions if s["isYours"])
    assert client.delete(f"/platform/sessions/{anas['id']}", headers=ben).status_code == 403
    assert client.delete(f"/platform/sessions/{bens['id']}", headers=ana).status_code == 204
    assert client.get("/auth/me", headers=ben).status_code == 401


def test_staff_roles_and_not_yourself(client, ana, ben):
    staff = client.get("/platform/staff", headers=ana).json()["staff"]
    ana_id = next(s["id"] for s in staff if s["email"] == "ana@example.com")
    ben_id = next(s["id"] for s in staff if s["email"] == "ben@example.com")
    assert client.patch(f"/platform/staff/{ana_id}", json={"isActive": False}, headers=ana).status_code == 409
    r = client.patch(f"/platform/staff/{ben_id}", json={"role": "admin"}, headers=ana)
    assert r.json()["staff"]["roleName"] == "Platform Admin"
    assert client.get("/auth/me", headers=ben).json()["canAdminister"] is True
    roles = client.get("/platform/access/roles", headers=ana).json()
    support = next(r for r in roles["staffRoles"] if r["role"] == "member")
    assert support["holders"] == [] and all(p["action"] != "Change" for p in support["permissions"])


def test_logout(client):
    headers = bearer(sign_in(client))
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_you_change_your_own_name_and_email(client, ana):
    from tests.conftest import PASSWORD, sign_in

    r = client.patch("/auth/me", json={"fullName": "Ana R. Reyes"}, headers=ana)
    assert r.status_code == 200 and r.json()["user"]["fullName"] == "Ana R. Reyes"
    # A new email needs your password, and can't be someone else's.
    assert client.patch("/auth/me", json={"email": "ana.reyes@example.com"}, headers=ana).status_code == 422
    assert client.patch("/auth/me", json={"email": "ben@example.com", "currentPassword": PASSWORD}, headers=ana).status_code == 422
    r = client.patch("/auth/me", json={"email": "Ana.Reyes@example.com", "currentPassword": PASSWORD}, headers=ana)
    assert r.status_code == 200 and r.json()["user"]["email"] == "ana.reyes@example.com"
    assert sign_in(client, "ana.reyes@example.com").status_code == 200
