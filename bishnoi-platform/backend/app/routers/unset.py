"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing staff have to fill in before the platform works in full:
a person with no password can't sign in, an application with no address can't
be opened from the platform. Only the counts this person may fix are sent, so a
mark in their sidebar is always one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import DB, CurrentUser
from app.models import Application, Identity
from app.routers.users import without_password

router = APIRouter(prefix="/platform", tags=["unset"])


@router.get("/unset")
def unset(me: CurrentUser, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    # Only an admin gives out passwords.
    if me.role == "admin":
        counts["userPasswords"] = db.scalar(select(func.count()).select_from(Identity).where(without_password())) or 0
    counts["applicationAddress"] = db.scalar(select(func.count()).select_from(Application).where(Application.is_active, Application.app_url.is_(None))) or 0
    return {k: v for k, v in counts.items() if v}
