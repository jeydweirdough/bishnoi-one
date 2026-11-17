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
    "import": "Upload",
    "credit": "Confirm credit status",
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
    Area("deals", "Deals", "CRM", CRUD),
    Area("activities", "Activities (calls, meetings, emails, notes, tasks)", "CRM", CRUD),
    Area("products", "Products & services", "Catalogue & paperwork", (*CRUD, "prices", "approve")),
    Area("quotes", "Quotes", "Catalogue & paperwork", (*CRUD, "approve")),
    # orders.credit: Finance confirms a B2B customer's credit status on a quote before it's ordered.
    Area("orders", "Sales orders", "Catalogue & paperwork", (*CRUD, "approve", "credit")),
    Area("visits", "Visits & collections", "Field work", CRUD),
    # goals.view: the tracker for everyone within reach; goals.manage: setting
    # goals; goals.import: uploading what doctors owe.
    Area("goals", "Targets and balances", "Field work", ("view", "manage", "import")),
    Area("reports", "Reports", "Insight & tools", ("view", "export")),
    # A manager's own department: its promos and bundles, quotation templates,
    # attention rules, retention windows and people's targets. Only for the
    # teams the role reaches; company-wide settings stay with admin.settings.
    Area("department", "Department settings", "Administration", ("manage",)),
    Area("admin", "Administration", "Administration", ("users", "roles", "teams", "types", "settings", "audit")),
)

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions())

# Areas decided but not built yet. Roles can already hold them, but nothing
# uses them, so neither the roles screen nor a person's account page offers
# them. Take one off as it lands (deals landed on 2026-10-01).
# (Leads, opportunities, contracts, documents, automations and integrations
# were here with no plan behind them, and were taken out on 2026-09-30: a lead
# is a customer status, by D2. Roles that held them simply no longer do.)
NOT_BUILT: frozenset[str] = frozenset()
ADMIN_PERMISSIONS: frozenset[str] = frozenset(p for p in ALL_PERMISSIONS if p.startswith("admin."))
# Someone must always hold both, or nobody could fix a mistake in access.
KEYS_TO_ADMINISTRATION = frozenset({"admin.users", "admin.roles"})

SCOPES = ("own", "team", "managed", "all")
SCOPE_LABELS = {"own": "Their own records", "team": "Their team's records", "managed": "The records of every team they manage", "all": "Every record"}


def catalogue_out() -> list[dict]:
    """What the roles screen offers: every area that has screens."""
    return [
        {
            "key": a.key,
            "name": a.name,
            "group": a.group,
            "actions": [{"key": x, "label": ACTION_LABELS[x], "permission": f"{a.key}.{x}"} for x in a.actions],
        }
        for a in AREAS
        if a.key not in NOT_BUILT
    ]


def _grant(*areas: str, actions: tuple[str, ...] = CRUD) -> set[str]:
    return {f"{area}.{action}" for area in areas for action in actions if f"{area}.{action}" in ALL_PERMISSIONS}


# The roles the CRM starts with. Administrator is the system role: it always
# holds every permission and can't be changed or deleted. The other two are
# ordinary roles, there to start from.
ADMINISTRATOR = "Administrator"
MANAGER = "Manager"
TEAM_LEAD = "Team Lead"
SALESPERSON = "Salesperson"
FIELD_AGENT = "Field agent"
STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (ADMINISTRATOR, "Everything, including users, roles, teams, settings and the audit log.", "all", ALL_PERMISSIONS),
    (
        TEAM_LEAD,
        "Manages their own team: its customers, quotes and prices. Approves the team's quotes.",
        "team",
        frozenset(
            _grant("customers", "deals", "activities", "quotes", "orders")
            | _grant("quotes", "orders", actions=("approve",))
            | _grant("dashboard", "products", actions=("view",))
            | _grant("products", actions=("prices",))
            | _grant("reports", actions=("view", "export"))
            | _grant("visits")
            | _grant("goals", actions=("view",))
        ),
    ),
    (
        SALESPERSON,
        "Works their own customers, activities and quotes.",
        "own",
        frozenset(
            _grant("customers", "deals", "activities", "quotes", "orders", actions=("view", "create", "edit"))
            | _grant("dashboard", "products", actions=("view",))
        ),
    ),
)
STARTING_ROLES += (
    (
        MANAGER,
        "Above the team leads: manages every team they're the manager of, and its people. Approves their quotes, sets their targets, and runs their department's settings.",
        "managed",
        frozenset(
            dict(((r[0], r[3]) for r in STARTING_ROLES))[TEAM_LEAD]
            | _grant("goals", actions=("view", "manage"))
            | _grant("department", actions=("manage",))
        ),
    ),
    (
        "Finance",
        "Curates baseline product prices and SRP, approves doctor's price, patient's price, and special price proposals from managers.",
        "all",
        frozenset(
            _grant("products", actions=("view", "edit", "prices", "approve"))
            | _grant("quotes", actions=("view", "approve"))
            | _grant("orders", actions=("view", "approve"))
            | _grant("reports", actions=("view", "export"))
            | _grant("dashboard", actions=("view",))
        ),
    ),
    (
        FIELD_AGENT,
        "Visits their own accounts and collects what they owe; sees their own goals.",
        "own",
        frozenset(
            _grant("customers", actions=("view", "edit"))
            | _grant("visits", actions=("view", "create", "edit"))
            | _grant("activities", actions=("view", "create", "edit"))
            | _grant("dashboard", actions=("view",))
        ),
    ),
)
