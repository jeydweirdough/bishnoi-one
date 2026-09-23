"""Bulk actions: one request for many records (up to 500).

Each answers with a job: how many were done, and which weren't and why. Every
record is checked on its own: within the person's reach, allowed by their
role, and still needing the change. The work runs within the request, so the
job comes back done; `/jobs/{id}` still answers for a little while after, for
pages that follow a job's progress.
"""

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time as clock
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import Access, CurrentAccess, require
from app.api import Api
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import PLANNED_KINDS, Activity, Company, Contact, User
from app.routers.customer_types import check_type
from app.scope import reachable_people, reaches

router = APIRouter(tags=["bulk actions"])

MAX_BULK = 500
Ids = Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]], Field(min_length=1, max_length=MAX_BULK)]

MISSING = "Not found, or outside what you can see."
NOT_ALLOWED = "Your role doesn't allow that."

# --- jobs ---------------------------------------------------------------------------------

KEEP_SECONDS = 3600
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def finish(owner_id: str, label: str, ids: list[str], failures: list[tuple[str, str]]) -> dict:
    """A job, already done, kept for an hour so its page can read it back."""
    job = {
        "id": uuid.uuid4().hex,
        "label": label,
        "status": "done",
        "total": len(ids),
        "processed": len(ids),
        "succeeded": len(ids) - len(failures),
        "failed": len(failures),
        "failures": [{"id": i, "error": e} for i, e in failures[:50]],
    }
    with _lock:
        now = time.time()
        for key in [k for k, (_, at, _) in _jobs.items() if now - at > KEEP_SECONDS]:
            del _jobs[key]
        _jobs[job["id"]] = (owner_id, now, job)
    return job


@router.get("/jobs/{job_id}")
def job_progress(job_id: str, me: CurrentUser) -> dict:
    with _lock:
        entry = _jobs.get(job_id)
    if entry is None or entry[0] != me.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That job is finished and forgotten, or isn't yours.")
    return entry[2]


def each(ids: list[str], work: Callable[[str], str | None]) -> list[tuple[str, str]]:
    """Runs `work` on every id once, in order; collects why any couldn't be done."""
    failures = []
    for item_id in dict.fromkeys(ids):
        reason = work(item_id)
        if reason:
            failures.append((item_id, reason))
    return failures


def assignee(db: Session, access: Access, user_id: str | None) -> User | None:
    """Someone this person may give things to, or None."""
    reachable = {u.id: u for u in reachable_people(db, access)}
    return reachable.get(user_id or access.user_id)


def due_at(on: str, settings) -> datetime:
    """A due date ("2026-09-30") as nine in the morning where the company is."""
    day = datetime.strptime(on, "%Y-%m-%d").date()
    return datetime.combine(day, clock(9), ZoneInfo(settings.org_timezone)).astimezone(UTC)


class FollowUpIn(Api):
    title: str = Field(min_length=2, max_length=160)
    due_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


# --- companies and contacts ------------------------------------------------------------------


class RecordsBulkIn(Api):
    ids: Ids
    action: Literal["status", "owner", "follow_up", "delete"]
    status: str | None = Field(None, max_length=40)
    owner_id: str | None = Field(None, max_length=36)
    follow_up: FollowUpIn | None = None
    # Follow-ups: for each record's owner, or for the person asking.
    to_owner: bool = True


def bulk_records(
    model: type[Company] | type[Contact],
    noun: str,
    body: RecordsBulkIn,
    access: Access,
    me: User,
    db: Session,
    settings,
) -> dict:
    permission = {"status": "customers.edit", "owner": "customers.edit", "follow_up": "activities.create", "delete": "customers.delete"}[body.action]
    if not access.can(permission):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_ALLOWED)
    if body.action == "status" and (model is not Company or body.status is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a type for the customers.")
    if body.action == "status":
        check_type(db, body.status)
    new_owner = None
    if body.action == "owner":
        new_owner = assignee(db, access, body.owner_id)
        if new_owner is None or not body.owner_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick someone you can give records to.")
    if body.action == "follow_up" and body.follow_up is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Give the follow-up a title and a date.")

    records = {r.id: r for r in db.scalars(select(model).where(model.id.in_(body.ids))).unique()}
    contacts_in = {}
    if model is Company and body.action == "delete":
        contacts_in = dict(db.execute(select(Contact.company_id, func.count()).where(Contact.company_id.in_(body.ids)).group_by(Contact.company_id)).all())

    def work(record_id: str) -> str | None:
        record = records.get(record_id)
        if record is None or not reaches(record, access):
            return MISSING
        name = record.name if model is Company else record.full_name
        if body.action == "status":
            if record.status != body.status:
                record.status = body.status
                audit(db, me, f"{noun}.updated", target=name, target_type=noun, target_id=record.id, fields=["status"])
        elif body.action == "owner":
            if record.owner_id != new_owner.id:
                record.owner_id, record.team_id = new_owner.id, new_owner.team_id
                audit(db, me, f"{noun}.updated", target=name, target_type=noun, target_id=record.id, fields=["ownerId"])
        elif body.action == "follow_up":
            owner = assignee(db, access, record.owner_id if body.to_owner else None)
            if owner is None:
                return "Its owner is outside what you can give tasks to."
            task = Activity(
                kind="task", subject=body.follow_up.title, at=due_at(body.follow_up.due_on, settings),
                company_id=record.id if model is Company else record.company_id,
                contact_id=record.id if model is Contact else None,
                owner_id=owner.id, team_id=owner.team_id, created_by_id=me.id,
            )
            db.add(task)
            db.flush()
            audit(db, me, "activity.created", target=f"task: {task.subject}", target_type="activity", target_id=task.id)
        elif body.action == "delete":
            if contacts_in.get(record.id):
                return "It still has contacts. Move or delete them first."
            if model is Contact:
                db.query(Activity).filter(Activity.contact_id == record.id, Activity.company_id.is_(None)).delete()
            audit(db, me, f"{noun}.deleted", target=name, target_type=noun, target_id=record.id)
            db.delete(record)
        return None

    failures = each(body.ids, work)
    db.commit()
    labels = {"status": "Set status", "owner": "Change owner", "follow_up": "Add follow-ups", "delete": "Delete"}
    return finish(me.id, labels[body.action], body.ids, failures)


@router.post("/companies/bulk")
def bulk_companies(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, body: RecordsBulkIn) -> dict:
    return bulk_records(Company, "company", body, access, me, db, settings)


@router.post("/contacts/bulk")
def bulk_contacts(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, body: RecordsBulkIn) -> dict:
    return bulk_records(Contact, "contact", body, access, me, db, settings)


# --- follow-ups (meetings and tasks) -----------------------------------------------------------------


class ActivitiesBulkIn(Api):
    ids: Ids
    action: Literal["done", "open", "due", "assign"]
    due_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    assignee_id: str | None = Field(None, max_length=36)


@router.post("/activities/bulk")
def bulk_activities(
    access: Annotated[Access, Depends(require("activities.edit"))], me: CurrentUser, db: DB, settings: SettingsDep, body: ActivitiesBulkIn
) -> dict:
    if body.action == "due" and not body.due_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick the new date.")
    person = assignee(db, access, body.assignee_id) if body.action == "assign" else None
    if body.action == "assign" and (person is None or not body.assignee_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick someone you can give tasks to.")
    found = {a.id: a for a in db.scalars(select(Activity).where(Activity.id.in_(body.ids))).unique()}
    now = datetime.now(UTC)

    def work(activity_id: str) -> str | None:
        a = found.get(activity_id)
        if a is None or not reaches(a, access):
            return MISSING
        if a.kind not in PLANNED_KINDS:
            return "Only meetings and tasks can be done, moved or reassigned."
        label = f"{a.kind}: {a.subject}"
        if body.action in ("done", "open"):
            wanted = body.action == "done"
            if (a.done_at is not None) != wanted:
                a.done_at = now if wanted else None
                audit(db, me, "activity.completed" if wanted else "activity.reopened", target=label, target_type="activity", target_id=a.id)
        elif body.action == "due":
            local = a.at.replace(tzinfo=UTC) if a.at.tzinfo is None else a.at
            keep_time = local.astimezone(ZoneInfo(settings.org_timezone)).time()
            day = datetime.strptime(body.due_on, "%Y-%m-%d").date()
            a.at = datetime.combine(day, keep_time, ZoneInfo(settings.org_timezone)).astimezone(UTC)
            audit(db, me, "activity.updated", target=label, target_type="activity", target_id=a.id, fields=["at"])
        elif body.action == "assign" and a.owner_id != person.id:
            a.owner_id, a.team_id = person.id, person.team_id
            audit(db, me, "activity.updated", target=label, target_type="activity", target_id=a.id, fields=["ownerId"])
        return None

    failures = each(body.ids, work)
    db.commit()
    labels = {"done": "Mark done", "open": "Reopen", "due": "Move date", "assign": "Reassign"}
    return finish(me.id, labels[body.action], body.ids, failures)

