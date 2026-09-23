"""The modules and the actions a role can be granted in each.

Each module is also a division: the module key is the division code, and
records in a module carry it. The Sales department's seven divisions share one
workspace
(customers, activities, follow-ups, quotes). Department modules get their own
screens one at a time: Finance (quote approvals, guarantee letters, payments)
and Inventory (products, prices, promos) have them; the rest are listed and
permissioned now and get screens later.

Orders is a module whose screens are another app's (the Orders app): Orbit
holds who may take which step of an order, and the Orders app asks. It isn't a
division. Its steps reach the sales divisions and BID, and a person's sales (or
BID) team assignment carries their role's order steps for that same team, so a
rep raises orders where they sell without a second assignment. Management,
Finance and Dispatch get theirs from an assignment to Orders itself (or to
every module).

Permissions are a matrix of role x module -> actions (see the role_permissions
table), not per-user flags. `settings` is the one non-module row: it gates the
admin screens.
"""

from dataclasses import dataclass
from enum import StrEnum


class Kind(StrEnum):
    SALES = "sales"
    DEPARTMENT = "department"
    # Screens in another app; Orbit holds the permissions.
    APP = "app"


BASE_ACTIONS: tuple[str, ...] = ("view", "create", "edit", "delete")
# "report" is seeing a whole team's figures and each rep's (customer retention),
# not only your own customers'. Sales modules only, for now.
REPORT = "report"
# Setting what this team charges: its own prices over the company's, and which
# price types it quotes with (app/price_book.py). A Team Lead's, not a rep's.
PRICES = "prices"
SALES_ACTIONS: tuple[str, ...] = (*BASE_ACTIONS, REPORT, PRICES)

# The steps of an order, grouped the way Settings -> Roles shows them.
ORDER_STEPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("Raise and edit", (("view", "See orders"), ("raise", "Raise"), ("edit", "Edit"))),
    ("Approvals", (("endorse", "Endorse (team lead)"), ("approve", "Approve"), ("send_back", "Send back"), ("reject", "Reject"))),
    ("Finance", (("verify_payment", "Verify payment"), ("hold", "Hold payment"))),
    ("Fulfilment", (("fulfil", "Pick, pack and dispatch"), ("deliver", "Mark delivered"))),
    ("Admin", (("delete", "Delete"), ("restore", "Restore deleted"))),
)
ORDER_ACTIONS: tuple[str, ...] = tuple(key for _, steps in ORDER_STEPS for key, _ in steps)


@dataclass(frozen=True)
class Module:
    key: str
    name: str
    kind: Kind
    # True when the module's records belong to other divisions too (HR keeps
    # records for every division's staff). False keeps an assignment inside
    # the module's own division. Revisit per module when it is built.
    spans_divisions: bool
    # Department modules whose screens exist. Sales modules share one workspace.
    has_screens: bool = False
    actions: tuple[str, ...] = BASE_ACTIONS
    # The divisions its grants may reach, when not every one.
    reaches: tuple[str, ...] | None = None
    # One line saying what it is, for an application's first row in Settings ->
    # Apps. The admins may rewrite it; this is only where it starts.
    blurb: str = ""

    @property
    def built(self) -> bool:
        return self.kind is Kind.SALES or self.has_screens

    @property
    def is_division(self) -> bool:
        return self.kind is not Kind.APP


ORDERS = "orders"
# Where orders are raised: the sales divisions, and BID.
ORDER_HOMES: tuple[str, ...] = ("b2c", "stc", "uro", "bnb", "b2b", "hos", "bid")

# The company's org chart, in its own order: the Sales department's divisions
# first, then the other departments.
MODULES: tuple[Module, ...] = (
    # Sales. Seven divisions sharing one workspace -- a division is a property of
    # a record, not a place, so Customers and Follow-ups merge across them.
    Module("b2c", "B2C", Kind.SALES, False, actions=SALES_ACTIONS),
    Module("stc", "STC", Kind.SALES, False, actions=SALES_ACTIONS),
    Module("uro", "URO", Kind.SALES, False, actions=SALES_ACTIONS),
    Module("bnb", "B&B", Kind.SALES, False, actions=SALES_ACTIONS),
    Module("b2b", "B2B", Kind.SALES, False, actions=SALES_ACTIONS),
    Module("hos", "HOS", Kind.SALES, False, actions=SALES_ACTIONS),
    # BID sells like the rest but bids rather than quoting from a price list
    # (app/price_book.py: NOTES_ONLY), so there is nothing for its teams to
    # price -- it takes the sales actions without PRICES.
    Module("bid", "BID", Kind.SALES, False, actions=(*BASE_ACTIONS, REPORT)),
    # The other departments.
    # Finance works on the sales divisions' quotes, so its grants reach them.
    Module("finance", "Finance", Kind.DEPARTMENT, True, has_screens=True),
    Module("hr", "Human Resource", Kind.DEPARTMENT, True),
    Module("regulatory", "Regulatory Affairs", Kind.DEPARTMENT, False),
    Module("inlicensing", "In-Licensing", Kind.DEPARTMENT, False),
    Module("pharmacy", "Pharmacy", Kind.DEPARTMENT, False),
    Module("exec", "Executive Admin", Kind.DEPARTMENT, True),
    # Desks rather than departments on the org chart, but real permission
    # targets: Dispatch is who the Orders app hands fulfilment to, and Inventory
    # owns the products, prices, promos and bundles every quote is built from.
    Module("dispatch", "Dispatch", Kind.DEPARTMENT, True),
    # Products and prices are company-wide; Inventory has no per-division records.
    Module("inventory", "Inventory", Kind.DEPARTMENT, False, has_screens=True),
    Module(
        ORDERS, "Orders", Kind.APP, True, actions=ORDER_ACTIONS, reaches=ORDER_HOMES,
        blurb="Raise an order and take it through to delivery.",
    ),
)

BY_KEY: dict[str, Module] = {m.key: m for m in MODULES}
SALES_KEYS: tuple[str, ...] = tuple(m.key for m in MODULES if m.kind is Kind.SALES)

# Every action, in the order screens list them.
ACTIONS: tuple[str, ...] = tuple(dict.fromkeys((*SALES_ACTIONS, *ORDER_ACTIONS)))
SETTINGS = "settings"
# Running the company: every settings screen, the business ones included.
MANAGE = "manage"
# Getting the company working again when something is broken: the company
# record, its accounts, the applications it reaches and the log of what
# happened. Deliberately not the business rules -- somebody restoring access at
# midnight has no business near the price list.
#
# Every Developer Admin holds this in every company, because that is the job.
# A company may also grant it locally to someone technical of its own.
#
# It is not a weaker MANAGE. Whoever holds it can put an account back, and an
# account is a way in, so treat it as break-glass: given to few, and every use
# of it written down.
RECOVER = "recover"
SETTINGS_ACTIONS: tuple[tuple[str, str, str], ...] = (
    (MANAGE, "Run the company", "Every settings screen: people, roles, teams and the business rules."),
    (RECOVER, "Technical recovery", "Apps, the audit log, the company record and its accounts. For when something is broken."),
)
ALL_MODULES = "*"


def valid_grant(module_key: str, action: str) -> bool:
    if module_key == SETTINGS:
        return action in (MANAGE, RECOVER)
    return module_key in BY_KEY and action in BY_KEY[module_key].actions


# The starting roles. Admins edit these in Settings -> Roles.
# Order steps each starting role takes. Reps and leads take them in their own
# teams (their sales assignment carries them); the others are assigned Orders.
LEAD_ORDER_STEPS = ("view", "raise", "edit", "endorse", "send_back", "reject")

DEFAULT_ROLES: tuple[tuple[str, str, str, dict[str, tuple[str, ...]]], ...] = (
    (
        "rep",
        "Rep / Agent",
        "Works their team's records: adds customers, logs calls and visits, follows up, raises orders.",
        {**{k: ("view", "create", "edit") for k in SALES_KEYS}, ORDERS: ("view", "raise")},
    ),
    (
        "team_lead",
        "Team Lead",
        "Everything a rep can do for the whole team, can delete, sees each rep's figures, sets what the team charges, "
        "and endorses the team's orders.",
        {**{k: BY_KEY[k].actions for k in SALES_KEYS}, ORDERS: LEAD_ORDER_STEPS},
    ),
    (
        "division_head",
        "Division Head",
        "Sees and manages every team in their division, sets what they charge, orders included.",
        {**{k: BY_KEY[k].actions for k in SALES_KEYS}, ORDERS: LEAD_ORDER_STEPS},
    ),
    (
        "management",
        "Management",
        "Approves, sends back or rejects orders, and sees the sales divisions' figures.",
        {**{k: ("view", REPORT) for k in SALES_KEYS}, ORDERS: ("view", "approve", "send_back", "reject", "edit")},
    ),
    (
        "department_staff",
        "Department Staff",
        "Works their own department module for the divisions they are assigned.",
        {m.key: ("view", "create", "edit") for m in MODULES if m.kind is Kind.DEPARTMENT},
    ),
    (
        "finance_staff",
        "Finance Staff",
        "Verifies order payments or holds them, and works the Finance desk.",
        {"finance": ("view", "create", "edit"), ORDERS: ("view", "verify_payment", "hold", "edit")},
    ),
    (
        "dispatch_staff",
        "Dispatch Staff",
        "Picks, packs, dispatches and delivers orders.",
        {"dispatch": ("view", "create", "edit"), ORDERS: ("view", "fulfil", "deliver")},
    ),
    (
        "executive",
        "Executive",
        "Sees everything, read-only, including every division's figures.",
        {m.key: ("view", REPORT) if m.kind is Kind.SALES else ("view",) for m in MODULES},
    ),
    (
        "admin",
        "Admin",
        "Runs the company: its people, roles, teams and business rules; deletes and restores orders.",
        {SETTINGS: (MANAGE,), ORDERS: ("view", "delete", "restore")},
    ),
)
# Developer Admin is not in this list, and cannot be: it is not a company's role
# to give. It belongs to the platform, above every company (app/platform.py), so
# a company's own admins can never grant it to themselves. What it holds inside
# a company is RECOVER, which a company may also grant locally to someone
# technical of its own.
