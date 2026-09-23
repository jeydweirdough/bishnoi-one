"""Everything a role can be allowed to do, and the roles Sales starts with.

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
    "users": "Users",
    "roles": "Roles & permissions",
    "teams": "Teams",
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
    Area("dashboard", "Dashboard", "Sales", ("view",)),
    Area("customers", "Customers (companies & contacts)", "Sales", CRUD),
    Area("leads", "Leads", "Sales", CRUD),
    Area("opportunities", "Opportunities", "Sales", CRUD),
    Area("deals", "Deals", "Sales", CRUD),
    Area("activities", "Activities (calls, meetings, emails, notes, tasks)", "Sales", CRUD),
    Area("products", "Products & services", "Catalogue & paperwork", CRUD),
    Area("quotes", "Quotes", "Catalogue & paperwork", (*CRUD, "approve")),
    Area("orders", "Sales orders", "Catalogue & paperwork", (*CRUD, "approve")),
    Area("contracts", "Contracts", "Catalogue & paperwork", CRUD),
    Area("documents", "Documents", "Catalogue & paperwork", CRUD),
    Area("reports", "Reports", "Insight & tools", ("view", "export")),
    Area("automations", "Automations", "Insight & tools", ("view", "manage")),
    Area("integrations", "Integrations", "Insight & tools", ("view", "manage")),
    Area("admin", "Administration", "Administration", ("users", "roles", "teams", "audit")),
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


# The roles Sales starts with. Administrator is the system role: it always
# holds every permission and can't be changed or deleted. The others are
# ordinary roles, there to start from.
ADMINISTRATOR = "Administrator"
STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (ADMINISTRATOR, "Everything, including users, roles, teams and the audit log.", "all", ALL_PERMISSIONS),
    (
        "Manager",
        "Sees and works every record, approves quotes and orders, runs reports. No administration.",
        "all",
        frozenset(
            _grant("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", "contracts", "documents")
            | _grant("quotes", "orders", actions=("approve",))
            | _grant("dashboard", "products", actions=("view",))
            | _grant("reports", actions=("view", "export"))
            | _grant("automations", "integrations", actions=("view",))
        ),
    ),
    (
        "Team Lead",
        "Works their team's records and runs its reports.",
        "team",
        frozenset(
            _grant("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", "documents")
            | _grant("dashboard", "products", "contracts", actions=("view",))
            | _grant("reports", actions=("view",))
        ),
    ),
    (
        "Sales Rep",
        "Works their own customers, leads, deals and quotes.",
        "own",
        frozenset(
            _grant("customers", "leads", "opportunities", "deals", "activities", "quotes", "orders", actions=("view", "create", "edit"))
            | _grant("dashboard", "products", "contracts", "documents", actions=("view",))
        ),
    ),
)
