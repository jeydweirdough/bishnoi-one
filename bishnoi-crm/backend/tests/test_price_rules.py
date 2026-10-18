"""Price rules: a line's price from the first source that has one, then the
adjustments in the admin's order, then tax from Finance (benchmarks D4)."""

import pytest

from app import finance
from tests.test_customers import company, crew  # noqa: F401 (crew is a fixture)
from tests.test_quotes import catalogue, ids, line, preview  # noqa: F401 (fixtures)


def rules(client, headers) -> dict:
    return client.get("/pricing/rules", headers=headers).json()


def add_group(client, ana, code="HOSP", name="Hospital"):
    r = client.post("/pricing/groups", json={"code": code, "name": name}, headers=ana)
    assert r.status_code == 201, r.text


def add_rule(client, ana, **body):
    r = client.post("/pricing/conditions", json=body, headers=ana)
    assert r.status_code == 201, r.text
    return next(c for c in r.json()["conditions"] if c["name"] == body["name"])


def test_the_default_order_changes_nothing(client, crew, ids):
    """With no rules set, a quote prices exactly as before."""
    acme = company(client, crew["ria"])
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 2)]).json()
    assert got["lines"][0]["priceSource"] == "list_price"
    assert got["totalCentavos"] == 2 * 145000 and "tax" not in got


def test_a_price_groups_price_comes_first(client, ana, crew, ids):
    add_group(client, ana)
    add_rule(client, ana, kind="group_price", name="Amoxil for hospitals", productId=ids["AMX-500"], priceGroupCode="HOSP", amountCentavos=120000)
    hospital = company(client, crew["ria"], name="St. Luke's", priceGroupCode="HOSP")
    walk_in = company(client, crew["ria"], name="Corner Drug")
    got = preview(client, crew["ria"], hospital, [line(ids["AMX-500"], 1)]).json()
    assert (got["lines"][0]["unitPriceCentavos"], got["lines"][0]["priceSource"], got["priceGroup"]["name"]) == (120000, "group_price", "Hospital")
    # The price list the quote form uses says so too.
    listed = client.get(f"/companies/{hospital['id']}/price-list", headers=crew["ria"]).json()
    amox = next(p for p in listed["products"] if p["code"] == "AMX-500")
    assert (amox["prices"]["PATIENT"], amox["priceSources"]["PATIENT"]) == (120000, "group_price")
    # Someone outside the group pays the list price.
    assert preview(client, crew["ria"], walk_in, [line(ids["AMX-500"], 1)]).json()["lines"][0]["unitPriceCentavos"] == 145000


def test_the_admin_decides_which_price_wins(client, ana, crew, ids):
    add_group(client, ana)
    add_rule(client, ana, kind="group_price", name="Hospital Amoxil", productId=ids["AMX-500"], priceGroupCode="HOSP", amountCentavos=120000)
    # Ria's team (North) has its own price too, set by Finance (here an Administrator, so it stands at once;
    # a lead's waits for Finance: tests/test_price_approvals.py).
    north = next(t["id"] for t in client.get("/prices/teams", headers=crew["lia"]).json() if t["name"] == "North")
    r = client.put(f"/prices?team={north}", json={"items": [{"productId": ids["AMX-500"], "priceTypeCode": "PATIENT", "amountCentavos": 110000}]}, headers=ana)
    assert r.status_code == 200, r.text
    hospital = company(client, crew["ria"], name="St. Luke's", priceGroupCode="HOSP")

    def priced():
        got = preview(client, crew["ria"], hospital, [line(ids["AMX-500"], 1)]).json()["lines"][0]
        return got["priceSource"], got["unitPriceCentavos"]

    # The default order: the group's price comes before the team's.
    assert priced() == ("group_price", 120000)
    client.put("/pricing/procedure", json={"price": ["team_price", "group_price", "list_price"], "adjust": ["volume", "promo", "manual", "surcharge"]}, headers=ana)
    assert priced() == ("team_price", 110000)


def test_the_list_price_can_t_be_left_out(client, ana):
    r = client.put("/pricing/procedure", json={"price": ["group_price"], "adjust": []}, headers=ana)
    assert r.status_code == 422 and "list price" in r.text


def test_volume_scale_then_surcharge_in_order(client, ana, crew, ids):
    add_rule(client, ana, kind="volume", name="Bulk", tiers=[{"minQty": 10, "percentBp": 500}, {"minQty": 50, "percentBp": 1000}])
    add_rule(client, ana, kind="surcharge", name="Cold chain", productId=ids["AMX-500"], amountCentavos=500)
    acme = company(client, crew["ria"])
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 10)]).json()["lines"][0]
    gross = 10 * 145000
    assert got["volumeDiscountCentavos"] == gross * 5 // 100 and got["volumeName"] == "Bulk"
    assert got["surchargeCentavos"] == 10 * 500 and got["surchargeName"] == "Cold chain"
    assert got["totalCentavos"] == gross - gross * 5 // 100 + 5000
    # Switched off in the order: not applied.
    client.put("/pricing/procedure", json={"price": ["group_price", "team_price", "list_price"], "adjust": ["promo", "manual"]}, headers=ana)
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 10)]).json()["lines"][0]
    assert (got["volumeDiscountCentavos"], got["surchargeCentavos"], got["totalCentavos"]) == (0, 0, gross)


def test_rules_have_dates(client, ana, crew, ids):
    add_rule(client, ana, kind="volume", name="Next year", tiers=[{"minQty": 1, "percentBp": 5000}], startsOn="2099-01-01")
    acme = company(client, crew["ria"])
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()["lines"][0]
    assert got["volumeDiscountCentavos"] == 0
    assert next(c for c in rules(client, ana)["conditions"] if c["name"] == "Next year")["state"] == "upcoming"


def test_only_editors_change_rules_and_bad_rules_are_refused(client, ana, crew, ids):
    assert client.post("/pricing/groups", json={"code": "X", "name": "X"}, headers=crew["ria"]).status_code == 403
    assert client.post("/pricing/conditions", json={"kind": "group_price", "name": "No group", "productId": ids["AMX-500"], "amountCentavos": 1}, headers=ana).status_code == 422
    assert client.post("/pricing/conditions", json={"kind": "surcharge", "name": "Both", "amountCentavos": 1, "percentBp": 100}, headers=ana).status_code == 422
    add_group(client, ana)
    company(client, crew["ria"], name="St. Luke's", priceGroupCode="HOSP")
    assert client.delete("/pricing/groups/HOSP", headers=ana).status_code == 409  # a customer is in it
    assert rules(client, crew["ria"])["can"]["edit"] is False


def test_tax_needs_finance_linked(client, ana):
    r = client.put("/pricing/procedure", json={"price": ["list_price"], "adjust": [], "tax": True}, headers=ana)
    assert r.status_code == 422 and "Finance" in r.text


def test_tax_from_finance_goes_on_the_quote(client, app, ana, crew, ids, monkeypatch):
    """With the tax step on, Finance's answer is kept on the quote. (Finance is
    stood in for here; its own tests check the tax itself.)"""
    app.state.settings.finance_api_url = "http://finance.test"
    monkeypatch.setattr(type(app.state.settings), "finance_linked", property(lambda self: True))
    sent = {}

    def fake_post(settings, path, body):
        sent["body"] = body
        lines = [{"taxCentavos": round(l["unitPriceCentavos"] * 12 / 112), "totalCentavos": l["unitPriceCentavos"]} for l in body["lines"]]
        total = sum(l["unitPriceCentavos"] for l in body["lines"])
        return {
            "document": "Sales Invoice", "on": "2026-09-25", "pricesIncludeTax": True,
            "seller": {"regime": "vat", "regimeName": "VAT-registered"}, "notice": None,
            "summary": [{"key": "tax", "label": "VAT (12%)", "amountCentavos": sum(l["taxCentavos"] for l in lines)}],
            "lines": lines, "totalDueCentavos": total,
        }

    monkeypatch.setattr(finance, "_post", fake_post)
    client.put("/pricing/procedure", json={"price": ["list_price"], "adjust": ["promo", "manual"], "tax": True}, headers=ana)
    acme = company(client, crew["ria"])
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    assert got["tax"]["document"] == "Sales Invoice" and got["lines"][0]["taxCentavos"] > 0
    assert sent["body"]["lines"][0]["category"] == "standard"

    # Finance down: the preview still prices, and says why there's no tax; saving waits.
    def down(settings, path, body):
        raise finance.TaxUnavailable("Finance can't be reached right now, so the tax can't be worked out.")

    monkeypatch.setattr(finance, "_post", down)
    got = preview(client, crew["ria"], acme, [line(ids["AMX-500"], 1)]).json()
    assert "taxError" in got and got["totalCentavos"] == 145000


@pytest.mark.parametrize("category", ["exempt", "zero_rated"])
def test_a_product_s_vat_category_is_what_finance_is_sent(client, ana, ids, category):
    r = client.patch(f"/products/{ids['AMX-500']}", json={"vatCategory": category}, headers=ana)
    assert r.status_code == 200 and r.json()["vatCategory"] == category
    assert client.patch(f"/products/{ids['AMX-500']}", json={"vatCategory": "luxury"}, headers=ana).status_code == 422
