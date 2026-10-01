"""Raising an order in Nabhi Order from a ready quote, and the printed quotation's letterhead.
(Nabhi Order is stood in for here.)"""

import pytest

from app import orders
from app.routers import quotes as quotes_router
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)


@pytest.fixture
def linked(app, monkeypatch):
    app.state.settings.orders_api_url = "http://orders.test"
    monkeypatch.setattr(type(app.state.settings), "orders_linked", property(lambda self: True))
    sent = []

    def fake_send(settings, quote_id, body):
        sent.append((quote_id, body))
        return {"id": "ord-1", "number": "SO-000123", "url": "https://orders.test/orders/ord-1", "status": "new"}

    monkeypatch.setattr(quotes_router, "send_order", fake_send)
    return sent


def test_a_ready_quote_is_ordered_once(client, crew, ids, linked):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 2)]).json()
    assert q["can"]["order"] and q["order"] is None

    payload = client.get(f"/quotes/{q['id']}/order-payload", headers=crew["ria"]).json()
    assert payload["quote"]["number"] == q["number"]
    assert payload["customer"]["name"] == acme["name"] and payload["customer"]["kind"] == "company"
    assert payload["lines"][0]["code"] == "AMX-500" and payload["lines"][0]["quantity"] == 2
    assert payload["totals"]["totalCentavos"] == q["totalCentavos"] and payload["payer"] == {"kind": "customer"}

    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["order"]["number"] == "SO-000123" and got["order"]["url"] == "https://orders.test/orders/ord-1"
    assert not got["can"]["order"]
    assert linked[0][0] == q["id"] and linked[0][1]["raisedBy"]["email"]

    again = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert again.status_code == 409 and "SO-000123" in again.json()["detail"]
    assert len(linked) == 1


def test_a_quote_waiting_for_approval_is_not_ordered(client, crew, ids, linked):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["ORS-SACH"], 1, discount={"kind": "percent", "value": 1500})]).json()
    assert q["state"] == "waiting" and not q["can"]["order"]
    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 409
    assert linked == []


def test_nabhi_order_down_says_so_and_keeps_nothing(client, crew, ids, linked, monkeypatch):
    def down(settings, quote_id, body):
        raise orders.OrdersUnavailable("Nabhi Order can't be reached right now. Try again in a moment.")

    monkeypatch.setattr(quotes_router, "send_order", down)
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 502 and "can't be reached" in r.json()["detail"]
    assert client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()["order"] is None


def test_not_connected(client, crew, ids):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    r = client.post(f"/quotes/{q['id']}/order", headers=crew["ria"])
    assert r.status_code == 503 and "ORDERS_API_URL" in r.json()["detail"]
    assert client.get("/auth/me", headers=crew["ria"]).json()["ordersLinked"] is False


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
    """The real HTTP call, against a stand-in Nabhi Order on localhost."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from pydantic import SecretStr

    from app.config import Settings

    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"] = self.path
            seen["key"] = self.headers["X-Nabhi-Key"]
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
        made = orders.send(settings, "quote-1", {"source": "nabhi-crm"})
    finally:
        server.shutdown()
    assert made == {"id": "o1", "number": "SO-1"}
    assert seen == {"path": "/orders", "key": "k1", "idem": "quote-1", "body": {"source": "nabhi-crm"}}
