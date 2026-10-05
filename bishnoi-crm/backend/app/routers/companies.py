"""Companies: the organisations the CRM works with.

Seeing them needs customers.view; adding, changing and deleting need
customers.create / edit / delete. All of it only within the person's reach
(app/scope.py).
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, camel, changed, check_email, digits, field_error, iso, not_found, person_out, team_out
from app.audit import audit
from app.deps import DB, CurrentUser
from app.extra import check_extra, check_required, fields_for
from app.access import permissions_of
from app.models import Activity, ActivityLink, Company, Contact, Deal, FormField, PriceGroup, User
from app.routers.activities import activity_out
from app.routers.customer_types import check_type, first_type
from app.routers.deals import check_source
from app.scope import owner_for, reaches, within

router = APIRouter(prefix="/companies", tags=["companies"])

View = Annotated[Access, Depends(require("customers.view"))]
Create = Annotated[Access, Depends(require("customers.create"))]
Edit = Annotated[Access, Depends(require("customers.edit"))]
Delete = Annotated[Access, Depends(require("customers.delete"))]



class CompanyFields(Api):
    status: str | None = Field(None, max_length=40)
    # The price group whose prices it gets (Settings → Price rules). A null: none.
    price_group_code: str | None = Field(None, max_length=40)
    industry: str | None = Field(None, max_length=80)
    lead_source: str | None = Field(None, max_length=60)
    website: str | None = Field(None, max_length=200)
    email: str | None = Field(None, max_length=254)
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=300)
    city: str | None = Field(None, max_length=80)
    country: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=5000)
    owner_id: str | None = Field(None, max_length=36)
    # Added fields' values, by key (Settings → Forms). A null clears one.
    extra: dict[str, Any] | None = None

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
    # Was "add it even though it looks like one already here". Customers are no
    # longer refused for that (one hospital can be a customer of several
    # divisions); still taken, so older screens keep working.
    allow_duplicate: bool = False


class CompanyPatch(CompanyFields):
    name: str | None = Field(None, min_length=1, max_length=160)


def check_price_group(db: Session, code: str | None) -> None:
    """A price group that's switched on (a customer already in a switched-off one stays)."""
    if code is None:
        return
    group = db.get(PriceGroup, code)
    if group is None or not group.is_active:
        raise field_error("priceGroupCode", "Pick a price group from the list.")


def can_of(company: Company, access: Access) -> dict:
    inside = reaches(company, access)
    return {"edit": inside and access.can("customers.edit"), "delete": inside and access.can("customers.delete")}


def company_row(company: Company, access: Access, contacts: int = 0, last_activity=None) -> dict:
    return {
        "id": company.id,
        "code": company.code,
        "name": company.name,
        "status": company.status,
        "priceGroupCode": company.price_group_code,
        "industry": company.industry,
        "leadSource": company.lead_source,
        "website": company.website,
        "email": company.email,
        "phone": company.phone,
        "city": company.city,
        "country": company.country,
        "owner": person_out(company.owner),
        "team": team_out(company.team),
        "contactCount": contacts,
        "lastActivityAt": iso(last_activity),
        "extra": company.extra or {},
        "updatedAt": iso(company.updated_at),
        "can": can_of(company, access),
    }


def get_company(db: Session, access: Access, company_id: str) -> Company:
    company = db.get(Company, company_id)
    if company is None or not reaches(company, access):
        raise not_found("customer")
    return company


@router.get("")
def list_companies(
    access: View,
    db: DB,
    q: str | None = Query(None, max_length=100),
    status_: str | None = Query(None, alias="status", max_length=40),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    sort: Literal["name", "updated"] = "name",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Company), Company, access)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Company.name).like(like),
                func.lower(Company.code).like(like),
                func.lower(Company.city).like(like),
                func.lower(Company.industry).like(like),
            )
        )
    if status_:
        query = query.where(Company.status == status_)
    if owner:
        query = query.where(Company.owner_id == (access.user_id if owner == "me" else owner))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (func.lower(Company.name),) if sort == "name" else (Company.updated_at.desc(),)
    companies = db.scalars(query.order_by(*order).limit(limit).offset(offset)).unique().all()
    ids = [c.id for c in companies]
    contacts = dict(db.execute(select(Contact.company_id, func.count()).where(Contact.company_id.in_(ids)).group_by(Contact.company_id)).all())
    last = dict(db.execute(select(Activity.company_id, func.max(Activity.done_at)).where(Activity.company_id.in_(ids), Activity.done_at.is_not(None)).group_by(Activity.company_id)).all())
    return {
        "items": [company_row(c, access, contacts.get(c.id, 0), last.get(c.id)) for c in companies],
        "total": total,
    }


@router.get("/link-options")
def link_options(access: View, db: DB, field: str = Query(max_length=40), q: str = Query("", max_length=100)) -> list[dict]:
    """Customers a customer field can point at (a doctor's hospital), by name.
    Any division's: like the look-alikes, it says what exists, not its details."""
    found = customer_fields(db).get(field)
    if found is None:
        raise not_found("field")
    query = select(Company).order_by(func.lower(Company.name)).limit(10)
    if found.options:
        query = query.where(Company.status.in_(found.options))
    if q.strip():
        query = query.where(func.lower(Company.name).like(f"%{q.strip().lower()}%"))
    return [{"id": c.id, "name": c.name, "teamName": c.team.name if c.team else None} for c in db.scalars(query).unique()]


@router.get("/lookalikes")
def find_lookalikes(
    access: View,
    db: DB,
    name: str = Query("", max_length=160),
    phone: str = Query("", max_length=40),
    email: str = Query("", max_length=254),
) -> list[dict]:
    """While a new customer is typed in: who may already be here. Customers in
    reach match on part of the name; others only on the same name, email or
    phone (so nobody adds one twice, without anyone browsing who's whose)."""
    name, wanted = name.strip(), digits(phone)
    found: dict[str, Company] = {}
    if len(name) >= 3:
        like = f"%{name.lower()}%"
        for c in db.scalars(within(select(Company), Company, access).where(func.lower(Company.name).like(like)).order_by(func.lower(Company.name)).limit(6)).unique():
            found[c.id] = c
    checks = []
    if name:
        checks.append(func.lower(Company.name) == name.lower())
    if email.strip():
        checks.append(func.lower(Company.email) == email.strip().lower())
    if checks:
        for c in db.scalars(select(Company).where(or_(*checks)).limit(6)).unique():
            found.setdefault(c.id, c)
    if wanted and len(wanted) >= 7:
        for c in db.scalars(select(Company).where(Company.phone.is_not(None))).unique():
            if digits(c.phone) == wanted:
                found.setdefault(c.id, c)
    return [
        {
            "id": c.id,
            "name": c.name,
            "teamName": c.team.name if c.team else None,
            "city": c.city if reaches(c, access) else None,
            "owner": c.owner.full_name if reaches(c, access) else None,
            "canOpen": reaches(c, access),
        }
        for c in list(found.values())[:6]
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_company(access: Create, me: CurrentUser, db: DB, body: CompanyIn) -> dict:
    owner = owner_for(db, access, body.owner_id)
    values = body.model_dump(exclude={"owner_id", "allow_duplicate"}, exclude_none=True)
    values["status"] = check_type(db, body.status, team_id=owner.team_id) if body.status else first_type(db, team_id=owner.team_id)
    check_price_group(db, body.price_group_code)
    check_source(db, body.lead_source)
    values["extra"] = check_extra(db, "company", body.extra, team_id=owner.team_id, kind=values["status"])
    company = Company(**values, owner_id=owner.id, team_id=owner.team_id, created_by_id=me.id)
    check_required(db, "company", company, team_id=owner.team_id, kind=company.status)
    db.add(company)
    db.flush()
    audit(db, me, "company.created", target=company.name, target_type="company", target_id=company.id)
    db.commit()
    db.refresh(company)
    return company_detail(db, access, company)


def customer_fields(db: Session) -> dict[str, FormField]:
    """The customer form's fields that point at another customer, by key."""
    return {f.key: f for f in fields_for(db, "company", added_only=True) if f.type == "customer"}


def links_of(db: Session, access: Access, company: Company) -> dict:
    """The customers this one points at (its doctor's hospital), by field: name, and whether one may open it."""
    out = {}
    for key in customer_fields(db):
        target = db.get(Company, str((company.extra or {}).get(key) or "")) or None
        if target is not None:
            out[key] = {"id": target.id, "name": target.name, "teamName": target.team.name if target.team else None, "canOpen": reaches(target, access)}
    return out


def linked_here(db: Session, access: Access, company: Company) -> list[dict]:
    """The customers in reach that point at this one: the doctors at a hospital."""
    keys = customer_fields(db)
    if not keys:
        return []
    found = []
    for other in db.scalars(within(select(Company), Company, access).where(Company.id != company.id).order_by(func.lower(Company.name))).unique():
        for key, field in keys.items():
            if (other.extra or {}).get(key) == company.id:
                found.append({"id": other.id, "name": other.name, "status": other.status, "field": field.label})
                break
    return found


def company_detail(db: Session, access: Access, company: Company) -> dict:
    contacts = db.scalars(within(select(Contact), Contact, access).where(Contact.company_id == company.id).order_by(func.lower(Contact.first_name))).unique().all()
    activities = db.scalars(
        within(select(Activity), Activity, access)
        .where(or_(Activity.company_id == company.id, Activity.id.in_(select(ActivityLink.activity_id).where(ActivityLink.company_id == company.id))))
        .order_by(Activity.at.desc())
        .limit(100)
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
        "links": links_of(db, access, company),
        "linkedHere": linked_here(db, access, company),
    }


@router.get("/{company_id}")
def read_company(access: View, db: DB, company_id: str) -> dict:
    return company_detail(db, access, get_company(db, access, company_id))


@router.patch("/{company_id}")
def update_company(access: Edit, me: CurrentUser, db: DB, company_id: str, body: CompanyPatch) -> dict:
    company = get_company(db, access, company_id)
    wanted = changed(body)
    if "name" in wanted and wanted["name"] is None:
        raise field_error("name", "Give the customer a name.")
    if "status" in wanted and wanted["status"] is None:
        raise field_error("status", "Pick a type.")
    # The team it will be in decides its form: a new owner may bring a new one.
    team_id = company.team_id
    if "owner_id" in wanted:
        owner = owner_for(db, access, wanted.pop("owner_id"))
        if owner.id != company.owner_id:
            wanted["owner_id"], wanted["team_id"] = owner.id, owner.team_id
            team_id = owner.team_id
    if wanted.get("status") and wanted["status"] != company.status:
        check_type(db, wanted["status"], team_id=team_id)
    if wanted.get("price_group_code") and wanted["price_group_code"] != company.price_group_code:
        check_price_group(db, wanted["price_group_code"])
    if wanted.get("lead_source") and wanted["lead_source"] != company.lead_source:
        check_source(db, wanted["lead_source"])
    if "extra" in wanted:
        wanted["extra"] = check_extra(
            db, "company", wanted["extra"], company.extra, team_id=team_id, kind=wanted.get("status") or company.status, record_id=company.id
        )
    fields = [k for k, v in wanted.items() if getattr(company, k) != v]
    for key in fields:
        setattr(company, key, wanted[key])
    check_required(db, "company", company, team_id=team_id, kind=company.status)
    if fields:
        audit(db, me, "company.updated", target=company.name, target_type="company", target_id=company.id, fields=camel([f for f in fields if f != "team_id"]))
        db.commit()
        db.refresh(company)  # its owner and team may be new
    return company_detail(db, access, company)


# --- handing a customer to someone else ---


class TransferIn(Api):
    employee_id: str = Field(min_length=1, max_length=20)


def transfer_target(db: Session, company: Company, employee_id: str) -> User:
    """Who an employee ID names, if a customer can go to them: someone switched
    on whose role works with customers. Typed, not picked, so it's deliberate."""
    code = employee_id.strip().upper()
    person = db.scalar(select(User).where(User.employee_id == code)) if code else None
    if person is None or not person.is_active:
        raise field_error("employeeId", "Nobody here has that employee ID. Check it with them or your administrator.")
    if "customers.view" not in permissions_of(person.role):
        raise field_error("employeeId", f"{person.full_name}'s role doesn't work with customers.")
    if person.id == company.owner_id:
        raise field_error("employeeId", f"This customer is already {person.full_name}'s.")
    return person


def person_card(person: User) -> dict:
    return {**person_out(person), "employeeId": person.employee_id, "role": person.role.name, "team": team_out(person.team)}


@router.get("/{company_id}/transfer")
def check_transfer(access: Edit, db: DB, company_id: str, employee_id: str = Query(alias="employeeId", min_length=1, max_length=20)) -> dict:
    """Who the customer would go to, to show before it does."""
    company = get_company(db, access, company_id)
    return person_card(transfer_target(db, company, employee_id))


@router.post("/{company_id}/transfer")
def transfer_company(access: Edit, me: CurrentUser, db: DB, company_id: str, body: TransferIn) -> dict:
    """Hands the customer to the person with that employee ID, with what the
    previous owner was working on there: its contacts and open deals. Quotes
    and the history stay as they were."""
    company = get_company(db, access, company_id)
    person = transfer_target(db, company, body.employee_id)
    before = company.owner_id
    moved = {"contacts": 0, "deals": 0}
    for model, key, extra in ((Contact, "contacts", ()), (Deal, "deals", (Deal.closed_at.is_(None),))):
        for record in db.scalars(select(model).where(model.company_id == company.id, model.owner_id == before, *extra)).unique():
            record.owner_id, record.team_id = person.id, person.team_id
            moved[key] += 1
    company.owner_id, company.team_id = person.id, person.team_id
    audit(db, me, "company.transferred", target=f"{company.name} to {person.full_name} ({person.employee_id})", target_type="company", target_id=company.id, fields=["ownerId"])
    db.commit()
    db.refresh(company)
    return {"to": person_card(person), "moved": moved, "stillYours": reaches(company, access)}


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(access: Delete, me: CurrentUser, db: DB, company_id: str) -> Response:
    company = get_company(db, access, company_id)
    contacts = db.scalar(select(func.count()).select_from(Contact).where(Contact.company_id == company.id)) or 0
    if contacts:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{contacts} {'contact is' if contacts == 1 else 'contacts are'} with this customer. Move or delete them first.",
        )
    audit(db, me, "company.deleted", target=company.name, target_type="company", target_id=company.id)
    db.delete(company)  # its activities go with it
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

