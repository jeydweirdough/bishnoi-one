"""A product's Certificate of Product Registration (CPR) from the Philippine FDA:
its number and the day it's valid until (decided 2026-10-24, workstream 04).

Every active stock product that's sold (not one that only groups its variants)
needs one. The number is kept as the FDA prints it, in capitals: letters for the
kind of registration, a hyphen, then its digits and letters (DR-XY12345,
DRP-1234-02, CMDR-123456, FR-4000001234567). The FDA's prefixes change, so the
shape is checked, not the prefix.

    missing    needs one and has no number
    no_date    has a number but not the day it's valid until
    expired    valid until a day that has passed
    expiring   valid until within the warning window (EXPIRY_WARNING_DAYS)
    valid      has both, and the day is further off
    not_needed a service, an asset, something inactive, or a product grouping variants
"""

import re
from datetime import date, timedelta

from sqlalchemy import and_, case, or_

from app.models import Product

SHAPE = re.compile(r"[A-Z]{2,6}(-[A-Z0-9]+)+")
STATES = ("missing", "no_date", "expired", "expiring", "valid", "not_needed")
# What needs someone: everything but valid and not needed.
ATTENTION = ("missing", "no_date", "expired", "expiring")
LABELS = {
    "missing": "No CPR",
    "no_date": "No validity date",
    "expired": "CPR expired",
    "expiring": "CPR expiring",
    "valid": "CPR valid",
    "not_needed": "Not needed",
}


def clean(value: str | None) -> str | None:
    """The number as the FDA prints it: capitals, no spaces. Blank is None; a wrong shape raises ValueError."""
    if value is None:
        return None
    text = re.sub(r"\s*-\s*", "-", value.strip().upper())
    text = re.sub(r"\s+", "", text)
    if not text:
        return None
    if len(text) > 40 or not SHAPE.fullmatch(text):
        raise ValueError("A CPR number is letters, a hyphen, then its digits, as on the certificate: DR-XY12345.")
    return text


def needs_one(p: Product) -> bool:
    return p.status == "active" and p.product_type == "stock" and not p.variant_count


def state(p: Product, today: date, warn_days: int) -> str:
    if not needs_one(p):
        return "not_needed" if not p.cpr_number else ("expired" if p.cpr_valid_until and p.cpr_valid_until < today else "valid")
    if not p.cpr_number:
        return "missing"
    if p.cpr_valid_until is None:
        return "no_date"
    if p.cpr_valid_until < today:
        return "expired"
    if p.cpr_valid_until <= today + timedelta(days=warn_days):
        return "expiring"
    return "valid"


def needs_one_sql():
    return (Product.status == "active") & (Product.product_type == "stock") & (Product.variant_count == 0)


def state_sql(today: date, warn_days: int):
    """The same as state(), worked out by the database, to filter and count on."""
    soon = today + timedelta(days=warn_days)
    has = and_(Product.cpr_number.is_not(None), Product.cpr_number != "")
    return case(
        (and_(needs_one_sql(), ~has), "missing"),
        (and_(needs_one_sql(), Product.cpr_valid_until.is_(None)), "no_date"),
        (and_(has, Product.cpr_valid_until < today), "expired"),
        (and_(needs_one_sql(), Product.cpr_valid_until <= soon), "expiring"),
        (or_(needs_one_sql(), has), "valid"),
        else_="not_needed",
    )


def out(p: Product, today: date, warn_days: int) -> dict:
    s = state(p, today, warn_days)
    return {
        "number": p.cpr_number,
        "validUntil": p.cpr_valid_until.isoformat() if p.cpr_valid_until else None,
        "daysLeft": (p.cpr_valid_until - today).days if p.cpr_valid_until else None,
        "state": s,
        "label": LABELS[s],
    }
