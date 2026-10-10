"""Registering an application's address is enough: its connect key is sent
to that address, signed (app/links.py deliver), and nobody copies it onto a
server. Asking in another's name gets the asker nothing."""

import base64
import json

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app import links
from tests.conftest import app_id


class Answer:
    status_code = 200


@pytest.fixture
def posted(monkeypatch):
    """What the platform sent, and where; deliveries run at once, not on a thread."""
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: (sent.append((url, json)), Answer())[1])
    monkeypatch.setattr(links, "deliver_later", lambda sessions, settings, app_id: links.deliver(sessions, settings, app_id))
    links._asked.clear()
    return sent


def claims_of(client, token: str) -> dict:
    head, body, sig = token.split(".")
    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
    public = client.get("/pass/key").json()["publicKey"]
    Ed25519PublicKey.from_public_bytes(base64.b64decode(public)).verify(pad(sig), f"{head}.{body}".encode())
    return json.loads(pad(body))


def test_an_application_says_hello_and_its_key_goes_to_its_own_address(client, ana, posted):
    crm = app_id(client, ana, "crm")
    client.patch(f"/platform/applications/{crm}", json={"apiUrl": "https://crm-api.example.com"}, headers=ana)
    assert client.post("/connect/hello", json={"app": "crm"}).status_code == 202
    [(url, body)] = posted
    assert url == "https://crm-api.example.com/platform/connect"  # the registered address, not the asker
    claims = claims_of(client, body["token"])
    assert claims["kind"] == "connect" and claims["aud"] == "crm"
    # The delivered key is the application's key: it's told its links with it.
    assert client.get("/connect/links", headers={"X-Bishnoi-App-Key": claims["key"]}).status_code == 200
    # Asking again soon sends nothing more; later, the same key again (other copies of the app).
    client.post("/connect/hello", json={"app": "crm"})
    assert len(posted) == 1
    links._asked.clear()
    client.post("/connect/hello", json={"app": "crm"})
    assert claims_of(client, posted[1][1]["token"])["key"] == claims["key"]


def test_no_address_no_delivery(client, ana, posted):
    crm = app_id(client, ana, "crm")
    client.patch(f"/platform/applications/{crm}", json={"apiUrl": None}, headers=ana)
    assert client.post("/connect/hello", json={"app": "crm"}).status_code == 202
    assert client.post("/connect/hello", json={"app": "nothing-like-it"}).status_code == 202
    assert posted == []


def test_making_a_key_delivers_it_too(client, ana, posted):
    crm = app_id(client, ana, "crm")
    client.patch(f"/platform/applications/{crm}", json={"apiUrl": "https://crm-api.example.com"}, headers=ana)
    made = client.post(f"/platform/applications/{crm}/connect-key", headers=ana).json()
    assert made["delivered"] is True
    assert claims_of(client, posted[-1][1]["token"])["key"] == made["key"]


def test_a_registered_applications_pages_may_call_the_platform(client, ana):
    crm = app_id(client, ana, "crm")
    client.patch(f"/platform/applications/{crm}", json={"appUrl": "https://crm.example.com"}, headers=ana)
    r = client.options("/public/applications", headers={"Origin": "https://crm.example.com", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "https://crm.example.com"
    r = client.options("/public/applications", headers={"Origin": "https://not-ours.example.com", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") is None
