"""Business events (feature plan step 7, decision 12): what this application tells the others, and
hears from them, through Bishnoi One Platform, never by reading another app's database.

- emit(db, slug, kind, data): an event, saved in the same transaction as the change it is about
  (the outbox), so it can't be lost or sent for a change that didn't happen. Once the transaction
  commits it is sent to the Platform (POST /connect/events, with this application's connect key);
  whatever couldn't be sent goes with the next one, or when the Platform's nightly check asks
  (POST /platform/events/flush).
- link(db, slug, source, document): one document came from another (step 9's document chain).
- POST /platform/events: an event from another application, signed by the Platform (kind "event").
  Taken once: its id is kept, so a delivery that comes again changes nothing. Its handler (below)
  runs in the same transaction; if it fails, nothing is kept and the Platform tries again later.

Without PLATFORM_API_URL (tests, standalone) events are kept and never sent.

The same in every Bishnoi One application but for the part marked below.
"""

import logging
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Request, Response, status
from sqlalchemy import JSON, DateTime, Integer, String, event, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app import platform_connect
from app.db import Base
from app.platform_roles import NoteIn, _checked, _nowhere, sessions_for

log = logging.getLogger(__name__)

# ---- This application ----------------------------------------------------------------------
PREFIX = "nbin"  # its tables' prefix


def company_slug(settings) -> str | None:
    """Inventory keeps a database per company: every event names its company when it is emitted."""
    return None


def remember_company(settings, slug: str | None) -> None:
    return None


# What this application does with each kind it takes: fn(db, data, slug). It takes none yet.
HANDLERS: dict[str, Callable] = {}
# --------------------------------------------------------------------------------------------

router = APIRouter(prefix="/platform", tags=["platform"])
BATCH = 200
_state: dict = {}  # the running app's settings, for sending after a commit


class OutboxEvent(Base):
    __tablename__ = f"{PREFIX}_events_out"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str | None] = mapped_column(String(40), default=None)
    kind: Mapped[str] = mapped_column(String(60))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300), default=None)


class InboxEvent(Base):
    __tablename__ = f"{PREFIX}_events_in"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(40))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def install(app) -> None:
    """At start: the settings to send with, and the routes."""
    _state["settings"] = app.state.settings
    app.include_router(router)


def emit(db: Session, slug: str | None, kind: str, data: dict) -> None:
    """`slug`: the company, where one database holds several; None: the one this database is, filled in when sent."""
    db.add(OutboxEvent(id=str(uuid.uuid4()), slug=slug, kind=kind, data=data, occurred_at=datetime.now(UTC)))
    db.info["events_out"] = True


def ref(kind: str, id_: str, number: str | None, app: str | None = None) -> dict:
    """A document, as the document chain names it (step 9)."""
    from app.platform_roles import APP_KEY

    return {"app": app or APP_KEY, "kind": kind, "id": id_, "number": number}


def link(db: Session, slug: str | None, source: dict, document: dict) -> None:
    """`document` came from `source` (step 9): told to the Platform's document chain, with the change itself."""
    emit(db, slug, "document.linked", {"from": source, "to": document})


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    if session.info.pop("events_out", False) and _state.get("settings") is not None and getattr(_state["settings"], "platform_api_url", None):
        bind = session.get_bind()
        threading.Thread(target=lambda: _flush_quietly(bind), name="events-out", daemon=True).start()


def _flush_quietly(bind) -> None:
    try:
        with Session(bind) as db:
            flush(db, _state["settings"])
    except Exception:  # noqa: BLE001 (sent with the next one, or when the Platform asks)
        log.exception("Events: couldn't send to the Platform.")


def flush(db: Session, settings) -> int:
    """Sends what this database still holds, oldest first. Returns how many the Platform took."""
    url, key = getattr(settings, "platform_api_url", None), platform_connect.connect_key(settings)
    if not url or not key:
        return 0
    waiting = db.scalars(select(OutboxEvent).where(OutboxEvent.sent_at.is_(None)).order_by(OutboxEvent.occurred_at).limit(BATCH)).all()
    taken = 0
    by_company: dict[str, list[OutboxEvent]] = {}
    for e in waiting:
        e.slug = e.slug or company_slug(settings)
        if e.slug:
            by_company.setdefault(e.slug, []).append(e)
    for slug, items in by_company.items():
        body = {"company": slug, "events": [{"id": e.id, "kind": e.kind, "data": e.data, "occurredAt": e.occurred_at.isoformat()} for e in items]}
        try:
            r = httpx.post(f"{url.rstrip('/')}/connect/events", json=body, headers={"X-Bishnoi-App-Key": key}, timeout=10)
            answer = r.json() if r.status_code == 200 else None
            problem = None if answer else f"answered {r.status_code}"
        except (httpx.HTTPError, ValueError) as e:
            answer, problem = None, f"out of reach ({e.__class__.__name__})"
        now = datetime.now(UTC)
        done = set((answer or {}).get("taken", [])) | set((answer or {}).get("refused", []))
        refused = set((answer or {}).get("refused", []))
        for e in items:
            if e.id in done:
                e.sent_at = now
                e.last_error = "The Platform doesn't route this kind from this app." if e.id in refused else None
                taken += e.id not in refused
            else:
                e.attempts += 1
                e.last_error = problem
    db.commit()
    return taken


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
def take_event(body: NoteIn, request: Request) -> Response:
    claims = _checked(request.app.state.settings, body.token, "event")
    item = claims.get("event") if claims else None
    if not isinstance(item, dict) or not item.get("id") or not item.get("kind"):
        raise _nowhere()
    remember_company(request.app.state.settings, claims["slug"])
    with sessions_for(request, claims["slug"])() as db:
        if db.get(InboxEvent, str(item["id"])) is None:
            handler = HANDLERS.get(str(item["kind"]))
            if handler is not None:
                handler(db, item.get("data") or {}, claims["slug"])
            db.add(InboxEvent(id=str(item["id"])[:36], kind=str(item["kind"])[:60], source=str(item.get("source") or "")[:40], received_at=datetime.now(UTC)))
            db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events/flush", status_code=status.HTTP_204_NO_CONTENT)
def send_held(body: NoteIn, request: Request) -> Response:
    """The Platform's nightly check: send whatever this company's database still holds."""
    claims = _checked(request.app.state.settings, body.token, "events-flush")
    if claims is None:
        raise _nowhere()
    with sessions_for(request, claims["slug"])() as db:
        flush(db, request.app.state.settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
