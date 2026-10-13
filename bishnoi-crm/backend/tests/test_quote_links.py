"""Order links (app/routers/quote_links.py): a rep's link a customer opens
with no account, to pick medicines at their own prices; a quote is made from
it, once, before it expires."""

import json
from datetime import UTC, datetime, timedelta

from app.models import Company, QuoteLink
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids  # noqa: F401 (fixtures)

PUBLIC = {"X-Bishnoi-Company": "getmeds"}


def send(client, token, order, files=()):
    """An order through the link, as the page sends it: a form, the order as JSON, the prescriptions as files."""
    return client.post(f"/public/quote-links/{token}", data={"order": json.dumps(order)}, files=[("prescription", f) for f in files], headers=PUBLIC)


def make_link(client, headers, customer, **body):
    r = client.post(f"/companies/{customer['id']}/quote-links", json={"hours": 24, **body}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_a_customer_orders_through_the_link_once(app, client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT")
    assert link["state"] == "open" and link["token"]

    # The customer, with no account: their medicines, at their price only.
    page = client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC)
    assert page.status_code == 200, page.text
    got = page.json()
    assert got["customer"] == "Acme Pharmacy" and got["rep"] == "Ria"
    amox = next(p for p in got["products"] if p["code"] == "AMX-500")
    assert "priceCentavos" not in amox and "prices" not in amox and "priceType" not in got  # no prices on the page

    # Not without agreeing to the privacy notice.
    r = send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 2}]})
    assert r.status_code == 422 and "privacy" in r.text

    r = send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 2}], "privacyAccepted": True})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["number"].startswith("Q-") and "totalCentavos" not in order and "totalCentavos" not in order["lines"][0]

    # The quote is the rep's, on the customer, like any other, priced at the link's price.
    quotes = client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["items"]
    assert [q["number"] for q in quotes] == [order["number"]]
    full = client.get(f"/quotes/{quotes[0]['id']}", headers=crew["ria"]).json()
    assert full["totalCentavos"] == 290000 and "privacy notice" in full["notes"]
    with app.state.sessions() as db:
        assert db.get(QuoteLink, link["id"]).privacy_accepted_at is not None
    # Used once: the link no longer opens.
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 410
    assert send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True}).status_code == 410
    listed = client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()["items"]
    assert listed[0]["state"] == "used" and "token" not in listed[0]


def test_an_expired_or_switched_off_link_is_gone(app, client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    old = make_link(client, crew["ria"], acme)
    with app.state.sessions() as db:
        db.get(QuoteLink, old["id"]).expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/public/quote-links/{old['token']}", headers=PUBLIC).status_code == 410

    off = make_link(client, crew["ria"], acme)
    r = client.patch(f"/quote-links/{off['id']}", json={"on": False}, headers=crew["ria"])
    assert r.status_code == 200 and r.json()["state"] == "switched_off"
    assert client.get(f"/public/quote-links/{off['token']}", headers=PUBLIC).status_code == 410
    assert client.get("/public/quote-links/not-a-real-link", headers=PUBLIC).status_code == 404


def test_only_listed_medicines_and_the_customers_own_rep(client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    # Another division's rep doesn't reach the customer: no link for them.
    assert client.post(f"/companies/{acme['id']}/quote-links", json={"hours": 24}, headers=crew["sam"]).status_code == 404
    # A price a rep types in can't go on a link.
    assert client.post(f"/companies/{acme['id']}/quote-links", json={"hours": 24, "priceType": "SPECIAL"}, headers=crew["ria"]).status_code == 422
    link = make_link(client, crew["ria"], acme)
    r = send(client, link['token'], {"lines": [{"productId": "not-a-product", "quantity": 1}], "privacyAccepted": True})
    assert r.status_code == 422
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 200  # a refused order doesn't use the link up


def test_someone_not_a_customer_yet_becomes_the_reps_customer(app, client, crew, ids):
    r = client.post("/quote-links", json={"hours": 24}, headers=crew["ria"])
    assert r.status_code == 201, r.text
    link = r.json()
    assert link["customer"] is None

    page = client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()
    assert page["asksWho"] is True and page["customer"] is None and page["products"]

    order = {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True}
    # Who's ordering, and how to reach them, are asked for.
    assert send(client, link['token'], order).status_code == 422
    assert send(client, link['token'], {**order, "customer": {"name": "Linus Aurin"}}).status_code == 422

    who = {"name": "Linus Aurin", "contactName": "Linus Aurin", "mobile": "0917 123 4567", "address": "12 Rizal St, Brgy. Poblacion", "city": "Makati", "latitude": 14.5547, "longitude": 121.0244}
    r = send(client, link['token'], {**order, "customer": who})
    assert r.status_code == 201, r.text
    mine = client.get("/companies?q=Linus", headers=crew["ria"]).json()["items"]
    assert [c["name"] for c in mine] == ["Linus Aurin"] and mine[0]["owner"]["name"] == "Ria"
    with app.state.sessions() as db:
        found = db.get(Company, mine[0]["id"])
        assert (found.address, found.city, found.latitude, found.longitude) == ("12 Rizal St, Brgy. Poblacion", "Makati", 14.5547, 121.0244)
    assert client.get(f"/quotes?company={mine[0]['id']}", headers=crew["ria"]).json()["total"] == 1
    listed = client.get("/quote-links", headers=crew["ria"]).json()["items"]
    assert listed[0]["state"] == "used" and listed[0]["customer"]["name"] == "Linus Aurin"

    # The next link, same mobile: the same customer, not a second one.
    again = client.post("/quote-links", json={"hours": 24}, headers=crew["ria"]).json()
    r = send(client, again['token'], {**order, "customer": {"name": "Linus A.", "mobile": "09171234567"}})
    assert r.status_code == 201, r.text
    assert len(client.get("/companies?q=Linus", headers=crew["ria"]).json()["items"]) == 1


def test_the_maker_changes_switches_and_deletes_a_link(app, client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT")
    # Lapsed: given more time, from now, it opens again; and its price can change.
    with app.state.sessions() as db:
        db.get(QuoteLink, link["id"]).expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    r = client.patch(f"/quote-links/{link['id']}", json={"hours": 4, "priceType": "TRADE"}, headers=crew["ria"])
    assert r.status_code == 200 and r.json()["state"] == "open" and r.json()["priceType"] == "TRADE"
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 200
    # Off, and on again.
    assert client.patch(f"/quote-links/{link['id']}", json={"on": False}, headers=crew["ria"]).json()["state"] == "switched_off"
    assert client.patch(f"/quote-links/{link['id']}", json={"on": True}, headers=crew["ria"]).json()["state"] == "open"
    # Someone who doesn't reach it can't touch it.
    assert client.patch(f"/quote-links/{link['id']}", json={"on": False}, headers=crew["sam"]).status_code == 404
    assert client.delete(f"/quote-links/{link['id']}", headers=crew["sam"]).status_code == 404
    # Used: it made its quote, and stays as it was; deleting it leaves the quote.
    send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True})
    assert client.patch(f"/quote-links/{link['id']}", json={"hours": 24}, headers=crew["ria"]).status_code == 409
    assert client.delete(f"/quote-links/{link['id']}", headers=crew["ria"]).status_code == 204
    assert client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()["items"] == []
    assert client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["total"] == 1
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 404


def test_a_price_cant_be_sent_through_a_link(client, crew, ids):
    """The customer sees no prices, so none can be sent: the quote is at the link's price."""
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT")
    r = send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 2, "askedPriceCentavos": 100}], "privacyAccepted": True})
    assert r.status_code == 422
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 200  # still open


def test_the_maker_copies_the_link_again(client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme)
    r = client.get(f"/quote-links/{link['id']}/token", headers=crew["ria"])
    assert r.status_code == 200 and r.json()["token"] == link["token"]
    assert "token" not in client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()["items"][0]
    assert client.get(f"/quote-links/{link['id']}/token", headers=crew["sam"]).status_code == 404
    send(client, link['token'], {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True})
    assert client.get(f"/quote-links/{link['id']}/token", headers=crew["ria"]).status_code == 409


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 64


def test_rx_medicines_need_the_prescription_and_a_pharmacist_sees_it(app, client, crew, ids):
    from app.models import Product, Quote

    with app.state.sessions() as db:
        db.get(Product, ids["AMX-500"]).needs_prescription = True
        db.commit()
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT")
    amox = next(p for p in client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()["products"] if p["code"] == "AMX-500")
    assert amox["rx"] is True
    order = {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True}
    # Not without it, and not as anything but a photo or a PDF.
    r = send(client, link["token"], order)
    assert r.status_code == 422 and "needs a prescription" in r.text
    r = send(client, link["token"], order, files=[("rx.txt", b"hello", "text/plain")])
    assert r.status_code == 422 and "photo" in r.text
    r = send(client, link["token"], order, files=[("rx.png", PNG, "image/png")])
    assert r.status_code == 201, r.text
    # On the quote: Rx (so a pharmacist checks it before it's ordered), the file there to open.
    quote = client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["items"][0]
    full = client.get(f"/quotes/{quote['id']}", headers=crew["ria"]).json()
    assert full["rx"] is True and [p["name"] for p in full["prescriptions"]] == ["rx.png"] and "Prescription attached" in full["notes"]
    got = client.get(f"/quotes/{quote['id']}/prescriptions/0", headers=crew["ria"])
    assert got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
    # Someone who can't see the quote can't open it.
    assert client.get(f"/quotes/{quote['id']}/prescriptions/0", headers=crew["sam"]).status_code == 404
    assert client.get(f"/quotes/{quote['id']}/prescriptions/1", headers=crew["ria"]).status_code == 404


def test_a_shared_location_gives_the_address(client, crew, ids, monkeypatch):
    import httpx

    class Found:
        status_code = 200

        def json(self):
            return {"address": {"house_number": "12", "road": "Rizal Street", "quarter": "Poblacion", "city": "Makati", "country_code": "ph"}}

    link = client.post("/quote-links", json={"hours": 24}, headers=crew["ria"]).json()
    monkeypatch.setattr(httpx, "get", lambda *a, **k: Found())
    r = client.post(f"/public/quote-links/{link['token']}/place", json={"latitude": 14.55, "longitude": 121.02}, headers=PUBLIC)
    assert r.json() == {"address": "12 Rizal Street, Brgy. Poblacion", "city": "Makati"}
    # Only for an open link: not a free lookup for anyone.
    assert client.post("/public/quote-links/not-a-link/place", json={"latitude": 14.55, "longitude": 121.02}, headers=PUBLIC).status_code == 404
