"""Organizations: every company on the platform, its departments and
branches, and which applications it may use.

A company is never deleted, because its tickets, incidents and history would
go with it. It is suspended instead: its people stay on record, and every
screen says they can't work.
"""

import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request, Response, status
from pydantic import Field, field_validator
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.api import SLUG, Api, camel, changed, check_email, conflict, field_error, iso, not_found, now
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app import company_push
from app.models import (
    TICKET_STATUSES,
    Application,
    Company,
    CompanyApp,
    Identity,
    IdentityApp,
    Incident,
    IncidentCompany,
    OrgUnit,
    Ticket,
)

router = APIRouter(prefix="/platform/companies", tags=["organizations"])

OPEN = [s for s in TICKET_STATUSES if s not in ("resolved", "closed")]


def _check_timezone(value: str | None) -> str | None:
    if value is None:
        return value
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Pick a time zone like Asia/Manila.") from None
    return value


def _check_currency(value: str | None) -> str | None:
    if value is not None and not re.fullmatch(r"[A-Z]{3}", value.upper()):
        raise ValueError("Use a three-letter currency code like PHP.")
    return value.upper() if value else value


def _check_slug(value: str | None) -> str | None:
    if value is not None and not SLUG.fullmatch(value):
        raise ValueError("Lower-case letters, numbers and dashes only, like getmeds or bay-side.")
    return value


def as_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-")


class CompanyFields(Api):
    @field_validator("timezone", check_fields=False)
    @classmethod
    def _tz(cls, v):
        return _check_timezone(v)

    @field_validator("currency", check_fields=False)
    @classmethod
    def _cur(cls, v):
        return _check_currency(v)

    @field_validator("slug", check_fields=False)
    @classmethod
    def _slug(cls, v):
        return _check_slug(v)

    @field_validator("contact_email", "admin_email", check_fields=False)
    @classmethod
    def _email(cls, v):
        return check_email(v)


class CompanyIn(CompanyFields):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(None, max_length=40)
    currency: str = "PHP"
    timezone: str = "Asia/Manila"
    contact_email: str | None = Field(None, max_length=254)
    notes: str | None = Field(None, max_length=4000)
    application_ids: list[str] = []
    # Who runs it: they join as its first company admin.
    admin_name: str | None = Field(None, min_length=2, max_length=120)
    admin_email: str | None = Field(None, max_length=254)


class CompanyPatch(CompanyFields):
    name: str | None = Field(None, min_length=2, max_length=120)
    slug: str | None = Field(None, max_length=40)
    currency: str | None = None
    timezone: str | None = None
    contact_email: str | None = Field(None, max_length=254)
    notes: str | None = Field(None, max_length=4000)
    status: Literal["active", "suspended"] | None = None


class AppsIn(Api):
    application_ids: list[str]


class UnitIn(Api):
    kind: Literal["department", "branch"]
    name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(None, max_length=200)


class UnitPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    location: str | None = Field(None, max_length=200)


def company_out(c: Company, **extra) -> dict:
    return {
        "id": c.id,
        "no": c.no,
        "name": c.name,
        "slug": c.slug,
        "status": c.status,
        "currency": c.currency,
        "timezone": c.timezone,
        "contactEmail": c.contact_email,
        "notes": c.notes,
        "createdAt": iso(c.created_at),
        "suspendedAt": iso(c.suspended_at),
        **extra,
    }


def unit_out(u: OrgUnit) -> dict:
    return {"id": u.id, "kind": u.kind, "name": u.name, "location": u.location, "createdAt": iso(u.created_at)}


def _counts(db: Session, column, where=None) -> dict[str, int]:
    query = select(column, func.count()).group_by(column)
    if where is not None:
        query = query.where(where)
    return dict(db.execute(query).all())


def _company(db: Session, company_id: str) -> Company:
    c = db.get(Company, company_id)
    if c is None:
        raise not_found("company")
    return c


def _apps(db: Session, ids: list[str]) -> list[Application]:
    unique = list(dict.fromkeys(ids))
    apps = db.scalars(select(Application).where(Application.id.in_(unique))).all() if unique else []
    if len(apps) != len(unique):
        raise field_error("applicationIds", "One of those applications doesn't exist.")
    return list(apps)


@router.get("")
def list_companies(db: DB, _: CurrentUser, q: str | None = None, status: str | None = None) -> dict:
    query = select(Company).order_by(func.lower(Company.name))
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Company.name).like(like), func.lower(Company.slug).like(like)))
    if status in ("active", "suspended"):
        query = query.where(Company.status == status)
    users = _counts(db, Identity.company_id)
    apps = _counts(db, CompanyApp.company_id)
    tickets = _counts(db, Ticket.company_id, Ticket.status.in_(OPEN))
    return {
        "companies": [
            company_out(c, userCount=users.get(c.id, 0), appCount=apps.get(c.id, 0), openTickets=tickets.get(c.id, 0))
            for c in db.scalars(query)
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_company(body: CompanyIn, db: DB, me: AdminUser) -> dict:
    slug = body.slug or as_slug(body.name)
    if not slug:
        raise field_error("name", "The name needs a letter or a number in it.")
    if db.scalar(select(Company).where(Company.slug == slug)):
        raise field_error("slug" if body.slug else "name", f"The address {slug} is taken. Give it another.")
    if (body.admin_name is None) != (body.admin_email is None):
        raise field_error("adminEmail" if body.admin_email is None else "adminName", "Give both their name and their email, or neither.")
    apps = _apps(db, body.application_ids)
    c = Company(name=body.name, slug=slug, currency=body.currency, timezone=body.timezone, contact_email=body.contact_email, notes=body.notes)
    db.add(c)
    db.flush()
    for a in apps:
        db.add(CompanyApp(company_id=c.id, application_id=a.id))
    audit(db, me, "company.created", target=c.name, target_type="company", target_id=c.id, company_id=c.id)
    if body.admin_email:
        person = Identity(company_id=c.id, full_name=body.admin_name, email=body.admin_email, is_company_admin=True)
        # Already at another company: the same person, with the password they have.
        elsewhere = db.scalar(select(Identity).where(func.lower(Identity.email) == body.admin_email.lower(), Identity.password_hash.is_not(None)))
        if elsewhere is not None:
            person.password_hash, person.password_changed_at = elsewhere.password_hash, elsewhere.password_changed_at
        db.add(person)
        db.flush()
        audit(db, me, "user.created", target=person.email, target_type="user", target_id=person.id, company_id=c.id, fields=["isCompanyAdmin"])
    db.commit()
    return {"company": company_out(c, userCount=1 if body.admin_email else 0, appCount=len(apps), openTickets=0)}


@router.get("/{company_id}")
def get_company(company_id: str, db: DB, _: CurrentUser) -> dict:
    c = _company(db, company_id)
    from app.routers.applications import statuses  # one place decides what an application's status is

    app_rows = db.scalars(
        select(Application).join(CompanyApp, CompanyApp.application_id == Application.id)
        .where(CompanyApp.company_id == c.id).order_by(Application.sort_order, Application.name)
    ).all()
    status_of = statuses(db, app_rows)
    people_per_app = dict(
        db.execute(
            select(IdentityApp.application_id, func.count())
            .join(Identity, Identity.id == IdentityApp.identity_id)
            .where(Identity.company_id == c.id)
            .group_by(IdentityApp.application_id)
        ).all()
    )
    users = db.scalar(select(func.count()).select_from(Identity).where(Identity.company_id == c.id))
    active = db.scalar(select(func.count()).select_from(Identity).where(Identity.company_id == c.id, Identity.status == "active"))
    admins = db.scalars(select(Identity).where(Identity.company_id == c.id, Identity.is_company_admin, Identity.via_operator.is_(False)).order_by(Identity.full_name)).all()
    units = db.scalars(select(OrgUnit).where(OrgUnit.company_id == c.id).order_by(OrgUnit.kind, func.lower(OrgUnit.name))).all()
    open_tickets = db.scalar(select(func.count()).select_from(Ticket).where(Ticket.company_id == c.id, Ticket.status.in_(OPEN)))
    incidents = [i for i in active_incidents(db) if reaches(i, c.id, {a.id for a in app_rows})]
    return {
        "company": company_out(
            c,
            userCount=users,
            activeUserCount=active,
            appCount=len(app_rows),
            openTickets=open_tickets,
            applications=[
                {"id": a.id, "key": a.key, "name": a.name, "status": status_of[a.id], "userCount": people_per_app.get(a.id, 0)}
                for a in app_rows
            ],
            units=[unit_out(u) for u in units],
            admins=[{"id": p.id, "name": p.full_name, "email": p.email} for p in admins],
            activeIncidents=[
                {"id": i.id, "number": i.number, "title": i.title, "severity": i.severity, "status": i.status} for i in incidents
            ],
        )
    }


@router.patch("/{company_id}")
def update_company(company_id: str, body: CompanyPatch, db: DB, me: AdminUser, request: Request, settings: SettingsDep) -> dict:
    c = _company(db, company_id)
    fields = changed(body)
    for required in ("name", "slug", "currency", "timezone", "status"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    if "slug" in fields and fields["slug"] != c.slug and db.scalar(select(Company).where(Company.slug == fields["slug"])):
        raise field_error("slug", f"The address {fields['slug']} is taken.")
    fields = {k: v for k, v in fields.items() if getattr(c, k) != v}
    if not fields:
        return {"company": company_out(c)}
    if "status" in fields:
        c.suspended_at = now() if fields["status"] == "suspended" else None
    for name, value in fields.items():
        setattr(c, name, value)
    action = {"suspended": "company.suspended", "active": "company.reactivated"}.get(fields.get("status"), "company.updated")
    audit(db, me, action, target=c.name, target_type="company", target_id=c.id, company_id=c.id, fields=camel(fields))
    db.commit()
    if fields.keys() & {"status", "name", "slug"}:
        # What its applications hold about it changed: tell them now, not at their next renewal.
        company_push.push(request.app.state.sessions, settings, c.id, company_push.apps_of(db, c.id))
    return {"company": company_out(c)}


@router.put("/{company_id}/applications")
def set_applications(company_id: str, body: AppsIn, db: DB, me: AdminUser, request: Request, settings: SettingsDep) -> dict:
    """Which applications the company may use. Taking one away also takes it
    from each of its people: nobody keeps access their company hasn't got."""
    c = _company(db, company_id)
    wanted = {a.id for a in _apps(db, body.application_ids)}
    have = set(db.scalars(select(CompanyApp.application_id).where(CompanyApp.company_id == c.id)))
    added, removed = wanted - have, have - wanted
    for app_id in added:
        db.add(CompanyApp(company_id=c.id, application_id=app_id))
    withdrawn = 0
    if removed:
        db.execute(delete(CompanyApp).where(CompanyApp.company_id == c.id, CompanyApp.application_id.in_(removed)))
        people = select(Identity.id).where(Identity.company_id == c.id)
        withdrawn = db.execute(
            delete(IdentityApp).where(IdentityApp.application_id.in_(removed), IdentityApp.identity_id.in_(people))
        ).rowcount
    names = dict(db.execute(select(Application.id, Application.name).where(Application.id.in_(added | removed))).all())
    for app_id in added:
        audit(db, me, "company.app_granted", target=f"{c.name} · {names[app_id]}", target_type="company", target_id=c.id,
              company_id=c.id, application_id=app_id)
    for app_id in removed:
        audit(db, me, "company.app_withdrawn", target=f"{c.name} · {names[app_id]}", target_type="company", target_id=c.id,
              company_id=c.id, application_id=app_id)
    db.commit()
    # Given: it may be used there at once. Taken away: it stops at once.
    company_push.push(request.app.state.sessions, settings, c.id, added | removed)
    return {"added": len(added), "removed": len(removed), "withdrawnFromPeople": withdrawn}


@router.post("/{company_id}/units", status_code=status.HTTP_201_CREATED)
def add_unit(company_id: str, body: UnitIn, db: DB, me: AdminUser) -> dict:
    c = _company(db, company_id)
    if db.scalar(select(OrgUnit).where(OrgUnit.company_id == c.id, OrgUnit.kind == body.kind, func.lower(OrgUnit.name) == body.name.lower())):
        raise field_error("name", f"{c.name} already has a {body.kind} called that.")
    u = OrgUnit(company_id=c.id, kind=body.kind, name=body.name, location=body.location)
    db.add(u)
    db.flush()
    audit(db, me, f"{body.kind}.created", target=f"{c.name} · {u.name}", target_type=body.kind, target_id=u.id, company_id=c.id)
    db.commit()
    return {"unit": unit_out(u)}


def _unit(db: Session, company_id: str, unit_id: str) -> OrgUnit:
    u = db.get(OrgUnit, unit_id)
    if u is None or u.company_id != company_id:
        raise not_found("department or branch")
    return u


@router.patch("/{company_id}/units/{unit_id}")
def update_unit(company_id: str, unit_id: str, body: UnitPatch, db: DB, me: AdminUser) -> dict:
    u = _unit(db, company_id, unit_id)
    fields = {k: v for k, v in changed(body).items() if getattr(u, k) != v}
    if fields.get("name") is None and "name" in fields:
        raise field_error("name", "Give it a name.")
    if "name" in fields and db.scalar(
        select(OrgUnit).where(OrgUnit.company_id == company_id, OrgUnit.kind == u.kind, func.lower(OrgUnit.name) == fields["name"].lower(), OrgUnit.id != u.id)
    ):
        raise conflict(f"There's already a {u.kind} called {fields['name']}.")
    for name, value in fields.items():
        setattr(u, name, value)
    if fields:
        audit(db, me, f"{u.kind}.updated", target=u.name, target_type=u.kind, target_id=u.id, company_id=company_id, fields=camel(fields))
    db.commit()
    return {"unit": unit_out(u)}


@router.delete("/{company_id}/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(company_id: str, unit_id: str, db: DB, me: AdminUser) -> Response:
    u = _unit(db, company_id, unit_id)
    audit(db, me, f"{u.kind}.deleted", target=u.name, target_type=u.kind, target_id=u.id, company_id=company_id)
    db.delete(u)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def company_names(db: Session, ids: set[str | None]) -> dict[str, str]:
    ids = {i for i in ids if i}
    return dict(db.execute(select(Company.id, Company.name).where(Company.id.in_(ids))).all()) if ids else {}


def active_incidents(db: Session) -> list[Incident]:
    """Every incident not yet resolved, with the companies each one names."""
    incidents = db.scalars(select(Incident).where(Incident.status != "resolved").order_by(Incident.started_at.desc())).all()
    named: dict[str, set[str]] = {}
    for incident_id, company_id in db.execute(select(IncidentCompany.incident_id, IncidentCompany.company_id)):
        named.setdefault(incident_id, set()).add(company_id)
    for i in incidents:
        i.company_ids = named.get(i.id, set())
    return list(incidents)


def reaches(incident: Incident, company_id: str, app_ids: set[str]) -> bool:
    """Whether an incident reaches a company: it names it, or it names none
    and is on an application the company uses."""
    if incident.company_ids:
        return company_id in incident.company_ids
    return incident.application_id in app_ids


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: str, db: DB, me: AdminUser, request: Request, settings: SettingsDep) -> Response:
    """Gone from the platform: its people, their access, its structure, its
    applications and connections. Tickets it raised stay, with no company on them.
    What it keeps in each application (the CRM's customers...) isn't touched here."""
    c = _company(db, company_id)
    people = db.scalar(select(func.count()).select_from(Identity).where(Identity.company_id == c.id)) or 0
    audit(db, me, "company.deleted", category="security", target=c.name, target_type="company", target_id=c.id, fields=[f"{people} people"] if people else ())
    had, gone = company_push.apps_of(db, c.id), {"id": c.id, "slug": c.slug, "name": c.name}
    db.execute(delete(Identity).where(Identity.company_id == c.id))
    db.delete(c)
    db.commit()
    # Each application it had is told it's gone, with a pass saying so.
    company_push.push(request.app.state.sessions, settings, gone["id"], had, gone=gone)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
