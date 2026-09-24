"""What the screens are told about the CRM and the person signed in to it."""

from app.access import access_of
from app.config import Settings
from app.models import User
from app.permissions import ADMIN_PERMISSIONS

MODULE = {"key": "crm", "name": "CRM", "kind": "crm"}
ORG_ID = "00000000-0000-4000-8000-000000004302"

# The actions the older screens read off the module, from the role's permissions.
MODULE_ACTIONS = ("view", "create", "edit", "delete")


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
    access = access_of(user)
    administers = bool(access.permissions & ADMIN_PERMISSIONS)
    return {
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": None},
        "org": org_out(settings),
        "role": {"id": user.role.id, "name": user.role.name, "scope": user.role.scope},
        "team": {"id": user.team.id, "name": user.team.name} if user.team else None,
        "permissions": sorted(access.permissions),
        "canManageSettings": administers,
        "canRecover": False,
        "viewedBy": None,
        "isOwner": user.role.is_system,
        "isDeveloperAdmin": False,
        "modules": [
            {
                **MODULE,
                "built": True,
                "url": None,
                "actions": [a for a in MODULE_ACTIONS if access.can(f"customers.{a}")],
                "teams": [],
            }
        ],
        "lists": {"customer_kind": [], "activity_kind": [], "outcome": []},
    }
