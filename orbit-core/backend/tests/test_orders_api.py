"""The API the Orders app calls. Orbit answers as the signed-in person: their
order steps, and customers and prices only where they raise or edit orders."""

import secrets

from app.models import ApiKey, utcnow
from app.routers.sso import digest
from app.tenancy import FIRST_ORG_ID, set_company
from tests.conftest import a_customer, post_quote, preview_quote, price_list_in, product_ids

API = "/orders-api/v1"


def test_me_says_what_steps_the_person_takes_and_where(client, as_):
    me = client.get(f"{API}/me", headers=as_("ana")).json()
    assert me["user"]["email"] == "ana@pharmacrm.test"
    assert me["org"]["orderPrefix"] == "GM" and me["org"]["currency"] == "PHP"
    assert set(me["grants"]) == {"view", "raise"}
    assert me["grants"]["raise"] == [{"division": "b2c", "team": "general"}, {"division": "bnb", "team": "md-telesales"}]
    tree = {d["code"]: [t["code"] for t in d["teams"]] for d in me["divisions"]}
    assert tree == {"b2c": ["general"], "bnb": ["md-telesales"]}
    assert me["sessionExpiresAt"]


def test_people_without_order_steps_are_turned_away(client, as_):
    assert client.get(f"{API}/me", headers=as_("iris")).status_code == 403
    assert client.get(f"{API}/customers", headers=as_("iris")).status_code == 403
    assert client.get(f"{API}/me").status_code == 401


def test_customers_only_from_teams_the_person_raises_orders_for(client, as_):
    ana = as_("ana")
    names = {c["name"] for c in client.get(f"{API}/customers", params={"limit": 50}, headers=ana).json()["items"]}
    assert "Dr. Alma Dizon" in names  # B&B / MD Telesales
    assert "Maria Lopez" in names  # B2C / General
    assert "Mercado Family Clinic" not in names  # B&B / General: not hers
    found = client.get(f"{API}/customers", params={"q": "alma", "division": "bnb"}, headers=ana).json()["items"]
    assert [c["name"] for c in found] == ["Dr. Alma Dizon"] and "notes" not in found[0]
    assert client.get(f"{API}/customers/{found[0]['id']}", headers=ana).status_code == 200
    mercado = client.get("/sales/customers", params={"division": "bnb", "q": "mercado"}, headers=as_("lorna")).json()["items"][0]["id"]
    assert client.get(f"{API}/customers/{mercado}", headers=ana).status_code == 404


def test_adding_a_customer_while_raising_an_order(client, as_):
    ana = as_("ana")
    new = {"division": "bnb", "team": "md-telesales", "name": "Dr. Orders Person", "kind": "doctor", "phone": "0917 123 4567"}
    r = client.post(f"{API}/customers", json=new, headers=ana)
    assert r.status_code == 201, r.text
    assert r.json()["team"] == "md-telesales" and r.json()["phone"] == "0917 123 4567"
    again = client.post(f"{API}/customers", json=new, headers=ana)
    assert again.status_code == 409 and again.json()["detail"]["duplicates"][0]["name"] == "Dr. Orders Person"
    elsewhere = {**new, "team": "general", "name": "Dr. Somewhere Else", "phone": None}
    assert client.post(f"{API}/customers", json=elsewhere, headers=ana).status_code == 403
    # It's an ordinary Orbit customer, in the rep's own list.
    assert "Dr. Orders Person" in {c["name"] for c in client.get("/sales/customers?division=bnb", headers=ana).json()["items"]}


def test_products_and_prices_come_from_orbits_own_rules(client, as_):
    ana = as_("ana")
    price_list = client.get(f"{API}/products", params={"division": "b2c"}, headers=ana).json()
    assert price_list == price_list_in(client, ana, "b2c")
    assert client.get(f"{API}/products", params={"division": "hos"}, headers=ana).status_code == 403

    amox = product_ids(client, ana, "b2c")["AMOX-500"]
    listed = next(t["code"] for t in price_list["priceTypes"] if t["entry"] == "list" and t["rule"] == "always")
    quote = {"priceType": listed, "lines": [{"productId": amox, "quantity": 12}]}
    priced = client.post(f"{API}/pricing/price", params={"division": "b2c"}, json=quote, headers=ana)
    assert priced.status_code == 200, priced.text
    preview = preview_quote(client, ana, a_customer(client, ana, "b2c"), quote).json()
    assert priced.json() == preview
    assert client.post(f"{API}/pricing/price", params={"division": "hos"}, json=quote, headers=ana).status_code == 403
    bad = client.post(f"{API}/pricing/price", params={"division": "b2c"}, json={"priceType": listed, "lines": [{"productId": "nope", "quantity": 1}]}, headers=ana)
    assert bad.status_code == 422


def test_order_settings_for_people_and_for_scheduled_jobs(client, app, as_):
    config = client.get(f"{API}/config", headers=as_("ana"))
    assert config.status_code == 200
    assert "GCash" in {i["name"] for i in config.json()["lists"]["payment_method"]}
    assert client.get(f"{API}/config", headers=as_("iris")).status_code == 403
    assert client.get(f"{API}/config").status_code == 401

    secret = secrets.token_urlsafe(32)
    with app.state.sessions() as db:
        set_company(db, FIRST_ORG_ID)
        db.add(ApiKey(id="k1", name="purge job", secret_hash=digest(secret), scopes=["orders:config"]))
        db.add(ApiKey(id="k2", name="no scope", secret_hash=digest(secret), scopes=[]))
        db.commit()
    key = {"X-Api-Key": f"orbit_k1_{secret}"}
    r = client.get(f"{API}/config", headers=key)
    assert r.status_code == 200 and r.json()["rules"]["recycleDays"] == 30
    assert client.get(f"{API}/config", headers={"X-Api-Key": f"orbit_k2_{secret}"}).status_code == 403
    assert client.get(f"{API}/config", headers={"X-Api-Key": f"orbit_k1_{secret}x"}).status_code == 401
    assert client.get(f"{API}/config", headers={"X-Api-Key": "not-a-key"}).status_code == 401
    # An API key opens the order settings and nothing else.
    assert client.get(f"{API}/me", headers=key).status_code == 401
    with app.state.sessions() as db:
        set_company(db, FIRST_ORG_ID)
        db.get(ApiKey, "k1").revoked_at = utcnow()
        db.commit()
    assert client.get(f"{API}/config", headers=key).status_code == 401


# --- a quote becoming an order -----------------------------------------------------------


def a_quote(client, headers, module="b2c", **over):
    """A saved, ready quote: nothing on it needs Finance."""
    customer = a_customer(client, headers, module)
    ids = product_ids(client, headers, module)
    quote = {"priceType": "srp", "lines": [{"productId": ids["ASC-500"], "quantity": 2}], **over}
    r = post_quote(client, headers, module, customer, quote)
    assert r.status_code == 201, r.text
    return r.json()


def test_the_orders_app_reads_a_quote_to_raise_an_order_from(client, as_):
    ana = as_("ana")
    quote = a_quote(client, ana)

    got = client.get(f"{API}/quotes/{quote['id']}", headers=ana)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["number"] == quote["number"]
    assert (body["division"], body["team"]) == ("b2c", "general")
    # What was agreed, exactly as it was priced: an order raised from it charges
    # the customer what they were quoted.
    assert body["priceType"] == "srp" and body["totalCentavos"] == quote["totalCentavos"]
    assert [line["productCode"] for line in body["lines"]] == ["ASC-500"]
    assert body["customer"]["name"] and "notes" not in body["customer"]


def test_a_quote_is_only_readable_where_you_raise_orders(client, as_):
    """Being able to read a quote in the sales workspace is not enough: raising
    the order is the thing being allowed, and that is an Orders grant."""
    ana, ramon = as_("ana"), as_("ramon")
    quote = a_quote(client, ana)
    # Ramon is an executive: he reads every division's quotes and raises no
    # orders anywhere. Same answer as a quote that doesn't exist, on purpose.
    assert client.get(f"/sales/quotes/{quote['id']}", headers=ramon).status_code == 200
    assert client.get(f"{API}/quotes/{quote['id']}", headers=ramon).status_code == 404
    # Iris keeps Inventory and has no business on this API at all.
    assert client.get(f"{API}/quotes/{quote['id']}", headers=as_("iris")).status_code == 403
    # Lorna raises orders, but in B&B; this one is B2C.
    assert client.get(f"{API}/quotes/{quote['id']}", headers=as_("lorna")).status_code == 404
    assert client.get(f"{API}/quotes/no-such-quote", headers=ana).status_code == 404


def test_a_quote_finance_has_not_finished_with_cannot_become_an_order(client, as_):
    ana, joy = as_("ana"), as_("joy")
    ids = product_ids(client, ana, "b2c")
    maria = a_customer(client, ana, "b2c")
    # A 20% discount is over B2C's limit, so it goes to Finance.
    big = {"priceType": "srp", "lines": [{"productId": ids["ASC-500"], "quantity": 2, "discount": {"kind": "percent", "value": 2000}}]}
    quote = post_quote(client, ana, "b2c", maria, big).json()
    assert quote["state"] == "waiting"

    waiting = client.get(f"{API}/quotes/{quote['id']}", headers=ana)
    assert waiting.status_code == 409 and "waiting on Finance" in waiting.json()["detail"]

    r = client.post(f"/finance/quotes/{quote['id']}/approval", json={"decision": "reject", "note": "Too much."}, headers=joy)
    assert r.status_code == 200
    rejected = client.get(f"{API}/quotes/{quote['id']}", headers=ana)
    assert rejected.status_code == 409 and "rejected" in rejected.json()["detail"]


def test_an_approved_quote_can_then_be_ordered(client, as_):
    ana, joy = as_("ana"), as_("joy")
    ids = product_ids(client, ana, "b2c")
    maria = a_customer(client, ana, "b2c")
    big = {"priceType": "srp", "lines": [{"productId": ids["ASC-500"], "quantity": 2, "discount": {"kind": "percent", "value": 2000}}]}
    quote = post_quote(client, ana, "b2c", maria, big).json()
    client.post(f"/finance/quotes/{quote['id']}/approval", json={"decision": "approve"}, headers=joy)
    assert client.get(f"{API}/quotes/{quote['id']}", headers=ana).status_code == 200


def test_the_quote_says_whether_this_person_may_raise_an_order_from_it(client, as_):
    """The button only appears where the person could actually use it."""
    ana, ramon = as_("ana"), as_("ramon")
    quote = a_quote(client, ana)
    assert client.get(f"/sales/quotes/{quote['id']}", headers=ana).json()["can"]["order"] is True
    # Ramon reads it as an executive, but raising an order isn't his to do.
    assert client.get(f"/sales/quotes/{quote['id']}", headers=ramon).json()["can"]["order"] is False


def test_orbit_keeps_no_order_of_its_own(client, as_):
    """The wire is one-way on purpose.

    An order's existence, its number and its eighteen steps belong to the Orders
    app, which keeps the quote's id on the order. If Orbit kept its own copy it
    would be the same fact in two places, wrong the moment they disagree — so
    there is nowhere here to write one, and a quote never carries one."""
    ana = as_("ana")
    quote = a_quote(client, ana)
    assert "orderedAs" not in client.get(f"{API}/quotes/{quote['id']}", headers=ana).json()
    assert "orderedAs" not in client.get(f"/sales/quotes/{quote['id']}", headers=ana).json()
    # Nothing on this API writes an order back to a quote: there is no such route.
    assert client.post(f"{API}/quotes/{quote['id']}/ordered", json={"number": "GM-1"}, headers=ana).status_code == 404
