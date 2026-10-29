"""Quality checks on receipt (feature plan step 14a, app/quality.py).

    GET  /inventory/quality-checks             waiting first, newest first (status=waiting|done, warehouse)
    GET  /inventory/quality-checks/{id}        one, with its lines
    POST /inventory/quality-checks/{id}/done   each line's passed and failed (with why); passed is released for use
"""

from fastapi import APIRouter, Query, Request
from pydantic import Field
from sqlalchemy import select

from app import business_events, quality
from app.access import allowed
from app.api import Api, found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import QualityCheck

router = APIRouter(prefix="/inventory", tags=["quality checks"])

View = allowed("receiving.view")


@router.get("/quality-checks")
def list_checks(_: View, db: DB, status: str | None = Query(None, max_length=10), warehouse: str | None = Query(None, max_length=36)) -> dict:
    q = select(QualityCheck).order_by((QualityCheck.status == "done"), QualityCheck.created_at.desc()).limit(300)
    if status in ("waiting", "done"):
        q = q.where(QualityCheck.status == status)
    if warehouse:
        q = q.where(QualityCheck.warehouse_id == warehouse)
    checks = db.scalars(q).all()
    waiting = len(db.scalars(select(QualityCheck.id).where(QualityCheck.status == "waiting")).all())
    return {"items": [quality.check_out(c, full=False) for c in checks], "waiting": waiting}


@router.get("/quality-checks/{check_id}")
def read_check(_: View, db: DB, check_id: str) -> dict:
    return quality.check_out(found(db, QualityCheck, check_id, "quality check"))


class ResultIn(Api):
    line_id: str = Field(max_length=36)
    passed: int = Field(ge=0, le=10**9)
    failed: int = Field(0, ge=0, le=10**9)
    reason: str | None = Field(None, max_length=40)
    note: str | None = Field(None, max_length=300)


class DoneIn(Api):
    lines: list[ResultIn] = Field(min_length=1, max_length=500)
    notes: str | None = Field(None, max_length=2000)


@router.post("/quality-checks/{check_id}/done")
def finish_check(_: allowed("receiving.receive"), me: CurrentUser, db: DB, check_id: str, body: DoneIn, request: Request) -> dict:
    check = found(db, QualityCheck, check_id, "quality check")
    quality.done(db, me, check, {r.line_id: r.model_dump() for r in body.lines}, body.notes)
    audit(db, me, "quality_check.done", target=check.number, target_type="quality_check", target_id=check.id,
          fields=["passed", *(["failed"] if any(line.failed for line in check.lines) else [])])
    business_events.link(db, getattr(request.state, "company", None), business_events.ref("receipt", check.receipt.id, check.receipt.number),
                         business_events.ref("quality_check", check.id, check.number))
    db.commit()
    return quality.check_out(check)
