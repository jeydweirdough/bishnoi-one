"""Raising an order from a ready quote (step 11: through the Sales app, as the event quote.ordered), and the printed
quotation's letterhead."""

from app import orders
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)


def sent(app) -> list:
    """The events the CRM saved to send (the outbox)."""
    from sqlalchemy import select

    from app.business_events import OutboxEvent
    from tests.test_platform_roles import database

    with database(app)() as db:
        return [(e.kind, e.data) for e in db.scalars(select(OutboxEvent).where(OutboxEvent.kind == "quote.ordered"))]


def test_a_ready_quote_is_ordered_once_through_the_sales_app(app, client, crew, ids):
    """Feature plan step 11: Raise order sends the event quote.ordered; the Sales app makes the order."""
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 2)]).json()
    assert q["can"]["order"] and q["order"] is None
    assert client.get("/auth/me", headers=crew["ria"]).json()["ordersLinked"] is True

    payload = client.get(f"/quotes/{q['id']}/order-payload", headers=crew["ria"]).json()
    assert payload["quote"]["number"] == q["number"]
    assert payload["customer"]["name"] == acme["name"] and payload["customer"]["kind"] == "company"
    assert payload["lines"][0]["code"] == "AMX-500" and payload["lines"][0]["quantity"] == 2
    assert payload["totals"]["totalCentavos"] == q["totalCentavos"] and payload["payer"] == {"kind": "customer"}

    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["order"]["status"] == "sent" and got["order"]["number"] is None and not got["can"]["order"]
    events = sent(app)
    assert len(events) == 1 and events[0][1]["quote"]["id"] == q["id"] and events[0][1]["raisedBy"]["email"]

    again = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert again.status_code == 409
    assert len(sent(app)) == 1


def test_the_quote_hears_what_became_of_its_order(app, client, crew, ids):
    from tests.test_platform_roles import note
    from tests.test_platform_sign_in import PUBLIC

    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    app.state.settings.platform_public_key = PUBLIC
    event = {"id": "ev-so-00001", "kind": "sales_order.updated", "source": "inventory", "occurredAt": "2026-10-29T00:00:00+00:00",
             "data": {"quoteId": q["id"], "id": "so-1", "number": "SO-2026-00001", "status": "pending"}}
    assert client.post("/platform/events", json={"pass": note("event", event=event)}).status_code == 204
    order = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()["order"]
    assert order["number"] == "SO-2026-00001" and order["status"] == "pending" and order["url"] == "/sales/orders/so-1"


def test_a_quote_waiting_for_approval_is_not_ordered(app, client, crew, ids):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})]).json()
    assert q["state"] == "waiting" and not q["can"]["order"]
    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 409
    assert sent(app) == []


def test_letterhead_comes_from_company_settings(client, crew, ana):
    r = client.patch(
        "/admin/company-settings",
        json={"companyAddress": "12 Ayala Ave, Makati City", "companyTin": "123-456-789-000", "companyContact": "(02) 8123 4567"},
        headers=ana,
    )
    assert r.status_code == 200, r.text
    got = client.get("/quote-letterhead", headers=crew["ria"]).json()
    assert got["address"] == "12 Ayala Ave, Makati City" and got["tin"] == "123-456-789-000"
    client.patch("/admin/company-settings", json={"companyTin": None}, headers=ana)
    assert client.get("/quote-letterhead", headers=crew["ria"]).json()["tin"] is None


def test_send_posts_the_payload_with_the_key(monkeypatch):
    """The real HTTP call, against a stand-in Bishnoi One Order on localhost."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from pydantic import SecretStr

    from app.config import Settings

    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"] = self.path
            seen["key"] = self.headers["X-Bishnoi-Key"]
            seen["idem"] = self.headers["Idempotency-Key"]
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"id": "o1", "number": "SO-1"}).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        settings = Settings(_env_file=None, orders_api_url=f"http://127.0.0.1:{server.server_port}/", orders_api_key=SecretStr("k1"))
        made = orders.send(settings, "quote-1", {"source": "bishnoi-crm"})
    finally:
        server.shutdown()
    assert made == {"id": "o1", "number": "SO-1"}
    assert seen == {"path": "/orders", "key": "k1", "idem": "quote-1", "body": {"source": "bishnoi-crm"}}
