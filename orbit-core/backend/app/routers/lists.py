"""Settings -> Lists: the choices a company keeps for its own records — what
kinds of customer it has, how its people record dealing with one, how a call
went. Admins only.

A list is saved whole, in the order it is shown. Nothing is ever deleted:
records carry a choice's code, so a choice that disappeared would leave them
naming nothing. Switching one off keeps every record that already has it and
stops it being picked again.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.audit import audit
from app.deps import DB, CurrentUser, require_settings
from app.errors import field_errors
from app.lists import BY_KEY, RECORD_KINDS, item_out, unique_codes
from app.models import ListItem
from app.schemas import ListIn

router = APIRouter(prefix="/admin/lists", tags=["settings"], dependencies=[Depends(require_settings)])


def lists_payload(db: DB) -> dict:
    rows = db.scalars(select(ListItem).where(ListItem.kind.in_(RECORD_KINDS)).order_by(ListItem.sort_order, ListItem.name))
    items: dict[str, list[dict]] = {kind: [] for kind in RECORD_KINDS}
    for row in rows:
        items[row.kind].append(item_out(row))
    return {
        "kinds": [
            {"kind": k, "label": BY_KEY[k].name, "hint": BY_KEY[k].help, "hasIcons": BY_KEY[k].has_icons,
             "required": BY_KEY[k].required}
            for k in RECORD_KINDS
        ],
        "lists": items,
    }


@router.get("")
def company_lists(db: DB) -> dict:
    return lists_payload(db)


@router.put("/{kind}")
def replace_list(kind: str, body: ListIn, db: DB, me: CurrentUser) -> dict:
    if kind not in RECORD_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such list.")
    definition = BY_KEY[kind]

    errors: list[tuple[tuple, str]] = []
    seen: set[str] = set()
    for i, item in enumerate(body.items):
        folded = item.name.casefold()
        if folded in seen:
            errors.append((("items", i, "name"), "Already in the list."))
        seen.add(folded)
    existing = {i.code: i for i in db.scalars(select(ListItem).where(ListItem.kind == kind))}
    for i, item in enumerate(body.items):
        if item.code is not None and item.code not in existing:
            errors.append((("items", i, "code"), "That choice was changed meanwhile. Reload and try again."))
    if definition.required and not any(item.is_active for item in body.items):
        errors.append((("items",), f"Keep at least one {definition.name.rstrip('s').lower()} switched on."))
    if errors:
        raise field_errors(errors)

    # Anything the screen didn't send is switched off rather than removed, so
    # records that already carry it still say something.
    sent = {item.code for item in body.items if item.code}
    for code, row in existing.items():
        if code not in sent:
            row.is_active = False
    new_codes = iter(unique_codes([i.name for i in body.items if not i.code], taken=set(existing)))
    for order, item in enumerate(body.items):
        row = existing.get(item.code) if item.code else None
        icon = item.icon if definition.has_icons else None
        if row is None:
            db.add(ListItem(kind=kind, code=next(new_codes), name=item.name, icon=icon, is_active=item.is_active, sort_order=order))
        else:
            row.name, row.is_active, row.sort_order = item.name, item.is_active, order
            if definition.has_icons:
                row.icon = icon
    db.commit()
    audit(db, me, "list.changed", definition.name)
    return lists_payload(db)
