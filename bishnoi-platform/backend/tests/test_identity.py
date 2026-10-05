"""Bishnoi One accounts: one sign-in, and a signed pass into each application the
person has been given, and no other."""

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tests.conftest import app_id, make_company

CRM_RETURN = "http://localhost:4302/auth/platform"


def claims_of(token: str, public_key: str) -> dict:
    head, body, sig = token.split(".")
    pad = lambda s: s + "=" * (-len(s) % 4)  # noqa: E731
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(base64.urlsafe_b64decode(pad(sig)), f"{head}.{body}".encode())
    return json.loads(base64.urlsafe_b64decode(pad(body)))


@pytest.fixture
def jade(client, ana) -> dict:
    """Jade at GetMeds (which has CRM and Pharmacy), given CRM as Salesperson, with a first password."""
    c = make_company(client, ana)
    person = client.post("/platform/users", json={"companyId": c["id"], "fullName": "Jade Madigal", "email": "jade@getmeds.test"}, headers=ana).json()["user"]
    client.put(f"/platform/users/{person['id']}/applications/{app_id(client, ana, 'crm')}", json={"role": "Salesperson"}, headers=ana)
    made = client.post(f"/platform/users/{person['id']}/password", json={}, headers=ana)
    assert made.status_code == 200, made.text
    return {"id": person["id"], "company": c, "password": made.json()["password"]}


def sign_in(client, email, password):
    return client.post("/identity/login", json={"email": email, "password": password})


def test_a_first_password_is_made_once_and_shown_once(client, ana, jade):
    assert len(jade["password"]) >= 12
    detail = client.get(f"/platform/users/{jade['id']}", headers=ana).json()["user"]
    assert detail["hasPassword"] is True
    set_by_admin = client.post(f"/platform/users/{jade['id']}/password", json={"password": "ChosenPass99"}, headers=ana)
    assert set_by_admin.json() == {"password": None}  # typed by the admin: not shown back


def test_only_platform_admins_set_passwords(client, ben, jade):
    assert client.post(f"/platform/users/{jade['id']}/password", json={}, headers=ben).status_code == 403


def test_sign_in_and_the_applications_given(client, jade):
    assert sign_in(client, "jade@getmeds.test", "wrong").status_code == 401
    r = sign_in(client, "JADE@getmeds.test", jade["password"])
    assert r.status_code == 200, r.text
    me = client.get("/identity/me", headers={"Authorization": f"Bearer {r.json()['accessToken']}"}).json()
    assert me["company"]["name"] == "GetMeds"
    assert [(a["key"], a["role"]) for a in me["apps"]] == [("crm", "Salesperson")]  # pharmacy: the company has it, she wasn't given it


def test_a_pass_into_crm_signed_by_the_platform(client, jade):
    token = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/identity/pass", json={"app": "crm", "returnTo": CRM_RETURN}, headers=h)
    assert r.status_code == 200, r.text
    key = client.get("/pass/key").json()
    claims = claims_of(r.json()["pass"], key["publicKey"])
    assert claims["aud"] == "crm" and claims["iss"] == "bishnoi-platform"
    assert (claims["email"], claims["role"], claims["companyName"]) == ("jade@getmeds.test", "Salesperson", "GetMeds")
    assert claims["exp"] - claims["iat"] == 120 and len(claims["jti"]) >= 20
    assert r.json()["returnTo"] == CRM_RETURN
    # the header names the key it was signed with
    head = json.loads(base64.urlsafe_b64decode(r.json()["pass"].split(".")[0] + "=="))
    assert head == {"alg": "EdDSA", "typ": "JWT", "kid": key["kid"]}


def test_no_pass_for_what_she_wasnt_given(client, ana, jade):
    token = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    pharmacy = client.post("/identity/pass", json={"app": "pharmacy", "returnTo": "http://localhost:4307/auth/platform"}, headers=h)
    assert pharmacy.status_code == 403 and "doesn't include Pharmacy" in pharmacy.json()["detail"]
    inventory = client.post("/identity/pass", json={"app": "inventory", "returnTo": "http://localhost:4304/auth/platform"}, headers=h)
    assert inventory.status_code == 403 and "GetMeds doesn't have Inventory" in inventory.json()["detail"]


def test_passes_go_back_only_to_the_app_or_bishnoi_exe(client, jade):
    token = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    for bad in ("https://evil.example/auth/platform", "http://localhost:4302/somewhere-else", "http://localhost:4302/auth/platform?x=1", "javascript:alert(1)"):
        assert client.post("/identity/pass", json={"app": "crm", "returnTo": bad}, headers=h).status_code == 400, bad
    desktop = client.post("/identity/pass", json={"app": "crm", "returnTo": "http://127.0.0.1:47302/auth/platform"}, headers=h)
    assert desktop.status_code == 200


def test_suspending_the_person_or_the_company_stops_it(client, ana, jade):
    token = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    client.patch(f"/platform/users/{jade['id']}", json={"status": "suspended"}, headers=ana)
    assert client.get("/identity/me", headers=h).status_code == 401
    assert sign_in(client, "jade@getmeds.test", jade["password"]).status_code == 403
    client.patch(f"/platform/users/{jade['id']}", json={"status": "active"}, headers=ana)
    client.patch(f"/platform/companies/{jade['company']['id']}", json={"status": "suspended"}, headers=ana)
    r = sign_in(client, "jade@getmeds.test", jade["password"])
    assert r.status_code == 403 and "company" in r.json()["detail"]


def test_changing_the_password_ends_other_sign_ins(client, jade):
    one = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    two = sign_in(client, "jade@getmeds.test", jade["password"]).json()["accessToken"]
    r = client.post("/identity/password", json={"currentPassword": jade["password"], "newPassword": "MyOwnPass2026"}, headers={"Authorization": f"Bearer {two}"})
    assert r.status_code == 204, r.text
    assert client.get("/identity/me", headers={"Authorization": f"Bearer {two}"}).status_code == 200
    assert client.get("/identity/me", headers={"Authorization": f"Bearer {one}"}).status_code == 401
    assert sign_in(client, "jade@getmeds.test", "MyOwnPass2026").status_code == 200


@pytest.fixture
def jade_at_two(client, ana, jade) -> dict:
    """Jade also works for Northwind (which has the CRM), as its Team Lead there."""
    north = make_company(client, ana, name="Northwind", apps=("crm",))
    person = client.post("/platform/users", json={"companyId": north["id"], "fullName": "Jade Madigal", "email": "jade@getmeds.test"}, headers=ana)
    assert person.status_code == 201, person.text
    client.put(f"/platform/users/{person.json()['user']['id']}/applications/{app_id(client, ana, 'crm')}", json={"role": "Team Lead"}, headers=ana)
    return {**jade, "north": north, "northId": person.json()["user"]["id"]}


def test_one_person_at_two_companies(client, ana, jade_at_two):
    # Her password from GetMeds works; she's at one company at a time, and sees both.
    token = sign_in(client, "jade@getmeds.test", jade_at_two["password"]).json()["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    me = client.get("/identity/me", headers=h).json()
    assert sorted((c["slug"], c["current"]) for c in me["companies"]) == [("getmeds", True), ("northwind", False)] or \
        sorted((c["slug"], c["current"]) for c in me["companies"]) == [("getmeds", False), ("northwind", True)]
    here = me["company"]["slug"]
    there = "northwind" if here == "getmeds" else "getmeds"

    # A pass for the other company, with her role there, without switching.
    key = client.get("/pass/key").json()["publicKey"]
    r = client.post("/identity/pass", json={"app": "crm", "returnTo": CRM_RETURN, "company": "northwind"}, headers=h)
    assert r.status_code == 200, r.text
    claims = claims_of(r.json()["pass"], key)
    assert (claims["companySlug"], claims["role"]) == ("northwind", "Team Lead")

    # Switching: a new sign-in there; the old one ends.
    switched = client.post("/identity/switch", json={"company": there}, headers=h)
    assert switched.status_code == 200, switched.text
    assert client.get("/identity/me", headers=h).status_code == 401
    h2 = {"Authorization": f"Bearer {switched.json()['accessToken']}"}
    assert client.get("/identity/me", headers=h2).json()["company"]["slug"] == there
    # Not a company of hers: refused.
    assert client.post("/identity/switch", json={"company": "nowhere"}, headers=h2).status_code == 403

    # One password for both: changed at one, it's changed at the other.
    assert client.post("/identity/password", json={"currentPassword": jade_at_two["password"], "newPassword": "A-new-pass-99"}, headers=h2).status_code == 204
    assert sign_in(client, "jade@getmeds.test", "A-new-pass-99").status_code == 200
    assert sign_in(client, "jade@getmeds.test", jade_at_two["password"]).status_code == 401


def test_the_same_email_twice_at_one_company_is_refused(client, ana, jade):
    again = client.post("/platform/users", json={"companyId": jade["company"]["id"], "fullName": "Jade M.", "email": "jade@getmeds.test"}, headers=ana)
    assert again.status_code == 422 and "GetMeds already has" in again.text


def test_suspended_at_one_company_she_still_works_at_the_other(client, ana, jade_at_two):
    assert client.patch(f"/platform/users/{jade_at_two['id']}", json={"status": "suspended"}, headers=ana).status_code == 200
    r = sign_in(client, "jade@getmeds.test", jade_at_two["password"])
    assert r.status_code == 200, r.text
    me = client.get("/identity/me", headers={"Authorization": f"Bearer {r.json()['accessToken']}"}).json()
    assert me["company"]["slug"] == "northwind" and [c["slug"] for c in me["companies"]] == ["northwind"]
