"""Customers as a spreadsheet: the columns, written for people to read
(exports) and read back the same way (imports, app/routers/imports.py).

One column per field: the built-in ones, then every added field that's on a
form (Settings → Forms), whichever team or type it's for, so one file holds
every division's customers. A value is written as a person would type it:
a pick-list's short code (its full name is read too), a linked customer's
name, our products' names, Yes or No, dates as YYYY-MM-DD. So a file that's
exported, corrected and imported again comes back as it went.
"""

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access
from app.api import check_email
from app.extra import applies, check_extra, check_required, fields_for, offered_products
from app.models import Association, Company, Contact, CustomerType, FormField, Product, User
from app.routers.customer_types import check_type, first_type
from app.routers.deals import check_source
from app.scope import owner_for, reaches, within

# The built-in columns: key (as imports call it), header, and the record's attribute.
BUILT_IN: tuple[tuple[str, str, str], ...] = (
    ("code", "Customer code", "code"),
    ("name", "Name", "name"),
    ("status", "Type", "status"),
    ("industry", "Industry", "industry"),
    ("leadSource", "Lead source", "lead_source"),
    ("email", "Email", "email"),
    ("phone", "Phone", "phone"),
    ("website", "Website", "website"),
    ("address", "Address", "address"),
    ("city", "City", "city"),
    ("country", "Country", "country"),
    ("owner", "Assigned to", "owner_id"),
    ("notes", "Notes", "notes"),
)
# Other names a header might give a built-in column (compared as normal() leaves them).
ALIASES: dict[str, list[str]] = {
    "code": ["code", "customercode", "id", "customerid", "accountcode"],
    "name": ["name", "customer", "customername", "account", "accountname", "company", "companyname", "fullname"],
    "status": ["type", "customertype", "status", "kind"],
    "industry": ["industry", "sector"],
    "leadSource": ["leadsource", "source"],
    "email": ["email", "emailaddress", "mail"],
    "phone": ["phone", "mobile", "mobilenumber", "contactnumber", "cellphone", "phonenumber"],
    "website": ["website", "web", "url", "site"],
    "address": ["address", "street", "streetaddress"],
    "city": ["city", "town", "municipality"],
    "country": ["country"],
    "owner": ["assignedto", "owner", "rep", "salesperson", "salesrep", "employeeid", "wholooksafterit"],
    "notes": ["notes", "note", "remarks", "comments"],
}


def normal(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def added_fields(db: Session) -> list[FormField]:
    return fields_for(db, "company", added_only=True, shown_only=True)


def import_fields(db: Session) -> list[dict]:
    """What a column can go into, for the import wizard."""
    out = [
        {"key": key, "label": label, "required": key == "name", "aliases": ALIASES.get(key, [])}
        for key, label, _ in BUILT_IN
    ]
    out[0]["label"] = "Customer code (to update one already here)"
    for f in added_fields(db):
        out.append({"key": f"extra:{f.key}", "label": f.label, "required": False, "aliases": [f.label, f.key.removeprefix("x_")]})
    return out


# --- writing ---------------------------------------------------------------------------------


class Lookups:
    """Names for what records keep as ids or codes, read once per file."""

    def __init__(self, db: Session):
        self.types = {t.code: t.name for t in db.scalars(select(CustomerType))}
        self.products = {p.code: p.name for p in db.scalars(select(Product))}
        self.people = {u.id: u for u in db.scalars(select(User))}
        self._names: dict[str, str] | None = None
        self.db = db

    def customer_name(self, company_id: str) -> str:
        if self._names is None:
            self._names = dict(self.db.execute(select(Company.id, Company.name)).all())
        return self._names.get(company_id, "")


def written(field: FormField, value: Any, look: Lookups) -> str:
    """An added field's value as a person reads it."""
    if value is None or value == "" or value == []:
        return ""
    if field.type == "yes_no":
        return "Yes" if value else "No"
    if field.type == "products":
        return ", ".join(look.products.get(c, c) for c in value)
    if field.type == "customer":
        return look.customer_name(str(value))
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def headers(db: Session) -> list[str]:
    return [label for _, label, _ in BUILT_IN] + ["Team", "Added on"] + [f.label for f in added_fields(db)]


def row_of(company: Company, fields: list[FormField], look: Lookups) -> list[str]:
    out = []
    for key, _, attr in BUILT_IN:
        value = getattr(company, attr)
        if key == "status":
            value = look.types.get(value, value)
        elif key == "owner":
            person = look.people.get(value)
            value = person.email if person else ""
        out.append("" if value is None else str(value))
    out.append(company.team.name if company.team else "")
    out.append(company.created_at.date().isoformat() if company.created_at else "")
    extra = company.extra or {}
    out.extend(written(f, extra.get(f.key), look) for f in fields)
    return out


def contact_rows(db: Session, access: Access, company_ids: set[str], unlinked: bool) -> list[list[str]]:
    """The contacts of these customers (their own, or linked to them, e.g. "works
    at"), one row per customer they're with; and, when `unlinked`, the contacts
    with no customer at all."""
    contacts = db.scalars(within(select(Contact), Contact, access).order_by(Contact.first_name, Contact.last_name)).unique().all()
    codes = dict(db.execute(select(Company.id, Company.code)).all())
    names = dict(db.execute(select(Company.id, Company.name)).all())
    linked: dict[str, set[str]] = {}
    for a in db.scalars(select(Association).where(Association.from_type != Association.to_type)):
        if {a.from_type, a.to_type} == {"contact", "company"}:
            person, firm = (a.from_id, a.to_id) if a.from_type == "contact" else (a.to_id, a.from_id)
            linked.setdefault(person, set()).add(firm)
    rows = []
    for c in contacts:
        firms = ({c.company_id} if c.company_id else set()) | linked.get(c.id, set())
        mine = sorted((f for f in firms if f in company_ids), key=lambda f: names.get(f, "").lower())
        for f in mine or ([None] if unlinked and not firms else []):
            rows.append([(codes.get(f) or "") if f else "", names.get(f, "") if f else "", c.full_name, c.job_title or "", c.email or "", c.phone or "", c.mobile or ""])
    return rows


CONTACT_HEADERS = ["Customer code", "Customer", "Contact", "Job title", "Email", "Phone", "Mobile"]


# --- reading ---------------------------------------------------------------------------------


def why(error: HTTPException) -> str:
    """A field error from the API's own checks, as one line for the row it's on."""
    detail = error.detail
    if isinstance(detail, list):
        return "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail)


class Readers:
    """How each column's text becomes what's kept, read once per file."""

    def __init__(self, db: Session, access: Access):
        self.db = db
        self.types = {}
        for t in db.scalars(select(CustomerType)):
            self.types[normal(t.code)] = t.code
            self.types[normal(t.name)] = t.code
        self.people: dict[str, str] = {}
        for u in db.scalars(select(User)):
            for name in (u.email, u.employee_id, u.full_name):
                if name:
                    self.people.setdefault(normal(name), u.id)
        self.by_code = {normal(c.code): c for c in db.scalars(select(Company).where(Company.code.is_not(None)))}
        self._by_name: dict[str, list[Company]] | None = None
        self.access = access

    def customer(self, text: str) -> str:
        """A customer named in a cell (by code or name), for a field that links to one."""
        found = self.by_code.get(normal(text))
        if found:
            return found.id
        if self._by_name is None:
            self._by_name = {}
            for c in self.db.scalars(select(Company)):
                self._by_name.setdefault(normal(c.name), []).append(c)
        hits = self._by_name.get(normal(text), [])
        if not hits:
            raise ValueError(f"no customer called {text}")
        if len(hits) > 1:
            raise ValueError(f"{len(hits)} customers are called {text}; use the customer code")
        return hits[0].id

    def value(self, field: FormField, text: str) -> Any:
        """A cell for an added field, as check_extra takes it."""
        if field.type == "yes_no":
            t = normal(text)
            if t in ("yes", "y", "true", "1"):
                return True
            if t in ("no", "n", "false", "0"):
                return False
            raise ValueError("write Yes or No")
        if field.type in ("choice", "multi_choice"):
            names = {normal(o): o for o in field.options}
            names.update({normal(full): code for code, full in (field.option_names or {}).items()})
            parts = [p.strip() for p in text.split(",")] if field.type == "multi_choice" else [text]
            picked = []
            for p in parts:
                if normal(p) not in names:
                    raise ValueError(f"{p} isn't one of the options")
                picked.append(names[normal(p)])
            return picked if field.type == "multi_choice" else picked[0]
        if field.type == "products":
            offered = offered_products(self.db, field)
            names = {normal(p.code): p.code for p in offered} | {normal(p.name): p.code for p in offered}
            picked = []
            for p in (x.strip() for x in text.split(",")):
                if p and normal(p) not in names:
                    raise ValueError(f"{p} isn't one of our products")
                if p:
                    picked.append(names[normal(p)])
            return picked
        if field.type == "customer":
            return self.customer(text)
        if field.type == "date":
            return text[:10]
        return text

    def type_of(self, text: str) -> str:
        code = self.types.get(normal(text))
        if code is None:
            raise ValueError(f"there's no customer type called {text}")
        return code

    def owner(self, text: str) -> str:
        found = self.people.get(normal(text))
        if found is None:
            raise ValueError(f"nobody here is {text} (use their email or employee ID)")
        return found


def import_customers(db: Session, access: Access, me: User, body, get) -> tuple[int, int, list[dict]]:
    """Each row: a customer to add, or one to update (its customer code is on
    the row). Every value goes through the same checks as the customer form."""
    read = Readers(db, access)
    fields = {f.key: f for f in added_fields(db)}
    mapped = lambda key: body.mapping.get(key) is not None  # noqa: E731
    seen: set[str] = set()
    made = changed = 0
    problems: list[dict] = []
    for n, row in enumerate(body.rows, start=2):
        if not any(c.strip() for c in row):
            continue
        v = lambda key: get(row, key)  # noqa: E731
        try:
            code = v("code")
            company = None
            if code:
                company = read.by_code.get(normal(code))
                if company is None:
                    raise ValueError(f"No customer has the code {code}. Leave the code empty to add them as new.")
                if not reaches(company, access) or not access.can("customers.edit"):
                    raise ValueError(f"{code} isn't one of the customers you can change.")
                if company.id in seen:
                    raise ValueError(f"{code} is on another row of this file too.")
            elif not v("name"):
                raise ValueError("No name.")
            elif not access.can("customers.create"):
                raise ValueError("You can update customers, not add them: give each row its customer code.")

            owner_id = read.owner(v("owner")) if v("owner") else (company.owner_id if company else None)
            owner = owner_for(db, access, owner_id)
            kind = read.type_of(v("status")) if v("status") else (company.status if company else first_type(db, team_id=owner.team_id))
            if not company or kind != company.status or owner.team_id != company.team_id:
                kind = check_type(db, kind, team_id=owner.team_id)
            texts: dict[str, str | None] = {}
            for key, label, attr in BUILT_IN:
                if key in ("code", "status", "owner") or not mapped(key):
                    continue
                text = v(key)
                if key == "name" and not text:
                    continue  # an update that leaves the name as it is
                texts[attr] = text or None
            if texts.get("email"):
                texts["email"] = check_email(texts["email"])
            if texts.get("website") and (" " in texts["website"] or "." not in texts["website"]):
                raise ValueError(f"{texts['website']}: enter a web address like example.com.")
            if texts.get("lead_source"):
                check_source(db, texts["lead_source"])
            for attr, limit in (("name", 160), ("industry", 80), ("lead_source", 60), ("website", 200), ("phone", 40), ("address", 300), ("city", 80), ("country", 80), ("notes", 5000)):
                if texts.get(attr) and len(texts[attr]) > limit:
                    raise ValueError(f"{attr.replace('_', ' ').capitalize()}: at most {limit} characters.")
            sent: dict[str, Any] = {}
            for key in body.mapping:
                field = fields.get(key.removeprefix("extra:")) if key.startswith("extra:") else None
                if field is None or not mapped(key) or not v(key):
                    continue
                try:
                    sent[field.key] = read.value(field, v(key))
                except ValueError as e:
                    raise ValueError(f"{field.label}: {e}.") from None
            # Fields not on this team's or type's form are left out, not refused:
            # one file can hold every division's customers.
            sent = {k: x for k, x in sent.items() if applies(fields[k], owner.team_id, kind)}
            extra = check_extra(db, "company", sent, company.extra if company else None, team_id=owner.team_id, kind=kind, record_id=company.id if company else None)
            if company is None:
                company = Company(name=texts.pop("name"), status=kind, owner_id=owner.id, team_id=owner.team_id, created_by_id=me.id, extra=extra)
                for attr, value in texts.items():
                    setattr(company, attr, value)
                check_required(db, "company", company, team_id=owner.team_id, kind=kind)
                db.add(company)
                made += 1
            else:
                before = {attr: getattr(company, attr) for attr in ("status", "owner_id", "team_id", "extra", *texts)}
                for attr, value in texts.items():
                    setattr(company, attr, value)
                company.status, company.owner_id, company.team_id, company.extra = kind, owner.id, owner.team_id, extra
                try:
                    check_required(db, "company", company, team_id=owner.team_id, kind=kind)
                except HTTPException:
                    for attr, value in before.items():
                        setattr(company, attr, value)
                    raise
                seen.add(company.id)
                changed += 1
            db.flush()
        except HTTPException as e:
            problems.append({"row": n, "message": why(e)})
        except ValueError as e:
            message = str(e)
            problems.append({"row": n, "message": message[:1].upper() + message[1:]})
    return made, changed, problems
