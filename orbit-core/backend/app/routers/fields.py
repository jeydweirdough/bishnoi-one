"""Settings -> Fields: the fields a company puts on its own products and
customers. Admins only.

A subject's fields are saved whole, in the order they are shown. Nothing is
ever deleted: a product keeps its values under a field's key, so a field that
disappeared would leave them naming nothing. Switching one off hides it from
the forms and keeps every record that already has a value for it.

Order fields are the same table (app/fields.py) but keep their own screen, so
they are shown here and changed in Settings -> Orders.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.audit import audit
from app.deps import DB, CurrentUser, require_settings
from app.errors import field_errors, invalid
from app.fields import BY_SUBJECT, OWN_SUBJECTS, SUBJECTS, fields_out
from app.lists import codes
from app.models import FIELD_SUBJECTS, CustomField
# The rules the order-fields screen already applies, so both screens judge a
# field the same way: two fields can't share a label, and a field's key comes
# from its label.
from app.routers.order_settings import duplicates, field_key
from app.schemas import OrderFieldsIn

router = APIRouter(prefix="/admin/fields", tags=["settings"], dependencies=[Depends(require_settings)])


def fields_payload(db: DB) -> dict:
    return {
        "subjects": [
            {"subject": s.key, "label": s.name, "hint": s.help, "screen": s.screen, "shownOn": list(s.shown_on)}
            for s in SUBJECTS
        ],
        "fields": {subject: fields_out(db, subject) for subject in FIELD_SUBJECTS},
    }


@router.get("")
def company_fields(db: DB) -> dict:
    return fields_payload(db)


@router.put("/{subject}")
def replace_fields(subject: str, body: OrderFieldsIn, db: DB, me: CurrentUser) -> dict:
    if subject not in BY_SUBJECT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such kind of record.")
    if subject not in OWN_SUBJECTS:
        raise invalid(f"{BY_SUBJECT[subject].name} fields are changed in {BY_SUBJECT[subject].screen}.")

    errors = duplicates([f.label for f in body.fields], "fields", "label")
    sections = codes(db, "field_section", active_only=False)
    for i, f in enumerate(body.fields):
        if f.type == "choice" and len(set(f.options)) < 2:
            errors.append((("fields", i, "options"), "A choice needs at least two options."))
        if f.section and f.section not in sections:
            errors.append((("fields", i, "section"), "Pick one of your form sections, or leave it for the last one."))
    existing = {f.key: f for f in db.scalars(select(CustomField).where(CustomField.subject == subject))}
    for i, f in enumerate(body.fields):
        if f.key is not None and f.key not in existing:
            errors.append((("fields", i, "key"), "That field was changed meanwhile. Reload and try again."))
    if errors:
        raise field_errors(errors)

    sent = {f.key for f in body.fields if f.key}
    for key, row in existing.items():
        if key not in sent:
            row.is_active = False
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
            db.add(CustomField(subject=subject, key=key, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
    db.commit()
    audit(db, me, "fields.changed", f"{BY_SUBJECT[subject].name} fields")
    return fields_payload(db)
