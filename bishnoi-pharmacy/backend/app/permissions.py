"""Everything a role can be allowed to do, and the roles the Pharmacy starts with.

A permission is "<area>.<action>", e.g. "prescriptions.verify" or "admin.users".

Checking a prescription and dispensing it are separate permissions on
purpose: whoever takes a prescription in (prescriptions.create) is not
necessarily whoever may pass it (prescriptions.verify), and only a verified
prescription can be dispensed (dispensing.create).
"""

from dataclasses import dataclass

CRUD = ("view", "create", "edit", "delete")

ACTION_LABELS = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "verify": "Check & verify",
    "manage": "Quarantine & recall",
    "receive": "Receive stock",
    "adjust": "Adjust stock",
    "refund": "Returns & refunds",
    "review": "Approve or return",
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
    Area("dashboard", "Dashboard", "Pharmacy", ("view",)),
    Area("prescriptions", "Prescriptions", "Pharmacy", ("view", "create", "edit", "verify")),
    Area("dispensing", "Dispensing", "Pharmacy", ("view", "create")),
    Area("patients", "Patients & customers", "Pharmacy", CRUD),
    Area("sales", "Sales", "Pharmacy", ("view", "create", "refund")),
    Area("medicines", "Medicines, categories & brands", "Stock", CRUD),
    Area("batches", "Batches & expiry", "Stock", ("view", "manage")),
    Area("stock", "Stock", "Stock", ("view", "receive", "adjust")),
    Area("suppliers", "Suppliers", "Stock", CRUD),
    # Designs sent by Admin: the pharmacist approves them before they're produced.
    Area("materials", "Promotional material reviews", "Pharmacy", ("view", "review")),
    Area("reports", "Reports", "Reports", ("view",)),
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


# The roles the Pharmacy starts with. Administrator is the system role: it
# always holds every permission and can't be changed or deleted. The other two
# are ordinary roles, there to start from; migration 0001 writes them out.
ADMINISTRATOR = "Administrator"
PHARMACIST = "Pharmacist"
ASSISTANT = "Pharmacy Assistant"
