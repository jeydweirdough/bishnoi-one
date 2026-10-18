"""A company that changes here is told to its applications at once
(app/company_push.py): a fresh signed pass, to each one's registered address.
Passes last 30 days, and each one given is recorded."""

import httpx
import pytest
from sqlalchemy import select

from app import company_push
from app.models import CompanyPass
from tests.conftest import app_id, make_company
from tests.test_connect_delivery import claims_of


class Taken:
    status_code = 204


@pytest.fixture
def pushed(monkeypatch):
    """What the platform sent, and where; sent at once, not on a thread."""
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(httpx, "post", lambda url, json=None, timeout=None: (sent.append((url, json)), Taken())[1])
    monkeypatch.setattr(company_push, "push", lambda sessions, settings, company_id, app_ids, gone=None: company_push._send(sessions, settings, company_id, app_ids, gone) if app_ids else None)
    return sent


@pytest.fixture
def addresses(client, ana):
    for key, url in (("crm", "https://crm-api.example.com"), ("pharmacy", "https://rx-api.example.com")):
        client.patch(f"/platform/applications/{app_id(client, ana, key)}", json={"apiUrl": url}, headers=ana)


def passes_sent(client, pushed) -> list[tuple[str, dict]]:
    return [(url, claims_of(client, body["pass"])) for url, body in pushed]


def test_a_pass_lasts_30_days_and_is_recorded_once_an_hour(app, client, ana):
    company = make_company(client, ana, apps=("crm",))
    claims = claims_of(client, client.get(f"/public/company-pass?app=crm&company={company['slug']}").json()["pass"])
    assert claims["exp"] - claims["iat"] == 30 * 24 * 3600
    for _ in range(5):  # asked again and again: recorded once, so nobody can fill the table
        client.get(f"/public/company-pass?app=crm&company={company['slug']}")
    with app.state.sessions() as db:
        assert db.scalar(select(CompanyPass.how).where(CompanyPass.company_slug == company["slug"])) == "asked"
        assert len(db.scalars(select(CompanyPass)).all()) == 1


def test_suspending_tells_every_application_at_once(app, client, ana, addresses, pushed):
    company = make_company(client, ana, apps=("crm", "pharmacy"))
    pushed.clear()
    client.patch(f"/platform/companies/{company['id']}", json={"status": "suspended"}, headers=ana)
    sent = dict(passes_sent(client, pushed))
    assert set(sent) == {"https://crm-api.example.com/platform/company", "https://rx-api.example.com/platform/company"}
    assert all(c["status"] == "suspended" and c["slug"] == company["slug"] for c in sent.values())
    assert sent["https://crm-api.example.com/platform/company"]["aud"] == "crm"
    with app.state.sessions() as db:
        assert {p.answer for p in db.scalars(select(CompanyPass).where(CompanyPass.how == "pushed"))} == {"taken"}
    # A change that's nothing to the applications sends nothing.
    pushed.clear()
    client.patch(f"/platform/companies/{company['id']}", json={"contactEmail": "it@getmeds.ph"}, headers=ana)
    assert pushed == []


def test_taking_an_application_away_tells_that_one(client, ana, addresses, pushed):
    company = make_company(client, ana, apps=("crm", "pharmacy"))
    pushed.clear()
    client.put(f"/platform/companies/{company['id']}/applications", json={"applicationIds": [app_id(client, ana, "pharmacy")]}, headers=ana)
    [(url, claims)] = passes_sent(client, pushed)
    assert url == "https://crm-api.example.com/platform/company" and claims["granted"] is False and claims["status"] == "active"


def test_a_deleted_company_is_told_as_gone(client, ana, addresses, pushed):
    company = make_company(client, ana, apps=("crm",))
    pushed.clear()
    assert client.delete(f"/platform/companies/{company['id']}", headers=ana).status_code == 204
    [(url, claims)] = passes_sent(client, pushed)
    assert url == "https://crm-api.example.com/platform/company"
    assert (claims["status"], claims["granted"], claims["slug"]) == ("deleted", False, company["slug"])


def test_an_application_out_of_reach_is_noted_and_nothing_stops(app, client, ana, addresses, monkeypatch):
    def down(url, json=None, timeout=None):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", down)
    monkeypatch.setattr(company_push, "push", lambda sessions, settings, company_id, app_ids, gone=None: company_push._send(sessions, settings, company_id, app_ids, gone))
    company = make_company(client, ana, apps=("crm",))
    assert client.patch(f"/platform/companies/{company['id']}", json={"status": "suspended"}, headers=ana).status_code == 200
    with app.state.sessions() as db:
        assert "out of reach" in db.scalar(select(CompanyPass.answer).where(CompanyPass.how == "pushed"))
