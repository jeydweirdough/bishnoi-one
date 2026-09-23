"""Everything a role can be allowed to do, and the roles the CRM starts with.

A permission is "<area>.<action>", e.g. "customers.edit" or "admin.users".
Every area of the CRM is listed here, including ones whose screens come
later, so roles can be set up once and keep working as each area lands.

A role's *scope* says whose records its permissions reach:
- own:  records the person owns;
- team: records owned by anyone in their team;
- all:  every record.
Administration permissions are not scoped: they are about the app itself.
"""

from dataclasses import dataclass

CRUD = ("view", "create", "edit", "delete")

ACTION_LABELS = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve",
    "export": "Export",
    "manage": "Manage",
    "prices": "Set team prices",
    "users": "Users",
    "roles": "Roles & permissions",
    "teams": "Teams",
    "types": "Customer types",
    "settings": "Settings",
    "audit": "Audit logs",
}


@dataclass(frozen=True)
class Area:
    key: str
    name: str
    group: str
    actions: tuple[str, ...]

    def permissions(self) -> list[str]:
        return [f"{self.key}.{a}" for a in self.actions]


AREAS: tuple[Area, ...] = (
    Area("dashboard", "Dashboard", "CRM", ("view",)),
    Area("customers", "Customers & contacts", "CRM", CRUD),
    Area("leads", "Leads", "CRM", CRUD),
    Area("opportunities", "Opportunities", "CRM", CRUD),
    Area("deals", "Deals", "CRM", CRUD),
    Area("activities", "Activities (calls, meetings, emails, notes, tasks)", "CRM", CRUD),
    Area("products", "Products & services", "Catalogue & paperwork", (*CRUD, "prices")),
    Area("quotes", "Quotes", "Catalogue & paperwork", (*CRUD, "approve")),
    Area("orders", "Sales orders", "Catalogue & paperwork", (*CRUD, "approve")),
    Area("contracts", "Contracts", "Catalogue & paperwork", CRUD),
    Area("documents", "Documents", "Catalogue & paperwork", CRUD),
    Area("reports", "Reports", "Insight & tools", ("view", "export")),
    Area("automations", "Automations", "Insight & tools", ("view", "manage")),
    Area("integrations", "Integrations", "Insight & tools", ("view", "manage")),
    Area("admin", "Administration", "Administration", ("users", "roles", "teams", "types", "settings", "audit")),
)

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions())
ADMIN_PERMISSIONS: frozenset[str] = frozenset(p for p in ALL_PERMISSIONS if p.startswith("admin."))
# Someone must always hold both, or nobody could fix a mistake in access.
KEYS_TO_ADMINISTRATION = frozenset({"admin.users", "admin.roles"})

SCOPES = ("own", "team", "all")
SCOPE_LABELS = {"own": "Their own records", "team": "Their team's records", "all": "Every record"}


def catalogue_out() -> list[dict]:
    return [
        {
            "key": a.key,
            "name": a.name,
            "group": a.group,
            "actions": [{"key": x, "label": ACTION_LABELS[x], "permission": f"{a.key}.{x}"} for x in a.actions],
        }
        for a in AREAS
    ]


def _grant(*areas: str, actions: tuple[str, ...] = CRUD) -> set[str]:
    return {f"{area}.{action}" for area in areas for action in actions if f"{area}.{action}" in ALL_PERMISSIONS}


# The roles the CRM starts with. Administrator is the system role: it always
# holds every permission and can't be changed or deleted. The other two are
# ordinary roles, there to start from.
ADMINISTRATOR = "Administrator"
TEAM_LEAD = "Team Lead"
SALESPERSON = "Salesperson"
STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (ADMINISTRATOR, "Everything, including users, roles, teams, settings and the audit log.", "all", ALL_PERMISSIONS),
    (
        TEAM_LEAD,
        "Manages their own team: its customers, quotes and prices. Approves the team's quotes.",
        "team",
        frozenset(
            _grant("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", "contracts", "documents")
            | _grant("quotes", "orders", actions=("approve",))
            | _grant("dashboard", "products", actions=("view",))
            | _grant("products", actions=("prices",))
            | _grant("reports", actions=("view", "export"))
            | _grant("automations", "integrations", actions=("view",))
        ),
    ),
    (
        SALESPERSON,
        "Works their own customers, activities and quotes.",
        "own",
        frozenset(
            _grant("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", actions=("view", "create", "edit"))
            | _grant("dashboard", "products", "contracts", "documents", actions=("view",))
        ),
    ),
)
