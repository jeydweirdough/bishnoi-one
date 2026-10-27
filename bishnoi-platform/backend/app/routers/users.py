"""Users: the people at the companies, one account each, and which
applications each one may use, with their role in each.

This is the platform's identity, not any application's record: the CRM's
salesperson and the Pharmacy's pharmacist are the same person here. Access
never goes past the company's: someone can only be given an application their
company has (Organizations), and loses it when their company does.
"""

import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api import Api, camel, changed, check_email, conflict, field_error, iso, not_found
from app.audit import audit
from app import passwords
from app.deps import DB, AdminUser, CurrentUser
from app.models import (
    TICKET_STATUSES,
    AccessRequest,
    Application,
    AuditEntry,
    Company,
    CompanyApp,
    Identity,
    IdentityApp,
    Ticket,
)

router = APIRouter(prefix="/platform/users", tags=["users"])

OPEN = [s for s in TICKET_STATUSES if s not in ("resolved", "closed")]


class Grant(Api):
    application_id: str
    role: str | None = Field(None, max_length=60)
    is_app_admin: bool = False


class UserIn(Api):
    company_id: str
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254)
    title: str | None = Field(None, max_length=120)
    is_company_admin: bool = False
    applications: list[Grant] = []

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)


class UserPatch(Api):
    company_id: str | None = None
    full_name: str | None = Field(None, min_length=2, max_length=120)
    email: str | None = Field(None, max_length=254)
    title: str | None = Field(None, max_length=120)
    is_company_admin: bool | None = None
    status: Literal["active", "suspended"] | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)


class GrantIn(Api):
    role: str | None = Field(None, max_length=60)
    is_app_admin: bool = False


def user_out(p: Identity, company: Company | None = None, **extra) -> dict:
    return {
        "id": p.id,
        "no": p.no,
        "fullName": p.full_name,
        "email": p.email,
        "title": p.title,
        "isCompanyAdmin": p.is_company_admin,
        "status": p.status,
        "companyId": p.company_id,
        "companyName": company.name if company else None,
        # A suspended company's people can't work, whatever their own status.
        "companyStatus": company.status if company else None,
        "createdAt": iso(p.created_at),
        "lastActiveAt": iso(p.last_active_at),
        # Can sign in to their Bishnoi One account (a first password has been set).
        "hasPassword": bool(p.password_hash),
        **extra,
    }


def grant_out(g: IdentityApp, app: Application) -> dict:
    return {
        "applicationId": app.id,
        "key": app.key,
        "name": app.name,
        "role": g.role,
        "isAppAdmin": g.is_app_admin,
        "grantedAt": iso(g.granted_at),
        "grantedBy": g.granted_by,
    }


def _person(db: Session, user_id: str) -> Identity:
    p = db.get(Identity, user_id)
    if p is None:
        raise not_found("user")
    return p


def _company_apps(db: Session, company_id: str) -> set[str]:
    return set(db.scalars(select(CompanyApp.application_id).where(CompanyApp.company_id == company_id)))


def _email_taken(db: Session, email: str, company_id: str, other_than: str | None = None) -> bool:
    """Somebody at this company has it. At another company it's the same person,
    who may work for both (models.Identity)."""
    query = select(Identity.id).where(func.lower(Identity.email) == email, Identity.company_id == company_id)
    if other_than:
        query = query.where(Identity.id != other_than)
    return db.scalar(query) is not None


def without_password():
    """Active, and never given a password, so they can't sign in yet."""
    return (Identity.status == "active") & Identity.password_hash.is_(None)


@router.get("")
def list_users(
    db: DB,
    _: CurrentUser,
    q: str | None = None,
    company_id: str | None = None,
    application_id: str | None = None,
    status: str | None = None,
    admins: bool = False,
    password: str | None = Query(None, description="none: only people who can't sign in yet"),
) -> dict:
    query = select(Identity, Company).join(Company, Company.id == Identity.company_id).order_by(func.lower(Identity.full_name))
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Identity.full_name).like(like), func.lower(Identity.email).like(like)))
    if company_id:
        query = query.where(Identity.company_id == company_id)
    if application_id:
        query = query.where(Identity.id.in_(select(IdentityApp.identity_id).where(IdentityApp.application_id == application_id)))
    if status in ("active", "suspended"):
        query = query.where(Identity.status == status)
    if admins:
        query = query.where(Identity.is_company_admin)
    if password == "none":
        query = query.where(without_password())
    rows = db.execute(query.limit(500)).all()
    grants: dict[str, list[dict]] = {}
    for g, a in db.execute(
        select(IdentityApp, Application).join(Application).where(IdentityApp.identity_id.in_([p.id for p, _ in rows])).order_by(Application.sort_order)
    ):
        grants.setdefault(g.identity_id, []).append({"applicationId": a.id, "key": a.key, "name": a.name, "role": g.role})
    # How many match, whether or not all of them fit in this answer.
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {"users": [user_out(p, c, applications=grants.get(p.id, [])) for p, c in rows], "total": total}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_user(body: UserIn, db: DB, me: AdminUser) -> dict:
    company = db.get(Company, body.company_id)
    if company is None:
        raise field_error("companyId", "Pick the company they work for.")
    if _email_taken(db, body.email, company.id):
        raise field_error("email", f"Somebody at {company.name} already has that email.")
    allowed = _company_apps(db, company.id)
    for g in body.applications:
        if g.application_id not in allowed:
            raise field_error("applications", f"{company.name} doesn't have one of those applications. Give it to the company first.")
    p = Identity(company_id=company.id, full_name=body.full_name, email=body.email, title=body.title, is_company_admin=body.is_company_admin)
    # Already at another company: the same person, with the password they have.
    elsewhere = db.scalar(select(Identity).where(func.lower(Identity.email) == body.email.lower(), Identity.password_hash.is_not(None)))
    if elsewhere is not None:
        p.password_hash, p.password_changed_at = elsewhere.password_hash, elsewhere.password_changed_at
    db.add(p)
    db.flush()
    for g in {g.application_id: g for g in body.applications}.values():
        db.add(IdentityApp(identity_id=p.id, application_id=g.application_id, role=g.role, is_app_admin=g.is_app_admin, granted_by=me.email))
    audit(db, me, "user.created", target=p.email, target_type="user", target_id=p.id, company_id=company.id)
    db.commit()
    return {"user": user_out(p, company)}


@router.get("/{user_id}")
def get_user(user_id: str, db: DB, _: CurrentUser) -> dict:
    p = _person(db, user_id)
    company = db.get(Company, p.company_id)
    grants = db.execute(
        select(IdentityApp, Application).join(Application).where(IdentityApp.identity_id == p.id).order_by(Application.sort_order)
    ).all()
    granted = {a.id for _, a in grants}
    available = db.scalars(
        select(Application).join(CompanyApp, CompanyApp.application_id == Application.id)
        .where(CompanyApp.company_id == p.company_id, Application.is_active).order_by(Application.sort_order)
    ).all()
    requests = db.execute(
        select(AccessRequest, Application.name).join(Application).where(AccessRequest.identity_id == p.id)
        .order_by(AccessRequest.created_at.desc()).limit(20)
    ).all()
    tickets = db.scalars(
        select(Ticket).where(or_(Ticket.identity_id == p.id, func.lower(Ticket.reporter_email) == p.email))
        .order_by(Ticket.created_at.desc()).limit(20)
    ).all()
    activity = db.scalars(select(AuditEntry).where(AuditEntry.target_id == p.id).order_by(AuditEntry.created_at.desc()).limit(30)).all()
    from app.routers.activity import entry_out

    return {
        "user": user_out(
            p,
            company,
            applications=[grant_out(g, a) for g, a in grants],
            canBeGiven=[{"id": a.id, "key": a.key, "name": a.name} for a in available if a.id not in granted],
            requests=[
                {"id": r.id, "applicationId": r.application_id, "applicationName": name, "role": r.role, "status": r.status, "createdAt": iso(r.created_at)}
                for r, name in requests
            ],
            tickets=[
                {"id": t.id, "number": t.number, "title": t.title, "kind": t.kind, "status": t.status, "createdAt": iso(t.created_at),
                 "isOpen": t.status in OPEN}
                for t in tickets
            ],
            activity=[entry_out(e) for e in activity],
        )
    }


@router.patch("/{user_id}")
def update_user(user_id: str, body: UserPatch, db: DB, me: AdminUser) -> dict:
    p = _person(db, user_id)
    fields = changed(body)
    for required in ("company_id", "full_name", "email", "is_company_admin", "status"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    fields = {k: v for k, v in fields.items() if getattr(p, k) != v}
    if ("email" in fields or "company_id" in fields) and _email_taken(db, fields.get("email", p.email), fields.get("company_id") or p.company_id, other_than=p.id):
        raise field_error("email", "Somebody at that company already has that email.")
    withdrawn = 0
    if "company_id" in fields:
        if db.get(Company, fields["company_id"]) is None:
            raise field_error("companyId", "That company doesn't exist.")
        # Moving companies keeps only the applications the new one has.
        keep = _company_apps(db, fields["company_id"])
        withdrawn = db.execute(
            delete(IdentityApp).where(IdentityApp.identity_id == p.id, IdentityApp.application_id.not_in(keep))
        ).rowcount
    for name, value in fields.items():
        setattr(p, name, value)
    if fields:
        action = {"suspended": "user.suspended", "active": "user.reactivated"}.get(fields.get("status"), "user.updated")
        audit(db, me, action, target=p.email, target_type="user", target_id=p.id, company_id=p.company_id, fields=camel(fields))
    db.commit()
    return {"user": user_out(p, db.get(Company, p.company_id)), "withdrawnApplications": withdrawn}


@router.put("/{user_id}/applications/{app_id}")
def grant_application(user_id: str, app_id: str, body: GrantIn, db: DB, me: AdminUser) -> dict:
    """Gives someone an application, or changes their role in it."""
    p = _person(db, user_id)
    app = db.get(Application, app_id)
    if app is None:
        raise not_found("application")
    if not app.is_active:
        raise field_error("applicationId", f"{app.name} is retired, so nobody can be given it.")
    if app_id not in _company_apps(db, p.company_id):
        raise field_error("applicationId", f"Their company doesn't have {app.name}. Give it to the company first.")
    g = db.get(IdentityApp, (p.id, app.id))
    if g is None:
        g = IdentityApp(identity_id=p.id, application_id=app.id, role=body.role, is_app_admin=body.is_app_admin, granted_by=me.email)
        db.add(g)
        audit(db, me, "access.granted", target=f"{p.email} · {app.name}", target_type="user", target_id=p.id,
              company_id=p.company_id, application_id=app.id)
    else:
        fields = [f for f in ("role", "is_app_admin") if getattr(g, f) != getattr(body, f)]
        g.role, g.is_app_admin = body.role, body.is_app_admin
        if fields:
            audit(db, me, "access.changed", target=f"{p.email} · {app.name}", target_type="user", target_id=p.id,
                  company_id=p.company_id, application_id=app.id, fields=camel(fields))
    db.commit()
    return {"grant": grant_out(g, app)}


@router.delete("/{user_id}/applications/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_application(user_id: str, app_id: str, db: DB, me: AdminUser) -> Response:
    p = _person(db, user_id)
    g = db.get(IdentityApp, (p.id, app_id))
    if g is None:
        raise not_found("access")
    app = db.get(Application, app_id)
    audit(db, me, "access.withdrawn", target=f"{p.email} · {app.name}", target_type="user", target_id=p.id,
          company_id=p.company_id, application_id=app_id)
    db.delete(g)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: DB, me: AdminUser) -> Response:
    """Gone from the platform: their applications and sign-ins go with them;
    tickets they raised stay, with nobody on them. Suspending keeps the person."""
    p = _person(db, user_id)
    # Never your own account, nor a company's last administrator: either locks people out
    # with nobody left to let them back in (2026-10-27, an administrator deleted their own).
    if p.email.lower() == me.email.lower():
        raise conflict("That's your own account. Another administrator can delete it, or suspend it instead.")
    if p.is_company_admin and not db.scalar(
        select(func.count()).select_from(Identity).where(Identity.company_id == p.company_id, Identity.is_company_admin, Identity.id != p.id, Identity.status == "active")
    ):
        raise conflict(f"{p.email} is the company's only administrator. Make someone else its administrator first.")
    audit(db, me, "user.deleted", category="security", target=p.email, target_type="user", target_id=p.id, company_id=p.company_id)
    db.delete(p)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class FirstPasswordIn(Api):
    # None: one is made, and shown once.
    password: str | None = Field(None, max_length=256)


@router.post("/{user_id}/password")
def set_password(user_id: str, body: FirstPasswordIn, me: AdminUser, db: DB) -> dict:
    """A first (or replacement) password for someone's Bishnoi One account. Their
    current sign-ins end. They change it themselves afterwards."""
    from app.security import check_password_rules, hash_password

    person = db.get(Identity, user_id)
    if person is None:
        raise not_found("user")
    made = body.password is None
    password = body.password or secrets.token_urlsafe(9)
    problem = check_password_rules(password)
    if problem:
        raise field_error("password", problem)
    hashed, now = hash_password(password), datetime.now(UTC)
    # One password at every company of theirs, and in the Admin Console (app/passwords.py).
    passwords.set_for(db, person.email, hashed, now)
    audit(db, me, "identity.password_set", category="security", target=person.email, target_type="identity", target_id=person.id, company_id=person.company_id)
    db.commit()
    return {"password": password if made else None}
