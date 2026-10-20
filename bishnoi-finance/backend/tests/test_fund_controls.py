"""Two controls Finance asked for (questionnaire, 2026-10-20), and what Finance
says when the CRM refuses a call.

- Whoever releases a cash advance doesn't review its liquidation (Malou Q11).
- A requester's next cash advance waits until the last one is liquidated (Malou Q21).
"""

import io
import urllib.error

import pytest

from app import crm
from app.config import Settings

from .test_funds import KEY, approved, categories, release, spend
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def submit(client, source_id="req-1"):
    r = client.post(f"/integration/funds/requests/{source_id}/submit", json={"by": "Rico Santos"}, headers=KEY)
    assert r.status_code == 200, r.text
    return r.json()


def test_whoever_released_it_doesnt_review_it(client, ana, ben):
    req = release(client, ben, approved(client)["id"])
    meal = spend(client, 300000, categories(client)["Food"])["expenses"][0]
    submit(client)
    base = f"/finance/funds/{req['id']}"
    said = "You released this cash advance, so someone else reviews its liquidation."
    # Every review step is refused to the one who released it, with the reason.
    for r in (
        client.patch(f"{base}/expenses/{meal['id']}", json={"accepted": True}, headers=ben),
        client.post(f"{base}/send-back", json={"note": "Blurry"}, headers=ben),
        client.post(f"{base}/finish-check", headers=ben),
    ):
        assert r.status_code == 409 and r.json()["detail"] == said
    # The page says so to them, and offers the review to anyone else.
    assert client.get(base, headers=ben).json()["holds"] == {"release": None, "check": said}
    assert client.get(base, headers=ana).json()["holds"] == {"release": None, "check": None}
    assert client.patch(f"{base}/expenses/{meal['id']}", json={"accepted": True}, headers=ana).status_code == 200
    assert client.post(f"{base}/finish-check", headers=ana).json()["status"] == "to_return"


def test_the_next_advance_waits_until_the_last_is_liquidated(client, ben):
    first = release(client, ben, approved(client)["id"])
    # The same person (their address in other capitals), another request.
    second = approved(client, "req-2", requester=("Rico Santos", "RICO@example.com"))
    page = client.get(f"/finance/funds/{second['id']}", headers=ben).json()
    assert page["holds"]["release"].startswith(f"Rico Santos still has {first['number']} to liquidate, due ")
    refused = client.post(f"/finance/funds/{second['id']}/release", json={"amountCentavos": 500000, "method": "cash"}, headers=ben)
    assert refused.status_code == 409 and refused.json()["detail"] == page["holds"]["release"]
    # Someone else's request isn't held by Rico's.
    other = approved(client, "req-3", requester=("Lia Cruz", "lia@example.com"))
    assert client.get(f"/finance/funds/{other['id']}", headers=ben).json()["holds"]["release"] is None
    # Liquidated (now waiting on Finance's review): the next one can go.
    submit(client)
    assert client.get(f"/finance/funds/{second['id']}", headers=ben).json()["holds"]["release"] is None
    assert release(client, ben, second["id"])["status"] == "to_liquidate"


def test_a_liquidation_sent_back_holds_the_next_one_again(client, ana, ben):
    first = release(client, ben, approved(client)["id"])
    submit(client)
    second = approved(client, "req-2")
    assert client.get(f"/finance/funds/{second['id']}", headers=ben).json()["holds"]["release"] is None
    back = client.post(f"/finance/funds/{first['id']}/send-back", json={"note": "Missing receipt"}, headers=ana)
    assert back.json()["status"] == "to_liquidate"
    assert client.get(f"/finance/funds/{second['id']}", headers=ben).json()["holds"]["release"] is not None


def test_an_advance_not_for_liquidation_holds_nothing(client, ben):
    release(client, ben, approved(client, liquidate=False)["id"])  # settled on release
    second = approved(client, "req-2")
    assert release(client, ben, second["id"])["status"] == "to_liquidate"


# --- what Finance says when the CRM refuses -----------------------------------------------------


@pytest.fixture
def linked() -> Settings:
    return Settings(_env_file=None, allowed_hosts=["testserver"], crm_api_url="https://crm.example.com", crm_api_key="k" * 32)


def crm_answers(monkeypatch, code: int, body: bytes = b"{}") -> None:
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, code, "refused", {}, io.BytesIO(body))

    monkeypatch.setattr(crm.urllib.request, "urlopen", refuse)


def test_a_refusal_says_trying_again_wont_help(monkeypatch, linked):
    crm_answers(monkeypatch, 400, b'{"detail": "Say which company: its short name on Bishnoi One Platform."}')
    with pytest.raises(crm.CrmUnavailable) as e:
        crm.waiting_prices(linked)
    assert str(e.value) == (
        "The CRM refused the request (400: Say which company: its short name on Bishnoi One Platform.). "
        "Trying again won't help. Please contact your system administrator."
    )


def test_a_refused_customer_search_offers_typing_them_in(monkeypatch, linked):
    crm_answers(monkeypatch, 403)
    with pytest.raises(crm.CrmUnavailable) as e:
        crm.find_customers(linked, "Reyes")
    assert "refused the request (403)" in str(e.value) and str(e.value).endswith("Or type the customer's details instead.")


def test_a_crm_outage_still_says_try_again(monkeypatch, linked):
    crm_answers(monkeypatch, 503)
    with pytest.raises(crm.CrmUnavailable) as e:
        crm.waiting_prices(linked)
    assert str(e.value) == "The CRM answered with an error (503). Try again in a minute."
