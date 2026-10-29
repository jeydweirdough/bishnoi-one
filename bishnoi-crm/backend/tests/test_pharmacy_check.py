"""A quote marked Rx is checked by a pharmacist in Bishnoi One Pharmacy before it's
ordered (app/pharmacy.py). Pharmacy is stood in for here, answering as the
real one does; the last test makes the real HTTP call to a stand-in on
localhost."""

from datetime import date

import pytest

from app import pharmacy
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, save  # noqa: F401 (fixtures)

RX = {"prescriberName": "Dr. Elena Ramos", "prescriberLicense": "PRC-0112233", "prescribedOn": date.today().isoformat()}


class FakePharmacy:
    """Pharmacy's /integration/checks, as far as the CRM uses it."""

    def __init__(self):
        self.checks: dict[str, dict] = {}
        self.sent: list[dict] = []
        self.down = False

    def decide(self, source_id: str, outcome: str, note: str | None = None):
        self.checks[source_id].update(outcome=outcome, note=note, checkedBy="Ben Cruz")

    def __call__(self, settings, method, path, body=None):
        if self.down:
            raise pharmacy.PharmacyUnavailable("Pharmacy can't be reached right now.")
        if method == "POST":
            self.sent.append(body)
            check = self.checks.setdefault(body["sourceId"], {"number": f"RX-2026-{len(self.checks) + 1:05d}", "outcome": "waiting", "note": None})
            if check["outcome"] == "needs_clarification":
                check["outcome"] = "waiting"
            return dict(check)
        return dict(self.checks[path])


@pytest.fixture
def fake(app, monkeypatch):
    stand_in = FakePharmacy()
    monkeypatch.setattr(pharmacy, "call", stand_in)
    app.state.settings.pharmacy_api_url = "http://pharmacy.test"
    monkeypatch.setattr(type(app.state.settings), "pharmacy_linked", property(lambda self: True))
    # Asked again every time, rather than after 30 seconds.
    monkeypatch.setattr(pharmacy, "FRESH_FOR", pharmacy.timedelta(0))
    return stand_in


@pytest.fixture
def ordering(app):
    """Raise order goes to the Sales app as an event (step 11): nothing to stand in for."""
    return app


def rx_quote(client, crew, ids):
    acme = company(client, crew["ria"])
    # With a prescription, a quote is at the Doctor's Price.
    return save(client, crew["ria"], acme, [line(ids["AMX-500"], 2)], price_type="DOCTOR", rx=True).json()


def test_an_rx_quote_isnt_ordered_until_the_pharmacist_verifies_it(client, crew, ids, fake, ordering):
    q = rx_quote(client, crew, ids)
    assert q["pharmacy"]["outcome"] == "not_sent" and q["can"]["sendToPharmacy"] and not q["can"]["order"]
    assert client.post(f"/quotes/{q['id']}/order", headers=crew["ria"]).status_code == 409

    r = client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    assert r.status_code == 200, r.text
    sent = fake.sent[0]
    assert sent["reference"] == q["number"] and sent["prescription"]["prescriberName"] == "Dr. Elena Ramos"
    assert sent["lines"][0]["code"] == "AMX-500" and sent["lines"][0]["quantity"] == 2 and sent["sentBy"]
    assert r.json()["pharmacy"]["outcome"] == "waiting" and not r.json()["can"]["order"]

    fake.decide(q["id"], "verified")
    seen = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()
    assert seen["pharmacy"]["outcome"] == "verified" and seen["pharmacy"]["checkedBy"] == "Ben Cruz"
    assert seen["can"]["order"] and not seen["can"]["sendToPharmacy"]
    assert client.post(f"/quotes/{q['id']}/order", headers=crew["ria"]).status_code == 200


def test_clarification_is_corrected_and_sent_again(client, crew, ids, fake):
    q = rx_quote(client, crew, ids)
    client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    fake.decide(q["id"], "needs_clarification", "The licence number is unreadable.")
    seen = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()
    assert (seen["pharmacy"]["outcome"], seen["pharmacy"]["note"]) == ("needs_clarification", "The licence number is unreadable.")
    assert seen["can"]["sendToPharmacy"]
    again = client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json={**RX, "prescriberLicense": "PRC-0112234"}).json()
    assert again["pharmacy"]["outcome"] == "waiting" and again["pharmacy"]["sent"]["prescriberLicense"] == "PRC-0112234"
    assert len(fake.checks) == 1  # the same check, sent again


def test_a_rejected_quote_cant_be_sent_again_or_ordered(client, crew, ids, fake, ordering):
    q = rx_quote(client, crew, ids)
    client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    fake.decide(q["id"], "rejected", "Not a valid prescription.")
    seen = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()
    assert seen["pharmacy"]["outcome"] == "rejected" and not seen["can"]["sendToPharmacy"] and not seen["can"]["order"]
    assert client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX).status_code == 409
    assert client.post(f"/quotes/{q['id']}/order", headers=crew["ria"]).status_code == 409


def test_pharmacy_down_keeps_the_last_answer_and_says_why(client, crew, ids, fake):
    q = rx_quote(client, crew, ids)
    client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    fake.down = True
    seen = client.get(f"/quotes/{q['id']}", headers=crew["ria"]).json()
    assert seen["pharmacy"]["outcome"] == "waiting" and "can't be reached" in seen["pharmacy"]["error"]
    r = client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    assert r.status_code == 502


def test_a_quote_without_rx_needs_no_pharmacy(client, crew, ids, fake):
    acme = company(client, crew["ria"])
    q = save(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    assert q["pharmacy"] is None and not q["can"]["sendToPharmacy"]
    assert client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX).status_code == 409


def test_not_linked_says_which_settings(client, crew, ids):
    q = rx_quote(client, crew, ids)
    r = client.post(f"/quotes/{q['id']}/pharmacy-check", headers=crew["ria"], json=RX)
    assert r.status_code == 503 and "PHARMACY_API_URL" in r.json()["detail"]
    assert client.get("/auth/me", headers=crew["ria"]).json()["pharmacyLinked"] is False


def test_the_call_goes_out_with_the_key():
    """The real HTTP call, against a stand-in Pharmacy on localhost."""
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from pydantic import SecretStr

    from app.config import Settings

    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"], seen["key"] = self.path, self.headers["X-Bishnoi-Key"]
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self._answer({"number": "RX-1", "outcome": "waiting"})

        def do_GET(self):  # noqa: N802
            seen["get"] = self.path
            self._answer({"number": "RX-1", "outcome": "verified"})

        def _answer(self, body):
            out = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        settings = Settings(_env_file=None, pharmacy_api_url=f"http://127.0.0.1:{server.server_port}", pharmacy_api_key=SecretStr("k" * 32))
        assert pharmacy.call(settings, "POST", "", {"sourceId": "q1"})["outcome"] == "waiting"
        assert seen["path"] == "/integration/checks" and seen["key"] == "k" * 32 and seen["body"] == {"sourceId": "q1"}
        assert pharmacy.call(settings, "GET", "q1")["outcome"] == "verified" and seen["get"] == "/integration/checks/q1"
    finally:
        server.shutdown()
