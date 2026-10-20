"""The lead inbox (decided 2026-10-19): people who reached the company on its own
channels wait here until someone adds them to the customers.

The channels are connected on Bishnoi One Platform (Companies → the company →
Connections), like Zoho Books and the mail providers; each gives the CRM the
secret it signs its calls with. Each channel calls the CRM's own address for it,
with the company's short name:

    /hooks/facebook?company=getmeds   Facebook lead forms and Messenger (Meta)
    /hooks/whatsapp?company=getmeds   WhatsApp Business, Cloud API (Meta)
    /hooks/viber?company=getmeds      a Viber bot
    /hooks/tawkto?company=getmeds     Tawk.to chats and tickets on the website
    /hooks/form?company=getmeds       the website's own forms, or Make or Zapier

A call that isn't signed with the company's secret is refused, and a channel
that isn't connected isn't there at all. What comes in is data, never
instructions: only the known fields are kept, cut to size. More messages from
the same sender while their lead waits join it.

The screens: GET /inbox (by status and channel), GET /inbox/{id} (with the
customers it looks like), POST /inbox/{id}/add (a new customer, or one already
in the CRM), /dismiss and /reopen. Handling it is customers.inbox.
"""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import connections as svc
from app.access import Access, require
from app.api import Api, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.extra import check_required
from app.models import Activity, Company, Contact, InboxLead
from app.routers.customer_types import first_type
from app.routers.deals import deal_lists
from app.routers.duplicates import LINE, score
from app.routers.lead_finder import offered_types
from app.routers.sharing import shown_to

log = logging.getLogger(__name__)

hooks = APIRouter(prefix="/hooks", tags=["inbox"])
router = APIRouter(prefix="/inbox", tags=["inbox"])

Handle = Annotated[Access, Depends(require("customers.inbox"))]

GRAPH = "https://graph.facebook.com/v21.0"
MAX_BODY = 256 * 1024
MAX_MESSAGES = 30
REPLY_WITHIN_HOURS = 4

# The channels, as the screens name them, and the Platform service each comes from.
CHANNELS = {
    "facebook": ("Facebook lead form", "facebook"),
    "messenger": ("Messenger", "facebook"),
    "whatsapp": ("WhatsApp", "whatsapp"),
    "viber": ("Viber", "viber"),
    "tawkto": ("Tawk.to", "tawkto"),
    "form": ("Website form", "web_forms"),
}
# Where each service calls: the hook's path.
HOOKS = {"facebook": "facebook", "whatsapp": "whatsapp", "viber": "viber", "tawkto": "tawkto", "web_forms": "form"}
# The lead source a new customer gets, when the company's list has it (Settings → Deals).
SOURCES = {"facebook": "Facebook", "messenger": "Facebook", "whatsapp": "WhatsApp", "viber": "Viber", "tawkto": "Website", "form": "Website"}


# --- keeping what came in ---------------------------------------------------------------


def cut(value: object, size: int) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text[:size] or None


def take(
    db: Session,
    channel: str,
    *,
    sender: str | None,
    name: str | None,
    text: str | None = None,
    message_id: str | None = None,
    business: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    city: str | None = None,
    details: dict | None = None,
    at: datetime | None = None,
) -> InboxLead | None:
    """Keeps what came in: on the sender's lead while it waits, or as a new one.
    None when it was already kept (a channel sending the same thing again)."""
    at = at or datetime.now(UTC)
    sender = cut(sender, 120)
    lead = None
    if sender:
        lead = db.scalars(select(InboxLead).where(InboxLead.channel == channel, InboxLead.sender == sender, InboxLead.status == "new")).first()
    if message_id and lead is not None and any(m.get("id") == message_id for m in lead.messages):
        return None
    message = {"at": iso(at), "text": cut(text, 2000)} | ({"id": message_id[:120]} if message_id else {})
    if lead is None:
        lead = InboxLead(channel=channel, sender=sender, name=cut(name, 160) or CHANNELS[channel][0] + " contact", messages=[], details={}, received_at=at, last_at=at)
        db.add(lead)
    elif name and lead.name.endswith(" contact"):
        lead.name = cut(name, 160)
    for attr, value, size in (("business", business, 160), ("phone", phone, 40), ("email", email, 254), ("city", city, 80)):
        if value and not getattr(lead, attr):
            setattr(lead, attr, cut(value, size))
    if message["text"]:
        lead.messages = [*lead.messages, message][-MAX_MESSAGES:]
    if details:
        lead.details = {**lead.details, **{cut(k, 60): cut(v, 300) for k, v in details.items() if cut(k, 60) and cut(v, 300)}}
    lead.last_at = at
    return lead


# --- the hooks --------------------------------------------------------------------------


def secrets_of(settings, service: str) -> dict:
    """The channel's details from the platform, or 404: a channel that isn't connected isn't there."""
    found = svc.service(settings, service)
    if not found:
        raise HTTPException(404, "Not found")
    return found


async def raw(request: Request) -> bytes:
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(413, "Too large")
    return body


def signed(secret: str | None, body: bytes, given: str | None, algo=hashlib.sha256, prefix: str = "") -> bool:
    if not secret or not given:
        return False
    expected = prefix + hmac.new(secret.encode(), body, algo).hexdigest()
    return hmac.compare_digest(expected, given.strip())


def as_json(body: bytes) -> dict:
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        raise HTTPException(400, "Not JSON") from None
    if not isinstance(data, dict):
        raise HTTPException(400, "Not JSON")
    return data


def when(seconds: object) -> datetime:
    try:
        n = float(seconds)  # Meta and Viber send seconds or milliseconds
        return datetime.fromtimestamp(n / 1000 if n > 1e11 else n, UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.now(UTC)


def verify_meta(service: str, settings, request: Request) -> Response:
    """Meta's handshake when the address is first given to it: echo the challenge when the token matches."""
    found = secrets_of(settings, service)
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and found.get("verify_token") and hmac.compare_digest(q.get("hub.verify_token") or "", found["verify_token"]):
        return Response(q.get("hub.challenge") or "", media_type="text/plain")
    raise HTTPException(403, "Wrong verify token")


def graph(path: str, token: str | None, **params) -> dict | None:
    if not token:
        return None
    try:
        r = httpx.get(f"{GRAPH}/{path}", params={**params, "access_token": token}, timeout=5)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


FORM_FIELDS = {
    "full_name": "name", "name": "name", "first_name": "first", "last_name": "last", "phone_number": "phone", "phone": "phone",
    "email": "email", "company_name": "business", "company": "business", "city": "city",
}


@hooks.get("/facebook")
def facebook_handshake(request: Request, settings: SettingsDep) -> Response:
    return verify_meta("facebook", settings, request)


@hooks.post("/facebook")
async def facebook(request: Request, settings: SettingsDep, db: DB) -> dict:
    found = secrets_of(settings, "facebook")
    body = await raw(request)
    if not signed(found.get("app_secret"), body, request.headers.get("x-hub-signature-256"), prefix="sha256="):
        raise HTTPException(401, "Not signed")
    data = as_json(body)
    token = found.get("page_access_token")
    page = str(found.get("page_id") or "")
    for entry in data.get("entry") or []:
        if page and str(entry.get("id")) != page:
            continue
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            if change.get("field") != "leadgen" or not value.get("leadgen_id"):
                continue
            lead_id = str(value["leadgen_id"])
            if db.scalar(select(InboxLead.id).where(InboxLead.channel == "facebook", InboxLead.sender == f"lead:{lead_id}")):
                continue
            got = graph(lead_id, token) or {}
            fields: dict[str, str] = {}
            extra: dict[str, str] = {}
            for item in got.get("field_data") or []:
                key, values = str(item.get("name") or ""), item.get("values") or []
                text = ", ".join(str(v) for v in values)
                (fields.__setitem__(FORM_FIELDS[key], text) if key in FORM_FIELDS else extra.__setitem__(key.replace("_", " ").capitalize(), text))
            name = fields.get("name") or " ".join(x for x in (fields.get("first"), fields.get("last")) if x)
            take(
                db, "facebook", sender=f"lead:{lead_id}", name=name or "Facebook lead", business=fields.get("business"),
                phone=fields.get("phone"), email=fields.get("email"), city=fields.get("city"),
                text=None if got else "Facebook didn't give the form's answers: check the page access token on Platform.",
                details={"Form": value.get("form_id"), "Ad": value.get("ad_id"), **extra}, at=when(value.get("created_time")),
            )
        for event in entry.get("messaging") or []:
            message = event.get("message") or {}
            psid = str((event.get("sender") or {}).get("id") or "")
            if not psid or message.get("is_echo") or psid == page:
                continue
            text = message.get("text") or ("[attachment]" if message.get("attachments") else None)
            known = db.scalar(select(InboxLead.id).where(InboxLead.channel == "messenger", InboxLead.sender == psid, InboxLead.status == "new"))
            who = None if known else graph(psid, token, fields="first_name,last_name")
            name = " ".join(x for x in ((who or {}).get("first_name"), (who or {}).get("last_name")) if x)
            take(db, "messenger", sender=psid, name=name or None, text=text, message_id=message.get("mid"), at=when(event.get("timestamp")))
    db.commit()
    return {"ok": True}


@hooks.get("/whatsapp")
def whatsapp_handshake(request: Request, settings: SettingsDep) -> Response:
    return verify_meta("whatsapp", settings, request)


@hooks.post("/whatsapp")
async def whatsapp(request: Request, settings: SettingsDep, db: DB) -> dict:
    found = secrets_of(settings, "whatsapp")
    body = await raw(request)
    if not signed(found.get("app_secret"), body, request.headers.get("x-hub-signature-256"), prefix="sha256="):
        raise HTTPException(401, "Not signed")
    data = as_json(body)
    number = str(found.get("phone_number_id") or "")
    for entry in data.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            if change.get("field") != "messages" or (number and str((value.get("metadata") or {}).get("phone_number_id")) != number):
                continue
            names = {str(c.get("wa_id")): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
            for m in value.get("messages") or []:
                sender = str(m.get("from") or "")
                if not sender:
                    continue
                kind = m.get("type")
                text = (m.get("text") or {}).get("body") if kind == "text" else (m.get(kind) or {}).get("caption") or f"[{kind}]"
                take(db, "whatsapp", sender=sender, name=names.get(sender), phone="+" + sender.lstrip("+"), text=text, message_id=m.get("id"), at=when(m.get("timestamp")))
    db.commit()
    return {"ok": True}


@hooks.post("/viber")
async def viber(request: Request, settings: SettingsDep, db: DB) -> dict:
    found = secrets_of(settings, "viber")
    body = await raw(request)
    if not signed(found.get("auth_token"), body, request.headers.get("x-viber-content-signature")):
        raise HTTPException(401, "Not signed")
    data = as_json(body)
    event = data.get("event")
    person = data.get("sender") or data.get("user") or {}
    if event in ("message", "conversation_started") and person.get("id"):
        message = data.get("message") or {}
        text = message.get("text") if message.get("type") == "text" else (f"[{message.get('type')}]" if message else "Started a conversation")
        take(db, "viber", sender=str(person["id"]), name=person.get("name"), text=text, message_id=str(data.get("message_token") or "") or None, at=when(data.get("timestamp")))
        db.commit()
    return {"ok": True}


@hooks.post("/tawkto")
async def tawkto(request: Request, settings: SettingsDep, db: DB) -> dict:
    found = secrets_of(settings, "tawkto")
    body = await raw(request)
    if not signed(found.get("webhook_secret"), body, request.headers.get("x-tawk-signature"), algo=hashlib.sha1):
        raise HTTPException(401, "Not signed")
    data = as_json(body)
    event = data.get("event")
    site = (data.get("property") or {}).get("name")
    if event == "chat:start":
        visitor = data.get("visitor") or {}
        text = (data.get("message") or {}).get("text")
        take(db, "tawkto", sender=visitor.get("email") or data.get("chatId"), name=visitor.get("name"), email=visitor.get("email"), city=visitor.get("city"),
             text=text, message_id=str(data.get("chatId") or "") or None, details={"Website": site, "Country": visitor.get("country")}, at=when(None))
    elif event == "ticket:create":
        who = data.get("requester") or {}
        ticket = data.get("ticket") or {}
        text = "\n".join(x for x in (ticket.get("subject"), ticket.get("message")) if x)
        take(db, "tawkto", sender=who.get("email"), name=who.get("name"), email=who.get("email"), text=text,
             message_id=str(ticket.get("id") or "") or None, details={"Website": site, "Ticket": ticket.get("humanId")}, at=when(None))
    db.commit()
    return {"ok": True}


FORM_ALIASES = {
    "name": "name", "full_name": "name", "fullname": "name", "your_name": "name",
    "business": "business", "company": "business", "company_name": "business", "pharmacy": "business", "clinic": "business",
    "phone": "phone", "mobile": "phone", "phone_number": "phone", "contact_number": "phone",
    "email": "email", "e-mail": "email", "city": "city", "message": "text", "inquiry": "text", "notes": "text",
}


@hooks.post("/form")
async def form(request: Request, settings: SettingsDep, db: DB) -> dict:
    found = secrets_of(settings, "web_forms")
    given = request.headers.get("x-bishnoi-key") or request.query_params.get("key") or ""
    if not found.get("form_key") or not hmac.compare_digest(given, found["form_key"]):
        raise HTTPException(401, "Wrong key")
    body = await raw(request)
    if "json" in (request.headers.get("content-type") or ""):
        data = as_json(body)
    else:
        data = dict((await request.form()).items())
    known: dict[str, str] = {}
    extra: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            continue
        k = str(key).strip().lower().replace(" ", "_")
        if k in FORM_ALIASES:
            known[FORM_ALIASES[k]] = str(value)
        elif k not in ("key", "company"):
            extra[str(key).replace("_", " ").capitalize()] = str(value)
    if not (known.get("name") or known.get("business") or known.get("email") or known.get("phone")):
        raise HTTPException(422, "Say who it's from: name, business, email or phone")
    take(db, "form", sender=known.get("email") or known.get("phone"), name=known.get("name") or known.get("business"), business=known.get("business"),
         phone=known.get("phone"), email=known.get("email"), city=known.get("city"), text=known.get("text"), details=extra)
    db.commit()
    return {"ok": True}


# --- the screens ------------------------------------------------------------------------


def lead_out(lead: InboxLead) -> dict:
    last = next((m for m in reversed(lead.messages) if m.get("text")), None)
    return {
        "id": lead.id,
        "channel": lead.channel,
        "channelName": CHANNELS[lead.channel][0],
        "status": lead.status,
        "name": lead.name,
        "business": lead.business,
        "phone": lead.phone,
        "email": lead.email,
        "city": lead.city,
        "lastMessage": last and last["text"],
        "messageCount": len(lead.messages),
        "receivedAt": iso(lead.received_at),
        "lastAt": iso(lead.last_at),
        "company": {"id": lead.company.id, "name": lead.company.name} if lead.company else None,
        "handledBy": lead.handled_by.full_name if lead.handled_by else None,
        "handledAt": iso(lead.handled_at) if lead.handled_at else None,
    }


def hook_address(request: Request, slug: str, path: str) -> str:
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and not any(h in base for h in ("localhost", "127.0.0.1")):
        base = "https://" + base[7:]
    return f"{base}/hooks/{path}?company={slug}"


@router.get("")
def inbox(
    access: Handle, db: DB, settings: SettingsDep, request: Request,
    status: Literal["new", "added", "dismissed"] = "new",
    channel: Literal["facebook", "messenger", "whatsapp", "viber", "tawkto", "form"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict:
    size = 50
    where = [InboxLead.status == status] + ([InboxLead.channel == channel] if channel else [])
    rows = db.scalars(select(InboxLead).where(*where).order_by(InboxLead.last_at.desc()).offset((page - 1) * size).limit(size)).unique().all()
    counts = dict(db.execute(select(InboxLead.status, func.count()).group_by(InboxLead.status)).all())
    on = svc.services(settings)
    return {
        "items": [lead_out(x) for x in rows],
        "total": db.scalar(select(func.count()).select_from(InboxLead).where(*where)) or 0,
        "page": page,
        "pageSize": size,
        "counts": {s: counts.get(s, 0) for s in ("new", "added", "dismissed")},
        "channels": [
            {"key": key, "name": next(s.name for s in svc.SERVICES if s.key == key), "on": key in on, "address": hook_address(request, settings.company, path)}
            for key, path in HOOKS.items()
        ],
        "connected": svc.connected(settings),
    }


@router.get("/count")
def new_count(access: Handle, db: DB) -> dict:
    return {"new": db.scalar(select(func.count()).select_from(InboxLead).where(InboxLead.status == "new")) or 0}


def the_lead(db: Session, lead_id: str) -> InboxLead:
    lead = db.get(InboxLead, lead_id)
    if lead is None:
        raise not_found("lead")
    return lead


@router.get("/{lead_id}")
def one(lead_id: str, access: Handle, me: CurrentUser, db: DB) -> dict:
    lead = the_lead(db, lead_id)
    probe = Company(name=lead.business or lead.name, phone=lead.phone, email=lead.email, city=lead.city)
    matches = []
    for c in db.scalars(select(Company)).unique():
        points, why = score("company", probe, c)
        if points >= LINE["company"]:
            named = shown_to(c, access)
            matches.append({"id": c.id if named else None, "name": c.name if named else "A customer of another division", "teamName": (c.team.name if c.team else None) if named else None, "why": why, "points": points})
    matches.sort(key=lambda m: -m["points"])
    return lead_out(lead) | {
        "messages": [{"at": m.get("at"), "text": m.get("text")} for m in lead.messages],
        "details": lead.details,
        "matches": matches[:3],
        "types": [{"code": t.code, "name": t.name} for t in offered_types(db, me.team_id)],
    }


class AddIn(Api):
    # A customer already in the CRM: the lead is theirs. None: a new customer.
    company_id: str | None = None
    name: str | None = Field(None, max_length=160)
    type: str | None = Field(None, max_length=40)


def conversation(lead: InboxLead) -> str:
    lines = [f"Came in on {CHANNELS[lead.channel][0]}."]
    lines += [f"{k}: {v}" for k, v in lead.details.items()]
    lines += [f"[{(m.get('at') or '')[:16].replace('T', ' ')}] {m['text']}" for m in lead.messages if m.get("text")]
    return "\n".join(lines)[:5000]


@router.post("/{lead_id}/add")
def add(lead_id: str, body: AddIn, access: Handle, me: CurrentUser, db: DB) -> dict:
    lead = the_lead(db, lead_id)
    if lead.status != "new":
        raise HTTPException(409, "Someone has already handled this lead.")
    now = datetime.now(UTC)
    if body.company_id:
        company = db.get(Company, body.company_id)
        if company is None or not shown_to(company, access):
            raise not_found("customer")
    else:
        offered = offered_types(db, me.team_id)
        if not offered:
            raise HTTPException(409, "Your team has no customer types: an administrator adds them in Settings.")
        want = (body.type or "").strip().lower()
        kind = next((t.code for t in offered if t.code.lower() == want), None) or first_type(db, team_id=me.team_id)
        source = SOURCES[lead.channel]
        company = Company(
            name=(body.name or lead.business or lead.name).strip()[:160], status=kind, city=lead.city, country="Philippines",
            phone=lead.phone, email=lead.email, notes=f"Came in on {CHANNELS[lead.channel][0]}.", extra={},
            lead_source=source if source in deal_lists(db)["sources"] else None,
            owner_id=me.id, team_id=me.team_id, created_by_id=me.id,
        )
        check_required(db, "company", company, team_id=me.team_id, kind=company.status)
        db.add(company)
        db.flush()
        if lead.business and lead.name and lead.name != lead.business and not lead.name.endswith(" contact"):
            first, _, last = lead.name.partition(" ")
            db.add(Contact(company_id=company.id, first_name=first[:80], last_name=last[:80] or None, phone=lead.phone, email=lead.email, extra={}, owner_id=me.id, team_id=me.team_id, created_by_id=me.id))
        audit(db, me, "company.created", target=company.name, target_type="company", target_id=company.id)
    db.add(Activity(kind="note", subject=f"Lead from {CHANNELS[lead.channel][0]}: {lead.name}"[:200], body=conversation(lead), company_id=company.id, at=now, done_at=now, owner_id=me.id, team_id=me.team_id, created_by_id=me.id))
    db.add(Activity(kind="task", subject=f"Reply to {lead.name}"[:200], company_id=company.id, at=now + timedelta(hours=REPLY_WITHIN_HOURS), owner_id=me.id, team_id=me.team_id, created_by_id=me.id))
    lead.status, lead.company_id, lead.handled_by_id, lead.handled_at = "added", company.id, me.id, now
    audit(db, me, "inbox.added", target=lead.name, target_type="company", target_id=company.id)
    db.commit()
    return {"companyId": company.id, "companyName": company.name}


@router.post("/{lead_id}/dismiss")
def dismiss(lead_id: str, access: Handle, me: CurrentUser, db: DB) -> dict:
    lead = the_lead(db, lead_id)
    if lead.status != "new":
        raise HTTPException(409, "Someone has already handled this lead.")
    lead.status, lead.handled_by_id, lead.handled_at = "dismissed", me.id, datetime.now(UTC)
    audit(db, me, "inbox.dismissed", target=lead.name, target_type="inbox", target_id=lead.id)
    db.commit()
    return lead_out(lead)


@router.post("/{lead_id}/reopen")
def reopen(lead_id: str, access: Handle, me: CurrentUser, db: DB) -> dict:
    lead = the_lead(db, lead_id)
    if lead.status != "dismissed":
        raise HTTPException(409, "Only a dismissed lead can be put back.")
    lead.status, lead.handled_by_id, lead.handled_at = "new", None, None
    audit(db, me, "inbox.reopened", target=lead.name, target_type="inbox", target_id=lead.id)
    db.commit()
    return lead_out(lead)
