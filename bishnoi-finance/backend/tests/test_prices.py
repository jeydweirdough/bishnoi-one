"""Price approvals: Finance sees what waits in the CRM and decides it there,
under its own name; only those with prices.approve decide."""

import pytest

from app.crm import CrmUnavailable
from app.routers import prices

from .test_tax_api import ana, app, ben, client  # noqa: F401 (fixtures)

WAITING = {
    "prices": [{"kind": "team", "productId": "p1", "priceTypeCode": "PATIENT", "teamId": "t1", "proposedAmountCentavos": 120000}],
    "quotes": [{"id": "q1", "number": "Q-0001", "lines": []}],
    "total": 2,
}


@pytest.fixture
def crm(monkeypatch) -> list:
    """The CRM, as Finance calls it: what it's asked is kept, in order."""
    asked: list = []
    monkeypatch.setattr(prices, "waiting_prices", lambda settings: WAITING)
    monkeypatch.setattr(prices, "decide_price", lambda settings, body: asked.append(("price", body)) or {"ok": True})
    monkeypatch.setattr(prices, "decide_quote", lambda settings, quote_id, body: asked.append((quote_id, body)) or {"ok": True})
    return asked


def test_finance_sees_what_waits_and_decides_it_by_name(client, ana, crm):  # noqa: F811 (fixtures)
    got = client.get("/finance/prices/waiting", headers=ana).json()
    assert (got["total"], got["canApprove"]) == (2, True)
    price = {"kind": "team", "productId": "p1", "priceTypeCode": "PATIENT", "teamId": "t1", "decision": "approve", "label": "Amoxil, Patient Price, North"}
    assert client.post("/finance/prices/decide", json=price, headers=ana).status_code == 200
    assert client.post("/finance/prices/quotes/q1/decide", json={"decision": "approve", "number": "Q-0001"}, headers=ana).status_code == 200
    (what, sent), (quote, said) = crm
    assert (what, sent["byName"], sent["decision"], "label" in sent) == ("price", "Ana Reyes", "approve", False)
    assert (quote, said["byName"]) == ("q1", "Ana Reyes")


def test_a_rejection_says_why(client, ana, crm):  # noqa: F811 (fixtures)
    price = {"kind": "product", "productId": "p1", "priceTypeCode": "DOCTOR", "decision": "reject"}
    assert client.post("/finance/prices/decide", json=price, headers=ana).status_code == 422
    assert client.post("/finance/prices/quotes/q1/decide", json={"decision": "reject"}, headers=ana).status_code == 422
    assert crm == []  # nothing reached the CRM
    assert client.post("/finance/prices/decide", json=price | {"reason": "Below cost"}, headers=ana).status_code == 200


def test_the_crms_words_come_through(client, ana, monkeypatch):  # noqa: F811 (fixtures)
    def taken(settings, body):
        raise CrmUnavailable("That price isn't waiting any more: someone has decided it.")

    monkeypatch.setattr(prices, "decide_price", taken)
    r = client.post("/finance/prices/decide", json={"kind": "product", "productId": "p1", "priceTypeCode": "SRP", "decision": "approve"}, headers=ana)
    assert r.status_code == 409 and "someone has decided it" in r.json()["detail"]


def test_without_the_crm_it_says_so(client, ana):  # noqa: F811 (fixtures)
    r = client.get("/finance/prices/waiting", headers=ana)
    assert r.status_code == 409 and "not connected to the CRM" in r.json()["detail"]


def test_finance_staff_approve_prices(client, ben, crm):  # noqa: F811 (fixtures)
    assert client.get("/finance/prices/waiting", headers=ben).json()["canApprove"] is True
    assert client.post("/finance/prices/quotes/q1/decide", json={"decision": "approve"}, headers=ben).status_code == 200
    assert crm[0][1]["byName"] == "Ben Cruz"
