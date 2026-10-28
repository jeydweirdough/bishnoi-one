"""Business events (app/business_events.py, feature plan step 7): Finance saves what happened with the
change itself, sends it to the Platform, and takes the Platform's deliveries once."""

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from app import business_events
from app.business_events import InboxEvent, OutboxEvent
from .test_invoices import issued, ready
from .test_platform_roles import note
from .test_platform_sign_in import PUBLIC
from .test_tax_api import ana, app, client  # noqa: F401 (fixtures)


class Answer:
    def __init__(self, status_code, body=None):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


def test_issuing_voiding_and_paying_an_invoice_are_told(app, client, ana, monkeypatch):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, salespersonName="Ben Cruz", divisionId="d1", divisionName="HOS")
    client.post(f"/finance/invoices/{inv['id']}/payments", json={"paidOn": inv["date"], "amountCentavos": 100000, "method": "bank"}, headers=ana)
    other = issued(client, ana)
    assert client.post(f"/finance/invoices/{other['id']}/void", json={"reason": "Wrong customer"}, headers=ana).status_code == 200
    with app.state.sessions() as db:
        out = db.scalars(select(OutboxEvent).order_by(OutboxEvent.occurred_at)).all()
        assert [e.kind for e in out] == ["invoice.issued", "payment.recorded", "invoice.issued", "invoice.voided"]
        assert out[0].data["number"] == inv["number"] and out[0].data["divisionId"] == "d1" and out[0].sent_at is None

    # Connected: sent to the Platform with the connect key, for the company this database is.
    sent = []

    def post(url, json=None, headers=None, timeout=None):
        sent.append((url, json, headers))
        return Answer(200, {"taken": [e["id"] for e in json["events"]], "refused": []})

    monkeypatch.setattr(httpx, "post", post)
    app.state.settings.platform_api_url = "https://platform.example.com"
    app.state.settings.platform_app_key = SecretStr("finance-connect-key")
    try:
        business_events.remember_company(app.state.settings, "getmeds")
        with app.state.sessions() as db:
            assert business_events.flush(db, app.state.settings) == 4
            assert all(e.sent_at for e in db.scalars(select(OutboxEvent)))
            assert business_events.flush(db, app.state.settings) == 0  # nothing left
    finally:
        app.state.settings.platform_api_url = None
        app.state.settings.platform_app_key = None
    url, body, headers = sent[0]
    assert url == "https://platform.example.com/connect/events" and headers["X-Bishnoi-App-Key"] == "finance-connect-key"
    assert body["company"] == "getmeds" and len(body["events"]) == 4


def test_a_delivery_is_taken_once(app, client, monkeypatch):  # noqa: F811
    app.state.settings.platform_public_key = PUBLIC
    heard = []
    monkeypatch.setitem(business_events.HANDLERS, "delivery.done", lambda db, data, slug: heard.append((data, slug)))
    event = {"id": "ev-11111111", "kind": "delivery.done", "source": "inventory", "data": {"order": "SO-1"}, "occurredAt": "2026-10-28T00:00:00+00:00"}
    for _ in range(2):
        r = client.post("/platform/events", json={"pass": note("event", event=event)})
        assert r.status_code == 204, r.text
    assert heard == [({"order": "SO-1"}, "getmeds")]
    with app.state.sessions() as db:
        assert db.get(InboxEvent, "ev-11111111").source == "inventory"
    # Signed for another purpose: answered as if the address didn't exist.
    assert client.post("/platform/events", json={"pass": note("roles", event=event)}).status_code == 404


def test_a_reissued_invoice_is_linked_to_the_one_it_replaces(app, client, ana):  # noqa: F811
    """Feature plan step 9: the voided invoice, then its replacement."""
    ready(client, ana)
    inv = issued(client, ana)
    client.post(f"/finance/invoices/{inv['id']}/void", json={"reason": "Wrong customer"}, headers=ana)
    new = client.post(f"/finance/invoices/{inv['id']}/reissue", json={}, headers=ana)
    assert new.status_code == 201, new.text
    with app.state.sessions() as db:
        link = db.scalar(select(OutboxEvent).where(OutboxEvent.kind == "document.linked")).data
    assert link["from"] == {"app": "finance", "kind": "invoice", "id": inv["id"], "number": inv["number"]}
    assert link["to"]["id"] == new.json()["id"]
