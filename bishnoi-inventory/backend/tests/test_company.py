"""A company must be registered on the platform to use Inventory (app/company.py):
its signed pass is kept in the database, renewed in the background, and
replaced at once when the platform sends a fresh one. The platform is stood in for."""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import company
from tests.conftest import bearer, sign_in

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def company_pass(status="active", granted=True, slug="getmeds", key=KEY, exp=None, **more) -> str:
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    body = b64(json.dumps({
        "iss": "bishnoi-platform", "aud": "inventory", "kind": "company", "company": "co-1", "slug": slug,
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


def test_a_restart_in_an_outage_keeps_the_kept_pass(app, client, platform):
    import httpx

    assert sign_in(client).status_code == 200
    company.forget()
    platform["answer"] = httpx.ConnectError("down")
    asked = platform["asked"]
    assert sign_in(client).status_code == 200 and platform["asked"] == asked
    company.forget(kept=True, settings=app.state.settings)
    assert sign_in(client).status_code == 503


def test_the_platform_tells_us_at_once_and_nobody_else_can(client, platform):
    headers = bearer(sign_in(client))
    assert client.get("/auth/me", headers=headers).status_code == 200
    newer = int(time.time()) + 5
    assert client.post("/platform/company", json={"pass": company_pass(granted=False, iat=newer)}).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 403
    for body in ({"pass": company_pass(iat=newer - 60)}, {"pass": company_pass(key=Ed25519PrivateKey.generate(), iat=newer + 10)}, {"pass": company_pass(aud="crm", iat=newer + 10)}, {"x": 1}):
        r = client.post("/platform/company", json=body)
        assert (r.status_code, r.json()) == (404, {"detail": "Not Found"})
    assert client.get("/platform/company").json() == client.get("/no/such/address").json()
    assert "/platform/company" not in client.get("/openapi.json").text
    assert client.post("/platform/company", json={"pass": company_pass(iat=newer + 20)}).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 200
