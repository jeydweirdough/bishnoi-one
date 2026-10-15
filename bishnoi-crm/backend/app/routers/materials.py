"""Promotional materials Admin gives out: the department's manager approves each request.

    Admin asks to give some of a material to a team (or one person in it)
        │  it lands here, waiting, for whoever runs that team's department
        ▼
    the manager approves or rejects it (a rejection says why)
        │  Admin reads the answer, gives it out, and says so here
        ▼
    given out on a date (or cancelled in Admin before that)

From Admin (an app holding one of INTEGRATION_KEYS, in X-Bishnoi-Key):
    GET  /integration/teams                         active teams, their manager and people
    POST /integration/material-requests             a request, or what became of it (state)
    GET  /integration/material-requests/{sourceId}  the manager's answer
For managers (department.manage, or admin.settings) over the teams they run:
    GET  /material-requests                         waiting first
    POST /material-requests/{id}/decision           approved or rejected
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import case, select

from app.access import DEPARTMENT, Access, require
from app.api import Api, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import MaterialRequest, Team, User, utcnow
from app.routers.integration import Caller

router = APIRouter(tags=["promotional materials"])
integration = APIRouter(tags=["integration"])
Manage = Annotated[Access, Depends(require(*DEPARTMENT))]


def answer_out(r: MaterialRequest) -> dict:
    """What Admin reads back."""
    return {
        "outcome": r.status,  # waiting, approved or rejected
        "decidedBy": r.decided_by.full_name if r.decided_by else None,
        "decidedAt": iso(r.decided_at),
        "note": r.note,
    }


def request_out(r: MaterialRequest) -> dict:
    return {
        "id": r.id,
        "reference": r.reference,
        "material": r.material or {},
        "team": {"id": r.team.id, "name": r.team.name},
        "recipient": {"id": r.recipient.id, "name": r.recipient.full_name} if r.recipient else None,
        "quantity": r.quantity,
        "purpose": r.purpose,
        "requestedBy": r.requested_by,
        "status": r.status,
        "adminState": r.admin_state,
        "distributedOn": r.distributed_on.isoformat() if r.distributed_on else None,
        "note": r.note,
        "decidedBy": r.decided_by.full_name if r.decided_by else None,
        "decidedAt": iso(r.decided_at),
        "receivedAt": iso(r.received_at),
    }


# --- from Admin ----------------------------------------------------------------------------


def members(db, team: Team) -> list[User]:
    """Active people in the team: it's their main team, or one of their others."""
    people = db.scalars(select(User).where(User.is_active).order_by(User.full_name)).all()
    return [u for u in people if team.id in u.all_team_ids]


@integration.get("/integration/teams")
def teams(_: Caller, db: DB) -> dict:
    out = []
    for t in db.scalars(select(Team).where(Team.is_active).order_by(Team.name)):
        manager = db.get(User, t.manager_id) if t.manager_id else None
        out.append({
            "id": t.id,
            "name": t.name,
            "manager": {"id": manager.id, "name": manager.full_name} if manager else None,
            "people": [{"id": u.id, "name": u.full_name} for u in members(db, t)],
        })
    return {"teams": out}


class MaterialOut(Api):
    no: int | None = None
    title: str = Field(min_length=1, max_length=160)
    kind: str | None = Field(None, max_length=40)
    product: str | None = Field(None, max_length=160)


class RequestIn(Api):
    source_id: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=40)
    material: MaterialOut
    team_id: str = Field(min_length=1, max_length=36)
    recipient_id: str | None = Field(None, max_length=36)
    quantity: int = Field(ge=1, le=10_000_000)
    purpose: str | None = Field(None, max_length=500)
    requested_by: str | None = Field(None, max_length=140)
    state: Literal["requested", "distributed", "cancelled"] = "requested"
    distributed_on: date | None = None


def _find(db, app: str, source_id: str) -> MaterialRequest | None:
    return db.scalar(select(MaterialRequest).where(MaterialRequest.source == app, MaterialRequest.source_id == source_id))


@integration.post("/integration/material-requests")
def receive(app: Caller, db: DB, body: RequestIn) -> dict:
    """A request for the manager, or what became of it in Admin. Once the manager
    has decided, only its state in Admin changes; the decision stands."""
    r = _find(db, app, body.source_id)
    if r is None:
        if body.state != "requested":
            raise not_found("request")
        team = db.get(Team, body.team_id)
        if team is None or not team.is_active:
            raise field_error("teamId", "That team isn't in the CRM.")
        if body.recipient_id:
            person = db.get(User, body.recipient_id)
            if person is None or not person.is_active or team.id not in person.all_team_ids:
                raise field_error("recipientId", "That person isn't in the team.")
        r = MaterialRequest(source=app, source_id=body.source_id, team_id=team.id, recipient_id=body.recipient_id, status="waiting")
        db.add(r)
        action = "material_request.received"
    else:
        action = f"material_request.{body.state}" if body.state != r.admin_state else "material_request.resent"
    if r.status == "waiting" and body.state == "requested":
        r.reference, r.material, r.quantity, r.purpose, r.requested_by = body.reference, body.material.model_dump(), body.quantity, body.purpose, body.requested_by
    r.admin_state = body.state
    r.distributed_on = body.distributed_on if body.state == "distributed" else None
    db.flush()
    audit(db, f"{app}: {body.requested_by or 'Admin'}", action, target=f"{body.reference} {body.material.title}", target_type="material_request", target_id=r.id)
    db.commit()
    db.refresh(r)
    return answer_out(r)


@integration.get("/integration/material-requests/{source_id}")
def read_answer(app: Caller, db: DB, source_id: str) -> dict:
    r = _find(db, app, source_id)
    if r is None:
        raise not_found("request")
    return answer_out(r)


# --- for the manager -----------------------------------------------------------------------


@router.get("/material-requests")
def inbox(access: Manage, db: DB, status_: Literal["waiting", "approved", "rejected"] | None = Query(None, alias="status")) -> dict:
    """The requests for the teams this person runs: waiting first, oldest first; then the decided, newest first."""
    rows = [r for r in db.scalars(select(MaterialRequest).order_by(case((MaterialRequest.status == "waiting", 0), else_=1), MaterialRequest.received_at)) if access.runs(r.team_id)]
    counts = {s: sum(1 for r in rows if r.status == s and r.admin_state != "cancelled") for s in ("waiting", "approved", "rejected")}
    if status_:
        rows = [r for r in rows if r.status == status_]
    waiting = [r for r in rows if r.status == "waiting"]
    decided = sorted((r for r in rows if r.status != "waiting"), key=lambda r: r.decided_at or r.received_at, reverse=True)
    return {"items": [request_out(r) for r in waiting + decided], "counts": counts}


class DecisionIn(Api):
    outcome: Literal["approved", "rejected"]
    note: str | None = Field(None, max_length=500)


@router.post("/material-requests/{request_id}/decision")
def decide(access: Manage, me: CurrentUser, db: DB, request_id: str, body: DecisionIn) -> dict:
    r = db.get(MaterialRequest, request_id)
    if r is None or not access.runs(r.team_id):
        raise not_found("request")
    if r.status != "waiting" or r.admin_state == "cancelled":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request has already been decided or was cancelled in Admin.")
    if body.outcome == "rejected" and not body.note:
        raise field_error("note", "Say why it's rejected.")
    r.status = body.outcome
    r.note = body.note
    r.decided_by_id = me.id
    r.decided_at = utcnow()
    title = (r.material or {}).get("title", "material")
    audit(db, me, f"material_request.{body.outcome}", target=f"{r.reference} {title}", target_type="material_request", target_id=r.id)
    db.commit()
    db.refresh(r)
    return request_out(r)
