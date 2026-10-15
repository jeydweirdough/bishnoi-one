"""Promotional material designs Admin sends for the pharmacist's approval, so
nothing is produced and given to doctors before a pharmacist has checked it
(the product's name and strength, claims, the FDA registration number).

    Admin sends a design ──> it lands here, waiting
                               │  the pharmacist opens the design and decides
                               ▼
    approved · returned for changes (with comments) · rejected
                               │
    Admin asks for the answer ─┘  a returned design comes back as a new version

From Admin (an app holding one of INTEGRATION_KEYS, in X-Bishnoi-Key):
    POST /integration/materials               a version; sending it again while waiting updates it
    GET  /integration/materials/{sourceId}    the answer
For the pharmacist (materials.view, materials.review):
    GET  /material-reviews                    the inbox, waiting first
    GET  /material-reviews/{id}               one, with the material's earlier versions
    GET  /material-reviews/{id}/file          its design
    POST /material-reviews/{id}/decision      approved, returned or rejected
"""

import base64
import binascii
from typing import Literal
from urllib.parse import quote as url_quote

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import case, select

from app.access import Can
from app.api import Api, field_error, iso, next_number, not_found
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import MaterialReview, utcnow
from app.routers.integration import Caller

router = APIRouter(prefix="/material-reviews", tags=["promotional material reviews"])
integration = APIRouter(prefix="/integration/materials", tags=["integration"])

MAX_BYTES = 3 * 1024 * 1024
FILE_KINDS = {b"%PDF": "application/pdf", b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg"}
DECIDED = ("approved", "returned", "rejected")


def review_out(r: MaterialReview) -> dict:
    return {
        "id": r.id, "number": r.number, "source": r.source, "reference": r.reference, "version": r.version,
        "title": r.title, "kind": r.kind, "product": r.product, "description": r.description, "notes": r.notes,
        "fileName": r.file_name, "contentType": r.content_type, "sentBy": r.sent_by, "status": r.status,
        "comments": r.comments, "reviewedBy": r.reviewed_by.full_name if r.reviewed_by else None,
        "reviewedByLicense": r.reviewed_by.license_no if r.reviewed_by else None,
        "reviewedAt": iso(r.reviewed_at), "receivedAt": iso(r.received_at),
    }


def answer_out(r: MaterialReview) -> dict:
    """What the sending app reads back."""
    return {
        "number": r.number,
        "outcome": r.status,  # waiting, approved, returned or rejected
        "comments": r.comments,
        "reviewedBy": r.reviewed_by.full_name if r.reviewed_by else None,
        "reviewedAt": iso(r.reviewed_at),
    }


# --- from Admin ----------------------------------------------------------------------------


class FileIn(Api):
    name: str = Field(min_length=1, max_length=200)
    content_type: str | None = Field(None, max_length=100)
    data: str = Field(min_length=4, max_length=5_000_000)  # base64


class MaterialIn(Api):
    source_id: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=40)
    version: int = Field(ge=1, le=1000)
    title: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=40)
    product: str | None = Field(None, max_length=160)
    description: str | None = Field(None, max_length=4000)
    notes: str | None = Field(None, max_length=4000)
    file: FileIn
    sent_by: str = Field(min_length=1, max_length=120)


def _find(db, app: str, source_id: str) -> MaterialReview | None:
    return db.scalar(select(MaterialReview).where(MaterialReview.source == app, MaterialReview.source_id == source_id))


@integration.post("")
def receive(app: Caller, db: DB, settings: SettingsDep, body: MaterialIn) -> dict:
    """A design for the pharmacist. Sending it again while it waits updates it; once decided, the answer stands."""
    review = _find(db, app, body.source_id)
    if review is not None and review.status in DECIDED:
        return answer_out(review)
    try:
        data = base64.b64decode(body.file.data, validate=True)
    except (binascii.Error, ValueError):
        raise field_error("file", "The design's file couldn't be read.") from None
    if len(data) > MAX_BYTES:
        raise field_error("file", "The design is over 3 MB.")
    kind = next((v for magic, v in FILE_KINDS.items() if data.startswith(magic)), None)
    if kind is None:
        raise field_error("file", "Send the design as a PDF or a picture (PNG or JPG).")
    action = "material_review.resent"
    if review is None:
        review = MaterialReview(number=next_number(db, "PMR", settings), source=app, source_id=body.source_id, status="waiting")
        db.add(review)
        action = "material_review.received"
    for field in ("reference", "version", "title", "kind", "product", "description", "notes", "sent_by"):
        setattr(review, field, getattr(body, field))
    review.file_name, review.content_type, review.file_data = body.file.name, kind, data
    db.flush()
    audit(db, f"{app}: {body.sent_by}", action, target=f"{review.number} {body.reference} v{body.version}", target_type="material_review", target_id=review.id)
    db.commit()
    db.refresh(review)
    return answer_out(review)


@integration.get("/{source_id}")
def read_answer(app: Caller, db: DB, source_id: str) -> dict:
    review = _find(db, app, source_id)
    if review is None:
        raise not_found("review")
    return answer_out(review)


# --- for the pharmacist --------------------------------------------------------------------


def _get(db, review_id: str) -> MaterialReview:
    review = db.get(MaterialReview, review_id)
    if review is None:
        raise not_found("review")
    return review


@router.get("")
def inbox(_: Can("materials.view"), db: DB, status_: Literal["waiting", "approved", "returned", "rejected"] | None = Query(None, alias="status")) -> dict:
    """Waiting first, oldest first (first come, first checked); then the decided, newest first."""
    query = select(MaterialReview).order_by(case((MaterialReview.status == "waiting", 0), else_=1), MaterialReview.received_at)
    if status_:
        query = query.where(MaterialReview.status == status_)
    rows = db.scalars(query).all()
    waiting = [r for r in rows if r.status == "waiting"]
    decided = sorted((r for r in rows if r.status != "waiting"), key=lambda r: r.reviewed_at or r.received_at, reverse=True)
    counts = {s: 0 for s in ("waiting", *DECIDED)}
    for (s,) in db.execute(select(MaterialReview.status)):
        counts[s] += 1
    return {"items": [review_out(r) for r in waiting + decided], "counts": counts}


@router.get("/{review_id}")
def one(access: Can("materials.view"), db: DB, review_id: str) -> dict:
    review = _get(db, review_id)
    earlier = db.scalars(
        select(MaterialReview).where(MaterialReview.source == review.source, MaterialReview.reference == review.reference, MaterialReview.id != review.id).order_by(MaterialReview.version.desc())
    ).all()
    return {
        "review": review_out(review),
        "earlier": [review_out(r) for r in earlier],
        "canDecide": access.can("materials.review") and review.status == "waiting",
    }


@router.get("/{review_id}/file")
def design_file(_: Can("materials.view"), db: DB, review_id: str) -> Response:
    review = _get(db, review_id)
    return Response(review.file_data, media_type=review.content_type, headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(review.file_name)}"})


class DecisionIn(Api):
    outcome: Literal["approved", "returned", "rejected"]
    comments: str | None = Field(None, max_length=4000)


@router.post("/{review_id}/decision")
def decide(access: Can("materials.review"), db: DB, review_id: str, body: DecisionIn) -> dict:
    review = _get(db, review_id)
    if review.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, "This design has already been decided.")
    if body.outcome != "approved" and not body.comments:
        raise field_error("comments", "Say what needs changing, or why it's rejected.")
    review.status = body.outcome
    review.comments = body.comments
    review.reviewed_by_id = access.user.id
    review.reviewed_at = utcnow()
    audit(db, access.user, f"material_review.{body.outcome}", target=f"{review.number} {review.reference} v{review.version}", target_type="material_review", target_id=review.id)
    db.commit()
    db.refresh(review)
    return one(access, db, review_id)
