"""What the screens are told about this app and the person signed in to it."""

from app.config import Settings
from app.models import User

# This app's module, as the screens' sidebar and door check read it. None: the
# Platform app, which works above any one company.
MODULE: dict | None = {"key": "regulatory", "name": "Regulatory", "kind": "department"}
# The Platform app's people are its Developer Admins.
DEVELOPER_ADMIN_APP = False
ORG_ID = "00000000-0000-4000-8000-000000004308"

ALL_ACTIONS = ["view", "create", "edit", "delete"]


def org_out(settings: Settings) -> dict:
    return {
        "id": ORG_ID,
        "slug": "nabhi",
        "name": settings.org_name,
        "brandName": settings.org_name,
        "currency": settings.org_currency,
        "minorUnits": settings.org_minor_units,
        "locale": settings.org_locale,
        "timezone": settings.org_timezone,
    }


def me_out(user: User, settings: Settings) -> dict:
    admin = user.role == "admin"
    return {
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": None},
        "org": None if DEVELOPER_ADMIN_APP else org_out(settings),
        "canManageSettings": admin and not DEVELOPER_ADMIN_APP,
        "canRecover": DEVELOPER_ADMIN_APP,
        "viewedBy": None,
        "isOwner": admin and not DEVELOPER_ADMIN_APP,
        "isDeveloperAdmin": DEVELOPER_ADMIN_APP,
        "modules": [] if MODULE is None else [{**MODULE, "built": True, "url": None, "actions": ALL_ACTIONS, "teams": []}],
        "lists": {"customer_kind": [], "activity_kind": [], "outcome": []},
    }
