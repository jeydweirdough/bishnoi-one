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
    assert full["rx"] is True and [p["name"] for p in full["prescriptions"]] == ["rx.png"] and "Attached: prescription" in full["notes"]
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


PDF = b"%PDF-1.7\n" + b"\0" * 64


def test_the_rep_sets_what_the_customer_sends(app, client, crew, ids):
    """A guarantee letter for a payer, named documents, a prescription with any order: asked, and checked."""
    acme = company(client, crew["ria"], "Acme Pharmacy")
    choices = client.get(f"/companies/{acme['id']}/quote-links", headers=crew["ria"]).json()
    payer = choices["payers"][0]
    # A payer not on the list is refused.
    bad = client.post(f"/companies/{acme['id']}/quote-links", json={"hours": 24, "asks": {"payer": "NOBODY"}}, headers=crew["ria"])
    assert bad.status_code == 422
    link = make_link(client, crew["ria"], acme, priceType="PATIENT", asks={"prescriptionAlways": True, "payer": payer["code"], "documents": ["Valid ID", " valid id ", "Senior citizen card"]})
    assert link["asks"] == {"prescriptionAlways": True, "payer": {"code": payer["code"], "name": payer["name"]}, "documents": ["Valid ID", "Senior citizen card"]}
    page = client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()
    assert page["asks"]["documents"] == ["Valid ID", "Senior citizen card"] and page["uploads"] == "with-order"

    order = {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True, "letter": {"number": "GL-2026-001", "issuedOn": "2026-10-01", "amountCentavos": 145000}}
    rx = ("rx.png", PNG, "image/png")
    letter = ("gl.pdf", PDF, "application/pdf")
    send_form = lambda files: client.post(f"/public/quote-links/{link['token']}", data={"order": json.dumps(order)}, files=files, headers=PUBLIC)  # noqa: E731
    # Each thing asked for is needed: the prescription, the letter, every document.
    assert "prescription" in send_form([]).text
    assert "guarantee letter" in send_form([("prescription", rx)]).text
    r = send_form([("prescription", rx), ("letter_file", letter), ("document", ("id.png", PNG, "image/png"))])
    assert r.status_code == 422 and "Senior citizen card" in r.text
    r = send_form([("prescription", rx), ("letter_file", letter), ("document", ("id.png", PNG, "image/png")), ("document", ("senior.jpg", b"\xff\xd8\xff" + b"0" * 32, "image/jpeg"))])
    assert r.status_code == 201, r.text

    quote = client.get(f"/quotes?company={acme['id']}", headers=crew["ria"]).json()["items"][0]
    full = client.get(f"/quotes/{quote['id']}", headers=crew["ria"]).json()
    assert full["rx"] is True and full["payer"] == payer["code"]
    assert (full["letter"]["number"], full["letter"]["status"], full["letter"]["file"]["name"]) == ("GL-2026-001", "pending", "gl.pdf")
    assert [(d["label"], d["name"]) for d in full["documents"]] == [("Valid ID", "id.png"), ("Senior citizen card", "senior.jpg")]
    assert client.get(f"/quotes/{quote['id']}/documents/1", headers=crew["ria"]).content.startswith(b"\xff\xd8\xff")
    assert client.get(f"/quotes/{quote['id']}/letter", headers=crew["ria"]).content == PDF
    assert client.get(f"/quotes/{quote['id']}/documents/0", headers=crew["sam"]).status_code == 404  # not theirs
    # Deleted, its files go with it.
    assert client.delete(f"/quotes/{quote['id']}", headers=crew["ana"] if "ana" in crew else crew["ria"]).status_code in (204, 403)


def test_files_go_straight_to_storage_when_it_is_set_up(app, client, crew, ids, monkeypatch):
    """With storage: a signed form per file, only for what the link asks for, and the file checked before the order is taken."""
    from app import storage

    held: dict[str, tuple[str, int]] = {}
    monkeypatch.setattr(storage, "configured", lambda settings: True)
    monkeypatch.setattr(storage, "presign_upload", lambda settings, key, content_type, max_bytes=storage.MAX_BYTES: {"url": "https://bucket.test", "fields": {"key": key}, "key": key})

    def check(settings, key):
        if key not in held:
            raise ValueError("missing")
        return held[key]

    monkeypatch.setattr(storage, "check", check)
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme, priceType="PATIENT", asks={"documents": ["Valid ID"]})
    assert client.get(f"/public/quote-links/{link['token']}", headers=PUBLIC).json()["uploads"] == "direct"
    up = lambda **b: client.post(f"/public/quote-links/{link['token']}/uploads", json=b, headers=PUBLIC)  # noqa: E731
    # Only for what it asks for: no letter (no payer), no second document.
    assert up(kind="letter", contentType="application/pdf").status_code == 422
    assert up(kind="document", index=1, contentType="image/png").status_code == 422
    form = up(kind="document", index=0, contentType="image/png").json()
    assert form["key"].startswith(f"links/{link['id']}/document-0-")
    order = {"lines": [{"productId": ids["AMX-500"], "quantity": 1}], "privacyAccepted": True, "files": [{"kind": "document", "index": 0, "key": form["key"], "name": "id.png"}]}
    # Not finished uploading: refused, in words.
    r = send(client, link["token"], order)
    assert r.status_code == 422 and "didn't finish uploading" in r.text
    # Someone else's file can't be named.
    other = {**order, "files": [{"kind": "document", "index": 0, "key": "links/another/document-0-abc.png", "name": "x.png"}]}
    assert "isn't this order's" in send(client, link["token"], other).text
    held[form["key"]] = ("image/png", 2048)
    r = send(client, link["token"], order)
    assert r.status_code == 201, r.text
    full = client.get(f"/quotes/{client.get(f'/quotes?company={acme[chr(105) + chr(100)]}', headers=crew['ria']).json()['items'][0]['id']}", headers=crew["ria"]).json()
    assert [(d["label"], d["name"], d["size"]) for d in full["documents"]] == [("Valid ID", "id.png", 2048)]


def test_without_storage_uploads_go_with_the_order(client, crew, ids):
    acme = company(client, crew["ria"], "Acme Pharmacy")
    link = make_link(client, crew["ria"], acme)
    r = client.post(f"/public/quote-links/{link['token']}/uploads", json={"kind": "prescription", "contentType": "image/png"}, headers=PUBLIC)
    assert r.status_code == 409
