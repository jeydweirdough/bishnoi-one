"""The pricing engine on its own: rules and arithmetic, no database."""

import pytest

from app.pricing import DivisionRules, PriceTypeInfo, PricingError, ProductInfo, PromoInfo, price_quote, share
from app.schemas import QuoteIn

TYPES = {
    "srp": PriceTypeInfo("srp", "SRP", "list", False, False),
    "patient": PriceTypeInfo("patient", "Patient's Price", "list", False, False),
    "doctor": PriceTypeInfo("doctor", "Doctor's Price", "list", False, False),
    "special": PriceTypeInfo("special", "Special Price", "entered", True, True),
    "government": PriceTypeInfo("government", "Government Price", "list", True, True),
}
B2C = DivisionRules("b2c", True, True, 1000, {"patient": "always", "srp": "always", "doctor": "with_rx", "special": "always"})
B2B = DivisionRules("b2b", True, False, 1000, {"srp": "always"})
BID = DivisionRules("bid", False, True, 1000, {})
PRODUCTS = {
    "p1": ProductInfo("p1", "P1", "Product One", "Box", True, {"srp": 10000, "patient": 9000, "doctor": 8000}),
    "p2": ProductInfo("p2", "P2", "Product Two", "Box", True, {"srp": 5000}),
    "old": ProductInfo("old", "OLD", "Old Product", "Box", False, {"srp": 100, "patient": 100}),
}
ISSUERS = {"dswd": "DSWD", "pcso": "PCSO"}
LETTER = {"number": "GL-1", "issuedOn": "2026-09-01", "amountCentavos": 18000}


def quote(**changes) -> QuoteIn:
    body = {"priceType": "patient", "lines": [{"productId": "p1", "quantity": 2}]}
    return QuoteIn.model_validate(body | changes)


def run(q: QuoteIn, rules: DivisionRules = B2C, promos: dict | None = None, **kw):
    return price_quote(q, rules, TYPES, PRODUCTS, promos or {}, ISSUERS, **kw)


def errors(q: QuoteIn, **kw) -> dict[str, str]:
    with pytest.raises(PricingError) as caught:
        run(q, **kw)
    return {".".join(map(str, loc)): message for loc, message in caught.value.errors}


def test_share_rounds_half_up_to_the_centavo():
    assert share(1, 5000) == 1  # half a centavo rounds up
    assert share(3, 3333) == 1
    assert share(18000, 1000) == 1800


def test_list_price_times_quantity():
    priced = run(quote())
    assert (priced.gross, priced.total, priced.approval_reasons) == (18000, 18000, ())
    assert priced.lines[0].unit_price == 9000


def test_only_the_divisions_price_types():
    assert run(quote(priceType="srp"), rules=B2B).total == 20000
    assert errors(quote(priceType="patient"), rules=B2B) == {"priceType": "Pick one of this division's prices."}


def test_an_rx_means_doctors_price_in_b2c():
    assert errors(quote(rx=True)) == {"priceType": "With an Rx, use Doctor's Price."}
    assert run(quote(rx=True, priceType="doctor")).total == 16000


def test_doctors_price_is_only_for_quotes_with_an_rx():
    assert errors(quote(priceType="doctor")) == {"priceType": "Doctor's Price is only for quotes with an Rx."}


def test_special_price_needs_notes_a_typed_price_and_approval():
    found = errors(quote(priceType="special"))
    assert found == {"notes": "Special Price needs notes.", "lines.0.unitPriceCentavos": "Enter the Special Price per unit."}
    priced = run(
        quote(priceType="special", notes="Matching a competitor.", lines=[{"productId": "p1", "quantity": 2, "unitPriceCentavos": 7000}])
    )
    assert priced.total == 14000
    assert priced.approval_reasons == ("price",)


def test_guarantee_letters():
    assert errors(quote(payer="dswd")) == {"letter": "Add the DSWD guarantee letter's number, date and amount."}
    assert errors(quote(payer="nobody")) == {"payer": "Pick who pays."}
    assert errors(quote(priceType="srp", payer="dswd", letter=LETTER), rules=B2B) == {
        "payer": "This division doesn't take guarantee letters."
    }
    assert run(quote(payer="pcso", letter=LETTER)).total == 18000


def test_a_preview_skips_the_paperwork():
    assert run(quote(payer="dswd", priceType="special", lines=[{"productId": "p1", "quantity": 1, "unitPriceCentavos": 500}]), paperwork=False).total == 500


def test_products_must_be_active_priced_and_listed_once():
    assert errors(quote(lines=[{"productId": "old", "quantity": 1}])) == {"lines.0.productId": "Pick a product from the price list."}
    assert errors(quote(lines=[{"productId": "p2", "quantity": 1}])) == {
        "lines.0.productId": "Product Two has no Patient's Price yet. Ask Inventory to add it."
    }
    twice = [{"productId": "p1", "quantity": 1}, {"productId": "p1", "quantity": 1}]
    assert errors(quote(lines=twice)) == {"lines.1.productId": "This product is already on the quote."}


def test_notes_only_divisions_have_no_price_list():
    assert errors(quote(), rules=BID) == {"priceType": "This division quotes with notes only, not a price list."}


PERCENT = PromoInfo("pct", "10% off", "percent", percent_bp=1000)
AMOUNT = PromoInfo("amt", "₱50 off each", "amount", amount_centavos=5000, product_ids=frozenset({"p1"}))
FREE = PromoInfo("free", "Buy 2 get 1", "free_goods", buy_qty=2, free_qty=1)
TIERED = PromoInfo("tier", "Volume", "tiered", tiers=((2, 500), (5, 1000)))
PROMOS = {p.id: p for p in (PERCENT, AMOUNT, FREE, TIERED)}


def with_promo(promo_id: str, quantity: int = 2, **line) -> QuoteIn:
    return quote(lines=[{"productId": "p1", "quantity": quantity, "promoId": promo_id, **line}])


def test_percent_off():
    line = run(with_promo("pct"), promos=PROMOS).lines[0]
    assert (line.promo_discount, line.total) == (1800, 16200)


def test_amount_off_each_unit_capped_at_the_line():
    line = run(with_promo("amt"), promos=PROMOS).lines[0]
    assert line.promo_discount == 10000 and line.total == 8000
    big = PromoInfo("big", "₱500 off", "amount", amount_centavos=50000)
    assert run(with_promo("big"), promos={"big": big}).lines[0].total == 0


def test_free_goods():
    line = run(with_promo("free", quantity=5), promos=PROMOS).lines[0]
    assert (line.free_quantity, line.total) == (2, 45000)
    assert errors(with_promo("free", quantity=1), promos=PROMOS) == {"lines.0.promoId": "Order at least 2 for this promo."}


def test_volume_tiers_take_the_highest_reached():
    assert run(with_promo("tier", quantity=2), promos=PROMOS).lines[0].promo_discount == 900  # 5% of 18000
    assert run(with_promo("tier", quantity=6), promos=PROMOS).lines[0].promo_discount == 5400  # 10% of 54000
    assert errors(with_promo("tier", quantity=1), promos=PROMOS) == {"lines.0.promoId": "Order at least 2 for this promo."}


def test_a_promo_must_apply_here():
    assert errors(with_promo("gone"), promos=PROMOS) == {
        "lines.0.promoId": "That promo doesn't apply to this product here, or it has ended."
    }
    only_p2 = PromoInfo("p2only", "P2 only", "percent", percent_bp=500, product_ids=frozenset({"p2"}))
    assert "lines.0.promoId" in errors(with_promo("p2only"), promos={"p2only": only_p2})


def test_manual_discount_comes_after_the_promo():
    line = run(with_promo("pct", discount={"kind": "percent", "value": 1000}), promos=PROMOS).lines[0]
    assert (line.promo_discount, line.discount, line.total) == (1800, 1620, 14580)


def test_manual_discount_cant_exceed_the_line():
    assert errors(quote(lines=[{"productId": "p1", "quantity": 1, "discount": {"kind": "amount", "value": 9001}}])) == {
        "lines.0.discount": "The discount is more than the line is worth."
    }


def test_big_manual_discounts_need_finance():
    at_limit = run(quote(lines=[{"productId": "p1", "quantity": 2, "discount": {"kind": "percent", "value": 1000}}]))
    assert at_limit.approval_reasons == ()
    over = run(quote(lines=[{"productId": "p1", "quantity": 2, "discount": {"kind": "percent", "value": 1001}}]))
    assert over.approval_reasons == ("discount",)
