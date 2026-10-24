"""The calendar: each person's own events, which dates they fall on, and reminders.

Decided 2026-10-22 (Plans/Plan - Finance calendar): switched on per person; each
person sees their own events and those shared with them; reminders appear in the
bell and on the Overview, worked out when the person opens Finance (Finance has no
timers), some working days before (Monday to Saturday, Philippine holidays off).
"""

import calendar as months
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CalendarEvent, CalendarShare, Notification, User
from app.notify import tell
from app.workdays import workdays_before

# How far ahead reminders look, and how long a missed one is still worth showing.
AHEAD_DAYS = 45
MISSED_DAYS = 7


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.org_timezone)).date()


def _month_day(year: int, month: int, day: int) -> date:
    """That day of the month, or its last day (31 January monthly -> 28/29 February)."""
    return date(year, month, min(day, months.monthrange(year, month)[1]))


def _add_months(start: date, n: int, day: int) -> date:
    m = start.month - 1 + n
    return _month_day(start.year + m // 12, m % 12 + 1, day)


def occurrences(e: CalendarEvent, since: date, until: date) -> list[date]:
    """The dates this event falls on within [since, until]."""
    last = min(until, e.until) if e.until else until
    if last < since or e.starts_on > last:
        return []
    if e.repeat == "none":
        return [e.starts_on] if since <= e.starts_on <= last else []
    found: list[date] = []
    if e.repeat == "twice_monthly":
        # The 15th and the last day of each month, from the month it starts.
        y, m = e.starts_on.year, e.starts_on.month
        while date(y, m, 1) <= last:
            for d in (date(y, m, 15), _month_day(y, m, 31)):
                if d >= e.starts_on and since <= d <= last:
                    found.append(d)
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        return found
    step = {"monthly": 1, "quarterly": 3, "yearly": 12}[e.repeat]
    n = 0
    while (d := _add_months(e.starts_on, n * step, e.starts_on.day)) <= last:
        if d >= since:
            found.append(d)
        n += 1
    return found


def visible(db: Session, user: User) -> list[CalendarEvent]:
    """This person's own events and those shared with them."""
    shared = select(CalendarShare.event_id).where(CalendarShare.user_id == user.id)
    return list(db.scalars(select(CalendarEvent).where(or_(CalendarEvent.owner_id == user.id, CalendarEvent.id.in_(shared)))))


def occurrence_link(e: CalendarEvent, on: date) -> str:
    """The calendar on that date, with that event: also what ties its reminders together."""
    return f"/calendar?on={on.isoformat()}&event={e.id}"


def is_done(e: CalendarEvent, on: date) -> bool:
    return any(d.occurs_on == on for d in e.done)


def remind(db: Session, user: User, settings: Settings) -> None:
    """Reminders due for this person, made once each, when they open Finance."""
    if not user.calendar_on:
        return
    now = today(settings)
    told = set(db.scalars(select(Notification.link).where(Notification.user_id == user.id, Notification.kind == "calendar.reminder")))
    made = 0
    for e in visible(db, user):
        if e.remind_days is None:
            continue
        for on in occurrences(e, now - timedelta(days=MISSED_DAYS), now + timedelta(days=AHEAD_DAYS)):
            link = occurrence_link(e, on)
            if link in told or is_done(e, on) or workdays_before(on, e.remind_days) > now:
                continue
            when = "today" if on == now else ("was due " if on < now else "") + f"{on:%a %d %b}"
            shared = "" if e.owner_id == user.id else f" (shared by {e.owner.full_name})"
            made += tell(db, [user], "calendar.reminder", f"{e.title}: {when}{shared}.", link=link)
    if made:
        db.commit()
