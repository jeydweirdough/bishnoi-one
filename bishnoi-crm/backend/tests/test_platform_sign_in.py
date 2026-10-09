"""Signing in with a Bishnoi One account: a pass signed by the platform opens a
session here, once, for the right person with the right role."""

import base64
import json
import secrets
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models import User

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_pass(key=KEY, **over) -> str:
    """A pass as the platform makes it (bishnoi-platform app/passes.py)."""
    now = int(time.time())
    claims = {
        "iss": "bishnoi-platform", "aud": "crm", "sub": "identity-1", "email": "jade@getmeds.test", "name": "Jade Madigal",
        "company": "c1", "companySlug": "getmeds", "companyName": "GetMeds", "role": "Salesperson", "appAdmin": False, "companyAdmin": False,
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
    assert (who["user"]["email"], who["user"]["fullName"], who["role"]["name"]) == ("jade@getmeds.test", "Jade Madigal", "Salesperson")
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
    assert me(client, take(client, make_pass(appAdmin=True, role="Salesperson")))["role"]["name"] == "Administrator"


def test_an_existing_account_is_linked_by_email_and_its_role_follows_the_platform(app, client, linked):
    before = client.post("/auth/login", json={"email": "ben@example.com", "password": "correct horse battery"})
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
    r = take(client, make_pass())
    assert r.status_code == 200, r.text
    with app.state.sessions() as db:
        db.query(User).filter_by(email="jade@getmeds.test").update({"is_active": False})
        db.commit()
    r = take(client, make_pass())
    assert r.status_code == 403 and "switched off" in r.json()["detail"]


def test_a_pass_signed_before_the_rename_is_still_taken(client, linked):
    # The platform may still sign passes as "nabhi-platform" until it's redeployed.
    assert take(client, make_pass(iss="nabhi-platform")).status_code == 200


def test_the_pass_names_the_company(client, linked):
    """Each company's people come in to that company's own database: the same
    person, in two companies, is two accounts, one in each."""
    here = take(client, make_pass())
    there = take(client, make_pass(companySlug="northwind", company="c2", companyName="Northwind"))
    assert here.status_code == 200 and there.status_code == 200, there.text
    assert here.json()["accessToken"].startswith("getmeds.") and there.json()["accessToken"].startswith("northwind.")
    assert me(client, here)["user"]["id"] != me(client, there)["user"]["id"]
    # A pass that doesn't say, or names a company that isn't one, opens nothing.
    assert take(client, make_pass(companySlug=None)).status_code == 401
    assert take(client, make_pass(companySlug="nowhere")).status_code == 403


def test_the_pass_and_the_platform_must_agree_on_the_company(app, client, linked, monkeypatch):
    """With the platform checking companies, a pass whose company isn't the one
    the platform has under that name is refused."""
    from app import company
    from tests.test_company import Answer, company_pass

    company.forget()
    app.state.settings = app.state.settings.model_copy(update={"platform_api_url": "https://platform.test"})
    monkeypatch.setattr(company.httpx, "get", lambda url, params=None, timeout=None: Answer(200, {"pass": company_pass(key=KEY)}))
    try:
        r = take(client, make_pass(company="someone-else"))
        assert r.status_code == 403 and "isn't for this company" in r.json()["detail"]
        assert take(client, make_pass(company="co-1")).status_code == 200
    finally:
        company.forget()


def test_the_platforms_key_is_fetched_from_the_platform(app, client, monkeypatch):
    """No PLATFORM_PUBLIC_KEY on the server: the CRM asks the platform for it, and again when it's replaced."""
    import httpx

    from app import company, platform_pass
    from tests.test_company import Answer, company_pass

    platform_pass.forget_key()
    company.forget()
    app.state.settings.platform_public_key = None
    app.state.settings.platform_api_url = "https://platform.test"
    asked = []
    keys = {"now": "not-the-key="}

    def get(url, params=None, headers=None, timeout=None):
        if url.endswith("/pass/key"):
            asked.append(url)
            return Answer(200, {"publicKey": keys["now"]})
        return Answer(200, {"pass": company_pass(key=KEY)})

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(platform_pass, "AGAIN", 0)
    # The first key it was given is wrong (the platform replaced it): it asks again, and the pass is taken.
    platform_pass.public_key(app.state.settings)
    keys["now"] = PUBLIC
    r = take(client, make_pass(company="co-1"))  # the company the stand-in platform has
    assert r.status_code == 200, r.text
    assert len(asked) == 2
    platform_pass.forget_key()
    company.forget()
