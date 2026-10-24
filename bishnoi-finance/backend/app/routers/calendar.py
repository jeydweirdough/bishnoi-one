"""The calendar (Finance → Calendar), for whoever has it switched on.

- GET /finance/calendar?from=&to=: this person's events and those shared with
  them, date by date; Philippine days off; liquidations falling due (for whoever
  releases or reviews); and who else has a calendar, to share with.
- POST /finance/calendar/events, PUT/DELETE /finance/calendar/events/{id}: the
  owner adds, changes and removes their events; shared people only see them.
- POST/DELETE /finance/calendar/events/{id}/done?on=: a date marked done (by the
  owner or anyone it's shared with), or undone. It stops reminding everyone.

Included into Finance's router (app/routers/finance.py), so main.py is untouched.
Decided 2026-10-22 (Plans/Plan - Finance calendar).
"""

import re
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.access import access_of, permitted
from app.audit import audit
from app.calendar_events import is_done, occurrence_link, occurrences, today, visible
from app.deps import DB, SettingsDep
from app.models import CalendarDone, CalendarEvent, CalendarShare, FundRequest, Notification, User, utcnow
from app.notify import done, tell
from app.routers.tax import Api, field_error
from app.workdays import holidays_between

router = APIRouter(prefix="/calendar", tags=["calendar"])

MAX_SPAN = 120  # days one request may cover
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def person(u: User) -> dict:
    return {"id": u.id, "name": u.full_name}


def event_out(e: CalendarEvent, me: User) -> dict:
    return {
        "id": e.id, "title": e.title, "notes": e.notes, "startsOn": e.starts_on.isoformat(), "atTime": e.at_time, "repeat": e.repeat,
        "until": e.until.isoformat() if e.until else None, "remindDays": e.remind_days, "link": e.link,
        "owner": person(e.owner), "mine": e.owner_id == me.id, "sharedWith": [person(s.user) for s in e.shares],
    }


def calendar_people(db: DB, me: User) -> list[User]:
    """Who else has a calendar, to share with."""
    return list(db.scalars(select(User).where(User.is_active, User.calendar_on, User.id != me.id).order_by(User.full_name)))


@router.get("")
def read_calendar(
    user: permitted("calendar.use"),
    db: DB,
    settings: SettingsDep,
    since: date | None = Query(None, alias="from"),
    until: date | None = Query(None, alias="to"),
) -> dict:
    now = today(settings)
    since = since or now.replace(day=1)
    until = until or since + timedelta(days=41)
    if until < since or (until - since).days > MAX_SPAN:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose dates up to {MAX_SPAN} days apart.")
    items = []
    for e in visible(db, user):
        for on in occurrences(e, since, until):
            d = next((x for x in e.done if x.occurs_on == on), None)
            items.append({"on": on.isoformat(), "event": event_out(e, user), "done": {"by": d.done_by, "at": d.done_at.isoformat()} if d else None})
    items.sort(key=lambda i: (i["on"], i["event"]["atTime"] or "", i["event"]["title"]))
    access = access_of(user)
    due = []
    if access.can("funds.check") or access.can("funds.release"):
        found = db.scalars(select(FundRequest).where(FundRequest.status == "to_liquidate", FundRequest.liquidate_by >= since, FundRequest.liquidate_by <= until))
        due = [{"on": r.liquidate_by.isoformat(), "id": r.id, "number": r.number, "requester": r.requester_name} for r in found]
    return {
        "from": since.isoformat(), "to": until.isoformat(), "today": now.isoformat(),
        "items": items,
        "holidays": [{"on": d.isoformat(), "name": name} for d, name in holidays_between(since, until)],
        "liquidations": sorted(due, key=lambda x: x["on"]),
        "people": [person(u) for u in calendar_people(db, user)],
    }


class EventIn(Api):
    title: str = Field(min_length=1, max_length=160)
    notes: str | None = Field(None, max_length=1000)
    starts_on: date
    at_time: str | None = None
    repeat: Literal["none", "monthly", "quarterly", "yearly", "twice_monthly"] = "none"
    until: date | None = None
    remind_days: Literal[0, 1, 3, 7] | None = None
    link: str | None = Field(None, max_length=200)
    shared_with: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("at_time")
    @classmethod
    def _time(cls, v: str | None) -> str | None:
        if v and not TIME.match(v):
            raise ValueError("Enter the time as HH:MM, e.g. 14:30.")
        return v or None

    @field_validator("link")
    @classmethod
    def _link(cls, v: str | None) -> str | None:
        # Only a page inside Finance: never somewhere else.
        if v and (not v.startswith("/") or v.startswith("//")):
            raise ValueError("Use a page inside Finance, e.g. /bir/sales-dat.")
        return v or None


def checked(db: DB, me: User, body: EventIn) -> list[User]:
    if body.until and body.until < body.starts_on:
        raise field_error("until", "The last date can't be before the first.")
    allowed = {u.id: u for u in calendar_people(db, me)}
    unknown = [i for i in body.shared_with if i not in allowed]
    if unknown:
        raise field_error("sharedWith", "Share only with people who have the calendar.")
    return [allowed[i] for i in dict.fromkeys(body.shared_with)]


def apply(e: CalendarEvent, body: EventIn) -> None:
    for key in ("title", "notes", "starts_on", "at_time", "repeat", "until", "remind_days", "link"):
        setattr(e, key, getattr(body, key))


def tell_shared(db: DB, e: CalendarEvent, me: User, people: list[User]) -> None:
    for p in people:
        tell(db, [p], "calendar.shared", f"{me.full_name} shared “{e.title}” with you ({e.starts_on:%a %d %b}).", link=occurrence_link(e, e.starts_on), not_to=[me.id])


def own_event(db: DB, me: User, event_id: str) -> CalendarEvent:
    e = db.get(CalendarEvent, event_id)
    if e is None or (e.owner_id != me.id and all(s.user_id != me.id for s in e.shares)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such event on your calendar.")
    if e.owner_id != me.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {e.owner.full_name}, who added it, can change it.")
    return e


def forget_reminders(db: DB, e: CalendarEvent) -> None:
    """Its reminders say dates that may no longer be right: they're done."""
    db.execute(
        update(Notification)
        .where(Notification.kind == "calendar.reminder", Notification.link.like(f"%&event={e.id}"), Notification.read_at.is_(None))
        .values(read_at=utcnow())
        .execution_options(synchronize_session=False)
    )


@router.post("/events", status_code=status.HTTP_201_CREATED)
def add_event(user: permitted("calendar.use"), db: DB, body: EventIn) -> dict:
    people = checked(db, user, body)
    e = CalendarEvent(owner_id=user.id)
    apply(e, body)
    e.shares = [CalendarShare(user_id=p.id) for p in people]
    db.add(e)
    db.flush()
    tell_shared(db, e, user, people)
    audit(db, user, "calendar.added", target=e.title, target_type="calendar_event", target_id=e.id)
    db.commit()
    db.refresh(e)
    return event_out(e, user)


@router.put("/events/{event_id}")
def change_event(user: permitted("calendar.use"), db: DB, event_id: str, body: EventIn) -> dict:
    e = own_event(db, user, event_id)
    people = checked(db, user, body)
    before = {s.user_id for s in e.shares}
    apply(e, body)
    e.shares = [s for s in e.shares if s.user_id in {p.id for p in people}] + [CalendarShare(user_id=p.id) for p in people if p.id not in before]
    forget_reminders(db, e)
    db.flush()
    tell_shared(db, e, user, [p for p in people if p.id not in before])
    audit(db, user, "calendar.changed", target=e.title, target_type="calendar_event", target_id=e.id)
    db.commit()
    db.refresh(e)
    return event_out(e, user)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_event(user: permitted("calendar.use"), db: DB, event_id: str) -> None:
    e = own_event(db, user, event_id)
    forget_reminders(db, e)
    audit(db, user, "calendar.removed", target=e.title, target_type="calendar_event", target_id=e.id)
    db.delete(e)
    db.commit()


class OnIn(Api):
    on: date


def seen_event(db: DB, me: User, event_id: str, on: date) -> CalendarEvent:
    e = db.get(CalendarEvent, event_id)
    if e is None or (e.owner_id != me.id and all(s.user_id != me.id for s in e.shares)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such event on your calendar.")
    if not occurrences(e, on, on):
        raise field_error("on", "This event doesn't fall on that date.")
    return e


@router.post("/events/{event_id}/done")
def mark_done(user: permitted("calendar.use"), db: DB, event_id: str, body: OnIn) -> dict:
    """Done for that date: it stops reminding the owner and everyone it's shared
    with. Two people ticking it at once: the first is kept, the second is fine."""
    e = seen_event(db, user, event_id, body.on)
    if not is_done(e, body.on):
        db.add(CalendarDone(event_id=e.id, occurs_on=body.on, done_by=user.full_name[:120], done_by_id=user.id))
        done(db, "calendar.reminder", occurrence_link(e, body.on))
        if e.owner_id != user.id:
            tell(db, [e.owner_id], "calendar.done", f"{user.full_name} marked “{e.title}” ({body.on:%a %d %b}) done.",
                 link=occurrence_link(e, body.on), not_to=[user.id])
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # someone else marked it done a moment before
    db.expire_all()
    e = db.get(CalendarEvent, event_id)
    d = next(x for x in e.done if x.occurs_on == body.on)
    return {"on": body.on.isoformat(), "event": event_out(e, user), "done": {"by": d.done_by, "at": d.done_at.isoformat()}}


@router.delete("/events/{event_id}/done", status_code=status.HTTP_204_NO_CONTENT)
def undo_done(user: permitted("calendar.use"), db: DB, event_id: str, on: date = Query(...)) -> None:
    e = seen_event(db, user, event_id, on)
    e.done = [x for x in e.done if x.occurs_on != on]
    db.commit()
