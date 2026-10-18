"""A person's own profile: what they may change about themselves.

- GET /auth/account: their role on the console, and since when they've had an account.
- GET /auth/profile: their name in parts, gender, contact number, email and birthday.
- PUT /auth/profile: changes them. A new email asks for their password first,
  since it's what they sign in with.

Their password is changed at POST /auth/password (app/routers/auth.py): every
other session ends, this one carries on.
- GET /auth/activity?from=&to=: what they did each day (their entries in the
  activity log), and the last few, for the profile's charts.

Their role stays a Platform Admin's to set (app/routers/access.py).
"""

import re
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import func, select

from app.api import Api, as_utc, check_email, field_error, iso
from app.audit import audit
from app.deps import DB, Address, CurrentUser, SettingsDep
from app.identity import ROLE_NAMES
from app.models import AuditEntry, User
from app.security import MAX_PASSWORD, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

Gender = Literal["male", "female", "other"]
PHONE = re.compile(r"^\+?[0-9][0-9 ()-]{5,18}[0-9]$")


def full_name(first: str, middle: str | None, last: str, suffix: str | None) -> str:
    """"Daniel A. Cruz Jr.": what every list and screen shows."""
    parts = [first, f"{middle}." if middle else None, last, suffix]
    return " ".join(p for p in parts if p)[:120]


def split_name(full: str) -> tuple[str, str]:
    """A name typed in one piece (by an admin), as a first and a last name: the last word is the last name."""
    words = full.split()
    return (" ".join(words[:-1]), words[-1]) if len(words) > 1 else (full.strip(), "")


def profile_out(user: User) -> dict:
    first, last = (user.first_name, user.last_name) if user.first_name or user.last_name else split_name(user.full_name)
    return {
        "firstName": first or "",
        "middleInitial": user.middle_initial,
        "lastName": last or "",
        "suffix": user.suffix,
        "gender": user.gender,
        "phone": user.phone,
        "email": user.email,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "fullName": user.full_name,
    }


class ProfileIn(Api):
    first_name: str = Field(min_length=1, max_length=60)
    middle_initial: str | None = Field(None, max_length=4)
    last_name: str = Field(min_length=1, max_length=60)
    suffix: str | None = Field(None, max_length=10)
    gender: Gender
    phone: str = Field(max_length=20)
    email: str = Field(max_length=254)
    birthday: date | None = None
    # Asked for only when the email changes.
    current_password: str | None = Field(None, max_length=MAX_PASSWORD)

    @field_validator("first_name", "last_name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter a name.")
        return value

    @field_validator("middle_initial")
    @classmethod
    def _initial(cls, value: str | None) -> str | None:
        value = (value or "").strip().rstrip(".").upper()
        if not value:
            return None
        if not re.fullmatch(r"[A-ZÑ]{1,2}", value):
            raise ValueError("Use the initial alone: one or two letters.")
        return value

    @field_validator("suffix")
    @classmethod
    def _suffix(cls, value: str | None) -> str | None:
        return " ".join((value or "").split()) or None

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = value.strip()
        if not PHONE.fullmatch(value):
            raise ValueError("Enter a contact number: digits, with + for a country code.")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return check_email(value.strip()) or ""

    @field_validator("birthday")
    @classmethod
    def _birthday(cls, value: date | None) -> date | None:
        if value and not (date(1900, 1, 1) <= value <= date.today()):
            raise ValueError("Enter a birthday in the past.")
        return value


ROLE_SAYS = {
    "admin": "A Platform Admin sees and changes everything on the platform. Your role is changed by another Platform Admin.",
    "member": "Support sees everything on the platform and works its tickets and incidents. Your role is changed by a Platform Admin.",
}


@router.get("/account")
def my_account(user: CurrentUser) -> dict:
    return {"role": {"name": ROLE_NAMES[user.role], "description": ROLE_SAYS.get(user.role)}, "team": None, "memberSince": iso(user.created_at)}


@router.get("/profile")
def get_profile(user: CurrentUser) -> dict:
    return profile_out(user)


@router.put("/profile")
def put_profile(user: CurrentUser, db: DB, address: Address, body: ProfileIn) -> dict:
    if body.email != user.email:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise field_error("currentPassword", "Enter your current password to change your email: it's what you sign in with.")
        if db.scalar(select(User.id).where(func.lower(User.email) == body.email, User.id != user.id)):
            raise field_error("email", "There's already a staff account with this email.")
    before = profile_out(user)
    user.first_name, user.middle_initial, user.last_name, user.suffix = body.first_name, body.middle_initial, body.last_name, body.suffix
    user.full_name = full_name(body.first_name, body.middle_initial, body.last_name, body.suffix)
    user.gender, user.phone, user.email, user.birthday = body.gender, body.phone, body.email, body.birthday
    after = profile_out(user)
    changed = [key for key in after if after[key] != before[key] and key != "fullName"]
    if changed:
        audit(db, user, "staff.profile_changed", category="security", target=user.email, target_type="staff", target_id=user.id, fields=changed, address=address)
    db.commit()
    db.refresh(user)
    return profile_out(user)


@router.get("/activity")
def my_activity(
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    from_: date = Query(alias="from"),
    to: date = Query(),
) -> dict:
    """The person's own entries in the activity log, counted by the company's
    day, and the latest eight. At most a year at a time."""
    if to <= from_ or (to - from_).days > 366:
        raise field_error("to", "Pick up to a year, ending after it starts.")
    zone = ZoneInfo(settings.org_timezone)
    start = datetime.combine(from_, time(), zone).astimezone(UTC)
    end = datetime.combine(to, time(), zone).astimezone(UTC)
    days: dict[str, int] = {}
    for at in db.scalars(select(AuditEntry.created_at).where(AuditEntry.actor_id == user.id, AuditEntry.created_at >= start, AuditEntry.created_at < end)).all():
        day = as_utc(at).astimezone(zone).date().isoformat()
        days[day] = days.get(day, 0) + 1
    recent = db.scalars(select(AuditEntry).where(AuditEntry.actor_id == user.id).order_by(AuditEntry.created_at.desc()).limit(8)).all()
    return {"days": days, "recent": [{"action": e.action, "target": e.target, "at": iso(e.created_at)} for e in recent]}
