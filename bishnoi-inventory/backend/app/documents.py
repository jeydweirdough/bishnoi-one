"""One document header on every stock document (feature plan step 8, 2026-10-28): what kind of
operation it is, when it is scheduled, when it was done, the document it came from, and who is
responsible. The same few fields in the same place on receipts, sales orders and issues, transfers,
adjustments and counts, so lists filter by type and by late or on time, and reports read scheduled
against done and work by person.

- HeaderIn: the fields a form may send with a new (or changed) document; whatever isn't sent is
  filled in: the company's default type for its kind, the person making it as responsible.
- apply(...), done(...): set the header; done() when the document is finished (received, issued,
  posted, approved).
- header_out(doc): the header as every screen shows it, with its timing (late, on time, overdue, due).
- narrow(query, model, operation_type, timing): the list filters.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from pydantic import Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.api import Api, field_error
from app.models import OperationType, User

TIMINGS = ("late", "on_time", "overdue", "due")


class HeaderIn(Api):
    operation_type_id: str | None = Field(None, max_length=36)
    scheduled_on: date | None = None
    source_document: str | None = Field(None, max_length=80)
    responsible_id: str | None = Field(None, max_length=36)


def default_type(db: Session, kind: str, warehouse_id: str | None = None) -> OperationType | None:
    """The type a new document of this kind gets: the warehouse's own default, else the company's."""
    found = db.scalars(select(OperationType).where(OperationType.kind == kind, OperationType.is_active, OperationType.is_default)).all()
    return next((t for t in found if t.warehouse_id == warehouse_id), None) or next((t for t in found if t.warehouse_id is None), None)


def apply(db: Session, doc, kinds: tuple[str, ...], body: HeaderIn | None, me: User, warehouse_id: str | None = None, *, new: bool) -> None:
    """The header from what the form sent; on a new document, the defaults for what it didn't."""
    sent = body.model_fields_set if body is not None else set()
    if body is not None and body.operation_type_id:
        t = db.get(OperationType, body.operation_type_id)
        if t is None or not t.is_active or t.kind not in kinds:
            raise field_error("operationTypeId", "Pick an operation type for this kind of document.")
        doc.operation_type_id = t.id
    elif new or doc.operation_type_id is None:
        t = default_type(db, kinds[0], warehouse_id)
        doc.operation_type_id = t.id if t else None
    if body is not None and body.responsible_id:
        person = db.get(User, body.responsible_id)
        if person is None or not person.is_active:
            raise field_error("responsibleId", "Pick someone who is switched on.")
        doc.responsible_id = person.id
    elif new and doc.responsible_id is None:
        doc.responsible_id = me.id
    # A date or source sent replaces what the document had (the caller sets its own defaults first:
    # a receipt's purchase order, an order's needed-by date).
    if "scheduled_on" in sent:
        doc.scheduled_on = body.scheduled_on
    if "source_document" in sent:
        doc.source_document = (body.source_document or "").strip() or None


def zone() -> ZoneInfo:
    """The company's time zone: a document done just after midnight in Manila is done that day there,
    though it is still the day before in UTC (2026-10-29)."""
    from app.config import get_settings

    try:
        return ZoneInfo(get_settings().org_timezone)
    except Exception:  # noqa: BLE001 (an unknown name: the default)
        return ZoneInfo("Asia/Manila")


def _as_date(moment: datetime) -> date:
    return (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment).astimezone(zone()).date()


def today() -> date:
    return datetime.now(UTC).astimezone(zone()).date()


def done(doc, when: datetime | None = None) -> None:
    doc.done_at = when or datetime.now(UTC)
    doc.done_on = _as_date(doc.done_at)


def timing(doc, on: date | None = None) -> str | None:
    """late / on_time (done), overdue / due (not done), or None without a scheduled date; days in the
    company's time zone."""
    if doc.scheduled_on is None:
        return None
    if doc.done_at is not None:
        done_day = doc.done_on or _as_date(doc.done_at)
        return "late" if done_day > doc.scheduled_on else "on_time"
    return "overdue" if doc.scheduled_on < (on or today()) else "due"


def header_out(doc) -> dict:
    t = doc.operation_type
    return {
        "operationType": {"id": t.id, "code": t.code, "name": t.name, "kind": t.kind} if t else None,
        "scheduledOn": doc.scheduled_on.isoformat() if doc.scheduled_on else None,
        "doneAt": (doc.done_at.replace(tzinfo=UTC) if doc.done_at.tzinfo is None else doc.done_at).isoformat() if doc.done_at else None,
        "sourceDocument": doc.source_document,
        "responsible": {"id": doc.responsible.id, "name": doc.responsible.full_name} if doc.responsible else None,
        "timing": timing(doc),
    }


def narrow(query, model, operation_type: str | None, when: str | None):
    """The lists' filters: by operation type, and by timing."""
    if operation_type:
        query = query.where(model.operation_type_id == operation_type)
    if when in TIMINGS:
        now = today()
        query = query.where({
            "late": and_(model.done_on.is_not(None), model.scheduled_on.is_not(None), model.done_on > model.scheduled_on),
            "on_time": and_(model.done_on.is_not(None), model.scheduled_on.is_not(None), model.done_on <= model.scheduled_on),
            "overdue": and_(model.done_at.is_(None), model.scheduled_on < now),
            "due": and_(model.done_at.is_(None), model.scheduled_on >= now),
        }[when])
    return query


def type_out(t: OperationType) -> dict:
    return {"id": t.id, "code": t.code, "name": t.name, "kind": t.kind, "warehouseId": t.warehouse_id, "isDefault": t.is_default, "isActive": t.is_active}

