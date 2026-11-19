"""Sales orders on approval slips (Step 4C): an order waiting for approval asks the Platform for a slip
(approval.requested, with what proves it); the slip's end comes back (approval.decided) and approves the order as its
last signer, or rejects it with the note. While connected, only an administrator decides here, withdrawing the slip."""

from sqlalchemy import select

from modules.inventory.models import Role, RolePermission, SalesOrder
from modules.inventory.routers import sales as sales_routes
from modules.inventory.tests.conftest import Api, receive
from modules.inventory.tests.test_platform_roles import database, note
from modules.inventory.tests.test_platform_sign_in import linked  # noqa: F401 (fixture)
from modules.inventory.tests.test_sales import outbox


def typed(sal: Api, world) -> dict:
    made = sal.post("/inventory/sales-orders", {"customerName": "St. Luke's Medical Center", "lines": [{"productId": world["gloves"], "quantity": 4}]})
    sal.post(f"/inventory/sales-orders/{made['id']}/submit")
    return made


def decided(client, order_id: str, decision: str, by_email: str, note_text: str | None = None, event_id: str = "ev-decided-1"):
    """The Platform's approval.decided, as approvals.py sends it."""
    event = {"id": event_id, "kind": "approval.decided", "source": "platform", "occurredAt": "2026-11-18T00:00:00+00:00", "data": {
        "app": "inventory", "kind": "sales_order", "id": order_id, "number": "SO", "approval": {"id": "a-1", "number": "AR-000001"},
        "decision": decision, "note": note_text, "by": {"identityId": "no-such", "email": by_email, "name": by_email.split("@")[0].title()}}}
    r = client.post("/platform/events", json={"pass": note("event", event=event)})
    assert r.status_code == 204, r.text


def test_a_submitted_order_asks_for_its_slip_and_the_slips_end_approves_it(app, client, people, ana, world, linked):  # noqa: F811
    sal = Api(client, people["sal"])
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 50}])
    made = typed(sal, world)
    [asked] = outbox(app, "approval.requested")
    assert asked["kind"] == "sales_order" and asked["id"] == made["id"] and asked["url"] == f"/crm/sales/orders/{made['id']}"
    assert asked["requester"]["email"] == "sal@example.com"
    assert asked["summary"]["customer"] == "St. Luke's Medical Center" and asked["summary"]["totalCentavos"] == 128000
    assert asked["summary"]["lines"][0]["name"] == "Gloves M" and asked["summary"]["warehouse"] == "Manila"

    decided(client, made["id"], "approved", "pia@example.com")
    order = ana.get(f"/inventory/sales-orders/{made['id']}")
    assert order["status"] == "confirmed" and order["decidedBy"]["name"] == "Pia"  # as the last signer
    assert order["deliveries"][0]["number"].startswith("DR-")
    decided(client, made["id"], "returned", "pia@example.com", "late", event_id="ev-decided-2")  # too late: it stays confirmed
    assert ana.get(f"/inventory/sales-orders/{made['id']}")["status"] == "confirmed"


def test_a_returned_slip_rejects_the_order_with_its_note_and_it_can_be_sent_again(app, client, people, ana, world, linked):  # noqa: F811
    sal = Api(client, people["sal"])
    made = typed(sal, world)
    decided(client, made["id"], "returned", "someone@elsewhere.test", "Wrong warehouse")
    order = ana.get(f"/inventory/sales-orders/{made['id']}")
    assert order["status"] == "rejected" and order["decisionNote"] == "Wrong warehouse (AR-000001)" and order["decidedBy"] is None
    sal.post(f"/inventory/sales-orders/{made['id']}/submit")
    assert len(outbox(app, "approval.requested")) == 2  # a new slip; the Platform links it to the returned one


def test_while_connected_only_an_administrator_decides_here_and_the_slip_is_withdrawn(app, client, people, ana, world, monkeypatch):
    monkeypatch.setattr(sales_routes, "on_slip", lambda request: True)
    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == "Purchasing"))
        for permission in {"sales.approve", "sales.view"} - role.permissions:
            db.add(RolePermission(role_id=role.id, permission=permission))
        db.commit()
    pia, sal = Api(client, people["pia"]), Api(client, people["sal"])
    made = typed(sal, world)
    r = client.post(f"/inventory/sales-orders/{made['id']}/approve", headers=pia.h)
    assert r.status_code == 409 and "approval slip" in r.text
    assert client.post(f"/inventory/sales-orders/{made['id']}/reject", headers=pia.h, json={"note": "Not yet"}).status_code == 409
    assert ana.post(f"/inventory/sales-orders/{made['id']}/approve")["status"] == "confirmed"
    [withdrawn] = outbox(app, "approval.withdrawn")
    assert withdrawn["id"] == made["id"] and "administrator" in withdrawn["reason"]
    # Cancelling one that waits withdraws its slip too.
    other = typed(sal, world)
    ana.post(f"/inventory/sales-orders/{other['id']}/cancel")
    assert [w["id"] for w in outbox(app, "approval.withdrawn")] == [made["id"], other["id"]]


def test_an_order_from_a_quote_carries_its_quote_rx_and_letter(app, client, ana, world, linked):  # noqa: F811
    quote = {"quote": {"id": "q-7", "number": "Q-2026-0007", "rx": True, "priceType": "Hospital"},
             "customer": {"kind": "company", "id": "c-1", "name": "PGH"}, "salesperson": {"id": "u-1", "name": "Ria Santos"},
             "payer": {"kind": "guarantee_letter", "issuer": "PCSO", "letterNumber": "GL-55", "amountCentavos": 500000},
             "raisedBy": {"id": "u-1", "name": "Ria Santos", "email": "ria@getmeds.test"}, "currency": "PHP",
             "lines": [{"inventoryId": world["gloves"], "code": "GLV-M", "name": "Gloves M", "quantity": 2, "unitPriceCentavos": 30000, "totalCentavos": 60000}]}
    event = {"id": "ev-quote-7", "kind": "quote.ordered", "source": "crm", "data": quote, "occurredAt": "2026-11-18T00:00:00+00:00"}
    assert client.post("/platform/events", json={"pass": note("event", event=event)}).status_code == 204
    [asked] = outbox(app, "approval.requested")
    assert asked["requester"] == {"email": "ria@getmeds.test", "name": "Ria Santos"}
    labels = [a["label"] for a in asked["attachments"]]
    assert labels == ["Quote Q-2026-0007", "Rx check: the quote's prescription", "Price type Hospital, approved by Finance", "Guarantee letter GL-55 from PCSO"]
    assert asked["attachments"][0]["url"] == "/crm/quotes/q-7"
    with database(app)() as db:
        assert db.scalar(select(SalesOrder.status).where(SalesOrder.quote_id == "q-7")) == "pending"


def test_a_waiting_adjustment_goes_on_a_slip_and_is_posted_as_its_signer(app, client, people, ana, world, linked, monkeypatch):  # noqa: F811
    from modules.inventory.routers import adjustments

    wes = Api(client, people["wes"])
    receive(ana, world["mnl"], [{"productId": world["gloves"], "quantity": 10}])
    a = wes.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "lost", "notes": "Shelf short", "lines": [{"productId": world["gloves"], "quantity": 3}]})
    assert a["status"] == "pending"
    [asked] = outbox(app, "approval.requested")
    assert asked["kind"] == "adjustment" and asked["id"] == a["id"] and asked["url"] == f"/inventory/adjustments/{a['id']}"
    assert asked["requester"]["email"] == "wes@example.com" and asked["summary"]["lines"][0]["name"] == "Gloves M"

    # While connected, only an administrator decides it here (and its slip is withdrawn).
    monkeypatch.setattr(adjustments, "on_slip", lambda request: True)
    with database(app)() as db:
        role = db.scalar(select(Role).where(Role.name == "Purchasing"))
        for permission in {"adjustments.approve", "adjustments.view"} - role.permissions:
            db.add(RolePermission(role_id=role.id, permission=permission))
        db.commit()
    assert client.post(f"/inventory/adjustments/{a['id']}/approve", headers=people["pia"]).status_code == 409

    event = {"id": "ev-adj-1", "kind": "approval.decided", "source": "platform", "occurredAt": "2026-11-18T00:00:00+00:00", "data": {
        "app": "inventory", "kind": "adjustment", "id": a["id"], "number": a["number"], "approval": {"id": "a-2", "number": "AR-000002"},
        "decision": "approved", "note": None, "by": {"identityId": None, "email": "pia@example.com", "name": "Pia"}}}
    assert client.post("/platform/events", json={"pass": note("event", event=event)}).status_code == 204
    got = ana.get(f"/inventory/adjustments/{a['id']}")
    assert got["status"] == "posted"

    other = wes.post("/inventory/adjustments", {"warehouseId": world["mnl"], "reason": "lost", "lines": [{"productId": world["gloves"], "quantity": 1}]})
    event = {**event, "id": "ev-adj-2", "data": {**event["data"], "id": other["id"], "decision": "returned", "note": "Count again first"}}
    assert client.post("/platform/events", json={"pass": note("event", event=event)}).status_code == 204
    back = ana.get(f"/inventory/adjustments/{other['id']}")
    assert back["status"] == "rejected" and "Count again first" in back["notes"]
    assert ana.post(f"/inventory/adjustments/{other['id']}/approve", expect=409)
