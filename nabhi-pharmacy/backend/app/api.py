"""What every router shares: request bodies in camelCase, errors worded for
people, moments that always carry their zone, and record numbers."""

import re
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Counter, User

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


def conflict(message: str) -> HTTPException:
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


def day(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def today(settings: Settings) -> date:
    """Today where the pharmacy is, not where the server is."""
    return datetime.now(ZoneInfo(settings.org_timezone)).date()


def day_start(value: date, settings: Settings) -> datetime:
    """Midnight at the pharmacy, as a moment, for "sold on this day" questions."""
    return datetime(value.year, value.month, value.day, tzinfo=ZoneInfo(settings.org_timezone)).astimezone(UTC)


def person_out(user: User | None) -> dict | None:
    return {"id": user.id, "name": user.full_name, "licenseNo": user.license_no} if user else None


def changed(model: BaseModel) -> dict:
    """The fields a PATCH actually sent, by their Python names."""
    return model.model_dump(exclude_unset=True)


def camel(names: list[str]) -> list[str]:
    return [to_camel(n) for n in names]


def next_number(db: Session, kind: str, settings: Settings) -> str:
    """The next number for a record: RX-2026-00125. Taken in the caller's
    transaction, so a record that fails to save gives its number back."""
    year = today(settings).year
    if db.get(Counter, (kind, year)) is None:
        db.add(Counter(kind=kind, year=year, value=0))
        db.flush()
    # One statement, so two people saving at once can't get the same number.
    db.execute(update(Counter).where(Counter.kind == kind, Counter.year == year).values(value=Counter.value + 1))
    value = db.scalar(select(Counter.value).where(Counter.kind == kind, Counter.year == year))
    return f"{kind}-{year}-{value:05d}"
