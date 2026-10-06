"""A company must be registered on the platform to use the CRM (app/company.py):
active, and given the CRM. The platform is stood in for with a signed company pass."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import company
from tests.conftest import PASSWORD, sign_in

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def company_pass(status="active", granted=True, slug="getmeds", key=KEY, exp=None, **more) -> str:
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    body = b64(json.dumps({
        "iss": "bishnoi-platform", "aud": "crm", "kind": "company", "company": "co-1", "slug": slug,
        "companyName": "GetMeds", "status": status, "granted": granted, "exp": exp or int(time.time()) + 3600, **more,
    }).encode())
    return f"{head}.{body}.{b64(key.sign(f'{head}.{body}'.encode()))}"


class Answer:
    def __init__(self, status_code, data=None):
        self.status_code, self.data = status_code, data

    def json(self):
        return self.data


@pytest.fixture
def platform(app, monkeypatch):
    """The CRM linked to GetMeds on a stand-in platform; set `answer` to change what it says."""
    company.forget()
    app.state.settings = app.state.settings.model_copy(update={"platform_api_url": "https://platform.test", "platform_public_key": PUBLIC})
    state = {"answer": Answer(200, {"pass": company_pass()}), "asked": 0}

    def get(url, params=None, timeout=None):
        state["asked"] += 1
        if isinstance(state["answer"], Exception):
            raise state["answer"]
        return state["answer"]

    monkeypatch.setattr(company.httpx, "get", get)
    yield state
    company.forget()


def test_a_registered_company_signs_in(client, platform):
    assert sign_in(client).status_code == 200
    assert client.get("/auth/company").json() == {"ok": True, "message": "GetMeds", "name": "GetMeds", "slug": "getmeds"}
    # Asked once, then kept for the hour the pass lasts.
    sign_in(client)
    assert platform["asked"] == 1


@pytest.mark.parametrize(
    ("answer", "says"),
    [
        (Answer(404), "isn't registered on Bishnoi One Platform"),
        (Answer(200, {"pass": company_pass(status="suspended")}), "is suspended"),
        (Answer(200, {"pass": company_pass(granted=False)}), "isn't set up to use the CRM"),
        (Answer(200, {"pass": company_pass(key=Ed25519PrivateKey.generate())}), "couldn't be checked"),
        (Answer(200, {"pass": company_pass(slug="another")}), "couldn't be checked"),
    ],
)
def test_no_sign_in_without_a_registered_company(client, platform, answer, says):
    platform["answer"] = answer
    r = sign_in(client)
    assert r.status_code == 403 and says in r.json()["detail"]


def test_a_suspended_company_is_stopped_on_its_next_click(client, platform):
    headers = {"Authorization": f"Bearer {sign_in(client).json()['accessToken']}"}
    assert client.get("/companies", headers=headers).status_code == 200
    company.forget()
    platform["answer"] = Answer(200, {"pass": company_pass(status="suspended")})
    assert client.get("/companies", headers=headers).status_code == 403


def test_a_short_outage_keeps_the_last_good_answer(client, platform):
    import httpx

    assert sign_in(client).status_code == 200
    company._last.clear()  # the hour is up; the platform is unreachable
    platform["answer"] = httpx.ConnectError("down")
    assert sign_in(client, password=PASSWORD).status_code == 200
    company.forget()  # and with no good answer to fall back on
    assert sign_in(client).status_code == 403


def test_production_needs_the_platform_and_a_company(app, client):
    company.forget()
    app.state.settings = app.state.settings.model_copy(update={"environment": "production"})
    try:
        r = sign_in(client)  # not saying which company: there's no default in production
        assert r.status_code == 400 and "Say which company" in r.json()["detail"]
        r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers={"X-Bishnoi-Company": "getmeds"})
        assert r.status_code == 403 and "PLATFORM_API_URL" in r.json()["detail"]
    finally:
        app.state.settings = app.state.settings.model_copy(update={"environment": "development"})


def test_on_this_computer_only_the_dev_companies(client):
    r = client.post("/auth/login", json={"email": "ana@example.com", "password": PASSWORD}, headers={"X-Bishnoi-Company": "nowhere"})
    assert r.status_code == 403 and "no company" in r.json()["detail"]
    assert client.get("/auth/company", headers={"X-Bishnoi-Company": "Not A Slug!"}).status_code == 400


def test_a_paused_company_is_told_until_when(client, platform):
    platform["answer"] = Answer(200, {"pass": company_pass(status="paused", pausedUntil="Mon 12 Oct 2026, 8:00 AM")})
    r = sign_in(client)
    assert r.status_code == 403 and "paused until Mon 12 Oct 2026, 8:00 AM" in r.json()["detail"]
