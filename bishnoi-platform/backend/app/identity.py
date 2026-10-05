"""What the screens are told about this app and the person signed in to it."""

from app.config import Settings
from app.models import User

# Everyone who signs in here works above every company, so none is open:
# `org` is null and the shell treats them as the platform tier.
ORG_ID = "00000000-0000-4000-8000-000000004305"

# Staff roles as the screens name them.
ROLE_NAMES = {"admin": "Platform Admin", "member": "Support"}


def org_out(settings: Settings) -> dict:
    return {
        "id": ORG_ID,
        "slug": "bishnoi",
        "name": settings.org_name,
        "brandName": settings.org_name,
        "currency": settings.org_currency,
        "minorUnits": settings.org_minor_units,
        "locale": settings.org_locale,
        "timezone": settings.org_timezone,
    }


def me_out(user: User, settings: Settings) -> dict:
    return {
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": None},
        "org": None,
        "canManageSettings": False,
        "canRecover": True,
        "viewedBy": None,
        "isOwner": False,
        "isDeveloperAdmin": True,
        "modules": [],
        "lists": {"customer_kind": [], "activity_kind": [], "outcome": []},
        # This app's own: which kind of staff, and so what they may change.
        "platformRole": user.role,
        "platformRoleName": ROLE_NAMES[user.role],
        "canAdminister": user.role == "admin",
    }
