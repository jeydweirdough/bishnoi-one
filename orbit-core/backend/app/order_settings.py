"""A company's order settings: the pick-lists on an order, its extra fields,
and its rules. Set in Settings -> Orders; the Orders app reads them.

A new company starts from its industry template's lists. Getmeds (pharma_ph)
starts from the lists its old Orders app had.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ORDER_LIST_KINDS, ListItem, Organization, CustomField, OrderSettings
from app.lists import KINDS, seed_lists
from app.tenancy import company_of

# The order pick-lists, as Settings -> Orders shows them. Every company list,
# these included, is defined once in app/lists.py.
LIST_KINDS: dict[str, tuple[str, str]] = {k.key: (k.name, k.help) for k in KINDS if k.screen == "orders"}
assert tuple(LIST_KINDS) == ORDER_LIST_KINDS

def seed_order_settings(db: Session) -> bool:
    """Gives the session's company its template's lists and default rules, once."""
    seed_lists(db)
    if db.get(OrderSettings, company_of(db)) is not None:
        return False
    db.add(OrderSettings())
    db.flush()
    return True


def settings_out(db: Session) -> dict:
    db.expire_all()
    org = db.get(Organization, company_of(db))
    rules = db.get(OrderSettings, company_of(db)) or OrderSettings(large_order_centavos=10_000_000, recycle_days=30)
    items = db.scalars(
        select(ListItem).where(ListItem.kind.in_(ORDER_LIST_KINDS)).order_by(ListItem.kind, ListItem.sort_order, ListItem.name)
    )
    lists: dict[str, list[dict]] = {kind: [] for kind in LIST_KINDS}
    for item in items:
        lists[item.kind].append({"code": item.code, "name": item.name, "isActive": item.is_active})
    fields = db.scalars(select(CustomField).where(CustomField.subject == "order").order_by(CustomField.sort_order, CustomField.label))
    return {
        "kinds": [{"kind": k, "label": label, "hint": hint} for k, (label, hint) in LIST_KINDS.items()],
        "lists": lists,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "type": f.type,
                "required": f.required,
                "options": list(f.options or []),
                "help": f.help,
                "section": f.section,
                "isActive": f.is_active,
            }
            for f in fields
        ],
        "rules": {
            "largeOrderCentavos": rules.large_order_centavos,
            "recycleDays": rules.recycle_days,
            "orderPrefix": org.order_prefix if org else "OR",
            "currency": org.currency if org else "PHP",
        },
    }
