"""A team's own prices, set by its lead.

The rule the owners chose: no floor and no approval — the lead's number is the
number. What must hold is that a team which sets nothing prices exactly as it
did before, and that one team's price never reaches another's quote.
"""

import pytest
from tests.conftest import a_customer, preview_quote, price_list_in


@pytest.fixture
def lead(as_):
    """Tess leads B2C's General team. B2C quotes from a price list, which is
    what makes her the one who can demonstrate any of this — B&B's leads quote
    with notes only, so they have nothing to price."""
    return as_("tess")


@pytest.fixture
def product(client, as_) -> dict:
    """A product B2C can quote, with a Patient's Price on it. Read as Iris, who
    is the one who works Inventory."""
    products = client.get("/inventory/products", headers=as_("iris")).json()
    return next(p for p in products if "patient" in p["prices"])


def sheet(client, headers, team: str = "general", module: str = "b2c") -> dict:
    r = client.get("/sales/prices", params={"division": module, "team": team}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def set_price(client, headers, product_id: str, amount, team: str = "general", module: str = "b2c"):
    body = {"items": [{"productId": product_id, "priceTypeCode": "patient", "amountCentavos": amount}]}
    return client.put("/sales/prices", params={"division": module, "team": team}, json=body, headers=headers)


def test_a_team_lead_sees_the_company_price_beside_their_own(client, as_, lead, product):
    payload = sheet(client, lead)
    row = next(p for p in payload["products"] if p["id"] == product["id"])
    assert row["prices"]["patient"]["company"] == product["prices"]["patient"]
    assert row["prices"]["patient"]["team"] is None
    assert payload["usesDivisionTypes"] is True


def test_a_team_price_is_what_that_team_quotes(client, as_, lead, product):
    company = product["prices"]["patient"]

    before = preview_quote(client, lead, a_customer(client, lead, "b2c", "general"), {"priceType": "patient", "lines": [{"productId": product["id"], "quantity": 2}]}).json()
    assert before["totalCentavos"] == company * 2

    assert set_price(client, lead, product["id"], company - 400).status_code == 200

    after = preview_quote(client, lead, a_customer(client, lead, "b2c", "general"), {"priceType": "patient", "lines": [{"productId": product["id"], "quantity": 2}]}).json()
    assert after["totalCentavos"] == (company - 400) * 2
    # and the price list the rep sees says the same
    listed = price_list_in(client, lead, "b2c", "general")
    priced = next(p for p in listed["products"] if p["id"] == product["id"])
    assert priced["prices"]["patient"] == company - 400


def test_above_the_company_price_is_allowed_and_nobody_is_asked(client, as_, lead, product):
    r = set_price(client, lead, product["id"], product["prices"]["patient"] + 100_000)
    assert r.status_code == 200
    row = next(p for p in r.json()["products"] if p["id"] == product["id"])
    assert row["prices"]["patient"]["team"] == product["prices"]["patient"] + 100_000


def test_clearing_a_team_price_hands_it_back_to_the_company(client, as_, lead, product):
    company = product["prices"]["patient"]
    set_price(client, lead, product["id"], company - 500)
    r = set_price(client, lead, product["id"], None)
    row = next(p for p in r.json()["products"] if p["id"] == product["id"])
    assert row["prices"]["patient"]["team"] is None

    quoted = preview_quote(client, lead, a_customer(client, lead, "b2c", "general"), {"priceType": "patient", "lines": [{"productId": product["id"], "quantity": 1}]}).json()
    assert quoted["totalCentavos"] == company


def test_one_teams_price_never_reaches_another_teams_quote(client, as_, lead, product):
    company = product["prices"]["patient"]
    assert set_price(client, lead, product["id"], company - 1000, team="general").status_code == 200

    # the other B2C team is untouched — read by Ben, who works in it
    other = price_list_in(client, as_("ben"), "b2c", "md-telesales")
    priced = next(p for p in other["products"] if p["id"] == product["id"])
    assert priced["prices"]["patient"] == company


def test_a_team_may_narrow_its_price_types_but_not_widen_them(client, as_, lead, product):
    division_types = {t["code"] for t in sheet(client, lead)["priceTypes"]}
    assert "patient" in division_types

    r = client.put(
        "/sales/prices/types", params={"division": "b2c", "team": "general"}, json={"codes": ["patient"]}, headers=lead
    )
    assert r.status_code == 200
    assert {t["code"] for t in r.json()["priceTypes"] if t["chosen"]} == {"patient"}
    listed = price_list_in(client, lead, "b2c", "general")
    assert [t["code"] for t in listed["priceTypes"]] == ["patient"]

    # a type the division doesn't quote with is refused
    refused = client.put(
        "/sales/prices/types", params={"division": "b2c", "team": "general"}, json={"codes": ["distributor"]}, headers=lead
    )
    assert refused.status_code == 422

    # handing them all back means following the division again
    back = client.put(
        "/sales/prices/types", params={"division": "b2c", "team": "general"}, json={"codes": list(division_types)}, headers=lead
    )
    assert back.json()["usesDivisionTypes"] is True


def test_a_rep_cannot_set_prices(client, as_):
    ana = as_("ana")  # a rep in B2C's General team
    assert client.get("/sales/prices", params={"division": "b2c", "team": "general"}, headers=ana).status_code == 403
    body = {"items": [{"productId": "whatever", "priceTypeCode": "patient", "amountCentavos": 100}]}
    assert client.put("/sales/prices", params={"division": "b2c", "team": "general"}, json=body, headers=ana).status_code == 403


def test_a_lead_cannot_price_another_teams_sheet(client, as_, lead, product):
    r = client.get("/sales/prices", params={"division": "b2c", "team": "md-telesales"}, headers=lead)
    assert r.status_code == 403


def test_a_price_change_is_written_to_the_audit_log(client, as_, lead, product):
    carmen = as_("carmen")
    set_price(client, lead, product["id"], product["prices"]["patient"] - 250)
    entries = client.get("/admin/audit", headers=carmen).json()["items"]
    assert any(e["action"] == "team_prices.changed" for e in entries)


@pytest.mark.parametrize("amount", [-1, 100_000_000_001])
def test_a_price_outside_what_a_number_can_be_is_refused(client, as_, lead, product, amount):
    assert set_price(client, lead, product["id"], amount).status_code == 422
