"""Business events through the platform (feature plan step 7; app/events.py says how they move).

- POST /connect/events: an app sends what happened at a company (its connect key in X-Bishnoi-App-Key).
  {"company": slug, "events": [{"id", "kind", "data", "occurredAt"}]}: each kept once; answers the
  ids taken, so the app marks them sent.
- GET  /platform/events: the Operations area's list (operators): counts, and the deliveries by status.
- POST /platform/events/{event_id}/{target}/retry | /skip: an operator's decision on a stuck one.
- POST /platform/events/run: deliver what is due now. POST /platform/events/check: the nightly check.
- GET  /cron/events-check: the same, for a scheduler (Vercel cron), with CRON_SECRET as its bearer.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import Field
from sqlalchemy import func, select

from app import events, links
from app.api import Api, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import BusinessEvent, Company, CompanyApp, EventDelivery

router = APIRouter(tags=["business events"])


class EventIn(Api):
    id: str = Field(min_length=8, max_length=36)
    kind: str = Field(max_length=60)
    data: dict = Field(default_factory=dict)
    occurred_at: datetime


class EventsIn(Api):
    company: str = Field(max_length=40)
    events: list[EventIn] = Field(max_length=500)


@router.post("/connect/events")
def take_events(body: EventsIn, request: Request, db: DB, settings: SettingsDep,
                key: Annotated[str | None, Header(alias="X-Bishnoi-App-Key")] = None) -> dict:
    app = links.app_of_key(db, key)
    if app is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That connect key isn't one the platform made, or it was replaced.")
    company = db.scalar(select(Company).where(Company.slug == body.company.strip().lower()))
    if company is None or db.get(CompanyApp, (company.id, app.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That company doesn't have this app on Bishnoi One.")
    taken, refused = [], []
    for e in body.events:
        kind = events.KINDS.get(e.kind)
        if kind is None or kind.source not in (app.key, events.ANY):
            refused.append(e.id)  # not one this app sends: kept by nobody
            continue
        events.accept(db, app.key, company, e.id, e.kind, e.data, e.occurred_at)
        taken.append(e.id)
    db.commit()
    if taken:
        events.kick(request.app.state.sessions, settings)
    return {"taken": taken, "refused": refused}


def delivery_out(d: EventDelivery, e: BusinessEvent, company: Company | None) -> dict:
    return {
        "eventId": e.id, "kind": e.kind, "says": events.KINDS[e.kind].says if e.kind in events.KINDS else e.kind,
        "source": e.source, "target": d.target, "company": company.name if company else None,
        "status": d.status, "attempts": d.attempts, "nextAt": iso(d.next_at), "lastError": d.last_error,
        "deliveredAt": iso(d.delivered_at), "occurredAt": iso(e.occurred_at),
    }


@router.get("/platform/events")
def list_events(db: DB, _: CurrentUser, state: str = Query("stuck", pattern="^(stuck|pending|delivered|skipped)$"), limit: int = Query(100, ge=1, le=500)) -> dict:
    counts = dict(db.execute(select(EventDelivery.status, func.count()).group_by(EventDelivery.status)).all())
    rows = db.execute(
        select(EventDelivery, BusinessEvent, Company).join(BusinessEvent, BusinessEvent.id == EventDelivery.event_id)
        .join(Company, Company.id == BusinessEvent.company_id, isouter=True)
        .where(EventDelivery.status == state).order_by(BusinessEvent.occurred_at.desc()).limit(limit)
    ).all()
    return {
        "counts": {s: counts.get(s, 0) for s in ("pending", "delivered", "stuck", "skipped")},
        "kinds": [{"kind": k, "source": v.source, "takers": list(v.takers), "says": v.says} for k, v in events.KINDS.items()],
        "deliveries": [delivery_out(d, e, c) for d, e, c in rows],
    }


def _delivery(db, event_id: str, target: str) -> EventDelivery:
    d = db.get(EventDelivery, (event_id, target))
    if d is None:
        raise not_found("delivery")
    return d


@router.post("/platform/events/{event_id}/{target}/retry")
def retry(event_id: str, target: str, request: Request, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    d = _delivery(db, event_id, target)
    if d.status in ("stuck", "skipped", "pending"):
        d.status, d.attempts, d.next_at, d.last_error = "pending", 0, datetime.now(UTC), None
        audit(db, me, "events.retried", category="system", target=f"{event_id} → {target}")
        db.commit()
        said = events.deliver_due(db, settings)
        return {"status": db.get(EventDelivery, (event_id, target)).status, **said}
    return {"status": d.status}


@router.post("/platform/events/{event_id}/{target}/skip")
def skip(event_id: str, target: str, db: DB, me: AdminUser) -> dict:
    d = _delivery(db, event_id, target)
    if d.status in ("stuck", "pending"):
        d.status, d.next_at = "skipped", None
        d.last_error = f"Skipped by {me.email}"
        audit(db, me, "events.skipped", category="system", target=f"{event_id} → {target}")
        db.commit()
    return {"status": d.status}


@router.post("/platform/events/run")
def run(db: DB, settings: SettingsDep, _: AdminUser) -> dict:
    return events.deliver_due(db, settings)


@router.post("/platform/events/check")
def run_check(db: DB, settings: SettingsDep, _: AdminUser) -> dict:
    return events.check(db, settings)


@router.get("/cron/events-check")
def cron_check(db: DB, settings: SettingsDep, authorization: Annotated[str | None, Header()] = None) -> dict:
    secret = settings.secret(settings.cron_secret)
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return events.check(db, settings)

