"""Scheduled cycle counts (feature plan step 14b, app/count_schedules.py).

    GET    /inventory/count-schedules               every schedule, due first
    POST   /inventory/count-schedules               a new one
    PATCH  /inventory/count-schedules/{id}          name, interval, next day, switched on or off
    DELETE /inventory/count-schedules/{id}
    POST   /inventory/count-schedules/{id}/start    its count, now
"""

from datetime import date

from fastapi import APIRouter, Response, status
from pydantic import Field
from sqlalchemy import func, select

from app import count_schedules as cs
from app import documents
from app.access import allowed
from app.api import Api, changed, conflict, field_error, found
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Category, CountSchedule, Warehouse
from app.routers.adjustments import begin_count

router = APIRouter(prefix="/inventory", tags=["count schedules"])

Manage = allowed("counts.approve")


class ScheduleIn(Api):
    name: str = Field(min_length=1, max_length=120)
    warehouse_id: str = Field(max_length=36)
    category_id: str | None = Field(None, max_length=36)
    every_days: int = Field(ge=1, le=730)
    next_on: date | None = None


class SchedulePatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    every_days: int | None = Field(None, ge=1, le=730)
    next_on: date | None = None
    is_active: bool | None = None


@router.get("/count-schedules")
def schedules(_: allowed("counts.view"), db: DB) -> dict:
    rows = [cs.schedule_out(db, s) for s in db.scalars(select(CountSchedule).order_by(CountSchedule.next_on, func.lower(CountSchedule.name)))]
    rows.sort(key=lambda r: (not r["due"], not r["isActive"], r["nextOn"] or ""))
    return {"items": rows, "due": sum(1 for r in rows if r["due"])}


@router.post("/count-schedules", status_code=status.HTTP_201_CREATED)
def add_schedule(_: Manage, me: CurrentUser, db: DB, body: ScheduleIn) -> dict:
    warehouse = db.get(Warehouse, body.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    if body.category_id and db.get(Category, body.category_id) is None:
        raise field_error("categoryId", "Pick a category that exists.")
    s = CountSchedule(name=body.name.strip(), warehouse_id=warehouse.id, category_id=body.category_id, every_days=body.every_days,
                      next_on=body.next_on or documents.today(), created_by_id=me.id)
    db.add(s)
    db.flush()
    audit(db, me, "count_schedule.created", target=s.name, target_type="count_schedule", target_id=s.id)
    db.commit()
    return cs.schedule_out(db, s)


@router.patch("/count-schedules/{schedule_id}")
def change_schedule(_: Manage, me: CurrentUser, db: DB, schedule_id: str, body: SchedulePatch) -> dict:
    s = found(db, CountSchedule, schedule_id, "count schedule")
    fields = {k: v for k, v in changed(body).items() if v is not None and getattr(s, k) != v}
    for k, v in fields.items():
        setattr(s, k, v.strip() if isinstance(v, str) else v)
    if fields:
        audit(db, me, "count_schedule.updated", target=s.name, target_type="count_schedule", target_id=s.id, fields=sorted(fields))
        db.commit()
    return cs.schedule_out(db, s)


@router.delete("/count-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(_: Manage, me: CurrentUser, db: DB, schedule_id: str) -> Response:
    s = found(db, CountSchedule, schedule_id, "count schedule")
    audit(db, me, "count_schedule.deleted", target=s.name, target_type="count_schedule", target_id=s.id)
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/count-schedules/{schedule_id}/start", status_code=status.HTTP_201_CREATED)
def start_scheduled(_: allowed("counts.create"), me: CurrentUser, db: DB, schedule_id: str) -> dict:
    """The schedule's count, now (due or early): one open count per schedule at a time."""
    s = found(db, CountSchedule, schedule_id, "count schedule")
    if not s.is_active:
        raise conflict(f"{s.name} is switched off.")
    current = cs.open_count(db, s)
    if current is not None:
        raise conflict(f"{current.number} is already open for {s.name}: finish it first.")
    if not s.warehouse.is_active:
        raise conflict(f"{s.warehouse.name} is switched off.")
    c = begin_count(db, me, s.warehouse, s.category_id, f"Cycle count: {s.name}", None, schedule=s)
    db.commit()
    return {"id": c.id, "number": c.number}
