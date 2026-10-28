"""Business events through the platform (feature plan step 7): kept once, delivered in order to the apps
that take them, retried, stuck for an operator after the tries run out; the nightly check."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app import events
from app.models import EventDelivery
from tests.conftest import app_id, make_company
from tests.test_identity import claims_of


class Answer:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture
def wire(monkeypatch, client, ana):
    """GetMeds with the CRM and Finance (API addresses set), Finance's connect key, and the apps'
    answers: crm answers what `answers` says (204 by default), at once rather than on a thread."""
    for key in ("crm", "finance"):
        client.patch(f"/platform/applications/{app_id(client, ana, key)}", json={"apiUrl": f"https://{key}-api.example.com"}, headers=ana)
    company = make_company(client, ana, apps=("crm", "finance"))
    finance_key = client.post(f"/platform/applications/{app_id(client, ana, 'finance')}/connect-key", headers=ana).json()["key"]
    sent: list[tuple[str, dict]] = []
    answers: list[int] = []

    def post(url, json=None, timeout=None):
        sent.append((url, json))
        return Answer(answers.pop(0) if answers and url.endswith("/platform/events") else 204)

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(events, "kick", lambda sessions, settings: _now(sessions, settings))
    return {"company": company, "key": finance_key, "sent": sent, "answers": answers}


def _now(sessions, settings):
    with sessions() as db:
        events.deliver_due(db, settings)


def send(client, wire, *items, key=None):
    body = {"company": wire["company"]["slug"], "events": [
        {"id": i, "kind": kind, "data": {"number": i}, "occurredAt": (datetime.now(UTC) + timedelta(seconds=n)).isoformat()} for n, (i, kind) in enumerate(items)]}
    return client.post("/connect/events", json=body, headers={"X-Bishnoi-App-Key": key or wire["key"]})


def delivered(wire) -> list[dict]:
    return [claims_of(b["pass"], None)["event"] for u, b in wire["sent"] if u == "https://crm-api.example.com/platform/events"]


@pytest.fixture(autouse=True)
def no_signature_check(monkeypatch):
    import base64
    import json

    def read(token, _key):
        body = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))

    monkeypatch.setattr("tests.test_events.claims_of", read)


def test_an_event_is_kept_once_and_delivered_to_the_apps_that_take_it(client, wire):
    r = send(client, wire, ("ev-00000001", "invoice.issued"))
    assert r.status_code == 200 and r.json() == {"taken": ["ev-00000001"], "refused": []}
    assert [e["id"] for e in delivered(wire)] == ["ev-00000001"]
    assert delivered(wire)[0]["data"] == {"number": "ev-00000001"} and delivered(wire)[0]["source"] == "finance"
    # Sent again (the app didn't hear the answer): kept once, not delivered twice.
    send(client, wire, ("ev-00000001", "invoice.issued"))
    assert len(delivered(wire)) == 1
    # A kind this app doesn't send, and a key the platform didn't make, are refused.
    assert send(client, wire, ("ev-00000002", "organisation.changed")).json()["refused"] == ["ev-00000002"]
    assert send(client, wire, ("ev-00000003", "invoice.issued"), key="not-a-key").status_code == 401


def test_a_failure_is_retried_holds_later_events_back_and_ends_stuck(app, client, ana, wire):
    wire["answers"].extend([500])
    send(client, wire, ("ev-00000010", "invoice.issued"), ("ev-00000011", "invoice.voided"))
    assert [e["id"] for e in delivered(wire)] == ["ev-00000010"]  # the second waits behind the first
    with app.state.sessions() as db:
        first = db.get(EventDelivery, ("ev-00000010", "crm"))
        assert first.status == "pending" and first.attempts == 1 and first.next_at is not None
        assert db.get(EventDelivery, ("ev-00000011", "crm")).attempts == 0
        # Every try fails: after the last, it's stuck.
        for _ in range(len(events.RETRY_AFTER)):
            first.next_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
            wire["answers"].append(500)
            events.deliver_due(db, app.state.settings)
            db.refresh(first)
        assert first.status == "stuck"
    listed = client.get("/platform/events?state=stuck", headers=ana).json()
    assert listed["counts"]["stuck"] == 1 and listed["deliveries"][0]["eventId"] == "ev-00000010"
    # The operator retries it: delivered, and the one behind it goes too, in order.
    r = client.post("/platform/events/ev-00000010/crm/retry", headers=ana).json()
    assert r["status"] == "delivered"
    assert [e["id"] for e in delivered(wire)][-2:] == ["ev-00000010", "ev-00000011"]


def test_an_operator_skips_a_stuck_event(app, client, ana, wire):
    wire["answers"].extend([500] * 10)
    send(client, wire, ("ev-00000020", "payment.recorded"))
    with app.state.sessions() as db:
        d = db.get(EventDelivery, ("ev-00000020", "crm"))
        d.status = "stuck"
        db.commit()
    assert client.post("/platform/events/ev-00000020/crm/skip", headers=ana).json()["status"] == "skipped"


def test_an_app_that_doesnt_take_events_yet_is_skipped(app, client, wire):
    wire["answers"].append(404)
    send(client, wire, ("ev-00000030", "invoice.issued"))
    with app.state.sessions() as db:
        assert db.get(EventDelivery, ("ev-00000030", "crm")).status == "skipped"


def test_the_nightly_check(app, client, ana, wire):
    assert client.get("/cron/events-check").status_code == 404  # no CRON_SECRET: not there
    from pydantic import SecretStr

    app.state.settings.cron_secret = SecretStr("nightly-secret")
    assert client.get("/cron/events-check", headers={"Authorization": "Bearer wrong"}).status_code == 404
    r = client.get("/cron/events-check", headers={"Authorization": "Bearer nightly-secret"})
    assert r.status_code == 200 and r.json()["stuck"] == 0
    # Finance (a sender) was asked to send what it holds.
    assert any(u == "https://finance-api.example.com/platform/events/flush" for u, _ in wire["sent"])
    assert client.post("/platform/events/check", headers=ana).status_code == 200


def test_documents_are_linked_into_one_chain(app, client, ana, wire):
    """Feature plan step 9: any app links its documents; the trail follows them both ways."""
    from tests.test_company_access import person

    def link(i, a, b):
        body = {"company": wire["company"]["slug"], "events": [{"id": i, "kind": "document.linked", "data": {"from": a, "to": b}, "occurredAt": datetime.now(UTC).isoformat()}]}
        return client.post("/connect/events", json=body, headers={"X-Bishnoi-App-Key": wire["key"]}).json()

    delivery = {"app": "inventory", "kind": "order", "id": "o-1", "number": "SO-2026-00001"}
    first = {"app": "finance", "kind": "invoice", "id": "i-1", "number": "SI-000101"}
    second = {"app": "finance", "kind": "invoice", "id": "i-2", "number": "SI-000102"}
    payment = {"app": "finance", "kind": "payment", "id": "p-1", "number": "OR-1"}
    assert link("ev-l-0001", delivery, first)["taken"] == ["ev-l-0001"]
    link("ev-l-0002", first, second)
    link("ev-l-0003", second, payment)
    link("ev-l-0003", second, payment)  # again: kept once
    # Neither side Finance's own: not kept.
    link("ev-l-0004", {"app": "crm", "kind": "quote", "id": "q-1"}, delivery)
    assert not any(u.endswith("/platform/events") and "document.linked" in str(b) for u, b in wire["sent"])  # nobody else is sent links

    owner = person(client, ana, wire["company"], "Olive Owner", "olive@getmeds.test", admin=True)
    r = client.get("/identity/documents/trail", params={"app": "finance", "kind": "invoice", "id": "i-2"}, headers=owner["h"])
    assert r.status_code == 200, r.text
    t = r.json()
    assert [d["number"] for d in t["before"]] == ["SO-2026-00001", "SI-000101"]
    assert [d["number"] for d in t["after"]] == ["OR-1"]
    assert len(t["links"]) == 3
    alone = client.get("/identity/documents/trail", params={"app": "crm", "kind": "quote", "id": "q-1"}, headers=owner["h"]).json()
    assert alone["before"] == [] and alone["after"] == []
