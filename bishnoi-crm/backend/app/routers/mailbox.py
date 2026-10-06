"""A person's own mailbox (app/mailbox.py), and sending an email to a customer
from it. What's sent is kept on the customer as an email activity."""

import html
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from pydantic import Field, field_validator

from app import mailbox as mb
from app.access import CurrentAccess
from app.api import Api, email_address, field_error, iso
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Activity, EmailTemplate, Mailbox, Team
from app.pricing import today
from app.routers.activities import activity_out, linked
from app.scope import within

router = APIRouter(tags=["mailbox"])


PROVIDER_NAMES = {**{k: p.name for k, p in mb.PROVIDERS.items()}, "smtp": "SMTP"}


def box_out(box: Mailbox) -> dict:
    return {
        "id": box.id, "provider": box.provider, "providerName": PROVIDER_NAMES.get(box.provider, box.provider), "address": box.address,
        "isDefault": box.is_default, "connectedAt": iso(box.connected_at), "lastError": box.last_error,
    }


def mailbox_out(db, settings, user_id: str) -> dict:
    """The person's mailboxes (the default first), and the providers they can sign in with."""
    return {
        "mailboxes": [box_out(b) for b in mb.mailboxes(db, user_id)],
        "providers": [{"key": k, "name": p.name, "ready": mb.registration(db, settings, k) is not None} for k, p in mb.PROVIDERS.items()],
    }


@router.get("/mailbox")
def read_mailbox(me: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    return mailbox_out(db, settings, me.id)


def own_box(db, user_id: str, box_id: str) -> Mailbox:
    box = db.get(Mailbox, box_id)
    if box is None or box.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such mailbox of yours.")
    return box


@router.get("/mailbox/detect")
def detect_mailbox(me: CurrentUser, db: DB, settings: SettingsDep, address: str = Query(min_length=3, max_length=254)) -> dict:
    """What connecting this address takes (app/mailbox.py detect): a sign-in, or a password."""
    try:
        clean = email_address(address)
    except ValueError as e:
        raise field_error("address", str(e)) from None
    return {"address": clean, **mb.detect(db, settings, clean)}


class StartIn(Api):
    provider: Literal["gmail", "outlook", "zoho_mail"]


@router.post("/mailbox/start")
def start(me: CurrentUser, db: DB, settings: SettingsDep, body: StartIn) -> dict:
    """Where to send the person to sign in with their provider."""
    try:
        return {"url": mb.sign_in_url(db, settings, me.id, body.provider)}
    except mb.MailboxError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


class FinishIn(Api):
    state: str = Field(max_length=2000)
    code: str = Field(min_length=1, max_length=4000)


@router.post("/mailbox/finish")
def finish(me: CurrentUser, db: DB, settings: SettingsDep, body: FinishIn) -> dict:
    """Back from the provider's sign-in: keeps the mailbox, for the person who started it only."""
    try:
        user_id, provider = mb.read_state(settings, body.state)
        if user_id != me.id:
            raise mb.MailboxError("That sign-in was started by someone else. Connect again from your own account.")
        box = mb.finish_sign_in(db, settings, me.id, provider, body.code)
    except mb.MailboxError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    box.connected_at = datetime.now(UTC)
    db.add(box)
    db.flush()
    audit(db, me, "mailbox.connected", target=f"{mb.PROVIDERS[provider].name}: {box.address}", target_type="mailbox", target_id=box.id)
    db.commit()
    return mailbox_out(db, settings, me.id)


class SmtpIn(Api):
    address: str = Field(max_length=254)
    host: str = Field(min_length=3, max_length=200)
    port: int = Field(ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=500)

    @field_validator("address")
    @classmethod
    def _address(cls, value: str) -> str:
        return email_address(value)


@router.put("/mailbox/smtp")
def connect_smtp(me: CurrentUser, db: DB, settings: SettingsDep, body: SmtpIn) -> dict:
    """Any other provider, by SMTP: signed in to once to check, then kept."""
    try:
        box = mb.connect_smtp(db, settings, me.id, body.model_dump())
    except mb.MailboxError as e:
        raise field_error("host", str(e)) from None
    box.connected_at = datetime.now(UTC)
    db.add(box)
    db.flush()
    audit(db, me, "mailbox.connected", target=f"SMTP: {box.address}", target_type="mailbox", target_id=box.id)
    db.commit()
    return mailbox_out(db, settings, me.id)


@router.put("/mailbox/{box_id}/default")
def make_default(me: CurrentUser, db: DB, settings: SettingsDep, box_id: str) -> dict:
    """The mailbox emails go from unless another is picked."""
    chosen = own_box(db, me.id, box_id)
    for b in mb.mailboxes(db, me.id):
        b.is_default = b.id == chosen.id
    db.commit()
    return mailbox_out(db, settings, me.id)


@router.delete("/mailbox/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(me: CurrentUser, db: DB, box_id: str) -> Response:
    box = own_box(db, me.id, box_id)
    audit(db, me, "mailbox.disconnected", target=box.address, target_type="mailbox", target_id=box.id)
    was_default = box.is_default
    db.delete(box)
    db.flush()
    # Another one becomes the default.
    left = mb.mailboxes(db, me.id)
    if was_default and left:
        left[0].is_default = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class EmailIn(Api):
    company_id: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    to: list[Annotated[str, Field(max_length=254)]] = Field(min_length=1, max_length=20)
    # Which of the person's mailboxes it goes from; their default when not given.
    mailbox_id: str | None = Field(None, max_length=36)
    # An approved template: its subject and wording are the template's, as approved;
    # only the personal note is the sender's own.
    template_id: str | None = Field(None, max_length=36)
    note: str | None = Field(None, max_length=5000)
    # Without a template: the sender's own email.
    subject: str | None = Field(None, max_length=200)
    body: str | None = Field(None, max_length=20000)

    @field_validator("to")
    @classmethod
    def _to(cls, value: list[str]) -> list[str]:
        return [email_address(v) for v in value]


# --- approved emails (Veeva): templates an administrator writes and approves -----------------


def offered(t: EmailTemplate, team_id: str | None, on: str) -> bool:
    return t.is_active and t.approved_on <= on and (not t.expires_on or t.expires_on >= on) and (not t.only_teams or team_id in t.only_teams)


def render(text: str, fill: dict[str, str]) -> str:
    for key, value in fill.items():
        text = text.replace("{" + key + "}", value)
    return text


def template_out(t: EmailTemplate, on: str) -> dict:
    return {
        "id": t.id, "name": t.name, "subject": t.subject, "body": t.body, "onlyTeams": t.only_teams or [],
        "approvedOn": t.approved_on, "expiresOn": t.expires_on, "isActive": t.is_active, "isCurrent": t.is_active and t.approved_on <= on and (not t.expires_on or t.expires_on >= on),
    }


@router.get("/email-templates")
def list_templates(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, everything: bool = Query(False, alias="all")) -> list[dict]:
    """The approved emails this person may send; with `all`, an administrator sees every one."""
    on = today(settings.org_timezone)
    rows = db.scalars(select(EmailTemplate).order_by(EmailTemplate.name)).all()
    if not (everything and access.can("admin.settings")):
        rows = [t for t in rows if offered(t, me.team_id, on)]
    return [template_out(t, on) for t in rows]


class TemplateIn(Api):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    only_teams: list[Annotated[str, Field(max_length=36)]] = Field(default_factory=list, max_length=50)
    approved_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    expires_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_active: bool = True


def check_template(db, body: TemplateIn) -> None:
    if body.only_teams and len(set(db.scalars(select(Team.id).where(Team.id.in_(body.only_teams))))) != len(set(body.only_teams)):
        raise field_error("onlyTeams", "Pick teams from the list.")
    if body.expires_on and body.expires_on < body.approved_on:
        raise field_error("expiresOn", "It expires before it's approved.")


@router.post("/admin/email-templates", status_code=status.HTTP_201_CREATED)
def add_template(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, body: TemplateIn) -> dict:
    access.require("admin.settings")
    check_template(db, body)
    t = EmailTemplate(**body.model_dump())
    db.add(t)
    db.flush()
    audit(db, me, "email_template.added", target=t.name, target_type="settings", target_id=t.id)
    db.commit()
    return template_out(t, today(settings.org_timezone))


@router.put("/admin/email-templates/{template_id}")
def change_template(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, template_id: str, body: TemplateIn) -> dict:
    access.require("admin.settings")
    t = db.get(EmailTemplate, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such email.")
    check_template(db, body)
    for key, value in body.model_dump().items():
        setattr(t, key, value)
    audit(db, me, "email_template.changed", target=t.name, target_type="settings", target_id=t.id)
    db.commit()
    return template_out(t, today(settings.org_timezone))


def as_html(text: str) -> str:
    paragraphs = "".join(f'<p style="margin:0 0 12px">{html.escape(p).replace(chr(10), "<br>")}</p>' for p in text.strip().split("\n\n"))
    return f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#1f1f1f">{paragraphs}</div>'


@router.post("/email/send", status_code=status.HTTP_201_CREATED)
def send_email(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, body: EmailIn) -> dict:
    """Sends from the person's own mailbox, and keeps it on the customer as an email."""
    access.require("activities.create")
    company, contact = linked(db, access, body.company_id, body.contact_id)
    if body.mailbox_id:
        box = own_box(db, me.id, body.mailbox_id)
    else:
        box = next(iter(mb.mailboxes(db, me.id)), None)
    if box is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Connect your mailbox first (Account → Mailbox), so emails go out from your own address.")
    if body.template_id:
        template = db.get(EmailTemplate, body.template_id)
        if template is None or not offered(template, me.team_id, today(settings.org_timezone)):
            raise field_error("templateId", "Pick one of the approved emails.")
        fill = {"customer": company.name if company else "", "contact": contact.full_name if contact else "", "me": me.full_name}
        subject = render(template.subject, fill)
        text = render(template.body, fill)
        if body.note and body.note.strip():
            text = body.note.strip() + "\n\n" + text
    else:
        if not (body.subject and body.subject.strip()):
            raise field_error("subject", "Give it a subject.")
        if not (body.body and body.body.strip()):
            raise field_error("body", "Write the email.")
        subject, text = body.subject.strip(), body.body.strip()
    try:
        mb.send(db, settings, box, me.full_name, body.to, subject, text, as_html(text))
    except mb.MailboxError as e:
        db.commit()  # keeps what went wrong on the mailbox
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from None
    box.last_error = None
    now = datetime.now(UTC)
    activity = Activity(
        kind="email", subject=subject, body=f"From {box.address} ({PROVIDER_NAMES.get(box.provider, box.provider)}) to {', '.join(body.to)}\n\n{text}", at=now, done_at=now, direction="out",
        company_id=company.id if company else None, contact_id=contact.id if contact else None, owner_id=me.id, team_id=me.team_id, created_by_id=me.id,
    )
    db.add(activity)
    db.flush()
    audit(db, me, "email.sent", target=subject, target_type="activity", target_id=activity.id)
    db.commit()
    db.refresh(activity)
    return activity_out(activity, access)


@router.get("/emails")
def sent_emails(
    access: CurrentAccess,
    me: CurrentUser,
    db: DB,
    who: Literal["me", "all"] = "me",
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    """Emails sent: one's own, or (for a role that sees others') everyone's in reach. Newest first."""
    query = within(select(Activity), Activity, access).where(Activity.kind == "email", Activity.direction == "out")
    if who == "me":
        query = query.where(Activity.owner_id == me.id)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Activity.subject).like(like), func.lower(Activity.body).like(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Activity.at.desc()).limit(limit).offset(offset)).unique().all()
    return {"items": [activity_out(a, access) for a in rows], "total": total}
