"""What this app is linked to comes from the platform's Connections page when
it has a connect key (app/platform_links.py). The platform is stood in for."""

import httpx
from pydantic import SecretStr

from app import platform_links
from app.config import Settings


class Answer:
    def __init__(self, status_code, data=None):
        self.status_code, self.data = status_code, data

    def json(self):
        return self.data


def connected(monkeypatch, answer) -> Settings:
    platform_links.forget()
    monkeypatch.setattr(httpx, "get", lambda url, headers=None, timeout=None: answer)
    return Settings(platform_api_url="https://platform.test", platform_app_key=SecretStr("bpk.finance.test"), integration_keys=[SecretStr("crm:old-key-in-env-0123456789abcdef")])


def test_the_platform_gives_the_keys_between_apps(monkeypatch):
    s = platform_links.effective(connected(monkeypatch, Answer(200, {"uses": {"crm": {"apiUrl": "https://crm-api.example.com", "appUrl": None, "key": "to-crm"}}, "usedBy": {"crm": "from-crm-0123456789abcdefghij"}, "askAgainIn": 300})))
    assert [k.get_secret_value() for k in s.integration_keys] == ["crm:from-crm-0123456789abcdefghij"]  # the platform's, not .env's
    assert (s.crm_api_url, s.crm_api_key.get_secret_value()) == ("https://crm-api.example.com", "to-crm")
    platform_links.forget()


def test_a_replaced_key_drops_the_links_and_no_key_keeps_env(monkeypatch):
    s = platform_links.effective(connected(monkeypatch, Answer(401)))
    assert s.integration_keys == []
    platform_links.forget()
    plain = Settings(_env_file=None, platform_api_url=None, integration_keys=[SecretStr("crm:in-env-0123456789abcdefghijkl")])
    assert platform_links.effective(plain) is plain


OWNER = {"id": "company-id", "slug": "getmeds", "name": "Getmeds", "currency": "PHP", "timezone": "Asia/Manila", "status": "active"}


def test_company_settings_come_from_platform_not_legacy_env(monkeypatch):
    original = connected(monkeypatch, Answer(200, {"databaseCompany": OWNER}))
    original.crm_company = "old-env-company"
    settings = platform_links.effective(original)
    assert settings.crm_company == "getmeds"
    assert (settings.org_name, settings.org_currency, settings.org_timezone) == ("Getmeds", "PHP", "Asia/Manila")
    assert platform_links.database_company(settings, fresh=True) == OWNER
    platform_links.forget()


def test_sensitive_binding_fails_closed_even_with_a_cached_owner(monkeypatch):
    settings = connected(monkeypatch, Answer(200, {"databaseCompany": OWNER}))
    assert platform_links.database_company(settings) == OWNER
    def unavailable(*args, **kwargs): raise httpx.ConnectError("offline")
    monkeypatch.setattr(httpx, "get", unavailable)
    assert platform_links.database_company(settings, fresh=True) is None
    # An old .env company never substitutes for missing central ownership.
    settings.crm_company = "env-company"
    assert platform_links.database_company(settings, fresh=True) is None
    platform_links.forget()


def test_missing_platform_owner_does_not_reuse_env_company(monkeypatch):
    settings = connected(monkeypatch, Answer(200, {}))
    settings.crm_company = "env-company"
    effective = platform_links.effective(settings)
    assert effective.crm_company is None
    assert platform_links.database_company(effective, fresh=True) is None
    platform_links.forget()
