"""What every router shares: request bodies in camelCase, errors worded for
people, and moments that always carry their zone."""

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s.]+")
SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


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


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def check_email(value: str | None) -> str | None:
    if value is not None and not EMAIL.fullmatch(value):
        raise ValueError("Enter an email address like name@company.com.")
    return value.lower() if value else value


def check_url(value: str | None) -> str | None:
    """An address the platform may call or link to: http(s) only."""
    if value is not None and not re.fullmatch(r"https?://[^\s/$.?#][^\s]*", value):
        raise ValueError("Enter a full address starting with http:// or https://.")
    return value.rstrip("/") if value else value


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def iso(moment: datetime | None) -> str | None:
    """A moment for the screens, always with its zone: SQLite hands times back
    without one, and a bare time would be read as the reader's local time."""
    return as_utc(moment).isoformat() if moment is not None else None


def now() -> datetime:
    return datetime.now(UTC)


def changed(model: BaseModel) -> dict:
    """The fields a PATCH actually sent, by their Python names."""
    return model.model_dump(exclude_unset=True)


def camel(names: list[str] | set[str]) -> list[str]:
    return sorted(to_camel(n) for n in names)


def ref(record: Any) -> dict | None:
    """A record the screens link to: its id and its name."""
    if record is None:
        return None
    return {"id": record.id, "name": getattr(record, "name", None) or getattr(record, "full_name", None)}
