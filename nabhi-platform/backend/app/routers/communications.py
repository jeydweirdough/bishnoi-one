"""Communications: announcements, system notifications and maintenance
notices, each for everyone, one company, or one application's users.

A notice is a draft until published, and shows from its start until its end
(a maintenance window, or open-ended). The applications read what's showing
from /public/notices (app/routers/public.py); writing notices takes a
Platform Admin.

They're kept in Discord, not in the database: app/announcements.py. Each has
an id like ANN-20260926-0001 and its own thread in the announcements channel.
"""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.announcements import Notices, next_id, remove, save, state_of, when
from app.api import Api, camel, changed, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import Application, Company

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


SNAKE_TO_ROW = {"level": "level", "title": "title", "body": "body", "company_id": "companyId", "application_id": "applicationId",
                "starts_at": "startsAt", "ends_at": "endsAt"}


def notice_out(n: dict, names: dict[str, str]) -> dict:
    return {
        "id": n["id"],
        "kind": n["kind"],
        "level": n["level"],
        "title": n["title"],
        "body": n.get("body"),
        "company": {"id": n["companyId"], "name": names.get(n["companyId"], "")} if n.get("companyId") else None,
        "application": {"id": n["applicationId"], "name": names.get(n["applicationId"], "")} if n.get("applicationId") else None,
        "startsAt": n["startsAt"],
        "endsAt": n.get("endsAt"),
        "publishedAt": n.get("publishedAt"),
        "state": state_of(n),
        "createdBy": n.get("createdBy"),
        "updatedAt": n.get("updatedAt"),
    }


def names_for(db: Session, notices: list[dict]) -> dict[str, str]:
    names: dict[str, str] = {}
    companies = {n["companyId"] for n in notices if n.get("companyId")}
    apps = {n["applicationId"] for n in notices if n.get("applicationId")}
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


def _notice(notices, notice_id: str) -> dict:
    n = notices.get(notice_id)
    if n is None:
        raise not_found("notice")
    return dict(n)


@router.get("")
def list_notices(db: DB, notices: Notices, _: CurrentUser, kind: str | None = None, state: str | None = None) -> dict:
    rows = sorted(notices.all(), key=lambda n: n["startsAt"], reverse=True)
    if kind in ("announcement", "notification", "maintenance"):
        rows = [n for n in rows if n["kind"] == kind]
    if state:
        rows = [n for n in rows if state_of(n) == state]
    rows = rows[:300]
    names = names_for(db, rows)
    return {"notices": [notice_out(n, names) for n in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_notice(body: NoticeIn, db: DB, notices: Notices, me: AdminUser, settings: SettingsDep) -> dict:
    fields = body.model_dump()
    _check(db, fields)
    publish = fields.pop("publish")
    now = datetime.now(UTC)
    n = {
        "id": next_id(notices, settings), "kind": fields["kind"], "level": fields["level"], "title": fields["title"],
        "body": fields["body"], "companyId": fields["company_id"], "applicationId": fields["application_id"],
        "startsAt": iso(fields["starts_at"] or now), "endsAt": iso(fields["ends_at"]), "publishedAt": iso(now) if publish else None,
        "createdBy": me.email, "createdAt": iso(now), "updatedAt": iso(now),
    }
    save(notices, n["id"], n)
    audit(db, me, f"{n['kind']}.{'published' if publish else 'drafted'}", target=n["title"], target_type="notice", target_id=n["id"],
          company_id=n["companyId"], application_id=n["applicationId"])
    db.commit()
    return {"notice": notice_out(n, names_for(db, [n]))}


@router.patch("/{notice_id}")
def update_notice(notice_id: str, body: NoticePatch, db: DB, notices: Notices, me: AdminUser) -> dict:
    n = _notice(notices, notice_id)
    fields = changed(body)
    _check(db, fields)
    publish = fields.pop("publish", None)
    for required in ("level", "title", "starts_at"):
        if required in fields and fields[required] is None:
            raise field_error(required, "This can't be empty.")
    values = {k: (iso(v) if isinstance(v, datetime) else v) for k, v in fields.items()}
    values = {k: v for k, v in values.items() if n.get(SNAKE_TO_ROW[k]) != v}
    for name, value in values.items():
        n[SNAKE_TO_ROW[name]] = value
    if n.get("endsAt") and when(n["endsAt"]) <= when(n["startsAt"]):
        raise field_error("endsAt", "It has to end after it starts.")
    if n["kind"] == "maintenance" and not n.get("endsAt"):
        raise field_error("endsAt", "A maintenance notice needs its end.")
    action = "updated"
    if publish is True and not n.get("publishedAt"):
        n["publishedAt"], action = iso(datetime.now(UTC)), "published"
    elif publish is False and n.get("publishedAt"):
        n["publishedAt"], action = None, "withdrawn"
    if values or action != "updated":
        n["updatedAt"] = iso(datetime.now(UTC))
        save(notices, n["id"], n)
        audit(db, me, f"{n['kind']}.{action}", target=n["title"], target_type="notice", target_id=n["id"],
              company_id=n.get("companyId"), application_id=n.get("applicationId"), fields=camel(values))
        db.commit()
    return {"notice": notice_out(n, names_for(db, [n]))}


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notice(notice_id: str, db: DB, notices: Notices, me: AdminUser) -> Response:
    n = _notice(notices, notice_id)
    remove(notices, notice_id)
    audit(db, me, f"{n['kind']}.deleted", target=n["title"], target_type="notice", target_id=n["id"])
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def showing(db: Session, notices, application_key: str | None = None, company_slug: str | None = None) -> list[dict]:
    """Published notices showing now or coming up, for one app and company."""
    now = datetime.now(UTC)
    app = db.scalar(select(Application).where(Application.key == application_key)) if application_key else None
    company = db.scalar(select(Company).where(Company.slug == company_slug)) if company_slug else None
    found = [
        n for n in notices.all()
        if n.get("publishedAt") and (not n.get("endsAt") or when(n["endsAt"]) > now)
        and n.get("applicationId") in (None, app.id if app else None)
        and n.get("companyId") in (None, company.id if company else None)
    ]
    return sorted(found, key=lambda n: n["startsAt"])
