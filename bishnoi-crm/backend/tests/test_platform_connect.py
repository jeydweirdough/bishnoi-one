"""The CRM's connect key is delivered by the Platform to the CRM's own
address, signed (app/platform_connect.py): nothing is copied onto the server.
The Platform is stood in for."""

import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import platform_connect, platform_links, platform_pass

KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def delivery(key="bpk.crm.delivered", signer=KEY, **over) -> str:
    claims = {"iss": "bishnoi-platform", "aud": "crm", "kind": "connect", "key": key, "iat": int(time.time()), "exp": int(time.time()) + 120, **over}
    head = b64(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    body = b64(json.dumps(claims).encode())
    return f"{head}.{body}.{b64(signer.sign(f'{head}.{body}'.encode()))}"


@pytest.fixture
def platform(app, monkeypatch):
    """A stand-in platform at https://platform.test, and a fresh key store."""
    platform_connect.forget()
    platform_links.forget()
    app.state.settings = app.state.settings.model_copy(update={"platform_api_url": "https://platform.test", "platform_public_key": PUBLIC, "platform_app_key": None})
    platform_connect.save_key(app.state.settings, None)
    said: list[str] = []
    monkeypatch.setattr(platform_connect, "say_hello", lambda settings: said.append(settings.platform_api_url))
    yield said
    platform_connect.save_key(app.state.settings, None)
    platform_connect.forget()
    platform_links.forget()


def test_the_platforms_delivery_is_kept_and_used(app, client, platform, monkeypatch):
    # No key yet: the CRM asks the Platform to deliver one.
    assert platform_links.answer(app.state.settings) is None
    assert platform == ["https://platform.test"]
    # The Platform delivers it, signed: it's kept.
    assert client.post("/platform/connect", json={"token": delivery()}).status_code == 204
    assert platform_connect.stored_key(app.state.settings) == "bpk.crm.delivered"
    # And it's what the CRM asks for its links with.
    asked = {}

    def get(url, params=None, headers=None, timeout=None):
        asked["key"] = (headers or {}).get("X-Bishnoi-App-Key")
        return type("A", (), {"status_code": 200, "json": lambda self: {"uses": {}, "usedBy": {}, "askAgainIn": 300}})()

    monkeypatch.setattr(httpx, "get", get)
    platform_links.forget()
    assert platform_links.answer(app.state.settings) is not None and asked["key"] == "bpk.crm.delivered"


def test_only_the_platforms_signature_is_taken(app, client, platform):
    impostor = Ed25519PrivateKey.generate()
    assert client.post("/platform/connect", json={"token": delivery(signer=impostor)}).status_code == 401
    assert client.post("/platform/connect", json={"token": delivery(aud="inventory")}).status_code == 401
    assert client.post("/platform/connect", json={"token": delivery(exp=int(time.time()) - 3600)}).status_code == 401
    assert client.post("/platform/connect", json={"token": delivery(key="not-a-key")}).status_code == 401
    assert platform_connect.stored_key(app.state.settings) is None


def test_platform_app_key_still_wins(app, platform):
    from pydantic import SecretStr

    settings = app.state.settings.model_copy(update={"platform_app_key": SecretStr("bpk.crm.from-env")})
    assert platform_connect.connect_key(settings) == "bpk.crm.from-env"
    assert platform == []  # no hello when the key is set
