"""Everything a role can be allowed to do in Executive Admin, and the starting roles.

A permission is "<area>.<action>", e.g. "permits.create" or "admin.users".
Executive Admin manages corporate permits, immigration, documents, leases, tickets,
the company's vehicles and fuel cards, travel sponsorships, devices issued, and administration.
"""

from dataclasses import dataclass

CRUD = ("view", "create", "edit", "delete")

ACTION_LABELS = {
    "view": "View",
    "create": "Create",
    "edit": "Edit",
    "delete": "Delete",
    "assign": "Assign",
    "resolve": "Resolve",
    "produce": "Produce",
    "distribute": "Distribute",
    "acknowledge": "Acknowledge",
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
    Area("dashboard", "Dashboard & countdowns", "Executive", ("view",)),
    Area("permits", "Corporate permits & accreditations", "Compliance", CRUD),
    Area("immigration", "Expatriate & visa compliance", "Immigration", CRUD),
    Area("documents", "Corporate documents & insurance", "Legal & Corporate", CRUD),
    Area("properties", "Properties & lease management", "Real Estate", CRUD),
    Area("vehicles", "Company vehicles and fuel cards", "Fleet and travel", CRUD),
    Area("travel", "Hotel and flight sponsorships", "Fleet and travel", CRUD),
    Area("devices", "Laptops, phones and SIMs issued", "Fleet and travel", CRUD),
    Area(
        "tickets",
        "Office concerns & service desk",
        "Office Services",
        ("view", "create", "edit", "assign", "resolve", "delete"),
    ),
    # Designed by marketing, approved in Pharmacy, produced here, given out with the CRM manager's approval.
    Area(
        "materials",
        "Promotional materials",
        "Marketing",
        ("view", "create", "edit", "produce", "distribute", "delete"),
    ),
    Area("notifications", "Renewal alerts & countdowns", "Executive", ("view", "acknowledge", "resolve")),
    Area("admin", "Administration", "Administration", ("users", "roles", "audit")),
)

ALL_PERMISSIONS: frozenset[str] = frozenset(p for a in AREAS for p in a.permissions())
ADMIN_PERMISSIONS: frozenset[str] = frozenset(p for p in ALL_PERMISSIONS if p.startswith("admin."))
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


VIEW_ALL = frozenset(_grant(*(a.key for a in AREAS if a.key != "admin"), actions=("view",)))

ADMINISTRATOR = "Administrator"
EXECUTIVE_ASSISTANT = "Executive Assistant"
COMPLIANCE_OFFICER = "Compliance Officer"
AUDITOR = "Auditor"
MARKETING_ASSISTANT = "Marketing Assistant"

ROLE_ADMIN_ID = "00000000-0000-4000-8000-000000000001"
ROLE_EXEC_ASST_ID = "00000000-0000-4000-8000-000000000002"
ROLE_COMPLIANCE_ID = "00000000-0000-4000-8000-000000000003"
ROLE_AUDITOR_ID = "00000000-0000-4000-8000-000000000004"
ROLE_MARKETING_ID = "00000000-0000-4000-8000-000000000005"

STARTING_ROLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    (
        ROLE_ADMIN_ID,
        ADMINISTRATOR,
        "Full administrative control across all executive office functions, users, roles, and the activity log.",
        ALL_PERMISSIONS,
    ),
    (
        ROLE_EXEC_ASST_ID,
        EXECUTIVE_ASSISTANT,
        "Manages executive documents, renewal countdowns, tickets, and facilities on a day-to-day basis.",
        VIEW_ALL
        | _grant("permits", "immigration", "documents", "properties", actions=("create", "edit"))
        | _grant("tickets", actions=("create", "edit", "assign", "resolve"))
        | _grant("vehicles", "travel", "devices", actions=("create", "edit"))
        | _grant("materials", actions=("produce",))
        | _grant("notifications", actions=("acknowledge", "resolve")),
    ),
    (
        ROLE_COMPLIANCE_ID,
        COMPLIANCE_OFFICER,
        "Oversees regulatory compliance (BOC, FDA, SEC, BIR, LGU), expatriate visas, and contracts.",
        VIEW_ALL
        | _grant("permits", "immigration", "documents", actions=("create", "edit", "delete"))
        | _grant("notifications", actions=("acknowledge", "resolve")),
    ),
    (
        ROLE_AUDITOR_ID,
        AUDITOR,
        "Read-only visibility across all corporate records, alerts, and the administration activity log.",
        VIEW_ALL | {"admin.audit"},
    ),
    (
        ROLE_MARKETING_ID,
        MARKETING_ASSISTANT,
        "Designs promotional materials, sends them for the pharmacist's approval, and gives them out once the manager approves.",
        _grant("materials", actions=("view", "create", "edit", "distribute")),
    ),
)
