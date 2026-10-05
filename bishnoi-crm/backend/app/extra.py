"""The forms an admin lays out (Settings → Forms), applied to what's saved:

- added fields' values are checked against their kind and kept in `extra`;
- a built-in field the admin made required must be filled;
- a field for only some teams (or everyone but some) is on a record only when
  its team is one of them: a customer's team is its owner's.
"""

import re
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import email_address
from app.models import FormField

# A check that doesn't depend on whose record it is (products, quotes), or on
# what kind of customer it is.
ANY_TEAM = ANY_TYPE = object()


def _within(value, only: list | None, but: list | None) -> bool:
    if value in (but or []):
        return False
    return not only or value in only


def applies(item, team_id, kind=ANY_TYPE) -> bool:
    """Whether a field (or customer type) is on a record of this team and, for
    a field, this customer type: not one it's kept from, and one of its only-
    ones if it has any."""
    if team_id is not ANY_TEAM and not _within(team_id, item.only_teams, item.except_teams):
        return False
    if kind is not ANY_TYPE and hasattr(item, "only_types") and not _within(kind, item.only_types, item.except_types):
        return False
    return True



def fields_for(db: Session, entity: str, *, added_only: bool = False, shown_only: bool = False) -> list[FormField]:
    query = select(FormField).where(FormField.entity == entity)
    if added_only:
        query = query.where(FormField.standard.is_(False))
    if shown_only:
        query = query.where(FormField.hidden.is_(False))
    return list(db.scalars(query.order_by(FormField.sort_order, FormField.label)))


def _value(field: FormField, raw: Any) -> Any:
    """The value as kept, or ValueError with what's wrong."""
    kind = field.type
    if kind in ("text", "long_text", "phone"):
        text = str(raw).strip()
        limit = 5000 if kind == "long_text" else 200
        if len(text) > limit:
            raise ValueError(f"At most {limit} characters.")
        return text
    if kind == "email":
        return email_address(str(raw))
    if kind == "url":
        text = str(raw).strip()
        if " " in text or "." not in text:
            raise ValueError("Enter a web address like example.com.")
        return text
    if kind in ("number", "money"):
        if isinstance(raw, bool):
            raise ValueError("Enter a number.")
        try:
            number = float(str(raw).replace(",", ""))
        except ValueError:
            raise ValueError("Enter a number.") from None
        if kind == "money":
            return round(number, 2)
        return int(number) if number.is_integer() else number
    if kind == "date":
        try:
            return date.fromisoformat(str(raw)).isoformat()
        except ValueError:
            raise ValueError("Pick a date.") from None
    if kind == "choice":
        if raw not in field.options:
            raise ValueError("Pick one of the options.")
        return raw
    if kind == "multi_choice":
        picked = raw if isinstance(raw, list) else [raw]
        if any(p not in field.options for p in picked):
            raise ValueError("Pick from the options.")
        return [o for o in field.options if o in picked]  # in the options' own order
    if kind == "yes_no":
        if not isinstance(raw, bool):
            raise ValueError("Yes or no.")
        return raw
    if kind == "molecule":
        text = str(raw).strip()
        if len(text) > 120:
            raise ValueError("At most 120 characters.")
        return text
    raise ValueError("This field can't be filled in.")


def _customer(db: Session, field: FormField, raw: Any, record_id: str | None) -> str:
    """Another customer, of one of the field's types (any division's: a doctor's hospital may be HOS's)."""
    from app.models import Company

    other = db.get(Company, str(raw)) if isinstance(raw, str) else None
    if other is None or other.id == record_id or (field.options and other.status not in field.options):
        raise ValueError("Pick a customer from the list.")
    return other.id


def offered_products(db: Session, field: FormField) -> list:
    """The catalogue's products a products field offers: the active ones it doesn't leave out."""
    from app.models import Product

    left_out = set(field.options or [])
    return [p for p in db.scalars(select(Product).where(Product.is_active).order_by(Product.name)) if p.code not in left_out]


def _products(db: Session, field: FormField, raw: Any) -> list[str]:
    picked = raw if isinstance(raw, list) else [raw]
    codes = [p.code for p in offered_products(db, field)]
    if any(not isinstance(p, str) or p not in codes for p in picked):
        raise ValueError("Pick from our products.")
    return [c for c in codes if c in picked]


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _taken(db: Session, entity: str, key: str, value, record_id: str | None) -> bool:
    """Whether another record already has this value in a unique field (any
    record: one out of reach still counts, or two people could use one code)."""
    from app.models import Company, Contact, Product, Quote

    model = {"company": Company, "contact": Contact, "product": Product, "quote": Quote}[entity]
    wanted = str(value).strip().lower()
    for rid, extra in db.execute(select(model.id, model.extra)):
        if rid != record_id and str((extra or {}).get(key, "")).strip().lower() == wanted:
            return True
    return False


def check_extra(
    db: Session,
    entity: str,
    sent: dict | None,
    current: dict | None = None,
    *,
    team_id=ANY_TEAM,
    kind=ANY_TYPE,
    record_id: str | None = None,
) -> dict:
    """The record's added-field values after this change. `sent` holds only what
    the form changed (a null clears one); unknown keys are refused, and a required
    field (on the form) must end up filled. `team_id` is the record's team and
    `kind` its customer type: a field for other teams or types isn't on its
    form. Values kept from before in such a field stay, untouched."""
    fields = {f.key: f for f in fields_for(db, entity, added_only=True) if applies(f, team_id, kind)}
    result = dict(current or {})
    problems = []
    for key, raw in (sent or {}).items():
        field = fields.get(key)
        if field is None or field.hidden:
            problems.append({"type": "value_error", "loc": ["body", "extra", key], "msg": "There's no such field."})
            continue
        if _empty(raw):
            result.pop(key, None)
            continue
        try:
            if field.type == "products":
                result[key] = _products(db, field, raw)
            elif field.type == "customer":
                result[key] = _customer(db, field, raw, record_id)
            else:
                result[key] = _value(field, raw)
        except ValueError as e:
            problems.append({"type": "value_error", "loc": ["body", "extra", key], "msg": str(e)})
            continue
        if field.unique and _taken(db, entity, key, result[key], record_id):
            problems.append({"type": "value_error", "loc": ["body", "extra", key], "msg": f"Another record already has this {field.label.lower()}."})
    for field in fields.values():
        if not field.hidden and field.required and _empty(result.get(field.key)) and not any(p["loc"][-1] == field.key for p in problems):
            problems.append({"type": "value_error", "loc": ["body", "extra", field.key], "msg": f"{field.label} is required."})
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)
    return result


def check_required(db: Session, entity: str, record: object, *, team_id=ANY_TEAM, kind=ANY_TYPE) -> None:
    """Built-in fields the admin made required, once the change is applied:
    `record` is the record about to be saved. (Locked ones are required by the
    API itself.) A field not on this team's form isn't required of it."""
    problems = []
    for field in fields_for(db, entity):
        if not field.standard or field.locked or field.hidden or not field.required or not applies(field, team_id, kind):
            continue
        attr = re.sub(r"(?<!^)(?=[A-Z])", "_", field.key).lower()  # jobTitle -> job_title
        if _empty(getattr(record, attr, None)):
            problems.append({"type": "value_error", "loc": ["body", field.key], "msg": f"{field.label} is required."})
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)
