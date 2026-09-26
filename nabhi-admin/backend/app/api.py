"""What every router shares: request bodies in camelCase, errors worded for
people, and moments that always carry their zone.
"""

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from app.models import User

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")


class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _blank_is_none(cls, data: Any) -> Any:
        # Forms send "" for an empty optional field; treat it as not given.
        if isinstance(data, dict):
            return {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in data.items()}
        return data


def field_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", field], "msg": message}]
    )


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"That {what} doesn't exist.")


def found(db, model, key, what: str):
    """The record with this key, or a 404 naming what was looked for."""
    record = db.get(model, key)
    if record is None:
        raise not_found(what)
    return record


def conflict(message: str) -> HTTPException:
    """The request is fine, but the records as they stand don't allow it."""
    return HTTPException(status.HTTP_409_CONFLICT, message)


def check_email(value: str | None) -> str | None:
    if value is not None and not EMAIL.fullmatch(value):
        raise ValueError("Enter an email address like name@company.com.")
    return value.lower() if value else value


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def iso(moment: datetime | None) -> str | None:
    """A moment for the screens, always with its zone: SQLite hands times back
    without one, and a bare time would be read as the reader's local time."""
    return as_utc(moment).isoformat() if moment is not None else None


def person_out(user: User | None) -> dict | None:
    return {"id": user.id, "name": user.full_name} if user else None


def changed(model: BaseModel) -> dict:
    """The fields a PATCH actually sent, by their Python names."""
    return model.model_dump(exclude_unset=True)


def camel(names: list[str]) -> list[str]:
    return [to_camel(n) for n in names]
