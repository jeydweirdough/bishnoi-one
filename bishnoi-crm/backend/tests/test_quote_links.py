"""Order links (app/routers/quote_links.py): a rep's link a customer opens
with no account, to pick medicines at their own prices; a quote is made from
it, once, before it expires."""

from datetime import UTC, datetime, timedelta

from app.models import QuoteLink
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids  # noqa: F401 (fixtures)

PUBLIC = {"X-Bishnoi-Company": "getmeds"}


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
    assert amox["priceCentavos"] == 145000 and "prices" not in amox  # one price, not the price list

    r = client.post(f"/public/quote-links/{link['token']}", json={"lines": [{"productId": ids["AMX-500"], "quantity": 2}]}, headers=PUBLIC)
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["totalCentavos"] == 290000 and order["number"].startswith("Q-")

    # The quote is the rep's, on the customer, like any other.
    quotes = client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["items"]
    assert [q["number"] for q in quotes] == [order["number"]]
    # Used once: the link no longer opens.
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 410
    assert client.post(f"/public/quote-links/{link['token']}", json={"lines": [{"productId": ids["AMX-500"], "quantity": 1}]}, headers=PUBLIC).status_code == 410
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
    r = client.post(f"/public/quote-links/{link['token']}", json={"lines": [{"productId": "not-a-product", "quantity": 1}]}, headers=PUBLIC)
    assert r.status_code == 422
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 200  # a refused order doesn't use the link up


def test_someone_not_a_customer_yet_becomes_the_reps_customer(client, crew, ids):
    r = client.post("/quote-links", json={"hours": 24}, headers=crew["ria"])
    assert r.status_code == 201, r.text
    link = r.json()
    assert link["customer"] is None

    page = client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()
    assert page["asksWho"] is True and page["customer"] is None and page["products"]

    order = {"lines": [{"productId": ids["AMX-500"], "quantity": 1}]}
    # Who's ordering, and how to reach them, are asked for.
    assert client.post(f"/public/quote-links/{link['token']}", json=order, headers=PUBLIC).status_code == 422
    assert client.post(f"/public/quote-links/{link['token']}", json={**order, "customer": {"name": "Linus Aurin"}}, headers=PUBLIC).status_code == 422

    r = client.post(f"/public/quote-links/{link['token']}", json={**order, "customer": {"name": "Linus Aurin", "contactName": "Linus Aurin", "mobile": "0917 123 4567", "city": "Makati"}}, headers=PUBLIC)
    assert r.status_code == 201, r.text
    mine = client.get("/companies?q=Linus", headers=crew["ria"]).json()["items"]
    assert [c["name"] for c in mine] == ["Linus Aurin"] and mine[0]["owner"]["name"] == "Ria"
    assert client.get(f"/quotes?company={mine[0]['id']}", headers=crew["ria"]).json()["total"] == 1
    listed = client.get("/quote-links", headers=crew["ria"]).json()["items"]
    assert listed[0]["state"] == "used" and listed[0]["customer"]["name"] == "Linus Aurin"

    # The next link, same mobile: the same customer, not a second one.
    again = client.post("/quote-links", json={"hours": 24}, headers=crew["ria"]).json()
    r = client.post(f"/public/quote-links/{again['token']}", json={**order, "customer": {"name": "Linus A.", "mobile": "09171234567"}}, headers=PUBLIC)
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
    amox = next(p for p in client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()["products"] if p["code"] == "AMX-500")
    assert amox["priceCentavos"] == 118000  # the trade price now
    # Off, and on again.
    assert client.patch(f"/quote-links/{link['id']}", json={"on": False}, headers=crew["ria"]).json()["state"] == "switched_off"
    assert client.patch(f"/quote-links/{link['id']}", json={"on": True}, headers=crew["ria"]).json()["state"] == "open"
    # Someone who doesn't reach it can't touch it.
    assert client.patch(f"/quote-links/{link['id']}", json={"on": False}, headers=crew["sam"]).status_code == 404
    assert client.delete(f"/quote-links/{link['id']}", headers=crew["sam"]).status_code == 404
    # Used: it made its quote, and stays as it was; deleting it leaves the quote.
    client.post(f"/public/quote-links/{link['token']}", json={"lines": [{"productId": ids["AMX-500"], "quantity": 1}]}, headers=PUBLIC)
    assert client.patch(f"/quote-links/{link['id']}", json={"hours": 24}, headers=crew["ria"]).status_code == 409
    assert client.delete(f"/quote-links/{link['id']}", headers=crew["ria"]).status_code == 204
    assert client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()["items"] == []
    assert client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["total"] == 1
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).status_code == 404


def test_the_customer_asks_for_another_price_and_someone_decides(client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT")  # Amoxicillin at 1,450.00
    r = client.post(
        f"/public/quote-links/{link['token']}",
        json={"lines": [{"productId": ids["AMX-500"], "quantity": 2, "askedPriceCentavos": 140000}], "note": "We order every month"},
        headers=PUBLIC,
    )
    assert r.status_code == 201, r.text
    assert r.json()["waitsForApproval"] is True  # a small cut, but asked for: it waits all the same
    assert r.json()["totalCentavos"] == 280000  # at the asked price
    quote = client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["items"][0]
    full = client.get(f"/quotes/{quote['id']}", headers=crew["ria"]).json()
    assert "asked" in full["approval"]["reasons"]
    assert "asked" in full["notes"] and "We order every month" in full["notes"]
    # Asking for more than the price isn't a discount: it's left at the price.
    other = make_link(client, crew["ria"], acme, priceType="PATIENT")
    r = client.post(f"/public/quote-links/{other['token']}", json={"lines": [{"productId": ids["AMX-500"], "quantity": 1, "askedPriceCentavos": 999999}]}, headers=PUBLIC)
    assert r.status_code == 201 and r.json()["totalCentavos"] == 145000



def test_the_maker_copies_the_link_again(client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme)
    r = client.get(f"/quote-links/{link['id']}/token", headers=crew["ria"])
    assert r.status_code == 200 and r.json()["token"] == link["token"]
    assert "token" not in client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()["items"][0]
    assert client.get(f"/quote-links/{link['id']}/token", headers=crew["sam"]).status_code == 404
    client.post(f"/public/quote-links/{link['token']}", json={"lines": [{"productId": ids["AMX-500"], "quantity": 1}]}, headers=PUBLIC)
    assert client.get(f"/quote-links/{link['id']}/token", headers=crew["ria"]).status_code == 409
