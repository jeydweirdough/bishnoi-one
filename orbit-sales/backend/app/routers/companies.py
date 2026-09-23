"""Companies: the organisations Sales works with.

Seeing them needs customers.view; adding, changing and deleting need
customers.create / edit / delete. All of it only within the person's reach
(app/scope.py).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, camel, changed, check_email, field_error, iso, not_found, person_out, team_out
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import COMPANY_STATUSES, Activity, Company, Contact
from app.routers.activities import activity_out
from app.scope import owner_for, reaches, within

router = APIRouter(prefix="/companies", tags=["companies"])

View = Annotated[Access, Depends(require("customers.view"))]
Create = Annotated[Access, Depends(require("customers.create"))]
Edit = Annotated[Access, Depends(require("customers.edit"))]
Delete = Annotated[Access, Depends(require("customers.delete"))]

Status = Literal["prospect", "customer", "partner", "inactive"]


class CompanyFields(Api):
    status: Status | None = None
    industry: str | None = Field(None, max_length=80)
    website: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=80)
    country: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=5000)
    owner_id: str | None = Field(None, max_length=36)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)

    @field_validator("website")
    @classmethod
    def _website(cls, value: str | None) -> str | None:
        if value is not None and (" " in value or "." not in value):
            raise ValueError("Enter a web address like example.com.")
        return value


class CompanyIn(CompanyFields):
    name: str = Field(min_length=1, max_length=160)


class CompanyPatch(CompanyFields):
    name: str | None = Field(None, min_length=1, max_length=160)


def can_of(company: Company, access: Access) -> dict:
    inside = reaches(company, access)
    return {"edit": inside and access.can("customers.edit"), "delete": inside and access.can("customers.delete")}


def company_row(company: Company, access: Access, contacts: int = 0, last_activity=None) -> dict:
    return {
        "id": company.id,
        "name": company.name,
        "status": company.status,
        "industry": company.industry,
        "website": company.website,
        "email": company.email,
        "phone": company.phone,
        "city": company.city,
        "country": company.country,
        "owner": person_out(company.owner),
        "team": team_out(company.team),
        "contactCount": contacts,
        "lastActivityAt": iso(last_activity),
        "updatedAt": iso(company.updated_at),
        "can": can_of(company, access),
    }


def get_company(db: Session, access: Access, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None or not reaches(company, access):
        raise not_found("company")
    return company


@router.get("")
def list_companies(
    access: View,
    db: DB,
    q: str | None = Query(None, max_length=100),
    status_: Status | None = Query(None, alias="status"),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    sort: Literal["name", "updated"] = "name",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Company), Company, access)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Company.name).like(like), func.lower(Company.city).like(like), func.lower(Company.industry).like(like)))
    if status_:
        query = query.where(Company.status == status_)
    if owner:
        query = query.where(Company.owner_id == (access.user_id if owner == "me" else owner))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (func.lower(Company.name),) if sort == "name" else (Company.updated_at.desc(),)
    companies = db.scalars(query.order_by(*order).limit(limit).offset(offset)).unique().all()
    ids = [c.id for c in companies]
    contacts = dict(db.execute(select(Contact.company_id, func.count()).where(Contact.company_id.in_(ids)).group_by(Contact.company_id)).all())
    last = dict(db.execute(select(Activity.company_id, func.max(Activity.at)).where(Activity.company_id.in_(ids), Activity.done_at.is_not(None)).group_by(Activity.company_id)).all())
    return {
        "items": [company_row(c, access, contacts.get(c.id, 0), last.get(c.id)) for c in companies],
        "total": total,
        "statuses": list(COMPANY_STATUSES),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(access: Create, me: CurrentUser, db: DB, body: CompanyIn) -> dict:
    owner = owner_for(db, access, body.owner_id)
    values = body.model_dump(exclude={"owner_id"}, exclude_none=True)
    company = Company(**values, owner_id=owner.id, team_id=owner.team_id, created_by_id=me.id)
    db.add(company)
    db.flush()
    audit(db, me, "company.created", target=company.name, target_type="company", target_id=company.id)
    db.commit()
    db.refresh(company)
    return company_detail(db, access, company)


def company_detail(db: Session, access: Access, company: Company) -> dict:
    contacts = db.scalars(within(select(Contact), Contact, access).where(Contact.company_id == company.id).order_by(func.lower(Contact.first_name))).unique().all()
    activities = db.scalars(
        within(select(Activity), Activity, access).where(Activity.company_id == company.id).order_by(Activity.at.desc()).limit(100)
    ).unique().all()
    all_contacts = db.scalar(select(func.count()).select_from(Contact).where(Contact.company_id == company.id)) or 0
    return {
        **company_row(company, access, all_contacts),
        "address": company.address,
        "notes": company.notes,
        "createdAt": iso(company.created_at),
        "contacts": [
            {"id": c.id, "name": c.full_name, "jobTitle": c.job_title, "email": c.email, "phone": c.phone or c.mobile}
            for c in contacts
        ],
        "activities": [activity_out(a, access) for a in activities],
    }


@router.get("/{company_id}")
def read_company(access: View, db: DB, company_id: str) -> dict:
    return company_detail(db, access, get_company(db, access, company_id))


@router.patch("/{company_id}")
def update_company(access: Edit, me: CurrentUser, db: DB, company_id: str, body: CompanyPatch) -> dict:
    company = get_company(db, access, company_id)
    wanted = changed(body)
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the company a name.")
    if "status" in wanted and wanted["status"] is None:
        raise field_error("status", "Pick a status.")
    if "owner_id" in wanted:
        owner = owner_for(db, access, wanted.pop("owner_id"))
        if owner.id != company.owner_id:
            wanted["owner_id"], wanted["team_id"] = owner.id, owner.team_id
    fields = [k for k, v in wanted.items() if getattr(company, k) != v]
    for key in fields:
        setattr(company, key, wanted[key])
    if fields:
        audit(db, me, "company.updated", target=company.name, target_type="company", target_id=company.id, fields=camel([f for f in fields if f != "team_id"]))
        db.commit()
        db.refresh(company)  # its owner and team may be new
    return company_detail(db, access, company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(access: Delete, me: CurrentUser, db: DB, company_id: str) -> Response:
    company = get_company(db, access, company_id)
    contacts = db.scalar(select(func.count()).select_from(Contact).where(Contact.company_id == company.id)) or 0
    if contacts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{contacts} {'contact is' if contacts == 1 else 'contacts are'} in this company. Move or delete them first.",
        )
    audit(db, me, "company.deleted", target=company.name, target_type="company", target_id=company.id)
    db.delete(company)  # its activities go with it
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

