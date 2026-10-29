"""Scheduled cycle counts (feature plan step 14b, 2026-10-29): counts that come round every so many days, per
warehouse (and category, when set), so the stock is counted a bit at a time instead of all at once a year.

A schedule is due from its next day on. Starting it makes the count as any other (every balance written down
as expected), tied to the schedule; approving that count sets the schedule's next day: the day approved plus
its interval. One open count per schedule at a time.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import documents
from app.api import iso
from app.models import Count, CountSchedule
from app.out import day, warehouse_ref


def open_count(db: Session, schedule: CountSchedule) -> Count | None:
    return db.scalar(select(Count).where(Count.schedule_id == schedule.id, Count.status.in_(("open", "submitted"))).order_by(Count.created_at.desc()))


def counted(db: Session, count: Count) -> None:
    """Its count was approved: the schedule comes round again."""
    schedule = db.get(CountSchedule, count.schedule_id) if count.schedule_id else None
    if schedule is None:
        return
    today = documents.today()
    schedule.last_counted_on = today
    schedule.next_on = today + timedelta(days=schedule.every_days)


def schedule_out(db: Session, s: CountSchedule) -> dict:
    today = documents.today()
    current = open_count(db, s)
    return {
        "id": s.id, "name": s.name, "warehouse": warehouse_ref(s.warehouse),
        "category": {"id": s.category.id, "name": s.category.name} if s.category else None,
        "everyDays": s.every_days, "nextOn": day(s.next_on), "lastCountedOn": day(s.last_counted_on), "isActive": s.is_active,
        "due": s.is_active and s.next_on <= today and current is None,
        "overdueDays": (today - s.next_on).days if s.is_active and s.next_on < today else 0,
        "openCount": {"id": current.id, "number": current.number, "status": current.status} if current else None,
        "createdAt": iso(s.created_at),
    }
