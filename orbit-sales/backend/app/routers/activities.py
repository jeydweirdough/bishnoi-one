"""Activities: calls, meetings, emails, notes and tasks, about a company and/or
a contact (or neither, for a task of one's own).

Calls, emails and notes are logged once they've happened. Meetings and tasks
are planned for a time and stay open until they're marked done. Needs
activities.view / create / edit / delete, within the person's reach; a
company or contact linked to one must be within reach too.
"""

from datetime import UTC, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, as_utc, camel, changed, field_error, iso, not_found, person_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.models import PLANNED_KINDS, Activity, Company, Contact
from app.scope import owner_for, reaches, within

router = APIRouter(prefix="/activities", tags=["activities"])

View = Annotated[Access, Depends(require("activities.view"))]
Create = Annotated[Access, Depends(require("activities.create"))]
Edit = Annotated[Access, Depends(require("activities.edit"))]
Delete = Annotated[Access, Depends(require("activities.delete"))]

Kind = Literal["call", "meeting", "email", "note", "task"]
State = Literal["open", "overdue", "today", "upcoming", "done"]


class ActivityFields(Api):
    body: str | None = Field(None, max_length=10000)
    # A time with no zone is the company's own local time (what a form sends).
    at: datetime | None = None
    company_id: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    duration_minutes: int | None = Field(None, ge=0, le=24 * 60)
    direction: Literal["in", "out"] | None = None
    owner_id: str | None = Field(None, max_length=36)
    done: bool | None = None


class ActivityIn(ActivityFields):
    kind: Kind
    subject: str = Field(min_length=1, max_length=200)


class ActivityPatch(ActivityFields):
    subject: str | None = Field(None, min_length=1, max_length=200)


def to_utc(moment: datetime, settings: Settings) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(settings.org_timezone))
    return moment.astimezone(UTC)


def is_planned(activity: Activity) -> bool:
    return activity.kind in PLANNED_KINDS


def activity_out(activity: Activity, access: Access) -> dict:
    inside = reaches(activity, access)
    now = datetime.now(UTC)
    return {
        "id": activity.id,
        "kind": activity.kind,
        "subject": activity.subject,
        "body": activity.body,
        "at": iso(activity.at),
        "doneAt": iso(activity.done_at),
        "isPlanned": is_planned(activity),
        "isDone": activity.done_at is not None,
        "isOverdue": activity.done_at is None and as_utc(activity.at) < now,
        "durationMinutes": activity.duration_minutes,
        "direction": activity.direction,
        "company": {"id": activity.company.id, "name": activity.company.name} if activity.company else None,
        "contact": {"id": activity.contact.id, "name": activity.contact.full_name} if activity.contact else None,
        "owner": person_out(activity.owner),
        "createdAt": iso(activity.created_at),
        "can": {"edit": inside and access.can("activities.edit"), "delete": inside and access.can("activities.delete")},
    }


def get_activity(db: Session, access: Access, activity_id: str) -> Activity:
    activity = db.get(Activity, activity_id)
    if activity is None or not reaches(activity, access):
        raise not_found("activity")
    return activity


def linked(db: Session, access: Access, company_id: str | None, contact_id: str | None) -> tuple[Company | None, Contact | None]:
    """The company and contact an activity is about, both within reach. A contact
    in a company brings its company along; a contact in another one is refused."""
    contact = db.get(Contact, contact_id) if contact_id else None
    if contact_id and (contact is None or not reaches(contact, access)):
        raise field_error("contactId", "Pick a contact you can see.")
    if contact and contact.company_id and not company_id:
        company_id = contact.company_id
    company = db.get(Company, company_id) if company_id else None
    if company_id and (company is None or not reaches(company, access)):
        raise field_error("companyId", "Pick a company you can see.")
    if contact and company and contact.company_id and contact.company_id != company.id:
        raise field_error("contactId", f"{contact.full_name} is in another company.")
    return company, contact


def day_bounds(settings: Settings) -> tuple[datetime, datetime]:
    """Today, from midnight to midnight in the company's own timezone, as UTC."""
    zone = ZoneInfo(settings.org_timezone)
    today = datetime.now(zone).date()
    start = datetime.combine(today, time(), zone).astimezone(UTC)
    return start, start + timedelta(days=1)


def in_state(query: Select, state: State, settings: Settings) -> Select:
    now = datetime.now(UTC)
    start, end = day_bounds(settings)
    open_ = Activity.done_at.is_(None)
    return {
        "open": query.where(open_),
        "overdue": query.where(open_, Activity.at < now),
        "today": query.where(open_, Activity.at >= start, Activity.at < end),
        "upcoming": query.where(open_, Activity.at >= end),
        "done": query.where(Activity.done_at.is_not(None)),
    }[state]


def audit_label(activity: Activity) -> str:
    return f"{activity.kind}: {activity.subject}"


@router.get("")
def list_activities(
    access: View,
    db: DB,
    settings: SettingsDep,
    kind: Kind | None = None,
    company: str | None = Query(None, max_length=36),
    contact: str | None = Query(None, max_length=36),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    state: State | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Activity), Activity, access)
    if kind:
        query = query.where(Activity.kind == kind)
    if company:
        query = query.where(Activity.company_id == company)
    if contact:
        query = query.where(Activity.contact_id == contact)
    if owner:
        query = query.where(Activity.owner_id == (access.user_id if owner == "me" else owner))
    if state:
        query = in_state(query, state, settings)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    # What's still to do reads soonest first; what's done, newest first.
    order = Activity.at.asc() if state in ("open", "overdue", "today", "upcoming") else Activity.at.desc()
    items = db.scalars(query.order_by(order).limit(limit).offset(offset)).unique().all()
    return {"items": [activity_out(a, access) for a in items], "total": total}


@router.get("/summary")
def summary(access: View, db: DB, settings: SettingsDep, owner: str | None = Query("me", max_length=36)) -> dict:
    """How much is still to do: overdue, due today, coming up."""
    base = within(select(Activity), Activity, access)
    if owner and owner != "all":
        base = base.where(Activity.owner_id == (access.user_id if owner == "me" else owner))
    counts = {}
    for state in ("overdue", "today", "upcoming", "open"):
        counts[state] = db.scalar(select(func.count()).select_from(in_state(base, state, settings).subquery())) or 0
    return counts


@router.post("", status_code=status.HTTP_201_CREATED)
def create_activity(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: ActivityIn) -> dict:
    company, contact = linked(db, access, body.company_id, body.contact_id)
    owner = owner_for(db, access, body.owner_id)
    at = to_utc(body.at, settings) if body.at else datetime.now(UTC)
    planned = body.kind in PLANNED_KINDS
    activity = Activity(
        kind=body.kind,
        subject=body.subject,
        body=body.body,
        at=at,
        done_at=(datetime.now(UTC) if body.done else None) if planned else at,
        duration_minutes=body.duration_minutes if body.kind in ("call", "meeting") else None,
        direction=body.direction if body.kind in ("call", "email") else None,
        company_id=company.id if company else None,
        contact_id=contact.id if contact else None,
        owner_id=owner.id,
        team_id=owner.team_id,
        created_by_id=me.id,
    )
    db.add(activity)
    db.flush()
    audit(db, me, "activity.created", target=audit_label(activity), target_type="activity", target_id=activity.id)
    db.commit()
    db.refresh(activity)
    return activity_out(activity, access)


@router.patch("/{activity_id}")
def update_activity(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, activity_id: str, body: ActivityPatch) -> dict:
    activity = get_activity(db, access, activity_id)
    wanted = changed(body)
    if "subject" in wanted and wanted["subject"] is None:
        raise field_error("subject", "Say what it was.")
    if "company_id" in wanted or "contact_id" in wanted:
        company, contact = linked(
            db, access, wanted.get("company_id", activity.company_id), wanted.get("contact_id", activity.contact_id)
        )
        wanted["company_id"], wanted["contact_id"] = (company.id if company else None), (contact.id if contact else None)
    if "owner_id" in wanted:
        owner = owner_for(db, access, wanted.pop("owner_id"))
        if owner.id != activity.owner_id:
            wanted["owner_id"], wanted["team_id"] = owner.id, owner.team_id
    if "at" in wanted:
        if wanted["at"] is None:
            raise field_error("at", "Pick when.")
        wanted["at"] = to_utc(wanted["at"], settings)
    done = wanted.pop("done", None)

    fields = [k for k, v in wanted.items() if getattr(activity, k) != v]
    for key in fields:
        setattr(activity, key, wanted[key])
    if not is_planned(activity) and "at" in fields:
        activity.done_at = activity.at  # logged kinds are done when they happened
    action = "activity.updated"
    if done is not None and is_planned(activity) and done != (activity.done_at is not None):
        activity.done_at = datetime.now(UTC) if done else None
        if not fields:
            action = "activity.completed" if done else "activity.reopened"
        fields.append("done_at")
    if fields:
        audit(db, me, action, target=audit_label(activity), target_type="activity", target_id=activity.id, fields=camel([f for f in fields if f != "team_id"]))
        db.commit()
        db.refresh(activity)
    return activity_out(activity, access)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(access: Delete, me: CurrentUser, db: DB, activity_id: str) -> Response:
    activity = get_activity(db, access, activity_id)
    audit(db, me, "activity.deleted", target=audit_label(activity), target_type="activity", target_id=activity.id)
    db.delete(activity)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

