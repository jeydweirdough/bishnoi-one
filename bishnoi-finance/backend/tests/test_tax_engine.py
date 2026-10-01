"""The tax engine and the Philippines pack, without a database: the worked
examples an accountant would check an invoice against."""

from datetime import date

import pytest

from app.tax.engine import LineIn, SaleIn, TaxError, compute
from app.tax.packs import ph

TODAY = date(2026, 9, 25)


def pack_rates(code: str, on: date) -> int | None:
    """The pack's own dated rates, as the database would hold them."""
    for c, bp, start, end, _ in ph.RATES:
        if c == code and date.fromisoformat(start) <= on and (end is None or on <= date.fromisoformat(end)):
            return bp
    return None


def sale(*lines: LineIn, regime="vat", treatment="regular", inclusive=True, on=TODAY):
    return compute(ph, pack_rates, SaleIn(regime, treatment, inclusive, on, list(lines)))


def peso(amount: float) -> int:
    return round(amount * 100)


def test_a_regular_sale_with_vat_in_the_price():
    out = sale(LineIn(1, peso(112), "standard"))
    line = out.lines[0]
    assert (line.base, line.tax, line.total) == (peso(100), peso(12), peso(112))
    assert (out.taxable_sales, out.tax, out.total_due) == (peso(100), peso(12), peso(112))


def test_prices_without_vat_get_it_added():
    out = sale(LineIn(2, peso(50), "standard"), inclusive=False)
    assert (out.taxable_sales, out.tax, out.total_due) == (peso(100), peso(12), peso(112))


def test_a_senior_citizen_buying_medicine_pays_80_on_112():
    """RR 7-2010: VAT off (₱100), then 20% off that (₱20), and the sale is VAT-exempt."""
    out = sale(LineIn(1, peso(112), "standard", relief_eligible=True), treatment="senior_citizen")
    line = out.lines[0]
    assert (line.base, line.relief, line.taxable, line.tax, line.code) == (peso(100), peso(20), peso(80), 0, ph.EXEMPT)
    assert (out.exempt_sales, out.tax, out.relief, out.total_due) == (peso(80), 0, peso(20), peso(80))
    assert out.relief_label == "Senior citizen discount (20%)"


def test_a_pwd_gets_the_same_but_only_on_what_qualifies():
    out = sale(
        LineIn(1, peso(112), "standard", relief_eligible=True),  # medicine
        LineIn(1, peso(56), "standard"),  # something that doesn't qualify
        treatment="pwd",
    )
    assert [line.total for line in out.lines] == [peso(80), peso(56)]
    assert (out.exempt_sales, out.taxable_sales, out.tax, out.total_due) == (peso(80), peso(50), peso(6), peso(136))


def test_exempt_and_zero_rated_products():
    out = sale(LineIn(1, peso(100), "exempt"), LineIn(1, peso(100), "zero_rated"))
    assert (out.exempt_sales, out.zero_rated_sales, out.tax, out.total_due) == (peso(100), peso(100), 0, peso(200))


def test_a_zero_rated_buyer_pays_no_vat_on_vatable_goods():
    out = sale(LineIn(1, peso(112), "standard"), treatment="zero_rated_buyer")
    assert (out.zero_rated_sales, out.tax, out.total_due) == (peso(100), 0, peso(100))


def test_a_non_vat_seller_charges_no_vat_and_owes_percentage_tax():
    out = sale(LineIn(1, peso(100), "standard"), regime="non_vat")
    assert (out.non_taxable_sales, out.tax, out.total_due) == (peso(100), 0, peso(100))
    assert (out.seller_tax_code, out.seller_tax) == (ph.PERCENTAGE, peso(3))


def test_percentage_tax_follows_the_date_of_the_sale():
    """1% under CREATE, 1 July 2020 to 30 June 2023; 3% either side."""
    during = sale(LineIn(1, peso(100), "standard"), regime="non_vat", on=date(2021, 5, 1))
    after = sale(LineIn(1, peso(100), "standard"), regime="non_vat", on=date(2023, 7, 1))
    assert (during.seller_tax, after.seller_tax) == (peso(1), peso(3))


def test_a_non_vat_senior_discount_comes_off_the_price():
    out = sale(LineIn(1, peso(100), "standard", relief_eligible=True), regime="non_vat", treatment="senior_citizen")
    assert (out.relief, out.total_due) == (peso(20), peso(80))


def test_inclusive_lines_always_total_their_price():
    """Rounding happens once per line, and a regular line's total is exactly its price."""
    prices = [999, 1, 3333, 12345, 7, 100_001]
    out = sale(*[LineIn(1, p, "standard") for p in prices])
    assert [line.total for line in out.lines] == prices
    assert out.total_due == sum(prices) == out.taxable_sales + out.tax


def test_line_discounts_come_off_before_tax():
    out = sale(LineIn(3, peso(112), "standard", discount=peso(112)))  # 3 for the price of 2
    assert (out.taxable_sales, out.tax, out.total_due) == (peso(200), peso(24), peso(224))


def test_no_rate_on_record_for_the_day_is_refused():
    with pytest.raises(TaxError, match="VAT 12%"):
        sale(LineIn(1, peso(112), "standard"), on=date(2005, 1, 1))


def test_bad_lines_are_refused():
    with pytest.raises(TaxError, match="discount"):
        sale(LineIn(1, peso(10), "standard", discount=peso(11)))
    with pytest.raises(ValueError, match="category"):
        sale(LineIn(1, peso(10), "luxury"))
