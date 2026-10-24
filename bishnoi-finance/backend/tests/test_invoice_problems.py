"""A draft that can't be worked out says what's wrong and where (fixed 2026-10-22: it
said only "Some lines need fixing", even when it was the customer's TIN)."""

from .test_invoices import draft, ready
from .test_tax_api import app, ana, ben, client  # noqa: F401 (fixtures)


def test_a_wrong_customer_tin_is_named(client, ana):
    ready(client, ana)
    d = draft(client, ana, customerTin="1231231230000")  # 13 digits: neither 12 nor 14
    assert d["problem"].startswith("Customer's TIN: Enter the TIN as 9 digits")
    assert set(d["problemFields"]) == {"customerTin"}


def test_a_missing_senior_citizen_id_is_named(client, ana):
    ready(client, ana)
    d = draft(client, ana, treatment="senior_citizen")
    assert d["problem"].startswith("ID number: A senior citizen's ID number goes on the invoice")
    assert set(d["problemFields"]) == {"buyerIdNumber"}


def test_a_line_problem_says_which_line(client, ana):
    ready(client, ana)
    good = {"description": "Amoxicillin", "quantity": 1, "unitPriceCentavos": 1000}
    d = draft(client, ana, lines=[good, {**good, "category": "no-such-category"}])
    assert d["problem"] == "Line 2 (VAT): Pick the product's VAT category."
    assert set(d["problemFields"]) == {"lines.1.category"}


def test_a_good_draft_has_no_problem(client, ana):
    ready(client, ana)
    d = draft(client, ana, customerTin="123-456-789-00000")
    assert d["problem"] is None and d["problemFields"] == {} and d["computed"]["totalDueCentavos"] == 224000
