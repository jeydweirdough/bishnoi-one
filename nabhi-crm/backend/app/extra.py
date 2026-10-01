"""The forms an admin lays out (Settings → Forms), applied to what's saved:

- added fields' values are checked against their kind and kept in `extra`;
- a built-in field the admin made required must be filled.
"""

import re
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import email_address
from app.models import FormField



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
    raise ValueError("This field can't be filled in.")


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def check_extra(db: Session, entity: str, sent: dict | None, current: dict | None = None) -> dict:
    """The record's added-field values after this change. `sent` holds only what
    the form changed (a null clears one); unknown keys are refused, and a required
    field (on the form) must end up filled."""
    fields = {f.key: f for f in fields_for(db, entity, added_only=True)}
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
            result[key] = _value(field, raw)
        except ValueError as e:
            problems.append({"type": "value_error", "loc": ["body", "extra", key], "msg": str(e)})
    for field in fields.values():
        if not field.hidden and field.required and _empty(result.get(field.key)) and not any(p["loc"][-1] == field.key for p in problems):
            problems.append({"type": "value_error", "loc": ["body", "extra", field.key], "msg": f"{field.label} is required."})
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)
    return result


def check_required(db: Session, entity: str, record: object) -> None:
    """Built-in fields the admin made required, once the change is applied:
    `record` is the record about to be saved. (Locked ones are required by the
    API itself.)"""
    problems = []
    for field in fields_for(db, entity):
        if not field.standard or field.locked or field.hidden or not field.required:
            continue
        attr = re.sub(r"(?<!^)(?=[A-Z])", "_", field.key).lower()  # jobTitle -> job_title
        if _empty(getattr(record, attr, None)):
            problems.append({"type": "value_error", "loc": ["body", field.key], "msg": f"{field.label} is required."})
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problems)
