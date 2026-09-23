"""Bundles: a set of products at one price, on the quote one way or the other."""

from datetime import date, timedelta

import pytest

from app.bundles import BundleError, BundleInfo, BundleItemInfo, share_price
from app.pricing import ProductInfo
from tests.conftest import a_customer, field_messages, preview_quote, price_list_in

START = (date.today() - timedelta(days=2)).isoformat()


def a_product(id_: str, price: int) -> ProductInfo:
    return ProductInfo(id_, id_.upper(), id_.title(), "box", True, {"srp": price})


def a_bundle(prices: dict[str, int], set_price: int, qty: int = 1) -> BundleInfo:
    return BundleInfo("b1", "PACK", "Starter Pack", set_price, False, tuple(BundleItemInfo(k, qty) for k in prices))


# --- the sharing maths, on its own ----------------------------------------------------


def test_the_set_price_is_shared_by_what_each_item_lists_at():
    """The page's worked example: P2,000 of goods sold as a P1,800 set."""
    products = {"amox": a_product("amox", 70000), "para": a_product("para", 40000), "vitc": a_product("vitc", 20000)}
    bundle = BundleInfo(
        "b1", "BDL-START", "Starter Pack", 180000, False,
        (BundleItemInfo("amox", 2), BundleItemInfo("para", 1), BundleItemInfo("vitc", 1)),
    )
    assert share_price(bundle, 1, products, "srp", "SRP") == [
        ("amox", 2, 126000),  # lists at P1,400, 70% of the set -> P1,260
        ("para", 1, 36000),   # lists at P400, 20% -> P360
        ("vitc", 1, 18000),   # lists at P200, 10% -> P180
    ]


@pytest.mark.parametrize(
    "prices, set_price, sets",
    [
        ({"a": 1000, "b": 1000, "c": 1000}, 1000, 1),  # thirds of a peso
        ({"a": 1000, "b": 1000, "c": 1000}, 1000, 7),
        ({"a": 100, "b": 100, "c": 100}, 1, 1),        # one centavo, three ways
        ({"a": 999999, "b": 1, "c": 1}, 123457, 1),    # wildly lopsided
        ({"a": 5000}, 4999, 1),                        # a set of one
        ({"a": 100, "b": 200}, 100000, 3),             # dearer than its parts
        ({"a": 333, "b": 667}, 99999, 11),
    ],
)
def test_the_lines_always_add_up_to_the_set_price(prices, set_price, sets):
    products = {k: a_product(k, v) for k in prices for v in [prices[k]]}
    shared = share_price(a_bundle(prices, set_price), sets, products, "srp", "SRP")
    assert sum(amount for _, _, amount in shared) == set_price * sets
    assert all(amount >= 0 for _, _, amount in shared)


def test_a_set_it_cannot_price_is_refused_rather_than_charged_wrong():
    products = {"a": a_product("a", 1000)}
    with pytest.raises(BundleError, match="no products in it"):
        share_price(BundleInfo("b", "P", "Pack", 500, False, ()), 1, products, "srp", "SRP")
    with pytest.raises(BundleError, match="no longer sold"):
        share_price(a_bundle({"gone": 0}, 500), 1, {}, "srp", "SRP")
    # In the price list, but with no price of the type this quote uses.
    priceless = ProductInfo("b", "B", "B", "box", True, {"patient": 900})
    with pytest.raises(BundleError, match="has no SRP yet"):
        share_price(a_bundle({"b": 0}, 500), 1, {"b": priceless}, "srp", "SRP")
    free = ProductInfo("c", "C", "C", "box", True, {"srp": 0})
    with pytest.raises(BundleError, match="no SRP to share its price across"):
        share_price(a_bundle({"c": 0}, 500), 1, {"c": free}, "srp", "SRP")


# --- keeping bundles ------------------------------------------------------------------


def a_set(client, headers, ids, **over) -> dict:
    return {
        "code": "BDL-START",
        "name": "Starter Pack",
        "priceCentavos": 300000,
        "items": [{"productId": ids["AMOX-500"], "qty": 2}, {"productId": ids["MET-500"], "qty": 1}],
        "startsOn": START,
        "divisionCodes": ["b2c"],
        **over,
    }


def test_inventory_staff_keep_bundles(client, as_):
    iris = as_("iris")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}

    r = client.post("/inventory/bundles", json=a_set(client, iris, ids), headers=iris)
    assert r.status_code == 201
    made = r.json()
    assert made["state"] == "running" and made["asOneLine"] is True
    assert [i["qty"] for i in made["items"]] == [2, 1]
    bundle_id = made["id"]

    offered = lambda module, who: {b["code"] for b in price_list_in(client, as_(who), module)["bundles"]}  # noqa: E731
    assert "BDL-START" in offered("b2c", "ana")
    assert "BDL-START" not in offered("hos", "grace")

    r = client.put(f"/inventory/bundles/{bundle_id}", json=a_set(client, iris, ids, divisionCodes=["b2c", "hos"]), headers=iris)
    assert r.json()["divisionCodes"] == ["b2c", "hos"]
    assert "BDL-START" in offered("hos", "grace")

    # Switched off, never deleted: quotes that used it still name it.
    assert client.patch(f"/inventory/bundles/{bundle_id}", json={"isActive": False}, headers=iris).json()["state"] == "off"
    assert "BDL-START" not in offered("b2c", "ana")
    assert [b["id"] for b in client.get("/inventory/bundles", params={"state": "off"}, headers=iris).json()] == [bundle_id]


def test_a_bundle_has_to_make_sense(client, as_):
    iris = as_("iris")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    assert client.post("/inventory/bundles", json=a_set(client, iris, ids), headers=iris).status_code == 201

    def refuse(**over):
        return field_messages(client.post("/inventory/bundles", json=a_set(client, iris, ids, **over), headers=iris))

    assert refuse() == {"code": "Another bundle already uses that code."}
    assert refuse(code="BDL-2", items=[{"productId": ids["AMOX-500"], "qty": 1}] * 2) == {
        "items": "Each product goes in once, with how many of it the set contains."
    }
    assert refuse(code="BDL-3", items=[{"productId": "no-such-product", "qty": 1}]) == {
        "items": "Some of those products don't exist, or are no longer sold."
    }
    # Finance has no prices of its own, so nothing can be offered to it.
    assert refuse(code="BDL-4", divisionCodes=["finance"]) == {"divisionCodes": "Pick divisions that quote."}
    # BID does have pricing rules, even though it bids rather than selling from
    # a list, so it is offerable — what it may quote with is its own setting.
    assert client.post("/inventory/bundles", json=a_set(client, iris, ids, code="BDL-BID", divisionCodes=["bid"]), headers=iris).status_code == 201
    assert refuse(code="BDL-5", startsOn="2026-06-01", endsOn="2026-05-01") == {"endsOn": "The end date is before the start date."}
    assert refuse(code="BDL-6", items=[]) == {"items": "Value error, Put at least one product in the set."}
    assert refuse(code="BDL-7", divisionCodes=[]) == {
        "divisionCodes": "Value error, Pick at least one division that may sell it."
    }


def test_who_can_touch_bundles(client, as_):
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=as_("iris")).json()}
    body = a_set(client, as_("iris"), ids)
    assert client.get("/inventory/bundles", headers=as_("ana")).status_code == 403
    assert client.get("/inventory/bundles", headers=as_("ramon")).status_code == 200  # Inventory, view only
    assert client.post("/inventory/bundles", json=body, headers=as_("ramon")).status_code == 403


# --- quoting one ----------------------------------------------------------------------


def make(client, headers, ids, **over) -> str:
    r = client.post("/inventory/bundles", json=a_set(client, headers, ids, **over), headers=headers)
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def preview(client, headers, lines, customer=None, who="ana", division="b2c") -> dict:
    """A quote as the rep sees it forming. A bundle is offered to a division,
    and a quote takes its division from its customer, so a preview needs one."""
    customer = customer or a_customer(client, headers, division)
    return preview_quote(client, headers, customer, {"priceType": "srp", "lines": lines}).json()


def test_a_bundle_reads_one_way_or_the_other_and_totals_the_same(client, as_):
    iris, ana = as_("iris"), as_("ana")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    whole = make(client, iris, ids, code="BDL-ONE", asOneLine=True)
    split = make(client, iris, ids, code="BDL-MANY", asOneLine=False)

    one = preview(client, ana, [{"bundleId": whole, "quantity": 1}])
    assert len(one["lines"]) == 1
    assert one["lines"][0]["productCode"] == "BDL-ONE" and one["lines"][0]["productId"] == ""
    assert "2 × Amoxicillin 500 mg" in one["lines"][0]["contents"]
    assert one["totalCentavos"] == 300000

    many = preview(client, ana, [{"bundleId": split, "quantity": 1}])
    assert [line["productCode"] for line in many["lines"]] == ["AMOX-500", "MET-500"]
    assert all(line["bundleName"] == "Starter Pack" for line in many["lines"])
    assert sum(line["totalCentavos"] for line in many["lines"]) == 300000
    assert many["totalCentavos"] == one["totalCentavos"]


def test_several_sets_still_come_to_the_right_money(client, as_):
    iris, ana = as_("iris"), as_("ana")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    split = make(client, iris, ids, code="BDL-MANY", asOneLine=False, priceCentavos=299999)
    out = preview(client, ana, [{"bundleId": split, "quantity": 7}])
    assert out["totalCentavos"] == 299999 * 7
    assert [line["quantity"] for line in out["lines"]] == [14, 7]


def test_a_bundles_price_is_the_price(client, as_):
    iris, ana = as_("iris"), as_("ana")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    bundle_id = make(client, iris, ids)

    maria = a_customer(client, ana, "b2c")

    def refuse(line):
        r = preview_quote(client, ana, maria, {"priceType": "srp", "lines": [line]})
        assert r.status_code == 422
        return str(r.json())

    assert "no promo or discount on top" in refuse({"bundleId": bundle_id, "quantity": 1, "promoId": "x"})
    assert "no promo or discount on top" in refuse(
        {"bundleId": bundle_id, "quantity": 1, "discount": {"kind": "percent", "value": 500}}
    )
    assert "either a product or a bundle" in refuse({"bundleId": bundle_id, "productId": ids["AMOX-500"], "quantity": 1})
    assert "either a product or a bundle" in refuse({"quantity": 1})


def test_a_bundle_you_cannot_have(client, as_):
    iris, ana, grace = as_("iris"), as_("ana"), as_("grace")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    bundle_id = make(client, iris, ids)  # B2C only

    # Grace sells to hospitals. Quoting a B2C-only bundle to a HOS customer is
    # refused on the bundle, not on the customer: the customer is properly hers.
    hospital = a_customer(client, grace, "hos")
    assert field_messages(
        preview_quote(client, grace, hospital, {"priceType": "srp", "lines": [{"bundleId": bundle_id, "quantity": 1}]})
    ) == {"lines.0.bundleId": "That bundle isn't offered here, or it has ended."}

    maria = a_customer(client, ana, "b2c")
    twice = preview_quote(
        client, ana, maria, {"priceType": "srp", "lines": [{"bundleId": bundle_id, "quantity": 1}] * 2}
    )
    assert field_messages(twice) == {"lines.1.bundleId": "This bundle is already on the quote."}

    client.patch(f"/inventory/bundles/{bundle_id}", json={"isActive": False}, headers=iris)
    assert "isn't offered here" in str(preview(client, ana, [{"bundleId": bundle_id, "quantity": 1}]))


def test_the_same_product_may_be_in_a_set_and_loose_on_the_same_quote(client, as_):
    """Buying the pack plus five more of one of its products is an ordinary thing to do."""
    iris, ana = as_("iris"), as_("ana")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    split = make(client, iris, ids, code="BDL-MANY", asOneLine=False)
    out = preview(client, ana, [{"bundleId": split, "quantity": 1}, {"productId": ids["AMOX-500"], "quantity": 5}])
    assert len(out["lines"]) == 3
    loose = [line for line in out["lines"] if line["bundleId"] is None]
    assert len(loose) == 1 and loose[0]["quantity"] == 5


def test_a_saved_quote_keeps_what_the_bundle_was(client, as_):
    """Editing a bundle afterwards must not change a quote already given."""
    from tests.conftest import customer_id, post_quote

    iris, ana = as_("iris"), as_("ana")
    ids = {p["code"]: p["id"] for p in client.get("/inventory/products", headers=iris).json()}
    bundle_id = make(client, iris, ids)
    customer = customer_id(client, ana, "b2c", "Maria Lopez")

    r = post_quote(client, ana, "b2c", customer, {"priceType": "srp", "lines": [{"bundleId": bundle_id, "quantity": 1}]})
    assert r.status_code == 201, r.json()
    saved = r.json()
    line = saved["lines"][0]
    assert line["bundleId"] == bundle_id and line["bundleName"] == "Starter Pack"
    assert line["totalCentavos"] == 300000

    client.put(f"/inventory/bundles/{bundle_id}", json=a_set(client, iris, ids, priceCentavos=999900), headers=iris)
    again = client.get(f"/sales/customers/{customer}/quotes/{saved['id']}", headers=ana)
    if again.status_code == 200:
        assert again.json()["lines"][0]["totalCentavos"] == 300000


# --- the company default --------------------------------------------------------------


def test_which_way_new_bundles_start_is_the_companys_choice(client, as_):
    carmen = as_("carmen")
    assert client.get("/admin/pricing", headers=carmen).json()["bundlesAsOneLine"] is True

    r = client.put("/admin/pricing/defaults", json={"bundlesAsOneLine": False}, headers=carmen)
    assert r.status_code == 200 and r.json()["bundlesAsOneLine"] is False
    assert client.get("/admin/pricing", headers=carmen).json()["bundlesAsOneLine"] is False

    # A default, not a rule: it says nothing about bundles that already exist.
    assert client.put("/admin/pricing/defaults", json={"bundlesAsOneLine": True}, headers=carmen).json()["bundlesAsOneLine"] is True
    assert client.put("/admin/pricing/defaults", json={"bundlesAsOneLine": False}, headers=as_("ana")).status_code == 403
