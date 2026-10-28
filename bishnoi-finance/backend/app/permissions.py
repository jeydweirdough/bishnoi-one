"""Everything a role can be allowed to do in Finance, and the roles it starts with.

A permission is "<area>.<action>", e.g. "funds.release" or "admin.users".
Finance keeps one company's books, so a role reaches all of it: there are no
own/team scopes as in the CRM.
"""

from dataclasses import dataclass

ACTION_LABELS = {
    "submit": "Submit for approval",
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
    "approve": "Approve and reject",
    "prepare": "Prepare BIR files",
    "reconcile": "Reconcile statements",
    "first": "Told first about entries waiting",
    "record": "Record (post to the books)",
    "add": "Add",
    "edit": "Edit",
    "deactivate": "Switch off",
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
    Area("integrations", "Finance connections", "Administration", ("manage",)),
    Area("sales_orders", "Sales orders", "Sales", ("view", "create", "submit", "approve", "cancel")),
    Area("dashboard", "Overview", "Finance", ("view",)),
    Area("funds", "Marketing requests", "Marketing requests", ("view", "release", "check", "settle", "cancel")),
    Area("categories", "Expense categories", "Marketing requests", ("view", "manage")),
    Area("invoices", "Sales invoices and payments", "Invoices", ("view", "create", "issue", "collect", "void", "setup")),
    # Accounts payable (2026-10-23): suppliers, and their bills, each step its own tick so any role
    # can have exactly what it needs. A bill (Aubrey's flow, migration 0020): made and submitted
    # ("create"), approved (Malou "first", Cristal backup), checked only if tax is withheld (Mel),
    # then posted and ready to pay; the payment voucher is prepared and released (Cristal).
    Area("suppliers", "Suppliers", "Payables", ("view", "add", "edit", "deactivate")),
    Area("bills", "Supplier bills", "Payables", ("view", "create", "approve", "first", "check", "void")),
    Area("vouchers", "Payment vouchers", "Payables", ("view", "prepare", "release", "void")),
    # approve: entries typed by hand wait for someone who holds it, never whoever posted them (2026-10-22).
    # first: the main approver (the Finance Head), told of every entry at once; other approvers are
    # backup, told only of the main approver's own entries and of ones waiting over a working day.
    Area("journal", "Journal entries and reports", "Accounting", ("view", "post", "reverse", "approve", "first")),
    Area("accounts", "Chart of accounts and default accounts", "Accounting", ("view", "manage")),
    Area("tax", "Tax setup", "Tax", ("view", "manage")),
    # Prices are Finance's: managers' prices and reps' requested prices wait in the CRM for these.
    Area("prices", "Product prices", "Prices", ("view", "approve")),
    # BIR files made from Oojeema's exports (the Sales DAT, app/bir.py); no role gets it until it's ticked.
    # Prepare BIR files (the Sales DAT); view the books of accounts, statements, VAT return and lists (app/bir_reports.py).
    Area("bir", "BIR files and reports", "Tax", ("view", "prepare")),
    # Matching the bank's statements against the books (app/routers/bank.py).
    Area("bank", "Bank reconciliation", "Accounting", ("view", "reconcile")),
    Area("admin", "Administration", "Administration", ("users", "roles", "audit")),
)

# Switched on for one person, not given with a role (decided 2026-10-22): an
# Administrator turns it on under Administration → Users. Not in AREAS, so the
# Roles screen never offers it, and no role holds it, the Administrator included.
PER_PERSON: frozenset[str] = frozenset({"calendar.use"})

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions()) | PER_PERSON
# Someone must always hold both, or nobody could fix a mistake in access.
KEYS_TO_ADMINISTRATION = frozenset({"admin.users", "admin.roles"})


# Where an action means something else in one area, its own label there (the shared one
# says "Review liquidations" for check, "Prepare BIR files" for prepare).
AREA_LABELS = {
    "sales_orders.create": "Add and edit Finance draft orders",
    "sales_orders.approve": "Approve or return for correction",
    "bills.create": "Make drafts (make, edit, attach, submit)",
    "bills.approve": "Approve or return",
    "bills.first": "Told first about bills to approve",
    "bills.check": "Check the tax withheld",
    "vouchers.prepare": "Prepare (make, edit, submit, cancel)",
    "vouchers.release": "Release (pay)",
    "vouchers.void": "Void a released voucher",
}


def catalogue_out() -> list[dict]:
    return [
        {
            "key": a.key,
            "name": a.name,
            "group": a.group,
            "actions": [{"key": x, "label": AREA_LABELS.get(f"{a.key}.{x}", ACTION_LABELS[x]), "permission": f"{a.key}.{x}"} for x in a.actions],
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
# what "member" used to be: the day's work, not the setup (approving prices included). The Auditor sees
# everything and changes nothing.
STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (ROLE_ADMIN_ID, ADMINISTRATOR, "Everything: the setup (accounts, categories, tax), users, roles and the activity log.", ALL_PERMISSIONS),
    (
        ROLE_STAFF_ID,
        FINANCE_STAFF,
        "Releases cash advances, reviews liquidations, records refunds and reimbursements, posts journal entries, makes and issues invoices and records their payments, keeps suppliers and records their bills, and approves prices.",
        VIEW_ALL
        | _grant("funds", actions=("release", "check", "settle", "cancel"))
        | _grant("journal", actions=("post", "reverse"))
        | _grant("invoices", actions=("create", "issue", "collect"))
        | _grant("suppliers", actions=("add", "edit", "deactivate"))
        | _grant("bills", actions=("create",))
        | _grant("vouchers", actions=("prepare",))
        | _grant("bank", actions=("reconcile",))
        | _grant("prices", actions=("approve",)),
    ),
    (ROLE_AUDITOR_ID, AUDITOR, "Sees everything, including the activity log, and changes nothing.", VIEW_ALL | {"admin.audit"}),
)
