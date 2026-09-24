"""Communications: announcements, system notifications and maintenance
notices, each for everyone, one company, or one application's users.

A notice is a draft until published, and shows from its start until its end
(a maintenance window, or open-ended). The applications read what's showing
from /public/notices (app/routers/public.py); writing notices takes a
Platform Admin.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api import Api, as_utc, camel, changed, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser
from app.models import Announcement, Application, Company

router = APIRouter(prefix="/platform/announcements", tags=["communications"])

Kind = Literal["announcement", "notification", "maintenance"]
Level = Literal["info", "warning", "critical"]


class NoticeIn(Api):
    kind: Kind = "announcement"
    level: Level = "info"
    title: str = Field(min_length=3, max_length=200)
    body: str | None = Field(None, max_length=10000)
    company_id: str | None = None
    application_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    publish: bool = False

    @model_validator(mode="after")
    def _window(self):
        if self.kind == "maintenance" and (self.starts_at is None or self.ends_at is None):
            raise ValueError("A maintenance notice needs its start and its end.")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("It has to end after it starts.")
        return self


class NoticePatch(Api):
    level: Level | None = None
    title: str | None = Field(None, min_length=3, max_length=200)
    body: str | None = Field(None, max_length=10000)
    company_id: str | None = None
    application_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    publish: bool | None = None


def state_of(n: Announcement, now: datetime | None = None) -> str:
    """draft, scheduled, showing or ended."""
    now = now or datetime.now(UTC)
    if n.published_at is None:
        return "draft"
    if as_utc(n.starts_at) > now:
        return "scheduled"
    if n.ends_at and as_utc(n.ends_at) <= now:
        return "ended"
    return "showing"


def notice_out(n: Announcement, names: dict[str, str]) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "level": n.level,
        "title": n.title,
        "body": n.body,
        "company": {"id": n.company_id, "name": names.get(n.company_id, "")} if n.company_id else None,
        "application": {"id": n.application_id, "name": names.get(n.application_id, "")} if n.application_id else None,
        "startsAt": iso(n.starts_at),
        "endsAt": iso(n.ends_at),
        "publishedAt": iso(n.published_at),
        "state": state_of(n),
        "createdBy": n.created_by,
        "updatedAt": iso(n.updated_at),
    }


def names_for(db: Session, notices: list[Announcement]) -> dict[str, str]:
    names: dict[str, str] = {}
    companies = {n.company_id for n in notices if n.company_id}
    apps = {n.application_id for n in notices if n.application_id}
    if companies:
        names.update(db.execute(select(Company.id, Company.name).where(Company.id.in_(companies))).all())
    if apps:
        names.update(db.execute(select(Application.id, Application.name).where(Application.id.in_(apps))).all())
    return names


def _check(db: Session, fields: dict) -> None:
    if fields.get("company_id") and db.get(Company, fields["company_id"]) is None:
        raise field_error("companyId", "That company doesn't exist.")
    if fields.get("application_id") and db.get(Application, fields["application_id"]) is None:
        raise field_error("applicationId", "That application doesn't exist.")


def _notice(db: Session, notice_id: str) -> Announcement:
    n = db.get(Announcement, notice_id)
    if n is None:
        raise not_found("notice")
    return n


@router.get("")
def list_notices(db: DB, _: CurrentUser, kind: str | None = None, state: str | None = None) -> dict:
    query = select(Announcement).order_by(Announcement.starts_at.desc()).limit(300)
    if kind in ("announcement", "notification", "maintenance"):
        query = query.where(Announcement.kind == kind)
    notices = db.scalars(query).all()
    if state:
        notices = [n for n in notices if state_of(n) == state]
    names = names_for(db, notices)
    return {"notices": [notice_out(n, names) for n in notices]}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_notice(body: NoticeIn, db: DB, me: AdminUser) -> dict:
    fields = body.model_dump()
    _check(db, fields)
    publish = fields.pop("publish")
    now = datetime.now(UTC)
    fields["starts_at"] = fields["starts_at"] or now
    n = Announcement(**fields, published_at=now if publish else None, created_by=me.email, created_at=now, updated_at=now)
    db.add(n)
    db.flush()
    audit(db, me, f"{n.kind}.{'published' if publish else 'drafted'}", target=n.title, target_type="notice", target_id=n.id,
          company_id=n.company_id, application_id=n.application_id)
    db.commit()
    return {"notice": notice_out(n, names_for(db, [n]))}


@router.patch("/{notice_id}")
def update_notice(notice_id: str, body: NoticePatch, db: DB, me: AdminUser) -> dict:
    n = _notice(db, notice_id)
    fields = changed(body)
    _check(db, fields)
    publish = fields.pop("publish", None)
    for required in ("level", "title", "starts_at"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    fields = {k: v for k, v in fields.items() if getattr(n, k) != v}
    for name, value in fields.items():
        setattr(n, name, value)
    if n.ends_at and as_utc(n.ends_at) <= as_utc(n.starts_at):
        raise field_error("endsAt", "It has to end after it starts.")
    if n.kind == "maintenance" and n.ends_at is None:
        raise field_error("endsAt", "A maintenance notice needs its end.")
    action = "updated"
    if publish is True and n.published_at is None:
        n.published_at, action = datetime.now(UTC), "published"
    elif publish is False and n.published_at is not None:
        n.published_at, action = None, "withdrawn"
    if fields or action != "updated":
        n.updated_at = datetime.now(UTC)
        audit(db, me, f"{n.kind}.{action}", target=n.title, target_type="notice", target_id=n.id,
              company_id=n.company_id, application_id=n.application_id, fields=camel(fields))
    db.commit()
    return {"notice": notice_out(n, names_for(db, [n]))}


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(notice_id: str, db: DB, me: AdminUser) -> Response:
    n = _notice(db, notice_id)
    audit(db, me, f"{n.kind}.deleted", target=n.title, target_type="notice", target_id=n.id)
    db.delete(n)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def showing(db: Session, application_key: str | None = None, company_slug: str | None = None) -> list[Announcement]:
    """Published notices showing now or coming up, for one app and company."""
    now = datetime.now(UTC)
    query = select(Announcement).where(Announcement.published_at.is_not(None), or_(Announcement.ends_at.is_(None), Announcement.ends_at > now))
    app = db.scalar(select(Application).where(Application.key == application_key)) if application_key else None
    company = db.scalar(select(Company).where(Company.slug == company_slug)) if company_slug else None
    query = query.where(or_(Announcement.application_id.is_(None), Announcement.application_id == (app.id if app else None)))
    query = query.where(or_(Announcement.company_id.is_(None), Announcement.company_id == (company.id if company else None)))
    return list(db.scalars(query.order_by(Announcement.starts_at)))
