"""Every pick-list a company can change, in one place.

A pick-list is a set of choices that belong to a company rather than to Orbit:
what kinds of customer it keeps, how its people record a visit, how a call
went, how an order is paid for. None of these are the same for two companies,
so none of them live in code as values. What lives in code is only their
*shape* — that a customer kind has a code, a name and an icon — and a first set
of values to start from, per industry template.

Seeding fills in a list that a company doesn't have yet. It never writes over
one its admins have since changed: a renamed choice stays renamed.

Records keep the code, not the name. Renaming "Doctor" to "Prescriber" changes
every screen at once and leaves the records alone; switching a choice off hides
it from new records without touching the ones that already carry it.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LIST_KINDS, ListItem, Organization
from app.scope import slugify
from app.tenancy import company_of

DEFAULT_TEMPLATE = "generic_b2b"


@dataclass(frozen=True)
class ListKind:
    key: str
    name: str
    help: str
    # "orders" shows in Settings -> Orders; "records" in Settings -> Lists.
    screen: str
    # Lists whose choices carry an icon on screen (activities in a timeline).
    has_icons: bool = False
    # Refuse to leave this list empty: records can't be made without a choice.
    required: bool = True


KINDS: tuple[ListKind, ...] = (
    ListKind("payment_method", "Payment methods", "How a customer pays.", "orders"),
    ListKind("payment_term", "Payment terms", "When a customer pays.", "orders"),
    ListKind("source", "Order sources", "Where an order came from.", "orders"),
    ListKind("delivery_method", "Delivery methods", "How an order reaches the customer.", "orders"),
    ListKind("invoicing_entity", "Invoicing entities", "Which of your companies bills the order.", "orders", required=False),
    ListKind(
        "field_section",
        "Form sections",
        "The parts an order form is divided into. Each extra field sits in one of them.",
        "orders",
        required=False,
    ),
    ListKind("customer_kind", "Customer kinds", "What sort of customer this is.", "records"),
    ListKind("activity_kind", "Activity kinds", "Ways your people record having dealt with a customer.", "records", has_icons=True),
    ListKind("outcome", "Call outcomes", "How a call or visit went. Optional on an activity.", "records", required=False),
)
BY_KEY: dict[str, ListKind] = {k.key: k for k in KINDS}
assert tuple(BY_KEY) == LIST_KINDS, "app/lists.py and models.LIST_KINDS disagree"

RECORD_KINDS: tuple[str, ...] = tuple(k.key for k in KINDS if k.screen == "records")

# The first values a new company gets, per industry template. Admins own them
# from the moment the company exists; these are a starting point, not a rule.
# (name, icon) — an icon only where the kind shows one.
Item = str | tuple[str, str]
TEMPLATES: dict[str, dict[str, list[Item]]] = {
    "pharma_ph": {
        "payment_method": ["Cash on delivery", "Bank transfer", "GCash", "Credit terms", "Check", "Credit Card", "PDC"],
        "payment_term": [
            "Due end of next month", "Due end of the month", "Paid", "Advanced Payment", "Advanced Payment - Partial",
            "Donation/Charity", "Samples", "Due on Receipt", "60% DP 40% UPON DEL", "CASH", "COD", "Net", "Net 15",
            "30 days", "45 Day", "BPO WALLET", "60 Day", "DSWD/PCSO", "OP", "90 Day", "INITIAL STOCKING", "120 Day", "180 Day",
        ],
        "source": [
            "Doctor order", "Patient order referred by doctor", "Patient order referred by patient", "Emergency purchase",
            "Hospital PO", "Distributor order",
        ],
        "delivery_method": [
            "Own Rider / Company Vehicle", "LBC Express", "Grab Express", "J&T Express", "Lalamove", "Customer Pick-up",
            "Distributor Delivery",
        ],
        "invoicing_entity": ["2mg Incorporated", "Getmeds Philippines Inc."],
        "field_section": ["Order Details", "Billing & Payment", "Logistics & Delivery", "Additional Information"],
        "customer_kind": ["Doctor", "Hospital", "Clinic", "Pharmacy", "Patient", "Company", "Distributor", "Other"],
        "activity_kind": [("Call", "call"), ("Visit", "visit"), ("Message", "message"), ("Note", "note")],
        "outcome": ["Reached", "No answer", "Call back", "Not interested"],
    },
    "generic_b2b": {
        "payment_method": ["Cash", "Bank transfer", "Check", "Credit card"],
        "payment_term": ["Due on receipt", "Net 15", "Net 30", "Net 60"],
        "source": ["Phone", "Email", "Walk-in", "Website"],
        "delivery_method": ["Our own delivery", "Courier", "Customer pick-up"],
        "invoicing_entity": [],
        "field_section": ["Details", "Payment", "Delivery", "Anything else"],
        "customer_kind": ["Company", "Individual", "Reseller", "Other"],
        "activity_kind": [("Call", "call"), ("Meeting", "visit"), ("Message", "message"), ("Note", "note")],
        "outcome": ["Reached", "No answer", "Call back", "Not interested"],
    },
}

# The codes the old fixed lists used. Keeping them means every record written
# before this screen existed still matches a choice by code.
LEGACY_CODES: dict[str, dict[str, str]] = {
    "customer_kind": {
        "Doctor": "doctor", "Hospital": "hospital", "Clinic": "clinic", "Pharmacy": "pharmacy",
        "Patient": "patient", "Company": "company", "Distributor": "distributor", "Other": "other",
    },
    "activity_kind": {"Call": "call", "Visit": "visit", "Meeting": "visit", "Message": "message", "Note": "note"},
    "outcome": {"Reached": "reached", "No answer": "no_answer", "Call back": "call_back", "Not interested": "not_interested"},
}


def unique_codes(names: list[str], taken: set[str] | None = None) -> list[str]:
    """A short code per name, unique among themselves and `taken`: "Net 15" -> "net-15"."""
    used = set(taken or ())
    codes = []
    for name in names:
        base = (slugify(name) or "item")[:56]
        code, n = base, 2
        while code in used:
            code, n = f"{base}-{n}"[:60], n + 1
        used.add(code)
        codes.append(code)
    return codes


def split(item: Item) -> tuple[str, str | None]:
    return item if isinstance(item, tuple) else (item, None)


def code_for(kind: str, name: str, taken: set[str]) -> str:
    """The code a new choice gets. The old fixed lists' codes are kept where the
    name matches, so records written before this screen still line up."""
    legacy = LEGACY_CODES.get(kind, {}).get(name)
    if legacy and legacy not in taken:
        return legacy
    return unique_codes([name], taken)[0]


def seed_lists(db: Session, template: str | None = None) -> None:
    """Give this company any list it hasn't got. Never touches a list it has,
    even an emptied one: an admin who cleared a list meant to clear it."""
    org = db.get(Organization, company_of(db))
    chosen = template or (org.template if org else DEFAULT_TEMPLATE)
    values = TEMPLATES.get(chosen, TEMPLATES[DEFAULT_TEMPLATE])
    have = {kind for kind in db.scalars(select(ListItem.kind).distinct())}
    for kind in LIST_KINDS:
        if kind in have:
            continue
        taken: set[str] = set()
        for order, item in enumerate(values.get(kind, [])):
            name, icon = split(item)
            code = code_for(kind, name, taken)
            taken.add(code)
            db.add(ListItem(kind=kind, code=code, name=name, icon=icon, sort_order=order))
    db.flush()


def items(db: Session, kind: str, active_only: bool = False) -> list[ListItem]:
    rows = db.scalars(select(ListItem).where(ListItem.kind == kind).order_by(ListItem.sort_order, ListItem.code))
    return [r for r in rows if r.is_active or not active_only]


def item_out(item: ListItem) -> dict:
    return {"code": item.code, "name": item.name, "icon": item.icon, "isActive": item.is_active}


def lists_out(db: Session, kinds: tuple[str, ...] = RECORD_KINDS, active_only: bool = True) -> dict[str, list[dict]]:
    """The company's lists, as the screens read them."""
    by_kind: dict[str, list[dict]] = {kind: [] for kind in kinds}
    rows = db.scalars(select(ListItem).where(ListItem.kind.in_(kinds)).order_by(ListItem.sort_order, ListItem.code))
    for row in rows:
        if row.is_active or not active_only:
            by_kind[row.kind].append(item_out(row))
    return by_kind


def codes(db: Session, kind: str, active_only: bool = True) -> set[str]:
    """What a record may carry for this kind. A record keeps a switched-off code
    it already has, so checks on an existing value pass `active_only=False`."""
    return {item.code for item in items(db, kind, active_only=active_only)}
