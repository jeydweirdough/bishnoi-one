"""Everything a role can be allowed to do, and the roles Inventory starts with.

A permission is "<area>.<action>", e.g. "adjustments.approve" or "admin.users".
Inventory has one company's stock, so a role reaches all of it: there are no
own/team scopes as in the CRM.
"""

from dataclasses import dataclass

CRUD = ("view", "create", "edit", "delete")

ACTION_LABELS = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "approve": "Approve",
    "manage": "Manage",
    "receive": "Receive",
    "issue": "Issue",
    "dispatch": "Dispatch",
    "export": "Export",
    "users": "Users",
    "roles": "Roles & permissions",
    "audit": "Activity log",
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
    Area("dashboard", "Dashboard & alerts", "Inventory", ("view",)),
    Area("products", "Products, categories, brands & units", "Catalog", CRUD),
    Area("stock", "Stock levels, movements, batches & serials", "Inventory", ("view",)),
    Area("warehouses", "Warehouses & locations", "Inventory", ("view", "manage")),
    Area("transfers", "Stock transfers", "Inventory", ("view", "create", "approve", "dispatch", "receive")),
    Area("adjustments", "Stock adjustments", "Inventory", ("view", "create", "approve")),
    Area("counts", "Inventory counts", "Inventory", ("view", "create", "approve")),
    Area("suppliers", "Suppliers & supplier prices", "Purchasing", CRUD),
    Area("purchasing", "Purchase orders", "Purchasing", ("view", "create", "edit", "approve")),
    Area("receiving", "Receiving", "Purchasing", ("view", "receive")),
    # The Sales app's sales orders (step 11): approve confirms one and makes its delivery.
    Area("sales", "Sales orders", "Sales", ("view", "create", "edit", "approve")),
    Area("orders", "Deliveries, reservations & issuance", "Orders", ("view", "create", "edit", "approve", "issue")),
    Area("reports", "Reports", "Insight", ("view", "export")),
    Area("admin", "Administration", "Administration", ("users", "roles", "audit")),
)

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions())
ADMIN_PERMISSIONS: frozenset[str] = frozenset(p for p in ALL_PERMISSIONS if p.startswith("admin."))
# Someone must always hold both, or nobody could fix a mistake in access.
KEYS_TO_ADMINISTRATION = frozenset({"admin.users", "admin.roles"})


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


def _grant(*areas: str, actions: tuple[str, ...]) -> set[str]:
    return {f"{area}.{action}" for area in areas for action in actions if f"{area}.{action}" in ALL_PERMISSIONS}


# Seeing everything, changing nothing.
VIEW_ALL = frozenset(_grant(*(a.key for a in AREAS if a.key != "admin"), actions=("view",)))

ADMINISTRATOR = "Administrator"
WAREHOUSE = "Warehouse"
PURCHASING = "Purchasing"
SALES = "Sales"
AUDITOR = "Auditor"

# The roles Inventory starts with. Administrator is the system role: it always
# holds every permission and can't be changed or deleted. The rest are
# ordinary roles to start from, set as:
#
#   Role        View  Receive  Adjust   Transfer  Approve
#   Warehouse   ✓     ✓        Limited  ✓         —
#   Purchasing  ✓     ✓        —        —         ✓
#   Sales       ✓     —        —        —         —
#   Auditor     ✓     —        —        —         —
#
# "Limited" adjusting: a warehouse person writes adjustments up, and they wait
# for someone who may approve them.
STARTING_ROLES: tuple[tuple[str, str, frozenset[str]], ...] = (
    (ADMINISTRATOR, "Everything, including users, roles and the activity log.", ALL_PERMISSIONS),
    (
        WAREHOUSE,
        "Receives, transfers, counts and issues stock. Adjustments they write wait for approval.",
        VIEW_ALL
        | _grant("receiving", actions=("receive",))
        | _grant("transfers", actions=("create", "dispatch", "receive"))
        | _grant("adjustments", "counts", actions=("create",))
        | _grant("orders", actions=("issue",)),
    ),
    (
        PURCHASING,
        "Keeps suppliers and purchase orders, receives deliveries, and approves orders, transfers and adjustments.",
        VIEW_ALL
        | _grant("suppliers", actions=("create", "edit", "delete"))
        | _grant("purchasing", actions=("create", "edit", "approve"))
        | _grant("receiving", actions=("receive",))
        | _grant("transfers", "adjustments", "counts", "orders", "sales", actions=("approve",))
        | _grant("reports", actions=("export",)),
    ),
    (SALES, "Sees stock, and writes up customer orders.", VIEW_ALL | _grant("orders", "sales", actions=("create", "edit"))),
    (AUDITOR, "Sees everything, including the activity log, and changes nothing.", VIEW_ALL | {"reports.export", "admin.audit"}),
)
