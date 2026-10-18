"""What the CRM is linked to comes from the platform's Connections page when the
CRM has a connect key (app/platform_links.py): addresses and keys aren't set
on its server. The platform is stood in for."""

import httpx
import pytest
from pydantic import SecretStr

from app import company, platform_links
from tests.test_company import PUBLIC, Answer, company_pass

LINKS = {
    "app": "crm",
    "appUrl": "https://crm.example.com",
    "uses": {"inventory": {"apiUrl": "https://inventory-api.example.com", "appUrl": "https://inventory.example.com", "key": "to-inventory"}},
    "usedBy": {"finance": "from-finance"},
    "askAgainIn": 300,
}


@pytest.fixture
def platform(app, monkeypatch):
    """A stand-in platform that knows GetMeds and the CRM's links; change `links` to change what it says."""
    company.forget()
    platform_links.forget()
    app.state.settings = app.state.settings.model_copy(update={
        "platform_api_url": "https://platform.test",
        "platform_public_key": PUBLIC,
        "platform_app_key": SecretStr("bpk.crm.test"),
        # What .env said before: the platform's answer replaces it.
        "integration_keys": [SecretStr("finance:old-key-in-env")],
        "pharmacy_api_url": "https://old-pharmacy.example.com",
        "pharmacy_api_key": SecretStr("old"),
    })
    state = {"links": Answer(200, LINKS), "asked": 0}

    def get(url, params=None, headers=None, timeout=None):
        if url.endswith("/public/company-pass"):
            return Answer(200, {"pass": company_pass()})
        assert url == "https://platform.test/connect/links" and headers == {"X-Bishnoi-App-Key": "bpk.crm.test"}
        state["asked"] += 1
        if isinstance(state["links"], Exception):
            raise state["links"]
        return state["links"]

    monkeypatch.setattr(httpx, "get", get)
    yield state
    company.forget()
    platform_links.forget()


def finance_asks(client, key: str):
    return client.get("/integration/customers?q=a", headers={"X-Bishnoi-Key": key, "X-Bishnoi-Company": "getmeds"})


def test_the_platform_says_what_the_crm_is_linked_to(app, client, platform):
    s = platform_links.effective(app.state.settings)
    assert (s.inventory_api_url, s.inventory_app_url, s.inventory_api_key.get_secret_value()) == ("https://inventory-api.example.com", "https://inventory.example.com", "to-inventory")
    assert s.inventory_linked and not s.pharmacy_linked  # the platform's word, over .env's old Pharmacy
    assert s.crm_app_url == "https://crm.example.com"

    # Finance calls with the key the platform gave it; the one left in .env no longer works.
    assert finance_asks(client, "from-finance").status_code == 200
    assert finance_asks(client, "old-key-in-env").status_code == 401
    assert platform["asked"] == 1  # asked once, then kept


def test_a_short_outage_changes_nothing_a_long_one_drops_the_links(app, client, platform, monkeypatch):
    assert platform_links.effective(app.state.settings).inventory_linked
    platform["links"] = httpx.ConnectError("down")
    clock = {"now": platform_links.time.time() + 301}  # past "ask again"
    monkeypatch.setattr(platform_links.time, "time", lambda: clock["now"])
    assert platform_links.effective(app.state.settings).inventory_linked  # the last answer stands
    clock["now"] += platform_links.GRACE + 60
    assert not platform_links.effective(app.state.settings).inventory_linked  # too long: dropped


def test_a_replaced_key_drops_every_link(app, platform):
    platform["links"] = Answer(401, {"detail": "replaced"})
    s = platform_links.effective(app.state.settings)
    assert not s.inventory_linked and not s.pharmacy_linked and s.integration_keys == []


def test_without_a_connect_key_env_is_used_as_before(app, platform):
    app.state.settings = app.state.settings.model_copy(update={"platform_app_key": None})
    s = platform_links.effective(app.state.settings)
    assert s.pharmacy_api_url == "https://old-pharmacy.example.com" and platform["asked"] == 0
