"""Settings: what an admin sets up for everyone (admin.settings).

- Forms: each record's form (company, contact, product, quote), laid out in
  sections. Every field is on it: the built-in ones (renamed, moved, hidden or
  made required) and the ones the admin added, with their pick-list options.
- Company & quotes: name, currency, locale, timezone; quote numbering, how
  long a quote is good for, and its standing terms.

Anyone signed in reads the forms (every form and record page is drawn from
them); only admin.settings changes them.
"""

import re
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, camel, changed
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.extra import fields_for
from app.models import FIELD_TYPES, Company, Contact, FormField, FormSection, Product, Quote
from app.pricing import sales_settings

router = APIRouter(tags=["settings"])

Manage = Annotated[Access, Depends(require("admin.settings"))]
Entity = Literal["company", "contact", "product", "quote"]
RECORDS = {"product": Product, "company": Company, "contact": Contact, "quote": Quote}
WITH_OPTIONS = ("choice", "multi_choice")


# --- forms ---------------------------------------------------------------------------------


def field_out(f: FormField, used: int | None = None) -> dict:
    out = {
        "id": f.id,
        "key": f.key,
        "label": f.label,
        "type": f.type,
        "standard": f.standard,
        "locked": f.locked,
        "required": f.required,
        "hidden": f.hidden,
        "inList": f.in_list,
        "options": f.options or [],
        "helpText": f.help_text,
        "placeholder": f.placeholder,
    }
    if used is not None:
        out["used"] = used
    return out


def usage(db: Session, entity: str) -> dict[str, int]:
    """How many records have a value in each added field."""
    counts: dict[str, int] = {}
    for extra in db.scalars(select(RECORDS[entity].extra)):
        for key in extra or {}:
            counts[key] = counts.get(key, 0) + 1
    return counts


def layout_out(db: Session, entity: str, *, everything: bool) -> dict:
    sections = list(db.scalars(select(FormSection).where(FormSection.entity == entity).order_by(FormSection.sort_order)))
    fields = fields_for(db, entity, shown_only=not everything)
    used = usage(db, entity) if everything else {}
    out = []
    for s in sections:
        here = [f for f in fields if f.section_id == s.id]
        if not everything and not here:
            continue
        out.append(
            {"id": s.id, "title": s.title, "columns": s.columns, "fields": [field_out(f, used.get(f.key, 0) if everything else None) for f in here]}
        )
    return {"entity": entity, "sections": out}


@router.get("/forms/{entity}")
def read_form(me: CurrentUser, db: DB, entity: Entity, everything: bool = Query(False, alias="all")) -> dict:
    """The form as people fill it in (hidden fields left out), or with `all` as
    Settings edits it (everything, with how many records use each added field)."""
    return layout_out(db, entity, everything=everything)


class FieldIn(Api):
    # None: a field being added now.
    id: str | None = Field(None, max_length=36)
    label: str = Field(min_length=1, max_length=80)
    type: str = Field(max_length=12)
    required: bool = False
    hidden: bool = False
    in_list: bool = False
    options: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=100)
    help_text: str | None = Field(None, max_length=200)
    placeholder: str | None = Field(None, max_length=80)


class SectionIn(Api):
    id: str | None = Field(None, max_length=36)
    title: str = Field(min_length=1, max_length=80)
    columns: Literal[1, 2] = 2
    fields: list[FieldIn] = Field(default_factory=list, max_length=100)


class LayoutIn(Api):
    sections: list[SectionIn] = Field(min_length=1, max_length=30)


def clean_options(options: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for o in (x.strip() for x in options):
        if o and o.lower() not in seen:
            seen[o.lower()] = o
    return list(seen.values())


@router.put("/admin/forms/{entity}")
def save_form(access: Manage, me: CurrentUser, db: DB, entity: Entity, body: LayoutIn) -> dict:
    """The whole form, as the editor shows it. Built-in fields must all be on it
    (hide one instead of taking it off); an added field left off is deleted,
    unless records have values in it."""
    fields = {f.id: f for f in fields_for(db, entity)}
    sections = {s.id: s for s in db.scalars(select(FormSection).where(FormSection.entity == entity))}
    problems: list[str] = []
    seen_fields: set[str] = set()
    labels: dict[str, str] = {}

    for s in body.sections:
        for f in s.fields:
            key = f.label.strip().lower()
            if key in labels:
                problems.append(f"Two fields are called {f.label}: give each its own name.")
            labels[key] = f.label
            if f.id:
                if f.id not in fields:
                    raise HTTPException(status.HTTP_409_CONFLICT, "Someone changed this form meanwhile. Reload it and make your changes again.")
                if f.id in seen_fields:
                    problems.append(f"{f.label} is on the form twice.")
                seen_fields.add(f.id)
            elif f.type not in FIELD_TYPES:
                problems.append(f"{f.label}: pick what kind of field it is.")
            kind = fields[f.id].type if f.id else f.type
            if kind in WITH_OPTIONS and len(clean_options(f.options)) < (1 if f.id and fields[f.id].standard else 2):
                problems.append(f"{f.label} needs at least two options to pick from.")
    for f in fields.values():
        if f.standard and f.id not in seen_fields:
            problems.append(f"{f.label} is built in: hide it instead of taking it off.")
    used = usage(db, entity)
    dropped = [f for f in fields.values() if not f.standard and f.id not in seen_fields]
    for f in dropped:
        if used.get(f.key):
            problems.append(f"{used[f.key]} {'record has' if used[f.key] == 1 else 'records have'} a value in {f.label}: hide it instead of deleting it.")
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(dict.fromkeys(problems)))

    # Sections first, in order; then every field into its place.
    kept_sections = set()
    for n, s in enumerate(body.sections):
        section = sections.get(s.id or "") or FormSection(entity=entity)
        section.title, section.columns, section.sort_order = s.title.strip(), s.columns, n
        db.add(section)
        db.flush()
        kept_sections.add(section.id)
        for m, f in enumerate(s.fields):
            if f.id:
                field = fields[f.id]
            else:
                base = "x_" + (re.sub(r"[^a-z0-9]+", "_", f.label.lower()).strip("_")[:30] or "field")
                key, k = base, 2
                taken = {x.key for x in fields.values()} | {x.key for x in db.new if isinstance(x, FormField)}
                while key in taken:
                    key, k = f"{base}_{k}", k + 1
                field = FormField(entity=entity, key=key, type=f.type, standard=False, locked=False)
                db.add(field)
            field.label = f.label.strip()
            # A locked field is always there and always required.
            field.required = True if field.locked else f.required
            field.hidden = False if field.locked else f.hidden
            field.in_list = f.in_list
            field.options = clean_options(f.options) if field.type in WITH_OPTIONS else []
            field.help_text = f.help_text
            field.placeholder = f.placeholder
            field.section_id = section.id
            field.sort_order = m
    for f in dropped:
        db.delete(f)
    for sid, s in sections.items():
        if sid not in kept_sections:
            db.delete(s)
    audit(db, me, "form.updated", target=f"{entity} form", target_type="form")
    db.commit()
    return layout_out(db, entity, everything=True)


# --- company & quotes ----------------------------------------------------------------------

CURRENCIES = ("PHP", "USD", "EUR", "GBP", "SGD", "MYR", "IDR", "THB", "VND", "JPY", "CNY", "HKD", "AUD", "INR")


def company_out(db: Session, settings) -> dict:
    s = sales_settings(db)
    return {
        "orgName": settings.org_name,
        "currency": settings.org_currency,
        "locale": settings.org_locale,
        "timezone": settings.org_timezone,
        "quotePrefix": s.quote_prefix,
        "quoteValidDays": s.quote_valid_days,
        "quoteTerms": s.quote_terms,
        "currencies": list(CURRENCIES),
    }


@router.get("/admin/company-settings")
def read_company(access: Manage, db: DB, settings: SettingsDep) -> dict:
    return company_out(db, settings)


class CompanyIn(Api):
    org_name: str | None = Field(None, min_length=1, max_length=120)
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    locale: str | None = Field(None, pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    timezone: str | None = Field(None, max_length=60)
    quote_prefix: str | None = Field(None, pattern=r"^[A-Z0-9]{1,10}$")
    quote_valid_days: int | None = Field(None, ge=1, le=365)
    quote_terms: str | None = Field(None, max_length=5000)

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Pick a timezone like Asia/Manila.") from None
        return value


@router.patch("/admin/company-settings")
def update_company(access: Manage, me: CurrentUser, db: DB, settings: SettingsDep, body: CompanyIn) -> dict:
    s = sales_settings(db)
    wanted = changed(body)
    # Terms can be cleared; the rest can only be changed.
    wanted = {k: v for k, v in wanted.items() if v is not None or k == "quote_terms"}
    fields = [k for k, v in wanted.items() if getattr(s, k) != v]
    for k in fields:
        setattr(s, k, wanted[k])
    if fields:
        audit(db, me, "company_settings.updated", target="Company & quotes", target_type="settings", fields=camel(fields))
    db.commit()
    names = {"org_name": "org_name", "currency": "org_currency", "locale": "org_locale", "timezone": "org_timezone"}
    fresh = settings.model_copy(update={names[k]: v for k, v in wanted.items() if k in names and v})
    return company_out(db, fresh)

