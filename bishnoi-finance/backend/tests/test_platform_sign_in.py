"""Signing in with a Bishnoi One account: a pass signed by the platform opens a
session here, once, for the right person with the right role."""

import base64
import json
import secrets
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import User
from app.routers.auth import attempts
from app.security import hash_password

PASSWORD = "correct horse battery"
KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


@pytest.fixture
def app(tmp_path):
    attempts.clear()
    settings = Settings(_env_file=None, allowed_hosts=["testserver"], database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    app = create_app(settings)
    with app.state.sessions() as db:
        db.add(User(email="ana@example.com", full_name="Ana Reyes", password_hash=hash_password(PASSWORD), role="admin"))
        db.add(User(email="ben@example.com", full_name="Ben Cruz", password_hash=hash_password(PASSWORD)))
        db.commit()
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_pass(key=KEY, **over) -> str:
    """A pass as the platform makes it (bishnoi-platform app/passes.py)."""
    now = int(time.time())
    claims = {
        "iss": "bishnoi-platform", "aud": "finance", "sub": "identity-1", "email": "jade@getmeds.test", "name": "Jade Madigal",
        "company": "c1", "companyName": "GetMeds", "role": "Accountant", "appAdmin": False, "companyAdmin": False,
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


def role_of(app, email):
    with app.state.sessions() as db:
        return db.query(User).filter_by(email=email).one().role.name


def test_someone_new_is_added_as_staff(app, client, linked):
    r = take(client, make_pass())
    assert r.status_code == 200, r.text
    who = me(client, r)
    assert (who["user"]["email"], who["user"]["fullName"], who["canManageSettings"]) == ("jade@getmeds.test", "Jade Madigal", False)
    assert role_of(app, "jade@getmeds.test") == "Finance Staff"
    # next time: the same person, found by their Bishnoi One account
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
        (lambda: make_pass(aud="crm"), "another application"),
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


def test_an_application_admin_is_an_admin_here(app, client, linked):
    r = take(client, make_pass(appAdmin=True, role="Accountant"))
    assert me(client, r)["canManageSettings"] is True
    assert role_of(app, "jade@getmeds.test") == "Administrator"


def test_the_administrator_role_is_an_admin_here(app, client, linked):
    r = take(client, make_pass(role="Administrator"))
    assert me(client, r)["canManageSettings"] is True
    assert role_of(app, "jade@getmeds.test") == "Administrator"


def test_an_existing_member_is_linked_by_email_and_its_role_follows_the_platform(app, client, linked):
    before = client.post("/auth/login", json={"email": "ben@example.com", "password": PASSWORD})
    assert before.status_code == 200 and me(client, before)["canManageSettings"] is False
    r = take(client, make_pass(email="BEN@example.com", sub="identity-9", role="Administrator", name="Ben Cruz"))
    who = me(client, r)
    assert (who["user"]["email"], who["canManageSettings"]) == ("ben@example.com", True)
    with app.state.sessions() as db:
        ben = db.query(User).filter_by(email="ben@example.com").one()
        assert (ben.platform_identity_id, ben.role.name) == ("identity-9", "Administrator")


def test_someone_switched_off_here_stays_out(app, client, linked):
    assert take(client, make_pass()).status_code == 200
    with app.state.sessions() as db:
        db.query(User).filter_by(email="jade@getmeds.test").update({"is_active": False})
        db.commit()
    r = take(client, make_pass())
    assert r.status_code == 403 and "switched off" in r.json()["detail"]


def test_the_first_pass_naming_the_company_signs_in_and_remembers_it(app, client, linked):
    """The company named on a pass is kept for the events this app sends (app/business_events.py).
    Written while the sign-in held SQLite's write lock, through a second connection, it waited
    for that same request's lock and every sign-in failed with "database isn't answering"
    (2026-10-29, Malou on the local site). It's kept once the sign-in is saved."""
    from app import business_events

    assert business_events.company_slug(app.state.settings) is None
    r = take(client, make_pass(companySlug="2mg"))
    assert r.status_code == 200, r.text
    assert business_events.company_slug(app.state.settings) == "2mg"
    assert me(client, r)["user"]["email"] == "jade@getmeds.test"
    # Next time the same company: nothing to write, still signs in.
    assert take(client, make_pass(companySlug="2mg")).status_code == 200
