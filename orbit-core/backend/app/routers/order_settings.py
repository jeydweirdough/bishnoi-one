"""Settings -> Orders: the order form's pick-lists, its extra fields, and the
order rules. Admins only. The Orders app reads them (see orders_api.py).

A list is saved whole, in its order. Removing an item is fine: orders keep
the name they were saved with.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.audit import audit
from app.deps import DB, CurrentUser, require_settings
from app.errors import field_errors
from app.models import ListItem, Organization, CustomField, OrderSettings
from app.lists import codes, unique_codes
from app.order_settings import LIST_KINDS, settings_out
from app.schemas import OrderFieldsIn, OrderListIn, OrderRulesIn
from app.scope import slugify
from app.tenancy import company_of

router = APIRouter(prefix="/admin/orders", tags=["settings"], dependencies=[Depends(require_settings)])


@router.get("")
def order_settings(db: DB) -> dict:
    return settings_out(db)


def duplicates(names: list[str], loc: str, what: str) -> list[tuple[tuple, str]]:
    seen: set[str] = set()
    errors = []
    for i, name in enumerate(names):
        key = name.casefold()
        if key in seen:
            errors.append(((loc, i, what), "Already in the list."))
        seen.add(key)
    return errors


@router.put("/lists/{kind}")
def replace_list(kind: str, body: OrderListIn, db: DB, me: CurrentUser) -> dict:
    if kind not in LIST_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such list.")
    errors = duplicates([i.name for i in body.items], "items", "name")
    existing = {i.code: i for i in db.scalars(select(ListItem).where(ListItem.kind == kind))}
    for i, item in enumerate(body.items):
        if item.code is not None and item.code not in existing:
            errors.append((("items", i, "code"), "That item was removed meanwhile. Reload and try again."))
    if errors:
        raise field_errors(errors)

    kept = {i.code for i in body.items if i.code}
    for code, row in existing.items():
        if code not in kept:
            db.delete(row)
    new_codes = iter(unique_codes([i.name for i in body.items if not i.code], taken=set(existing)))
    for order, item in enumerate(body.items):
        row = existing.get(item.code) if item.code else None
        if row is None:
            db.add(ListItem(kind=kind, code=next(new_codes), name=item.name, is_active=item.is_active, sort_order=order))
        else:
            row.name, row.is_active, row.sort_order = item.name, item.is_active, order
    db.commit()
    audit(db, me, "orders.list_changed", LIST_KINDS[kind][0])
    return settings_out(db)


def field_key(label: str) -> str:
    return (slugify(label).replace("-", "_") or "field")[:36]


@router.put("/fields")
def replace_fields(body: OrderFieldsIn, db: DB, me: CurrentUser) -> dict:
    errors = duplicates([f.label for f in body.fields], "fields", "label")
    sections = codes(db, "field_section", active_only=False)
    for i, f in enumerate(body.fields):
        if f.type == "choice" and len(set(f.options)) < 2:
            errors.append((("fields", i, "options"), "A choice needs at least two options."))
        if f.section and f.section not in sections:
            errors.append((("fields", i, "section"), "Pick one of your form sections, or leave it for the last one."))
    existing = {f.key: f for f in db.scalars(select(CustomField).where(CustomField.subject == "order"))}
    for i, f in enumerate(body.fields):
        if f.key is not None and f.key not in existing:
            errors.append((("fields", i, "key"), "That field was removed meanwhile. Reload and try again."))
    if errors:
        raise field_errors(errors)

    kept = {f.key for f in body.fields if f.key}
    for key, row in existing.items():
        if key not in kept:
            db.delete(row)
    taken = set(existing)
    for order, f in enumerate(body.fields):
        options = list(dict.fromkeys(f.options)) if f.type == "choice" else []
        values = {"label": f.label, "type": f.type, "required": f.required, "options": options, "help": f.help,
                  "section": f.section, "is_active": f.is_active, "sort_order": order}
        row = existing.get(f.key) if f.key else None
        if row is None:
            base = key = field_key(f.label)
            n = 2
            while key in taken:
                key, n = f"{base}_{n}", n + 1
            taken.add(key)
            db.add(CustomField(subject="order", key=key, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
    db.commit()
    audit(db, me, "orders.fields_changed", "Extra order fields")
    return settings_out(db)


@router.put("/rules")
def save_rules(body: OrderRulesIn, db: DB, me: CurrentUser) -> dict:
    rules = db.get(OrderSettings, company_of(db))
    if rules is None:
        rules = OrderSettings()
        db.add(rules)
    changed = [
        name
        for name, before, after in (
            ("largeOrderCentavos", rules.large_order_centavos, body.large_order_centavos),
            ("recycleDays", rules.recycle_days, body.recycle_days),
        )
        if before != after
    ]
    rules.large_order_centavos, rules.recycle_days = body.large_order_centavos, body.recycle_days
    org = db.get(Organization, company_of(db))
    if org.order_prefix != body.order_prefix:
        changed.append("orderPrefix")
        org.order_prefix = body.order_prefix
    db.commit()
    audit(db, me, "orders.rules_changed", "Order rules", changed)
    return settings_out(db)
