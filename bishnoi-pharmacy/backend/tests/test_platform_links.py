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
    return Settings(platform_api_url="https://platform.test", platform_app_key=SecretStr("bpk.pharmacy.test"), integration_keys=[SecretStr("crm:old-key-in-env-0123456789abcdef")])


def test_the_platform_gives_the_keys_between_apps(monkeypatch):
    s = platform_links.effective(connected(monkeypatch, Answer(200, {"uses": {}, "usedBy": {"crm": "from-crm-0123456789abcdefghij"}, "askAgainIn": 300})))
    assert [k.get_secret_value() for k in s.integration_keys] == ["crm:from-crm-0123456789abcdefghij"]  # the platform's, not .env's
    platform_links.forget()


def test_a_replaced_key_drops_the_links_and_no_key_keeps_env(monkeypatch):
    s = platform_links.effective(connected(monkeypatch, Answer(401)))
    assert s.integration_keys == []
    platform_links.forget()
    plain = Settings(integration_keys=[SecretStr("crm:in-env-0123456789abcdefghijkl")])
    assert platform_links.effective(plain) is plain
