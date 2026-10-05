"""Activity & audit: everything done on the platform, newest first.

One log, filed four ways (app/audit.py): administrative actions, security
events, support work, and what the platform did by itself. The screens filter
it by category, by who did it, by company, by application, or by words.
"""

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import func, or_, select

from app.api import iso
from app.deps import DB, CurrentUser
from app.models import AuditEntry

router = APIRouter(prefix="/platform/activity", tags=["activity"])

PAGE = 100


def entry_out(e: AuditEntry) -> dict:
    return {
        "id": e.id,
        "at": iso(e.created_at),
        "actor": e.actor,
        "actorId": e.actor_id,
        "action": e.action,
        "category": e.category,
        "targetType": e.target_type,
        "targetId": e.target_id,
        "target": e.target,
        "fields": e.fields or [],
        "companyId": e.company_id,
        "applicationId": e.application_id,
        "address": e.address,
    }


@router.get("")
def activity(
    db: DB,
    _: CurrentUser,
    category: str | None = None,
    actor: str | None = None,
    company_id: str | None = None,
    application_id: str | None = None,
    target_id: str | None = None,
    q: str | None = None,
    before: datetime | None = None,
) -> dict:
    """A page of the log. `before` (the last one's `at`) gets the next page."""
    query = select(AuditEntry).order_by(AuditEntry.created_at.desc())
    if category in ("admin", "security", "support", "system"):
        query = query.where(AuditEntry.category == category)
    if actor:
        query = query.where(or_(AuditEntry.actor_id == actor, func.lower(AuditEntry.actor) == actor.lower()))
    if company_id:
        query = query.where(AuditEntry.company_id == company_id)
    if application_id:
        query = query.where(AuditEntry.application_id == application_id)
    if target_id:
        query = query.where(AuditEntry.target_id == target_id)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(AuditEntry.target).like(like), func.lower(AuditEntry.action).like(like),
                                func.lower(AuditEntry.actor).like(like)))
    if before:
        query = query.where(AuditEntry.created_at < before)
    rows = db.scalars(query.limit(PAGE + 1)).all()
    actors = db.execute(select(AuditEntry.actor).where(AuditEntry.actor_id.is_not(None)).distinct().order_by(AuditEntry.actor)).scalars().all()
    return {"entries": [entry_out(e) for e in rows[:PAGE]], "more": len(rows) > PAGE, "actors": actors}
