"""Signing in with a Nabhi account: a pass signed by the platform opens a
session here, once, for the right person with the right role."""

import base64
import json
import secrets
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models import User
from tests.test_auth import PASSWORD, app, client  # noqa: F401  (the fixtures)

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_pass(key=KEY, **over) -> str:
    """A pass as the platform makes it (nabhi-platform app/passes.py)."""
    now = int(time.time())
    claims = {
        "iss": "nabhi-platform", "aud": "exec", "sub": "identity-1", "email": "jade@getmeds.test", "name": "Jade Madigal",
        "company": "c1", "companyName": "GetMeds", "role": "Executive Assistant", "appAdmin": False, "companyAdmin": False,
        "iat": now, "exp": now + 120, "jti": secrets.token_urlsafe(18), **over,
    }
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT", "kid": "test"}).encode())
    body = b64(json.dumps(claims).encode())
    return f"{head}.{body}.{b64(key.sign(f'{head}.{body}'.encode()))}"


@pytest.fixture
def linked(app):
    app.state.settings.platform_public_key = PUBLIC
    return app


def take(client, token):
    return client.post("/auth/platform", json={"pass": token})


def me(client, r):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['accessToken']}"}).json()


def test_someone_new_is_added_with_their_role(client, linked):
    r = take(client, make_pass())
    assert r.status_code == 200, r.text
    who = me(client, r)
    assert (who["user"]["email"], who["user"]["fullName"], who["role"]["name"]) == ("jade@getmeds.test", "Jade Madigal", "Executive Assistant")
    # next time: the same person, found by their Nabhi account
    again = take(client, make_pass(name="Jade M. Madigal"))
    assert me(client, again)["user"]["id"] == who["user"]["id"]
    assert me(client, again)["user"]["fullName"] == "Jade M. Madigal"


def test_a_pass_works_once(client, linked):
    token = make_pass()
    assert take(client, token).status_code == 200
    second = take(client, token)
    assert second.status_code == 401 and "already used" in second.json()["detail"]


@pytest.mark.parametrize(
    ("token", "why"),
    [
        (lambda: make_pass(key=Ed25519PrivateKey.generate()), "isn't valid"),
        (lambda: make_pass(aud="inventory"), "another application"),
        (lambda: make_pass(iss="someone-else"), "another application"),
        (lambda: make_pass(exp=int(time.time()) - 300), "expired"),
        (lambda: "not.a.pass-at-all-but-long-enough", "isn't valid"),
    ],
)
def test_passes_that_are_refused(client, linked, token, why):
    r = take(client, token())
    assert r.status_code == 401 and why in r.json()["detail"], r.text


def test_not_set_up_without_the_platform_key(client, app):
    r = take(client, make_pass())
    assert r.status_code == 401 and "isn't set up" in r.json()["detail"]


def test_an_application_admin_is_an_administrator_here(client, linked):
    assert me(client, take(client, make_pass(appAdmin=True, role="Executive Assistant")))["role"]["name"] == "Administrator"


def test_an_existing_account_is_linked_by_email_and_its_role_follows_the_platform(app, client, linked):
    before = client.post("/auth/login", json={"email": "ben@example.com", "password": PASSWORD})
    assert before.status_code == 200
    r = take(client, make_pass(email="BEN@example.com", sub="identity-9", role="Administrator", name="Ben Cruz"))
    who = me(client, r)
    assert (who["user"]["email"], who["role"]["name"]) == ("ben@example.com", "Administrator")
    with app.state.sessions() as db:
        assert db.query(User).filter_by(email="ben@example.com").one().platform_identity_id == "identity-9"


def test_a_role_this_app_doesnt_have(client, linked):
    r = take(client, make_pass(role="Pharmacist"))
    assert r.status_code == 403 and "Pharmacist" in r.json()["detail"]


def test_someone_switched_off_here_stays_out(app, client, linked):
    assert take(client, make_pass()).status_code == 200
    with app.state.sessions() as db:
        db.query(User).filter_by(email="jade@getmeds.test").update({"is_active": False})
        db.commit()
    r = take(client, make_pass())
    assert r.status_code == 403 and "switched off" in r.json()["detail"]
