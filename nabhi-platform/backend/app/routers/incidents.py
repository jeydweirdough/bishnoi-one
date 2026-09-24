"""Incidents: something happening now that stops people working.

A ticket is one person's report; an incident is the platform saying "this is
broken for many, and we're on it". It moves Investigating -> Identified ->
Monitoring -> Resolved, each move an update with words for whoever is
affected. It may name the companies it reaches; naming none means everyone
on its application (or the whole platform, with no application).

Anyone signed in here may declare, update and resolve one.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api import Api, camel, changed, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Application, Company, Incident, IncidentCompany, IncidentUpdate, Ticket, User
from app.numbers import insert_numbered

router = APIRouter(prefix="/platform/incidents", tags=["incidents"])

Kind = Literal["disruption", "application", "performance", "security"]
Severity = Literal["critical", "major", "minor"]
Status = Literal["investigating", "identified", "monitoring", "resolved"]


class IncidentIn(Api):
    title: str = Field(min_length=3, max_length=200)
    kind: Kind = "disruption"
    severity: Severity = "major"
    application_id: str | None = None
    company_ids: list[str] = []
    summary: str | None = Field(None, max_length=10000)
    lead_id: str | None = None
    started_at: datetime | None = None
    # The first update, for whoever is affected.
    update: str | None = Field(None, max_length=10000)


class IncidentPatch(Api):
    title: str | None = Field(None, min_length=3, max_length=200)
    kind: Kind | None = None
    severity: Severity | None = None
    application_id: str | None = None
    company_ids: list[str] | None = None
    summary: str | None = Field(None, max_length=10000)
    lead_id: str | None = None


class UpdateIn(Api):
    status: Status
    body: str = Field(min_length=1, max_length=10000)


def incident_out(i: Incident, names: dict[str, str], companies: list[dict], **extra) -> dict:
    return {
        "id": i.id,
        "number": i.number,
        "title": i.title,
        "kind": i.kind,
        "severity": i.severity,
        "status": i.status,
        "isActive": i.status != "resolved",
        "application": {"id": i.application_id, "name": names.get(i.application_id, "")} if i.application_id else None,
        "lead": {"id": i.lead_id, "name": names.get(i.lead_id, "")} if i.lead_id else None,
        "companies": companies,
        "summary": i.summary,
        "startedAt": iso(i.started_at),
        "resolvedAt": iso(i.resolved_at),
        "createdBy": i.created_by,
        **extra,
    }


def _names(db: Session, incidents: list[Incident]) -> dict[str, str]:
    names: dict[str, str] = {}
    apps = {i.application_id for i in incidents if i.application_id}
    leads = {i.lead_id for i in incidents if i.lead_id}
    if apps:
        names.update(db.execute(select(Application.id, Application.name).where(Application.id.in_(apps))).all())
    if leads:
        names.update(db.execute(select(User.id, User.full_name).where(User.id.in_(leads))).all())
    return names


def _companies(db: Session, ids: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not ids:
        return out
    for incident_id, company_id, name in db.execute(
        select(IncidentCompany.incident_id, Company.id, Company.name)
        .join(Company, Company.id == IncidentCompany.company_id)
        .where(IncidentCompany.incident_id.in_(ids))
        .order_by(Company.name)
    ):
        out.setdefault(incident_id, []).append({"id": company_id, "name": name})
    return out


def _incident(db: Session, incident_id: str) -> Incident:
    i = db.get(Incident, incident_id)
    if i is None:
        raise not_found("incident")
    return i


def _check_links(db: Session, fields: dict) -> None:
    if fields.get("application_id") and db.get(Application, fields["application_id"]) is None:
        raise field_error("applicationId", "That application doesn't exist.")
    if fields.get("lead_id") and db.get(User, fields["lead_id"]) is None:
        raise field_error("leadId", "That staff member doesn't exist.")
    ids = fields.get("company_ids") or []
    if ids and db.scalar(select(func.count()).select_from(Company).where(Company.id.in_(set(ids)))) != len(set(ids)):
        raise field_error("companyIds", "One of those companies doesn't exist.")


def _set_companies(db: Session, incident_id: str, ids: list[str]) -> None:
    db.execute(delete(IncidentCompany).where(IncidentCompany.incident_id == incident_id))
    for company_id in dict.fromkeys(ids):
        db.add(IncidentCompany(incident_id=incident_id, company_id=company_id))


@router.get("")
def list_incidents(db: DB, _: CurrentUser, state: str = "active", kind: str | None = None, application_id: str | None = None) -> dict:
    query = select(Incident).order_by(Incident.started_at.desc()).limit(200)
    if state == "active":
        query = query.where(Incident.status != "resolved")
    elif state == "resolved":
        query = query.where(Incident.status == "resolved")
    if kind:
        query = query.where(Incident.kind == kind)
    if application_id:
        query = query.where(Incident.application_id == application_id)
    incidents = db.scalars(query).all()
    names = _names(db, incidents)
    companies = _companies(db, [i.id for i in incidents])
    tickets = dict(
        db.execute(
            select(Ticket.incident_id, func.count()).where(Ticket.incident_id.in_([i.id for i in incidents])).group_by(Ticket.incident_id)
        ).all()
    ) if incidents else {}
    active = db.scalar(select(func.count()).select_from(Incident).where(Incident.status != "resolved"))
    return {
        "incidents": [incident_out(i, names, companies.get(i.id, []), ticketCount=tickets.get(i.id, 0)) for i in incidents],
        "active": active,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def declare(body: IncidentIn, db: DB, me: CurrentUser) -> dict:
    fields = body.model_dump()
    _check_links(db, fields)
    company_ids, update = fields.pop("company_ids"), fields.pop("update")
    started = fields.pop("started_at") or datetime.now(UTC)
    i = insert_numbered(
        db, lambda number: Incident(number=number, started_at=started, created_by=me.email, **fields), Incident.number, "INC", 4
    )
    _set_companies(db, i.id, company_ids)
    db.add(IncidentUpdate(incident_id=i.id, status="investigating", author=me.full_name,
                          body=update or body.summary or "We're looking into it."))
    audit(db, me, "incident.declared", category="support", target=f"{i.number} {i.title}", target_type="incident", target_id=i.id,
          application_id=i.application_id)
    db.commit()
    return get_incident(i.id, db, me)


@router.get("/{incident_id}")
def get_incident(incident_id: str, db: DB, _: CurrentUser) -> dict:
    i = _incident(db, incident_id)
    updates = db.scalars(select(IncidentUpdate).where(IncidentUpdate.incident_id == i.id).order_by(IncidentUpdate.created_at.desc())).all()
    tickets = db.scalars(select(Ticket).where(Ticket.incident_id == i.id).order_by(Ticket.created_at.desc())).all()
    return {
        "incident": incident_out(
            i,
            _names(db, [i]),
            _companies(db, [i.id]).get(i.id, []),
            updates=[{"id": u.id, "status": u.status, "body": u.body, "author": u.author, "createdAt": iso(u.created_at)} for u in updates],
            tickets=[{"id": t.id, "number": t.number, "title": t.title, "status": t.status, "severity": t.severity} for t in tickets],
        )
    }


@router.patch("/{incident_id}")
def update_incident(incident_id: str, body: IncidentPatch, db: DB, me: CurrentUser) -> dict:
    i = _incident(db, incident_id)
    fields = changed(body)
    for required in ("title", "kind", "severity"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    _check_links(db, fields)
    touched = set()
    if "company_ids" in fields:
        _set_companies(db, i.id, fields.pop("company_ids") or [])
        touched.add("company_ids")
    fields = {k: v for k, v in fields.items() if getattr(i, k) != v}
    for name, value in fields.items():
        setattr(i, name, value)
    touched |= set(fields)
    if touched:
        audit(db, me, "incident.updated", category="support", target=f"{i.number} {i.title}", target_type="incident", target_id=i.id,
              application_id=i.application_id, fields=camel(touched))
    db.commit()
    return get_incident(i.id, db, me)


@router.post("/{incident_id}/updates", status_code=status.HTTP_201_CREATED)
def post_update(incident_id: str, body: UpdateIn, db: DB, me: CurrentUser) -> dict:
    """Moves the incident along, with words for whoever it reaches. Resolving
    it stamps when; a later update reopens it."""
    i = _incident(db, incident_id)
    was = i.status
    i.status = body.status
    i.resolved_at = (i.resolved_at or datetime.now(UTC)) if body.status == "resolved" else None
    db.add(IncidentUpdate(incident_id=i.id, status=body.status, body=body.body, author=me.full_name))
    if was != body.status:
        audit(db, me, f"incident.{body.status}", category="support", target=f"{i.number} {i.title}", target_type="incident",
              target_id=i.id, application_id=i.application_id, fields=["status"])
    db.commit()
    return get_incident(i.id, db, me)
