"""Signing in safely on one's own (2026-10-30, app/sign_in.py): password rules, a lockout kept in the
database, forgot password and invitations by one-time link, a handed-over password changed at the first
sign-in, two-step sign-in with an authenticator app, and people imported from a file."""

import time

from app import sign_in
from app.models import Account, SignInLink
from tests.test_company_access import getmeds, modules  # noqa: F401 (fixtures)


def account(app, email):
    with app.state.sessions() as db:
        return db.query(Account).filter(Account.email == email).one()


def test_password_rules():
    assert sign_in.password_problem("short") is not None
    assert sign_in.password_problem("password123") is not None
    assert sign_in.password_problem("aaaaaaaaaa") is not None
    assert sign_in.password_problem("jade.madigal.2026", "jade@getmeds.test") is not None
    assert sign_in.password_problem("Madigal-river-77", None, "Jade Madigal") is not None
    assert sign_in.password_problem("tall-mango-river-77", "jade@getmeds.test", "Jade Madigal") is None


def test_wrong_passwords_are_counted_in_the_database(client, getmeds):
    for _ in range(5):
        assert client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "wrong-one-here"}).status_code == 401
    r = client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "wrong-one-here"})
    assert r.status_code == 429 and "Try again" in r.text


def test_a_handed_over_password_is_changed_at_the_first_sign_in(client, getmeds):
    h, jade = getmeds["owner"]["h"], getmeds["jade"]
    given = client.post(f"/identity/access/people/{jade['id']}/password", json={}, headers=h).json()["password"]
    signed = client.post("/identity/login", json={"email": "jade@getmeds.test", "password": given}).json()
    assert signed["mustChangePassword"] is True
    jh = {"Authorization": f"Bearer {signed['accessToken']}"}
    assert client.get("/identity/me", headers=jh).json()["mustChangePassword"] is True
    # no app opens until it's changed
    refused = client.post("/identity/pass", json={"app": "crm", "returnTo": "http://localhost:9/auth/platform"}, headers=jh)
    assert refused.status_code == 403 and "Change the password" in refused.text
    assert client.post("/identity/password", json={"currentPassword": given, "newPassword": given}, headers=jh).status_code == 422
    assert client.post("/identity/password", json={"currentPassword": given, "newPassword": "tall-mango-river-77"}, headers=jh).status_code == 204
    assert client.get("/identity/me", headers=jh).json()["mustChangePassword"] is False


def test_forgot_password_and_invitations_by_one_time_link(app, client, getmeds, monkeypatch):
    sent = []
    monkeypatch.setattr(sign_in, "send", lambda db, settings, company_id, to, subject, text: sent.append((to, text)) or True)
    # an unknown email answers the same, and sends nothing
    assert client.post("/identity/password/forgot", json={"email": "nobody@getmeds.test"}).status_code == 204 and not sent
    assert client.post("/identity/password/forgot", json={"email": "jade@getmeds.test"}).status_code == 204
    to, text = sent[-1]
    token = text.split("reset=")[1].split()[0]
    assert to == "jade@getmeds.test"
    info = client.get("/identity/password/link", params={"token": token}).json()
    assert info["kind"] == "reset" and info["email"] == "jade@getmeds.test"
    bad = client.post("/identity/password/set", json={"token": token, "password": "password1"})
    assert bad.status_code == 422
    assert client.post("/identity/password/set", json={"token": token, "password": "tall-mango-river-77"}).status_code == 204
    assert client.post("/identity/password/set", json={"token": token, "password": "tall-mango-river-78"}).status_code == 404  # once
    assert client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).status_code == 200
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).status_code == 401  # her other sign-ins ended
    # an invitation: emailed, and given back to copy
    r = client.post(f"/identity/access/people/{getmeds['rio']['id']}/invite", headers=getmeds["owner"]["h"])
    assert r.status_code == 200 and r.json()["emailed"] is True and "/password?invite=" in r.json()["link"]
    invite = r.json()["link"].split("invite=")[1]
    assert client.get("/identity/password/link", params={"token": invite}).json()["kind"] == "invite"


def test_two_step_sign_in(app, client, getmeds):
    from tests.conftest import PASSWORD  # noqa: F401

    h = getmeds["jade"]["h"]
    # Jade's password, set by the fixture: read it back by setting a known one through a reset link
    with app.state.sessions() as db:
        acc = db.query(Account).filter(Account.email == "jade@getmeds.test").one()
        token = sign_in.make_link(db, acc, "reset", 1)
        db.commit()
    client.post("/identity/password/set", json={"token": token, "password": "tall-mango-river-77"})
    h = {"Authorization": "Bearer " + client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).json()["accessToken"]}
    assert client.post("/identity/two-step/start", json={"password": "wrong"}, headers=h).status_code == 422
    started = client.post("/identity/two-step/start", json={"password": "tall-mango-river-77"}, headers=h).json()
    assert started["uri"].startswith("otpauth://totp/") and started["qr"].startswith("data:image/svg+xml;base64,")
    assert client.post("/identity/two-step/confirm", json={"code": "000000"}, headers=h).status_code in (409, 422)
    on = client.post("/identity/two-step/confirm", json={"code": sign_in.code_now(started["secret"])}, headers=h).json()
    assert on["on"] and len(on["recoveryCodes"]) == 10
    # signing in now takes the code
    first = client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).json()
    assert first == {"twoStep": True, "ticket": first["ticket"]}
    assert client.post("/identity/login/code", json={"ticket": first["ticket"], "code": "123456"}).status_code == 401
    done = client.post("/identity/login/code", json={"ticket": first["ticket"], "code": sign_in.code_now(started["secret"])})
    assert done.status_code == 200 and done.json()["accessToken"]
    # a recovery code works once
    second = client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).json()
    code = on["recoveryCodes"][0]
    used = client.post("/identity/login/code", json={"ticket": second["ticket"], "code": code}).json()
    assert used["recoveryCodesLeft"] == 9
    third = client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).json()
    assert client.post("/identity/login/code", json={"ticket": third["ticket"], "code": code}).status_code == 401
    # an administrator resets it (a lost phone)
    assert client.post(f"/identity/access/people/{getmeds['jade']['id']}/two-step/reset", headers=getmeds["owner"]["h"]).json() == {"reset": True}
    assert "accessToken" in client.post("/identity/login", json={"email": "jade@getmeds.test", "password": "tall-mango-river-77"}).json()


def test_two_step_is_required_of_administrators_where_it_is_required(app, client, getmeds):
    app.state.settings.require_two_step = True
    h = getmeds["owner"]["h"]
    me = client.get("/identity/me", headers=h).json()
    assert me["twoStep"] == {"on": False, "needed": True}
    refused = client.get("/identity/access", headers=h)
    assert refused.status_code == 403 and "two-step" in refused.text
    assert client.get("/identity/me", headers=getmeds["jade"]["h"]).json()["twoStep"]["needed"] is False  # not an administrator


def test_people_are_imported_from_a_file_checked_first_then_all_at_once(client, getmeds, monkeypatch):
    monkeypatch.setattr(sign_in, "send", lambda *a, **k: False)
    h = getmeds["owner"]["h"]
    role = client.post("/identity/access/roles", json={"name": "Medical rep", "permissions": {"crm": ["customers.view"]}}, headers=h).json()
    rows = [
        {"fullName": "Kay Lim", "email": "kay@getmeds.test", "title": "Rep", "role": "medical rep", "apps": ["CRM"]},
        {"fullName": "Jade Madigal", "email": "jade@getmeds.test"},
        {"fullName": "No Email", "email": "not-an-email"},
        {"fullName": "Kay Again", "email": "kay@getmeds.test"},
        {"fullName": "Odd Role", "email": "odd@getmeds.test", "role": "Pilot", "apps": ["Spaceship"]},
    ]
    check = client.post("/identity/access/people/import", json={"rows": rows}, headers=h).json()
    assert [r["outcome"] for r in check["rows"]] == ["new", "already", "problem", "problem", "problem"]
    assert check["rows"][0]["role"] == role["name"] and check["rows"][0]["apps"] == ["crm"]
    assert client.post("/identity/access/people/import", json={"rows": rows, "apply": True}, headers=h).status_code == 422  # all or none
    done = client.post("/identity/access/people/import", json={"rows": rows[:2], "apply": True, "invite": True}, headers=h).json()
    assert done["added"] == 1 and done["invited"] == 1 and done["emailed"] == 0
    people = {p["email"]: p for p in client.get("/identity/access", headers=h).json()["people"]}
    assert people["kay@getmeds.test"]["roleId"] == role["id"] and [a["key"] for a in people["kay@getmeds.test"]["apps"]] == ["crm"]
