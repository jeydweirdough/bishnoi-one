"""Support: complaints, bug reports, system issues, feature requests and
support tickets, one list with a kind each.

- A bug: something that should work doesn't.
- A complaint: somebody is unhappy with how something works for them.
- A system issue: something wrong behind the scenes (a sync, a job).
- A feature request: something that doesn't exist yet.
- A support ticket: a question, or a hand needed.

Each moves Reported -> Triaged -> Assigned -> Investigating -> Fix in
development -> Testing -> Resolved -> Closed, and any step may be skipped.
Every move is kept on the ticket, with who made it. Anyone signed in here
works tickets; Support is who they're for.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import platform_settings
from app.api import Api, as_utc, camel, changed, check_email, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import TICKET_STATUSES, Application, Company, Identity, Incident, Ticket, TicketNote, User
from app.numbers import TICKET_PREFIXES, insert_numbered

router = APIRouter(prefix="/platform/tickets", tags=["support"])

OPEN = [s for s in TICKET_STATUSES if s not in ("resolved", "closed")]
Kind = Literal["complaint", "bug", "issue", "feature", "support"]
Severity = Literal["critical", "high", "medium", "low"]
Status = Literal["reported", "triaged", "assigned", "investigating", "fixing", "testing", "resolved", "closed"]


class TicketIn(Api):
    kind: Kind
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=10000)
    severity: Severity = "medium"
    company_id: str | None = None
    application_id: str | None = None
    # Somebody on the platform, or a name and email as they gave them.
    identity_id: str | None = None
    reporter_name: str | None = Field(None, max_length=120)
    reporter_email: str | None = Field(None, max_length=254)
    affected_users: int | None = Field(None, ge=0, le=10_000_000)
    assignee_id: str | None = None

    @field_validator("reporter_email")
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return check_email(value)


class TicketPatch(Api):
    kind: Kind | None = None
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=10000)
    severity: Severity | None = None
    status: Status | None = None
    company_id: str | None = None
    application_id: str | None = None
    assignee_id: str | None = None
    incident_id: str | None = None
    affected_users: int | None = Field(None, ge=0, le=10_000_000)
    # Said with the change, and kept on the ticket beside it.
    note: str | None = Field(None, max_length=10000)


class NoteIn(Api):
    body: str = Field(min_length=1, max_length=10000)


def overdue_after(db: Session, settings) -> dict[str, timedelta]:
    hours = platform_settings.notifications(db, settings).response_hours
    return {s: timedelta(hours=getattr(hours, s)) for s in ("critical", "high", "medium", "low")}


def ticket_out(t: Ticket, names: dict, limits: dict[str, timedelta] | None = None, **extra) -> dict:
    is_open = t.status in OPEN
    due = as_utc(t.created_at) + limits[t.severity] if limits else None
    return {
        "id": t.id,
        "number": t.number,
        "kind": t.kind,
        "title": t.title,
        "description": t.description,
        "severity": t.severity,
        "status": t.status,
        "isOpen": is_open,
        "company": _ref(t.company_id, names),
        "application": _ref(t.application_id, names),
        "reporter": {"id": t.identity_id, "name": t.reporter_name, "email": t.reporter_email},
        "assignee": _ref(t.assignee_id, names),
        "incident": _ref(t.incident_id, names),
        "affectedUsers": t.affected_users,
        "createdAt": iso(t.created_at),
        "updatedAt": iso(t.updated_at),
        "resolvedAt": iso(t.resolved_at),
        "closedAt": iso(t.closed_at),
        "dueAt": iso(due) if due and is_open else None,
        "isOverdue": bool(due and is_open and due < datetime.now(UTC)),
        **extra,
    }


def _ref(record_id: str | None, names: dict) -> dict | None:
    return {"id": record_id, "name": names.get(record_id, "")} if record_id else None


def names_for(db: Session, tickets: list[Ticket]) -> dict[str, str]:
    """Every company, application, assignee and incident the tickets name, by id."""
    names: dict[str, str] = {}
    for model, column, attr in (
        (Company, Company.name, "company_id"),
        (Application, Application.name, "application_id"),
        (User, User.full_name, "assignee_id"),
        (Incident, Incident.number, "incident_id"),
    ):
        ids = {getattr(t, attr) for t in tickets if getattr(t, attr)}
        if ids:
            names.update(db.execute(select(model.id, column).where(model.id.in_(ids))).all())
    return names


def note_out(n: TicketNote) -> dict:
    return {"id": n.id, "author": n.author, "body": n.body, "from": n.status_from, "to": n.status_to, "createdAt": iso(n.created_at)}


def _ticket(db: Session, ticket_id: str) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if t is None:
        raise not_found("ticket")
    return t


def _check_links(db: Session, fields: dict) -> None:
    for field, model, what in (
        ("company_id", Company, "company"),
        ("application_id", Application, "application"),
        ("assignee_id", User, "staff member"),
        ("incident_id", Incident, "incident"),
        ("identity_id", Identity, "user"),
    ):
        if fields.get(field) and db.get(model, fields[field]) is None:
            raise field_error(field, f"That {what} doesn't exist.")


def _move(t: Ticket, to: str) -> None:
    """A new status, and the moments that go with it. Reopening clears them."""
    now = datetime.now(UTC)
    t.status = to
    if to not in ("resolved", "closed"):
        t.resolved_at = None
    elif t.resolved_at is None:
        t.resolved_at = now
    t.closed_at = now if to == "closed" else None


@router.get("")
def list_tickets(
    db: DB,
    settings: SettingsDep,
    _: CurrentUser,
    kind: str | None = None,
    state: str = "open",
    severity: str | None = None,
    company_id: str | None = None,
    application_id: str | None = None,
    assignee_id: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Ticket).order_by(Ticket.created_at.desc()).limit(300)
    if kind:
        query = query.where(Ticket.kind == kind)
    if state == "open":
        query = query.where(Ticket.status.in_(OPEN))
    elif state == "done":
        query = query.where(Ticket.status.not_in(OPEN))
    elif state in TICKET_STATUSES:
        query = query.where(Ticket.status == state)
    if severity:
        query = query.where(Ticket.severity == severity)
    if company_id:
        query = query.where(Ticket.company_id == company_id)
    if application_id:
        query = query.where(Ticket.application_id == application_id)
    if assignee_id == "none":
        query = query.where(Ticket.assignee_id.is_(None))
    elif assignee_id:
        query = query.where(Ticket.assignee_id == assignee_id)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Ticket.title).like(like), func.lower(Ticket.number).like(like),
                                func.lower(Ticket.reporter_name).like(like)))
    tickets = db.scalars(query).all()
    limits = overdue_after(db, settings)
    names = names_for(db, tickets)
    counts = dict(db.execute(select(Ticket.kind, func.count()).where(Ticket.status.in_(OPEN)).group_by(Ticket.kind)).all())
    return {"tickets": [ticket_out(t, names, limits) for t in tickets], "openByKind": counts}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_ticket(body: TicketIn, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    fields = body.model_dump()
    _check_links(db, fields)
    if body.identity_id:
        person = db.get(Identity, body.identity_id)
        fields["reporter_name"] = fields["reporter_name"] or person.full_name
        fields["reporter_email"] = fields["reporter_email"] or person.email
        fields["company_id"] = fields["company_id"] or person.company_id
    if not fields["reporter_name"] and not fields["reporter_email"]:
        raise field_error("reporterName", "Say who reported it: pick them, or give a name or an email.")
    if fields["assignee_id"]:
        fields["status"] = "assigned"
    now = datetime.now(UTC)
    t = insert_numbered(
        db, lambda number: Ticket(number=number, created_at=now, updated_at=now, **fields), Ticket.number, TICKET_PREFIXES[body.kind], 5
    )
    db.add(TicketNote(ticket_id=t.id, author_id=me.id, author=me.full_name, status_to=t.status,
                      body=f"Logged for {t.reporter_name or t.reporter_email}.", created_at=now))
    audit(db, me, "ticket.created", category="support", target=f"{t.number} {t.title}", target_type="ticket", target_id=t.id,
          company_id=t.company_id, application_id=t.application_id)
    db.commit()
    return {"ticket": ticket_out(t, names_for(db, [t]), overdue_after(db, settings))}


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    t = _ticket(db, ticket_id)
    notes = db.scalars(select(TicketNote).where(TicketNote.ticket_id == t.id).order_by(TicketNote.created_at)).all()
    return {"ticket": ticket_out(t, names_for(db, [t]), overdue_after(db, settings), notes=[note_out(n) for n in notes])}


@router.patch("/{ticket_id}")
def update_ticket(ticket_id: str, body: TicketPatch, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    t = _ticket(db, ticket_id)
    fields = changed(body)
    note = fields.pop("note", None)
    for required in ("kind", "title", "severity", "status"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    _check_links(db, fields)
    fields = {k: v for k, v in fields.items() if getattr(t, k) != v}
    # Given to somebody while nobody has looked yet: it is Assigned now.
    if fields.get("assignee_id") and "status" not in fields and t.status in ("reported", "triaged"):
        fields["status"] = "assigned"
    was = t.status
    if "status" in fields:
        _move(t, fields.pop("status"))
    for name, value in fields.items():
        setattr(t, name, value)
    moved = t.status != was
    if moved or fields or note:
        t.updated_at = datetime.now(UTC)
        db.add(TicketNote(ticket_id=t.id, author_id=me.id, author=me.full_name, body=note,
                          status_from=was if moved else None, status_to=t.status if moved else None))
    if moved or fields:
        audit(db, me, f"ticket.{t.status}" if moved else "ticket.updated", category="support", target=f"{t.number} {t.title}",
              target_type="ticket", target_id=t.id, company_id=t.company_id, application_id=t.application_id,
              fields=camel(set(fields) | ({"status"} if moved else set())))
    db.commit()
    return get_ticket(t.id, db, settings, me)


@router.post("/{ticket_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(ticket_id: str, body: NoteIn, db: DB, me: CurrentUser) -> dict:
    t = _ticket(db, ticket_id)
    n = TicketNote(ticket_id=t.id, author_id=me.id, author=me.full_name, body=body.body)
    db.add(n)
    t.updated_at = datetime.now(UTC)
    db.commit()
    return {"note": note_out(n)}


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: str, db: DB, me: AdminUser) -> Response:
    """Gone, with its notes: a ticket raised by mistake, or a test."""
    t = _ticket(db, ticket_id)
    audit(db, me, "ticket.deleted", target=f"{getattr(t, 'number', '')} {t.title}".strip(), target_type="ticket", target_id=t.id, company_id=t.company_id)
    db.delete(t)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
