"""Outside services are connected on Bishnoi One Platform, per company, and the
CRM is given them (app/connections.py): nothing about them is kept here. The
platform is stood in for."""

import httpx
import pytest
from pydantic import SecretStr

from app import company, connections, platform_links
from tests.test_company import PUBLIC, Answer, company_pass

GMAIL = {"client_id": "123.apps.googleusercontent.com", "client_secret": "google-secret-value"}


@pytest.fixture
def platform(app, monkeypatch):
    """A stand-in platform: `services` is what it gives GetMeds; `asked` counts the questions."""
    company.forget()
    connections.forget()
    platform_links.forget()
    app.state.settings = app.state.settings.model_copy(update={"platform_app_key": SecretStr("bpk.crm.test"), "platform_api_url": "https://platform.test", "platform_public_key": PUBLIC})
    state = {"services": {"gmail": GMAIL}, "asked": 0, "down": False}

    def get(url, params=None, headers=None, timeout=None):
        if url.endswith("/public/company-pass"):
            return Answer(200, {"pass": company_pass()})
        assert headers == {"X-Bishnoi-App-Key": "bpk.crm.test"}
        if url.endswith("/connect/links"):
            return Answer(200, {"uses": {}, "usedBy": {}, "dataKey": "6K1f3fL0eF3_1ExqhW0Y1n7mJm6r8Y0Vb4J2l7nA9cQ=", "askAgainIn": 300})
        assert url == "https://platform.test/connect/services" and params == {"company": "getmeds"}
        state["asked"] += 1
        if state["down"]:
            raise httpx.ConnectError("down")
        return Answer(200, {"company": "getmeds", "services": state["services"], "askAgainIn": 300})

    monkeypatch.setattr(httpx, "get", get)
    yield state
    company.forget()
    connections.forget()
    platform_links.forget()


def test_only_administrators_see_connections(client, ana, ben):
    assert client.get("/admin/connections", headers=ben).status_code == 403
    page = client.get("/admin/connections", headers=ana).json()
    # Not connected to the platform: nothing is on, and the page says why.
    assert page["connected"] is False and not any(s["on"] for s in page["services"])


def test_the_platform_says_which_services_are_on(client, ana, platform):
    page = client.get("/admin/connections", headers=ana).json()
    assert page["connected"] is True and {s["key"]: s["on"] for s in page["services"]} == {"zoho_books": False, "gmail": True, "outlook": False, "zoho_mail": False, "smtp": False, "facebook": False, "whatsapp": False, "viber": False, "tawkto": False, "web_forms": False}
    # Asked once, then the answer is kept; while the platform is down, the last answer stands.
    client.get("/admin/connections", headers=ana)
    assert platform["asked"] == 1
    connections._known["getmeds"] = (connections._known["getmeds"][0], connections._known["getmeds"][1], 0.0)
    platform["down"] = True
    assert next(s for s in client.get("/admin/connections", headers=ana).json()["services"] if s["key"] == "gmail")["on"] is True
    # Nothing to save here any more: it's done on the platform.
    assert client.put("/admin/connections/gmail", json={"values": GMAIL}, headers=ana).status_code in (404, 405)


def test_the_crms_own_secrets_use_the_platforms_key(app, platform):
    from cryptography.fernet import Fernet

    settings = app.state.settings
    sealed = connections.seal(settings, {"refresh_token": "rt"})
    assert connections.unseal(settings, sealed) == {"refresh_token": "rt"}
    # Sealed with the key the platform gave, so it reads the same on any server.
    assert Fernet(b"6K1f3fL0eF3_1ExqhW0Y1n7mJm6r8Y0Vb4J2l7nA9cQ=").decrypt(sealed.encode()) == b'{"refresh_token": "rt"}'
