"""What the screens are told about the CRM and the person signed in to it."""

from app.access import access_of
from app.config import Settings
from app.models import User
from app.permissions import ADMIN_PERMISSIONS
from app import terms

MODULE = {"key": "crm", "name": "CRM", "kind": "crm"}
ORG_ID = "00000000-0000-4000-8000-000000004302"

# The actions the older screens read off the module, from the role's permissions.
MODULE_ACTIONS = ("view", "create", "edit", "delete")


def org_out(settings: Settings) -> dict:
    return {
        "id": ORG_ID,
        # The company signed in to (its short name on the platform): order links are made with it.
        "slug": settings.company,
        "name": settings.org_name,
        "brandName": settings.org_name,
        "currency": settings.org_currency,
        "minorUnits": settings.org_minor_units,
        "locale": settings.org_locale,
        "timezone": settings.org_timezone,
        # The company's own words (Settings → Terms): "Doctors" at GetMeds, "Accounts" elsewhere.
        "terms": terms.out(settings.terms),
    }


def me_out(user: User, settings: Settings) -> dict:
    access = access_of(user)
    administers = bool(access.permissions & ADMIN_PERMISSIONS)
    return {
        "user": {"id": user.id, "email": user.email, "fullName": user.full_name, "photoAt": None},
        "org": org_out(settings),
        "role": {"id": user.role.id, "name": user.role.name, "scope": user.role.scope},
        "team": {"id": user.team.id, "name": user.team.name} if user.team else None,
        "otherTeams": [{"id": t.id, "name": t.name} for t in user.other_teams],
        "permissions": sorted(access.permissions),
        "canManageSettings": administers,
        "canRecover": False,
        # Bishnoi One Order is connected: ready quotes show "Raise order".
        # Raise order goes to the Sales app through the Platform (step 11): always available.
        "ordersLinked": True,
        "pharmacyLinked": settings.pharmacy_linked,
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
