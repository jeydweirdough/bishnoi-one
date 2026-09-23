"""The fields a company puts on its own records, beyond the ones Orbit knows.

Orbit knows a product has a code, a name and a unit, and that a customer has a
name and a kind. What else either of them needs is the company's business: a
pharmacy wants Generic name, Strength and Form on a product; a machinery
dealer wants Model and Warranty instead. Rather than a column per industry,
each company writes its own fields down in Settings and its records carry the
values under those fields' keys — `Product.details`, or `details` on a
customer's record.

The order form's extra fields are the same thing with `subject = "order"`, so
all three screens are one mechanism and one table.

Seeding gives a new company the fields its industry template starts with and
nothing more. It never writes over fields a company already has, for the same
reason app/lists.py doesn't: from the moment the company exists, those belong
to its admins.
"""

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import Loc, field_errors
from app.models import FIELD_SUBJECTS, CustomField, Organization
from app.tenancy import company_of

DEFAULT_TEMPLATE = "generic_b2b"

# Where a subject's fields are edited. Orders came first and keeps its own
# screen, so Settings -> Fields shows the other two.
ORDERS_SCREEN = "Settings -> Orders"
FIELDS_SCREEN = "Settings -> Fields"


@dataclass(frozen=True)
class FieldSubject:
    key: str
    name: str
    # The subject on its own, for a sentence about one record ("no product field").
    one: str
    help: str
    # Where an admin changes these fields.
    screen: str
    # The screens that ask for them and show them back.
    shown_on: tuple[str, ...]


SUBJECTS: tuple[FieldSubject, ...] = (
    FieldSubject(
        "order", "Orders", "order", "Extra questions the order form asks.", ORDERS_SCREEN,
        ("The order form", "An order's page"),
    ),
    FieldSubject(
        "product", "Products", "product", "What your products have that Orbit doesn't know about.", FIELDS_SCREEN,
        ("Inventory", "The product form", "The price list"),
    ),
    FieldSubject(
        "customer", "Customers", "customer", "What you keep about a customer beyond their contact details.", FIELDS_SCREEN,
        ("A customer's page", "The customer form"),
    ),
)
BY_SUBJECT: dict[str, FieldSubject] = {s.key: s for s in SUBJECTS}
assert tuple(BY_SUBJECT) == FIELD_SUBJECTS, "app/fields.py and models.FIELD_SUBJECTS disagree"

# The subjects Settings -> Fields owns. Order fields stay on their own screen.
OWN_SUBJECTS: tuple[str, ...] = tuple(s.key for s in SUBJECTS if s.screen == FIELDS_SCREEN)

# The fields a new company starts with, per industry template: a starting
# point, not a rule. Pharma's three are the columns a product used to have, so
# their keys are the old column names — migration 0016 moves the values under
# exactly these keys. A company selling anything else starts with none and
# writes its own.
StartingField = tuple[str, str, str]  # key, label, type
TEMPLATES: dict[str, dict[str, list[StartingField]]] = {
    "pharma_ph": {
        "product": [
            ("generic_name", "Generic name", "text"),
            ("strength", "Strength", "text"),
            ("form", "Form", "text"),
        ],
    },
    "generic_b2b": {},
}

# What one value may be. Long enough for a model number, an address or a note,
# short enough that nobody stores a document in a product.
MAX_TEXT = 200
MAX_TEXTAREA = 2000
MAX_NUMBER = 1_000_000_000_000
# A record can't have more values than a company can have fields; well past
# that, the payload isn't a form's, so it's refused in one line rather than
# answered with hundreds of messages.
MAX_VALUES = 60


def seed_fields(db: Session, template: str | None = None) -> None:
    """Give this company any subject's fields it hasn't got. A subject with
    fields is left alone, even one an admin emptied: that was meant."""
    org = db.get(Organization, company_of(db))
    chosen = template or (org.template if org else DEFAULT_TEMPLATE)
    starting = TEMPLATES.get(chosen, TEMPLATES[DEFAULT_TEMPLATE])
    have = set(db.scalars(select(CustomField.subject).distinct()))
    for subject in FIELD_SUBJECTS:
        if subject in have:
            continue
        for order, (key, label, kind) in enumerate(starting.get(subject, [])):
            db.add(CustomField(subject=subject, key=key, label=label, type=kind, sort_order=order))
    db.flush()


def fields(db: Session, subject: str, active_only: bool = False) -> list[CustomField]:
    rows = db.scalars(
        select(CustomField).where(CustomField.subject == subject).order_by(CustomField.sort_order, CustomField.label)
    )
    return [f for f in rows if f.is_active or not active_only]


def field_out(f: CustomField) -> dict:
    return {
        "key": f.key,
        "label": f.label,
        "type": f.type,
        "required": f.required,
        "options": list(f.options or []),
        "help": f.help,
        "section": f.section,
        "isActive": f.is_active,
    }


def fields_out(db: Session, subject: str, active_only: bool = False) -> list[dict]:
    return [field_out(f) for f in fields(db, subject, active_only=active_only)]


def a_number(value: Any) -> float | int | None:
    """The number in what was typed, or None. True isn't 1 here: a tick isn't a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
        if number.is_integer():
            number = int(number)
    else:
        return None
    return number if math.isfinite(number) else None


def is_a_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def clean_value(f: CustomField, value: Any) -> tuple[Any, str | None]:
    """The value as it is stored, or the sentence saying why it can't be.
    Nothing typed is "not filled in", which is the same as leaving it out."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if f.type == "number":
        number = a_number(value)
        if number is None:
            return None, f"{f.label} should be a number."
        if abs(number) > MAX_NUMBER:
            return None, f"{f.label} is a bigger number than Orbit keeps."
        return number, None
    if not isinstance(value, str):
        return None, f"{f.label} should be typed as text."
    text = value.strip()
    if f.type == "date":
        return (text, None) if is_a_date(text) else (None, f"{f.label} should be a date, like 2026-03-31.")
    if f.type == "choice":
        if text not in (f.options or []):
            return None, f"Pick one of the choices for {f.label}."
        return text, None
    limit = MAX_TEXTAREA if f.type == "textarea" else MAX_TEXT
    if len(text) > limit:
        return None, f"{f.label} is too long. Use at most {limit} characters."
    return text, None


def check_values(db: Session, subject: str, values: dict[str, Any], loc: str = "details") -> dict[str, Any]:
    """What a record may keep for this company's fields of that subject, or a
    message per field that's wrong, landing on the field it's about.

    A switched-off field's value is still accepted, so a record that already
    carries one can be saved again; only an active field can be required."""
    known = {f.key: f for f in fields(db, subject)}
    if len(values) > MAX_VALUES:
        raise field_errors([((loc,), "That's more fields than your company has.")])
    errors: list[tuple[Loc, str]] = []
    kept: dict[str, Any] = {}
    for key, value in values.items():
        f = known.get(key)
        if f is None:
            what = BY_SUBJECT[subject].one if subject in BY_SUBJECT else subject
            errors.append(((loc, key), f'Your company has no {what} field called "{key}".'))
            continue
        cleaned, problem = clean_value(f, value)
        if problem is not None:
            errors.append(((loc, key), problem))
        elif cleaned is not None:
            kept[key] = cleaned
    for key, f in known.items():
        if f.required and f.is_active and key not in kept:
            errors.append(((loc, key), f"{f.label} is needed."))
    if errors:
        raise field_errors(errors)
    return kept
