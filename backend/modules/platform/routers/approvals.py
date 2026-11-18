"""Approval slips for the people of a company (Step 4C; approvals.py says how a slip moves).

    GET  /identity/approvals?box=waiting|mine|done|all   the inbox: waiting on me, my requests, finished, everything
                                                         waiting at the company (administrators)
    GET  /identity/approvals/count                       how many wait on me, and whether I have any at all
    GET  /identity/approvals/for?app&kind&id             a record's slip (its latest) and the ones before it
    GET  /identity/approvals/{id}                        one slip: steps, signatures, attachments, what I may do
    POST /identity/approvals/{id}/sign                   {note?}: the step that waits is signed
    POST /identity/approvals/{id}/return                 {note}: back to the requester
    POST /identity/approvals/{id}/files                  multipart file + label: a photo or document added
    GET  /identity/approvals/{id}/files/{file_id}        the file
"""

from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import select

from modules.platform import approvals, events, signatures
from modules.platform.accounts import runs_company
from modules.platform.api import Api, iso, not_found
from modules.platform.deps import DB, SettingsDep
from modules.platform.models import AccountSignature, Approval, ApprovalAttachment, Identity
from modules.platform.routers.identity import Signed

router = APIRouter(prefix="/identity/approvals", tags=["approvals"])

STATUS_LABELS = {"pending": "Waiting", "approved": "Approved", "returned": "Returned", "cancelled": "Cancelled"}
KIND_LABELS = {"sales_order": "Sales order", "price_change": "Price change"}


def _refused(e: approvals.Refused) -> HTTPException:
    return HTTPException(e.status, str(e))


def brief(db, slip: Approval, me: Identity) -> dict:
    step = approvals.current(db, slip)
    return {
        "id": slip.id, "no": slip.no, "number": slip.number, "status": slip.status, "statusLabel": STATUS_LABELS[slip.status],
        "app": slip.app, "kind": slip.kind, "kindLabel": KIND_LABELS.get(slip.kind, slip.kind.replace("_", " ").capitalize()),
        "record": {"id": slip.record_id, "number": slip.record_number, "url": slip.record_url},
        "title": slip.title, "summary": slip.summary or {},
        "requestedBy": {"id": slip.requested_by_id, "name": slip.requested_by_name, "email": slip.requested_by_email},
        "waitingOn": (step.approver_name or step.label) if step else None,
        "waitingStep": step.label if step else None,
        "mine": approvals.is_requester(slip, me),
        "myTurn": approvals.acts_as(db, slip, step, me) is not None,
        "createdAt": iso(slip.created_at), "finishedAt": iso(slip.finished_at), "note": slip.note,
    }


def full(db, slip: Approval, me: Identity) -> dict:
    step = approvals.current(db, slip)
    how = approvals.acts_as(db, slip, step, me)
    sigs = {s.id: s for s in db.scalars(select(AccountSignature).where(AccountSignature.id.in_(
        [x.signature_id for x in approvals.steps_of(db, slip) if x.signature_id])))}
    before = db.get(Approval, slip.replaces_id) if slip.replaces_id else None
    files = db.scalars(select(ApprovalAttachment).where(ApprovalAttachment.approval_id == slip.id).order_by(ApprovalAttachment.added_at)).all()
    return {
        **brief(db, slip, me),
        "steps": [{
            "id": s.id, "position": s.position, "label": s.label, "status": s.status,
            "approver": {"id": s.approver_id, "name": s.approver_name} if s.approver_id or s.approver_name else None,
            "group": {"app": s.app_key, "permission": s.permission} if s.permission else None,
            "note": s.note, "actedBy": s.acted_by_name, "actedAs": s.acted_as, "actedAt": iso(s.acted_at),
            "signature": signatures.data_url(sigs[s.signature_id].image) if s.signature_id in sigs else None,
            "current": step is not None and s.id == step.id,
        } for s in approvals.steps_of(db, slip)],
        "attachments": [{
            "id": a.id, "kind": a.kind, "label": a.label, "app": a.app, "recordKind": a.record_kind, "recordId": a.record_id,
            "number": a.record_number, "url": a.url, "fileName": a.file_name, "contentType": a.content_type, "size": a.size,
            "addedBy": a.added_by, "addedAt": iso(a.added_at),
        } for a in files],
        "replaces": {"id": before.id, "number": before.number, "status": before.status, "note": before.note} if before else None,
        "canSign": how is not None, "actingAs": how, "canAddFiles": slip.status == "pending",
    }


def slip_for(db, slip_id: str, me: Identity) -> Approval:
    slip = db.get(Approval, slip_id)
    if slip is None or not approvals.may_see(db, slip, me):
        raise not_found("approval slip")
    return slip


def _box(db, me: Identity, box: str) -> list[Approval]:
    rows = db.scalars(select(Approval).where(Approval.company_id == me.company_id).order_by(Approval.created_at.desc()).limit(500)).all()
    if box == "waiting":
        return [s for s in rows if s.status == "pending" and approvals.acts_as(db, s, approvals.current(db, s), me) in ("approver", "holder")]
    if box == "mine":
        return [s for s in rows if approvals.is_requester(s, me)]
    if box == "all":
        return [s for s in rows if s.status == "pending"] if runs_company(db, me) else []
    return [s for s in rows if s.status != "pending" and approvals.may_see(db, s, me)]


@router.get("")
def inbox(signed: Signed, db: DB, box: str = Query("waiting", pattern="^(waiting|mine|done|all)$")) -> dict:
    _, me = signed
    items = _box(db, me, box)
    return {"box": box, "items": [brief(db, s, me) for s in items[:200]], "isAdmin": runs_company(db, me)}


@router.get("/count")
def count(signed: Signed, db: DB) -> dict:
    """For the menu: how many wait on me; any = I have slips to see at all (waiting, mine, or I approve)."""
    _, me = signed
    waiting = len(_box(db, me, "waiting"))
    mine = db.scalar(select(Approval.id).where(Approval.company_id == me.company_id, Approval.requested_by_id == me.id).limit(1)) is not None
    return {"waiting": waiting, "any": bool(waiting or mine or runs_company(db, me))}


@router.get("/for")
def for_record(signed: Signed, db: DB, app: str = Query(max_length=40), kind: str = Query(max_length=40), id: str = Query(max_length=36)) -> dict:
    """A record's latest slip (in full, when I may see it) and the earlier ones, newest first."""
    _, me = signed
    rows = db.scalars(select(Approval).where(Approval.company_id == me.company_id, Approval.app == app, Approval.kind == kind,
                                             Approval.record_id == id).order_by(Approval.created_at.desc()).limit(20)).all()
    seen = [s for s in rows if approvals.may_see(db, s, me)]
    return {"slip": full(db, seen[0], me) if seen else None, "earlier": [brief(db, s, me) for s in seen[1:]]}


@router.get("/{slip_id}")
def read(slip_id: str, signed: Signed, db: DB) -> dict:
    _, me = signed
    return full(db, slip_for(db, slip_id, me), me)


class NoteIn(Api):
    note: str | None = Field(None, max_length=500)


def _after(request: Request, settings) -> None:
    events.kick(request.app.state.sessions, settings)


@router.post("/{slip_id}/sign")
def sign(slip_id: str, body: NoteIn, signed: Signed, db: DB, settings: SettingsDep, request: Request) -> dict:
    _, me = signed
    slip = slip_for(db, slip_id, me)
    try:
        approvals.sign(db, slip, me, body.note)
    except approvals.Refused as e:
        raise _refused(e) from None
    db.commit()
    if slip.status != "pending":
        _after(request, settings)
    return full(db, slip, me)


@router.post("/{slip_id}/return")
def give_back(slip_id: str, body: NoteIn, signed: Signed, db: DB, settings: SettingsDep, request: Request) -> dict:
    _, me = signed
    slip = slip_for(db, slip_id, me)
    try:
        approvals.give_back(db, slip, me, body.note or "")
    except approvals.Refused as e:
        raise _refused(e) from None
    db.commit()
    _after(request, settings)
    return full(db, slip, me)


@router.post("/{slip_id}/files", status_code=status.HTTP_201_CREATED)
async def add_file(slip_id: str, signed: Signed, db: DB, file: UploadFile = File(...), label: str = Form("")) -> dict:
    _, me = signed
    slip = slip_for(db, slip_id, me)
    data = await file.read(approvals.MAX_FILE_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That file is empty.")
    try:
        approvals.add_file(db, slip, me, label, file.filename or "file", data)
    except approvals.Refused as e:
        raise _refused(e) from None
    db.commit()
    return full(db, slip, me)


@router.get("/{slip_id}/files/{file_id}")
def open_file(slip_id: str, file_id: str, signed: Signed, db: DB) -> Response:
    _, me = signed
    slip = slip_for(db, slip_id, me)
    item = db.get(ApprovalAttachment, file_id)
    if item is None or item.approval_id != slip.id or item.kind != "file" or item.data is None:
        raise not_found("file")
    safe = (item.file_name or "file").replace('"', "").replace("\r", "").replace("\n", "")
    return Response(item.data, media_type=item.content_type or "application/octet-stream", headers={
        "Content-Disposition": f"inline; filename=\"{safe.encode('ascii', 'replace').decode()}\"; filename*=UTF-8''{quote(safe)}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
