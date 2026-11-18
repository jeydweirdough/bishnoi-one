"""Prices are Finance's: a manager's price waits for Finance before salespeople
see it, and a quote at a price the rep asked for waits for Finance, not the
team lead. Finance decides in its own app, with its key."""

import pytest
from pydantic import SecretStr

from modules.crm.tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from modules.crm.tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)
from modules.crm.tests.test_platform_sign_in import linked  # noqa: F401 (fixture)

KEY = "finance-key-that-is-long-enough-1234"
OTHER = "inventory-key-that-is-long-enough-12"


@pytest.fixture
def finance(app) -> dict:
    """Finance's key, as Bishnoi One Finance sends it (and another app's, refused)."""
    app.state.settings = app.state.settings.model_copy(update={"integration_keys": [SecretStr(f"finance:{KEY}"), SecretStr(f"inventory:{OTHER}")]})
    return {"X-Bishnoi-Key": KEY}


def patient_prices(client, headers, customer) -> dict[str, int | None]:
    products = client.get(f"/companies/{customer['id']}/price-list", headers=headers).json()["products"]
    return {p["id"]: p["prices"].get("PATIENT") for p in products}


def test_a_managers_price_waits_for_finance(client, crew, ids, finance):
    teams = {t["name"]: t["id"] for t in client.get("/prices/teams", headers=crew["max"]).json()}
    proposal = {"productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "amountCentavos": 120000}
    r = client.put(f"/prices?team={teams['North']}", json={"items": [proposal]}, headers=crew["max"])
    assert r.status_code == 200, r.text
    acme = company(client, crew["ria"])
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 145000  # the rep still sees the company's price

    [waiting] = client.get("/integration/prices", headers=finance).json()["prices"]
    assert (waiting["kind"], waiting["teamName"], waiting["proposedAmountCentavos"], waiting["submittedByName"]) == ("team", "North", 120000, "Max")
    decision = {"kind": "team", "productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "teamId": teams["North"], "byName": "Fe Santos"}
    assert client.post("/integration/prices/decide", json=decision | {"decision": "approve"}, headers=finance).status_code == 200
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 120000
    assert client.get("/integration/prices", headers=finance).json()["prices"] == []

    # A change Finance rejects leaves the approved price in use.
    client.put(f"/prices?team={teams['North']}", json={"items": [proposal | {"amountCentavos": 90000}]}, headers=crew["max"])
    assert client.post("/integration/prices/decide", json=decision | {"decision": "reject", "reason": "Below cost"}, headers=finance).status_code == 200
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 120000


def test_finance_approves_a_quote_at_a_requested_price(client, crew, ids, finance):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1, unitPriceCentavos=100000)], price_type="SPECIAL", notes="Hospital tender").json()
    [waiting] = client.get("/integration/prices", headers=finance).json()["quotes"]
    assert (waiting["number"], waiting["repName"], waiting["lines"][0]["unitPriceCentavos"]) == (q["number"], "Ria", 100000)
    no_reason = client.post(f"/integration/prices/quotes/{q['id']}/decide", json={"decision": "reject", "byName": "Fe Santos"}, headers=finance)
    assert no_reason.status_code == 422  # the rep is told why
    r = client.post(f"/integration/prices/quotes/{q['id']}/decide", json={"decision": "approve", "byName": "Fe Santos"}, headers=finance)
    assert r.status_code == 200, r.text
    got = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()
    assert (got["approval"]["status"], got["approval"]["by"]["name"]) == ("approved", "Fe Santos (Finance)")
    assert client.get("/integration/prices", headers=finance).json()["quotes"] == []


def test_only_finance_decides_prices(client, finance):
    assert client.get("/integration/prices").status_code == 401
    assert client.get("/integration/prices", headers={"X-Bishnoi-Key": OTHER}).status_code == 403


def _decided(client, batch: str, decision: str, note: str | None = None, event_id: str = "ev-price-1"):
    """The Platform's approval.decided for a price change, as modules/platform/approvals.py sends it."""
    from modules.crm.tests.test_platform_roles import note as signed

    event = {"id": event_id, "kind": "approval.decided", "source": "platform", "occurredAt": "2026-11-18T00:00:00+00:00", "data": {
        "app": "crm", "kind": "price_change", "id": batch, "number": None, "approval": {"id": "a-1", "number": "AR-000007"},
        "decision": decision, "note": note, "by": {"identityId": None, "email": "mia@example.com", "name": "Mia"}}}
    r = client.post("/platform/events", json={"pass": signed("event", event=event)})
    assert r.status_code == 204, r.text


def test_on_bishnoi_one_a_managers_price_needs_finance_and_its_slip(app, client, crew, ids, finance, monkeypatch, linked):  # noqa: F811
    from sqlalchemy import select

    from modules.crm import price_slips
    from modules.crm.business_events import OutboxEvent
    from modules.crm.tests.test_platform_roles import database

    monkeypatch.setattr(price_slips, "connected", lambda: True)
    teams = {t["name"]: t["id"] for t in client.get("/prices/teams", headers=crew["max"]).json()}
    proposal = {"productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "amountCentavos": 120000}
    assert client.put(f"/prices?team={teams['North']}", json={"items": [proposal]}, headers=crew["max"]).status_code == 200
    with database(app)() as db:
        [asked] = [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "approval.requested"))]
    assert asked["kind"] == "price_change" and asked["requester"]["email"].startswith("max") and asked["attachments"][0]["app"] == "finance"
    acme = company(client, crew["ria"])
    decision = {"kind": "team", "productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "teamId": teams["North"], "byName": "Fe Santos"}
    # Finance decides exactly as before; the price waits for the slip.
    assert client.post("/integration/prices/decide", json=decision | {"decision": "approve"}, headers=finance).status_code == 200
    assert client.get("/integration/prices", headers=finance).json()["prices"] == []
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 145000
    _decided(client, asked["id"], "approved")
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 120000

    # Signed first, then Finance: live at Finance's approval, as today. Returned: the proposal is withdrawn.
    client.put(f"/prices?team={teams['North']}", json={"items": [proposal | {"amountCentavos": 110000}]}, headers=crew["max"])
    with database(app)() as db:
        second = [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "approval.requested"))][-1]
    _decided(client, second["id"], "approved", event_id="ev-price-2")
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 145000  # as today, a team price waiting for Finance isn't quoted
    assert client.post("/integration/prices/decide", json=decision | {"decision": "approve"}, headers=finance).status_code == 200
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 110000
    client.put(f"/prices?team={teams['North']}", json={"items": [proposal | {"amountCentavos": 99000}]}, headers=crew["max"])
    with database(app)() as db:
        third = [e.data for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "approval.requested"))][-1]
    _decided(client, third["id"], "returned", "Too low for North", event_id="ev-price-3")
    assert client.get("/integration/prices", headers=finance).json()["prices"] == []
    assert patient_prices(client, crew["ria"], acme)[ids["AMX-500"]] == 110000
