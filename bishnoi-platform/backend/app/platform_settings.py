"""Settings a Platform Admin changes while the platform runs (nbpl_settings).

Four sections, each one JSON row. A section never saved yet is its defaults,
and those come from backend/.env where there is one (sign-in rules), so a
fresh database behaves exactly as the environment says.

- platform: what the platform calls itself, and where people write for help
- monitoring: how often applications are checked, and what counts as slow
- notifications: how fast each severity of ticket should be answered, and
  which incidents raise the banner on every screen
- security: how long a sign-in lasts, and how many wrong passwords it takes
"""

from typing import Literal

from pydantic import Field, field_validator
from sqlalchemy.orm import Session

from app.api import Api, check_email
from app.config import Settings
from app.models import PlatformSetting


class PlatformSection(Api):
    name: str = Field("Nabhi", min_length=2, max_length=60)
    support_email: str | None = Field(None, max_length=254)
    timezone: str = Field("Asia/Manila", min_length=3, max_length=64)

    @field_validator("support_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)


class MonitoringSection(Api):
    # A health check older than this is out of date, and the next look runs one.
    stale_seconds: int = Field(60, ge=15, le=3600)
    # How long an application has to answer before it counts as down.
    timeout_seconds: int = Field(3, ge=1, le=15)
    # Slower than this, and an answering application is degraded.
    slow_ms: int = Field(1500, ge=100, le=15000)
    # Health checks and traffic older than this are cleared away.
    keep_days: int = Field(30, ge=1, le=365)


class ResponseHours(Api):
    critical: int = Field(4, ge=1, le=720)
    high: int = Field(24, ge=1, le=720)
    medium: int = Field(72, ge=1, le=720)
    low: int = Field(168, ge=1, le=720)


class NotificationsSection(Api):
    # A ticket still open this long after it was reported is overdue.
    response_hours: ResponseHours = Field(default_factory=ResponseHours)
    # An active incident this severe or worse shows on every screen.
    banner_severity: Literal["critical", "major", "minor"] = "major"


class SecuritySection(Api):
    session_hours: int = Field(10, ge=1, le=168)
    login_attempts: int = Field(5, ge=3, le=20)
    lockout_minutes: int = Field(15, ge=1, le=240)


SECTIONS: dict[str, type[Api]] = {
    "platform": PlatformSection,
    "monitoring": MonitoringSection,
    "notifications": NotificationsSection,
    "security": SecuritySection,
}


def _defaults(key: str, settings: Settings) -> dict:
    if key == "platform":
        return {"name": settings.org_name, "timezone": settings.org_timezone}
    if key == "security":
        return {
            "session_hours": settings.session_hours,
            "login_attempts": settings.login_attempts,
            "lockout_minutes": settings.login_lockout_minutes,
        }
    return {}


def read(db: Session, key: str, settings: Settings):
    """One section, saved values over its defaults."""
    model = SECTIONS[key]
    row = db.get(PlatformSetting, key)
    saved = row.value if row else {}
    base = model(**_defaults(key, settings)).model_dump()
    return model.model_validate({**base, **saved})


def security(db: Session, settings: Settings) -> SecuritySection:
    return read(db, "security", settings)


def monitoring(db: Session, settings: Settings) -> MonitoringSection:
    return read(db, "monitoring", settings)


def notifications(db: Session, settings: Settings) -> NotificationsSection:
    return read(db, "notifications", settings)
