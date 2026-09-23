"""Contacts: the people Sales talks to, usually in a company.

Same permissions as companies (customers.view / create / edit / delete), within
the person's reach. A contact can be put only in a company within reach.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, camel, changed, check_email, digits, duplicates_error, field_error, iso, not_found, person_out, team_out
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Activity, Company, Contact
from app.routers.activities import activity_out
from app.scope import owner_for, reaches, within

router = APIRouter(prefix="/contacts", tags=["contacts"])

View = Annotated[Access, Depends(require("customers.view"))]
Create = Annotated[Access, Depends(require("customers.create"))]
Edit = Annotated[Access, Depends(require("customers.edit"))]
Delete = Annotated[Access, Depends(require("customers.delete"))]


class ContactFields(Api):
    last_name: str | None = Field(None, max_length=80)
    job_title: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    mobile: str | None = Field(None, max_length=40)
    notes: str | None = Field(None, max_length=5000)
    company_id: str | None = Field(None, max_length=36)
    owner_id: str | None = Field(None, max_length=36)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)


class ContactIn(ContactFields):
    first_name: str = Field(min_length=1, max_length=80)
    # Add them even though they look like someone already here.
    allow_duplicate: bool = False


class ContactPatch(ContactFields):
    first_name: str | None = Field(None, min_length=1, max_length=80)


def contact_row(contact: Contact, access: Access, last_activity=None) -> dict:
    inside = reaches(contact, access)
    return {
        "id": contact.id,
        "firstName": contact.first_name,
        "lastName": contact.last_name,
        "name": contact.full_name,
        "jobTitle": contact.job_title,
        "email": contact.email,
        "phone": contact.phone,
        "mobile": contact.mobile,
        "company": {"id": contact.company.id, "name": contact.company.name} if contact.company else None,
        "owner": person_out(contact.owner),
        "team": team_out(contact.team),
        "lastActivityAt": iso(last_activity),
        "updatedAt": iso(contact.updated_at),
        "can": {"edit": inside and access.can("customers.edit"), "delete": inside and access.can("customers.delete")},
    }


def get_contact(db: Session, access: Access, contact_id: str) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None or not reaches(contact, access):
        raise not_found("contact")
    return contact


def company_in_reach(db: Session, access: Access, company_id: str | None) -> Company | None:
    if company_id is None:
        return None
    company = db.get(Company, company_id)
    if company is None or not reaches(company, access):
        raise field_error("companyId", "Pick a company you can see.")
    return company


def contact_detail(db: Session, access: Access, contact: Contact) -> dict:
    activities = db.scalars(
        within(select(Activity), Activity, access).where(Activity.contact_id == contact.id).order_by(Activity.at.desc()).limit(100)
    ).unique().all()
    return {
        **contact_row(contact, access),
        "notes": contact.notes,
        "createdAt": iso(contact.created_at),
        "activities": [activity_out(a, access) for a in activities],
    }


@router.get("")
def list_contacts(
    access: View,
    db: DB,
    q: str | None = Query(None, max_length=100),
    company: str | None = Query(None, max_length=36),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Contact), Contact, access).outerjoin(Company, Contact.company_id == Company.id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Contact.first_name).like(like),
                func.lower(Contact.last_name).like(like),
                func.lower(Contact.email).like(like),
                func.lower(Company.name).like(like),
            )
        )
    if company:
        query = query.where(Contact.company_id == company)
    if owner:
        query = query.where(Contact.owner_id == (access.user_id if owner == "me" else owner))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    contacts = db.scalars(query.order_by(func.lower(Contact.first_name), func.lower(Contact.last_name)).limit(limit).offset(offset)).unique().all()
    ids = [c.id for c in contacts]
    last = dict(
        db.execute(
            select(Activity.contact_id, func.max(Activity.done_at)).where(Activity.contact_id.in_(ids), Activity.done_at.is_not(None)).group_by(Activity.contact_id)
        ).all()
    )
    return {"items": [contact_row(c, access, last.get(c.id)) for c in contacts], "total": total}


def lookalikes(db: Session, access: Access, body: ContactIn) -> list[dict]:
    """People with the same email or phone, or the same name in the same company."""
    checks = []
    if body.email:
        checks.append(func.lower(Contact.email) == body.email.lower())
    same_name = func.lower(Contact.first_name) == body.first_name.lower()
    if body.last_name:
        same_name = same_name & (func.lower(Contact.last_name) == body.last_name.lower())
    checks.append(same_name & (Contact.company_id == body.company_id) if body.company_id else same_name & Contact.company_id.is_(None))
    found = list(db.scalars(select(Contact).where(or_(*checks)).limit(5)).unique())
    for phone in {digits(body.phone), digits(body.mobile)} - {None}:
        found += [c for c in db.scalars(select(Contact).where(or_(Contact.phone.is_not(None), Contact.mobile.is_not(None)))).unique()
                  if phone in (digits(c.phone), digits(c.mobile)) and c not in found][:5]
    return [
        {
            "id": c.id,
            "name": c.full_name,
            "teamName": c.team.name if c.team else None,
            "phone": (c.phone or c.mobile) if reaches(c, access) else None,
            "canOpen": reaches(c, access),
        }
        for c in found[:5]
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_contact(access: Create, me: CurrentUser, db: DB, body: ContactIn) -> dict:
    company_in_reach(db, access, body.company_id)
    if not body.allow_duplicate:
        found = lookalikes(db, access, body)
        if found:
            raise duplicates_error("contact", found)
    owner = owner_for(db, access, body.owner_id)
    values = body.model_dump(exclude={"owner_id", "allow_duplicate"}, exclude_none=True)
    contact = Contact(**values, owner_id=owner.id, team_id=owner.team_id, created_by_id=me.id)
    db.add(contact)
    db.flush()
    audit(db, me, "contact.created", target=contact.full_name, target_type="contact", target_id=contact.id)
    db.commit()
    db.refresh(contact)
    return contact_detail(db, access, contact)


@router.get("/{contact_id}")
def read_contact(access: View, db: DB, contact_id: str) -> dict:
    return contact_detail(db, access, get_contact(db, access, contact_id))


@router.patch("/{contact_id}")
def update_contact(access: Edit, me: CurrentUser, db: DB, contact_id: str, body: ContactPatch) -> dict:
    contact = get_contact(db, access, contact_id)
    wanted = changed(body)
    if "first_name" in wanted and wanted["first_name"] is None:
        raise field_error("firstName", "Give their first name.")
    if wanted.get("company_id"):
        company_in_reach(db, access, wanted["company_id"])
    if "owner_id" in wanted:
        owner = owner_for(db, access, wanted.pop("owner_id"))
        if owner.id != contact.owner_id:
            wanted["owner_id"], wanted["team_id"] = owner.id, owner.team_id
    fields = [k for k, v in wanted.items() if getattr(contact, k) != v]
    for key in fields:
        setattr(contact, key, wanted[key])
    if fields:
        audit(db, me, "contact.updated", target=contact.full_name, target_type="contact", target_id=contact.id, fields=camel([f for f in fields if f != "team_id"]))
        db.commit()
        db.refresh(contact)
    return contact_detail(db, access, contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(access: Delete, me: CurrentUser, db: DB, contact_id: str) -> Response:
    """Activities only about them go with them; those also about a company stay
    with the company."""
    contact = get_contact(db, access, contact_id)
    audit(db, me, "contact.deleted", target=contact.full_name, target_type="contact", target_id=contact.id)
    db.execute(delete(Activity).where(Activity.contact_id == contact.id, Activity.company_id.is_(None)))
    db.delete(contact)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
