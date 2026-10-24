"""Finance names its company on every call to the CRM (CRM_COMPANY), since the
CRM keeps one database per company and, in production, won't guess which."""

import io
import json

import pytest
from pydantic import ValidationError

from app import crm
from app.config import Settings

LINKED = {"_env_file": None, "allowed_hosts": ["testserver"], "crm_api_url": "https://crm.example.com", "crm_api_key": "k" * 32}


class Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


@pytest.fixture
def sent(monkeypatch) -> list:
    """Each request Finance makes to the CRM, answered with an empty list."""
    asked: list = []

    def answer(request, timeout):
        asked.append(request)
        return Answer(json.dumps({"items": []}).encode())

    monkeypatch.setattr(crm.urllib.request, "urlopen", answer)
    return asked


def test_every_call_names_the_company(sent):
    settings = Settings(**LINKED, crm_company=" 2MG ")
    assert settings.crm_company == "2mg"  # kept as the CRM keeps it
    crm.find_customers(settings, "Reyes")
    crm.waiting_prices(settings)
    assert [r.get_header("X-bishnoi-company") for r in sent] == ["2mg", "2mg"]


def test_unset_off_production_names_none(sent):
    crm.find_customers(Settings(**LINKED), None)
    assert sent[0].get_header("X-bishnoi-company") is None


def test_unset_in_production_says_so_without_calling(sent, monkeypatch):
    settings = Settings(**LINKED)
    monkeypatch.setattr(Settings, "is_production", property(lambda self: True))
    with pytest.raises(crm.CrmUnavailable) as e:
        crm.waiting_prices(settings)
    assert str(e.value) == "Finance is not connected to a CRM company (CRM_COMPANY isn't set). Please contact your system administrator."
    # The customer picker still offers typing the customer in.
    with pytest.raises(crm.CrmUnavailable) as e:
        crm.find_customers(settings, "Reyes")
    assert str(e.value).endswith("Or type the customer's details instead.")
    assert sent == []


@pytest.mark.parametrize("bad", ["2mg corp", "-2mg", "a", "x" * 41, "2mg/gpi"])
def test_only_a_short_name_the_crm_would_take(bad):
    with pytest.raises(ValidationError, match="CRM_COMPANY"):
        Settings(**LINKED, crm_company=bad)
