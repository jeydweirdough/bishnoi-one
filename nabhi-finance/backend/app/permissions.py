"""Everything a role can be allowed to do in Finance, and the roles it starts with.

A permission is "<area>.<action>", e.g. "funds.release" or "admin.users".
Finance keeps one company's books, so a role reaches all of it: there are no
own/team scopes as in the CRM.
"""

from dataclasses import dataclass

ACTION_LABELS = {
    "view": "View",
    "release": "Release",
    "check": "Review liquidations",
    "settle": "Record refunds and reimbursements",
    "cancel": "Cancel",
    "manage": "Add and edit",
    "post": "Post journal entries",
    "reverse": "Reverse entries",
    "create": "Make drafts",
    "issue": "Issue",
    "void": "Void",
    "setup": "Invoice numbers",
    "collect": "Record payments",
    "users": "Users",
    "roles": "Roles and permissions",
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
    Area("dashboard", "Overview", "Finance", ("view",)),
    Area("funds", "Fund requests", "Fund requests", ("view", "release", "check", "settle", "cancel")),
    Area("categories", "Expense categories", "Fund requests", ("view", "manage")),
    Area("invoices", "Sales invoices and payments", "Invoices", ("view", "create", "issue", "collect", "void", "setup")),
    Area("journal", "Journal entries and reports", "Accounting", ("view", "post", "reverse")),
    Area("accounts", "Chart of accounts and default accounts", "Accounting", ("view", "manage")),
    Area("tax", "Tax setup", "Tax", ("view", "manage")),
    Area("admin", "Administration", "Administration", ("users", "roles", "audit")),
)

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions())
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
FINANCE_STAFF = "Finance Staff"
AUDITOR = "Auditor"

# Fixed ids, so the migration that made them and the code agree.
ROLE_ADMIN_ID = "00000000-0000-4000-8000-00000000f001"
ROLE_STAFF_ID = "00000000-0000-4000-8000-00000000f002"
ROLE_AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"

# The roles Finance starts with. Administrator is the system role: it always
# holds every permission and can't be changed or deleted. Finance Staff is
# what "member" used to be: the day's work, not the setup. The Auditor sees
# everything and changes nothing.
STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (ROLE_ADMIN_ID, ADMINISTRATOR, "Everything: the setup (accounts, categories, tax), users, roles and the activity log.", ALL_PERMISSIONS),
    (
        ROLE_STAFF_ID,
        FINANCE_STAFF,
        "Releases cash advances, reviews liquidations, records refunds and reimbursements, posts journal entries, and makes and issues invoices and records their payments.",
        VIEW_ALL
        | _grant("funds", actions=("release", "check", "settle", "cancel"))
        | _grant("journal", actions=("post", "reverse"))
        | _grant("invoices", actions=("create", "issue", "collect")),
    ),
    (ROLE_AUDITOR_ID, AUDITOR, "Sees everything, including the activity log, and changes nothing.", VIEW_ALL | {"admin.audit"}),
)
