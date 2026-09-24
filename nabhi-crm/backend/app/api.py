"""What every router shares: request bodies in camelCase, errors worded for
people, and moments that always carry their zone."""

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from app.models import Team, User

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
    """Also the answer for a record out of reach: nothing is given away."""
    return HTTPException(status.HTTP_404_NOT_FOUND, f"That {what} doesn't exist, or it's outside what you can see.")


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


def team_out(team: Team | None) -> dict | None:
    return {"id": team.id, "name": team.name} if team else None


def changed(model: BaseModel) -> dict:
    """The fields a PATCH actually sent, by their Python names."""
    return model.model_dump(exclude_unset=True)


def camel(names: list[str]) -> list[str]:
    return [to_camel(n) for n in names]


def digits(phone: str | None) -> str | None:
    """A phone number's digits alone, for telling two ways of writing it apart."""
    only = re.sub(r"\D", "", phone or "")
    return only or None


def duplicates_error(noun: str, found: list[dict]) -> HTTPException:
    """Refuses a new record that looks like one already there. The screens list
    them, and send it again with allowDuplicate if it really is a different one."""
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "message": f"This looks like {'a ' + noun if len(found) == 1 else noun + 's'} already here. Check before adding another.",
            "duplicates": found,
        },
    )

