"""Business events (feature plan step 7, decision 12): the apps tell each other what happened ("invoice
issued", "organisation changed") through the platform, never by reading each other's databases.

- KINDS: every event Bishnoi One knows, which app sends it and which apps take it.
- accept(...): an event from an app (its connect key, POST /connect/events) or from the platform
  itself (publish). Kept once by its id, so an app sending it again changes nothing; a delivery is
  made for each app that takes that kind and that the company has.
- deliver_due(...): sends what is due, signed (kind "event"), to POST <api>/platform/events, oldest
  first and in order for each app and company: a failure holds the later ones back so nothing
  arrives out of order. Each app takes an event once (it keeps the ids it has taken). A failure is
  tried again after 1 minute, 5, 30, 2 hours and 12 hours; then the delivery is stuck, for an
  operator to retry or skip in the Operations area. An app that answers 404 doesn't take events
  yet: skipped.
- check(...): the nightly check: delivers what is due, asks each app to send what it still holds
  (POST <api>/platform/events/flush), and counts what is stuck.
"""

import logging
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Application, BusinessEvent, Company, CompanyApp, EventDelivery

log = logging.getLogger(__name__)

PLATFORM = "platform"
LIFETIME = 600  # seconds a delivery note may be taken
RETRY_AFTER = (60, 300, 1800, 7200, 43200)  # then stuck
BATCH = 200


@dataclass(frozen=True)
class Kind:
    source: str
    takers: tuple[str, ...]
    says: str


KINDS: dict[str, Kind] = {
    "organisation.changed": Kind(PLATFORM, ("crm",), "The company's org chart, or where someone sits, changed"),
    "invoice.issued": Kind("finance", ("crm", "inventory"), "An invoice was issued"),
    # Paid in full (step 13): the sales order's chain is closed.
    "invoice.paid": Kind("finance", ("crm", "inventory"), "An invoice was paid in full"),
    # What sold from a vendor's consignment, to pay them (step 15d): a draft vendor bill in Finance.
    "consignment.billed": Kind("inventory", ("finance",), "A vendor's consignment sales were settled"),
    "invoice.voided": Kind("finance", ("crm",), "An invoice was voided"),
    "payment.recorded": Kind("finance", ("crm",), "A customer's payment was recorded"),
    "delivery.done": Kind("inventory", ("finance",), "Goods left the warehouse for a customer"),
    # The Sales app (step 11): Raise order in the CRM makes the sales order; the CRM hears what became of it.
    "quote.ordered": Kind("crm", ("inventory",), "A quote was ordered: its sales order is made"),
    "sales_order.updated": Kind("inventory", ("crm",), "A sales order was approved, rejected, delivered or cancelled"),
    # Any app (ANY) links its documents into the chain; the platform keeps it (app/document_chain.py).
    "document.linked": Kind("*", (), "Two documents were linked: one came from the other"),
}
ANY = "*"


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def accept(db: Session, source: str, company: Company, event_id: str, kind: str, data: dict, occurred_at: datetime) -> bool:
    """Keeps a new event and makes its deliveries; False when it was already here."""
    if db.get(BusinessEvent, event_id) is not None:
        return False
    db.add(BusinessEvent(id=event_id, source=source, company_id=company.id, kind=kind, data=data, occurred_at=occurred_at, received_at=datetime.now(UTC)))
    if kind == "document.linked":
        from app.document_chain import keep

        keep(db, company.id, source, data)
    has = set(db.scalars(select(Application.key).join(CompanyApp, CompanyApp.application_id == Application.id).where(CompanyApp.company_id == company.id)))
    now = datetime.now(UTC)
    for target in KINDS[kind].takers:
        if target in has and target != source:
            db.add(EventDelivery(event_id=event_id, target=target, status="pending", next_at=now))
    db.flush()
    return True


def publish(db: Session, company: Company, kind: str, data: dict) -> str:
    """An event of the platform's own (the org chart): kept and delivered like an app's."""
    event_id = str(uuid.uuid4())
    accept(db, PLATFORM, company, event_id, kind, data, datetime.now(UTC))
    return event_id


def note(settings: Settings, event: BusinessEvent, company: Company, target: str) -> str:
    from app.passes import ISSUER, sign

    now = int(time.time())
    return sign(settings, {
        "iss": ISSUER, "aud": target, "kind": "event", "company": company.id, "slug": company.slug,
        "event": {"id": event.id, "kind": event.kind, "source": event.source, "data": event.data, "occurredAt": as_utc(event.occurred_at).isoformat()},
        "iat": now, "exp": now + LIFETIME, "jti": secrets.token_urlsafe(12),
    })


def _send(db: Session, settings: Settings, d: EventDelivery, event: BusinessEvent, company: Company, app: Application | None) -> bool:
    """One try; True when it was taken (or skipped)."""
    now = datetime.now(UTC)
    if app is None or not app.api_url:
        answer, ok = "the app has no API address registered", False
    else:
        try:
            r = httpx.post(app.api_url.rstrip("/") + "/platform/events", json={"pass": note(settings, event, company, d.target)}, timeout=10)
            if r.status_code in (200, 204):
                answer, ok = None, True
            elif r.status_code == 404:
                d.status, d.last_error, d.next_at = "skipped", "The app doesn't take events yet.", None
                return True
            else:
                answer, ok = f"answered {r.status_code}", False
        except httpx.HTTPError as e:
            answer, ok = f"out of reach ({e.__class__.__name__})", False
    if ok:
        d.status, d.delivered_at, d.next_at, d.last_error = "delivered", now, None, None
        d.attempts += 1
        return True
    d.attempts += 1
    d.last_error = answer
    if d.attempts > len(RETRY_AFTER):
        d.status, d.next_at = "stuck", None
        log.warning("Event %s (%s) to %s is stuck: %s.", event.id, event.kind, d.target, answer)
    else:
        d.next_at = now + timedelta(seconds=RETRY_AFTER[d.attempts - 1])
    return False


def deliver_due(db: Session, settings: Settings) -> dict[str, int]:
    """Sends what is due, oldest first; a failure holds back the later ones for that app and company."""
    now = datetime.now(UTC)
    rows = db.execute(
        select(EventDelivery, BusinessEvent).join(BusinessEvent, BusinessEvent.id == EventDelivery.event_id)
        .where(EventDelivery.status.in_(("pending", "stuck"))).order_by(BusinessEvent.occurred_at, BusinessEvent.id).limit(BATCH * 5)
    ).all()
    apps = {a.key: a for a in db.scalars(select(Application))}
    companies: dict[str, Company] = {}
    held: set[tuple[str, str]] = set()
    said = {"delivered": 0, "failed": 0, "held": 0}
    tried = 0
    for d, event in rows:
        line = (d.target, event.company_id)
        if d.status == "stuck" or line in held:
            held.add(line)
            said["held"] += d.status == "pending"
            continue
        if d.next_at is not None and as_utc(d.next_at) > now:
            held.add(line)  # waiting for its next try: the later ones wait too
            continue
        if tried >= BATCH:
            break
        tried += 1
        company = companies.get(event.company_id) or db.get(Company, event.company_id)
        companies[event.company_id] = company
        if _send(db, settings, d, event, company, apps.get(d.target)):
            said["delivered"] += 1
        else:
            said["failed"] += 1
            held.add(line)
    db.commit()
    return said


def kick(sessions, settings: Settings) -> None:
    """Delivers what is due, in the background (after an event comes in)."""

    def run() -> None:
        try:
            with sessions() as db:
                deliver_due(db, settings)
        except Exception:  # noqa: BLE001 (the next event, or the nightly check, tries again)
            log.exception("Events: a delivery round failed.")

    threading.Thread(target=run, name="events", daemon=True).start()


def ask_to_flush(db: Session, settings: Settings) -> int:
    """Asks every app at every active company to send the events it still holds. Returns how many answered."""
    from app.passes import ISSUER, sign

    answered = 0
    senders = {k.source for k in KINDS.values()} - {PLATFORM}
    rows = db.execute(
        select(Application, Company).join(CompanyApp, CompanyApp.application_id == Application.id).join(Company, Company.id == CompanyApp.company_id)
        .where(Application.key.in_(senders), Application.is_active, Application.api_url.is_not(None), Company.status == "active")
    ).all()
    for app, company in rows:
        now = int(time.time())
        token = sign(settings, {"iss": ISSUER, "aud": app.key, "kind": "events-flush", "company": company.id, "slug": company.slug,
                                "iat": now, "exp": now + LIFETIME, "jti": secrets.token_urlsafe(12)})
        try:
            answered += httpx.post(app.api_url.rstrip("/") + "/platform/events/flush", json={"pass": token}, timeout=10).status_code in (200, 204)
        except httpx.HTTPError:
            pass
    return answered


def check(db: Session, settings: Settings) -> dict:
    """The nightly check: deliver what is due, have each app send what it holds, count what is stuck."""
    from app.audit import audit

    asked = ask_to_flush(db, settings)
    sent = deliver_due(db, settings)
    counts = {s: len(db.scalars(select(EventDelivery.event_id).where(EventDelivery.status == s)).all()) for s in ("pending", "stuck")}
    audit(db, "Bishnoi One", "events.checked", category="system", target="Business events",
          fields=[f"delivered {sent['delivered']}", f"failed {sent['failed']}", f"pending {counts['pending']}", f"stuck {counts['stuck']}", f"apps asked {asked}"])
    db.commit()
    return {**sent, **counts, "appsAsked": asked}
