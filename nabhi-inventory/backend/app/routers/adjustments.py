"""Correcting stock: adjustments, and the physical counts they often come from.

An adjustment always has a reason, and is logged as a movement. Someone who
may approve adjustments posts theirs at once; anyone else's waits for them
(the "limited" adjusting a warehouse role has).

A count writes down what the system expects when it starts. People count;
the count is submitted; an approver approves it, and every difference is
posted as one adjustment, with the count as its source.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query, Response, status
from pydantic import Field, field_validator
from sqlalchemy import select

from app.access import CurrentAccess, allowed
from app.api import Api, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import ADJUSTMENT_REASONS, Adjustment, AdjustmentLine, Batch, Category, Count, CountLine, Location, Product, Stock, User, Warehouse
from app.out import batch_ref, location_ref, person, product_ref, warehouse_ref
from app.routers.stock import in_category
from app.stock import Ref, available, clean_serials, next_number, post, resolve_batch, serials_in, serials_out

router = APIRouter(prefix="/inventory", tags=["adjustments"])

# Reasons that only ever add, and only ever remove. The rest go either way.
ADDS = {"found", "customer_return"}
REMOVES = {"supplier_return", "damaged", "write_off", "expired", "lost"}

REASON_LABELS = {
    "count": "Count correction",
    "found": "Found",
    "other": "Other",
    "customer_return": "Customer return",
    "supplier_return": "Returned to supplier",
    "damaged": "Damaged",
    "write_off": "Written off (damaged)",
    "expired": "Expired",
    "lost": "Lost / missing",
}


class AdjustmentLineIn(Api):
    product_id: str = Field(max_length=36)
    location_id: str | None = Field(None, max_length=36)
    # An existing batch, or a batch number (made if new) for stock that adds.
    batch_id: str | None = Field(None, max_length=36)
    batch_no: str | None = Field(None, max_length=60)
    expires_on: date | None = None
    quantity: int = Field(ge=-(10**9), le=10**9)
    serials: list[str] = Field(default_factory=list, max_length=10000)

    @field_validator("quantity")
    @classmethod
    def _nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Give a quantity other than 0.")
        return v


class AdjustmentIn(Api):
    warehouse_id: str = Field(max_length=36)
    reason: str
    notes: str | None = Field(None, max_length=4000)
    lines: list[AdjustmentLineIn] = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        if v not in ADJUSTMENT_REASONS:
            raise ValueError("Pick a reason.")
        return v


def adjustment_brief(a: Adjustment) -> dict:
    return {
        "id": a.id,
        "number": a.number,
        "status": a.status,
        "reason": a.reason,
        "reasonLabel": REASON_LABELS[a.reason],
        "warehouse": warehouse_ref(a.warehouse),
        "lineCount": len(a.lines),
        "units": sum(line.quantity for line in a.lines),
        "value": sum(line.quantity * line.product.cost_price for line in a.lines),
        "countId": a.count_id,
        "createdAt": iso(a.created_at),
        "createdBy": person(a.created_by),
        "decidedBy": person(a.decided_by),
        "decidedAt": iso(a.decided_at),
    }


def adjustment_out(a: Adjustment, warn: int) -> dict:
    return {
        **adjustment_brief(a),
        "notes": a.notes,
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "location": location_ref(line.location),
                "batch": batch_ref(line.batch, warn),
                "quantity": line.quantity,
                "value": line.quantity * line.product.cost_price,
                "serials": line.serials or [],
            }
            for line in a.lines
        ],
    }


def signed(reason: str, quantity: int) -> int:
    """Reasons that only add or only remove take the size and give it the sign."""
    if reason in ADDS:
        return abs(quantity)
    if reason in REMOVES:
        return -abs(quantity)
    return quantity


def build_lines(db: DB, warehouse: Warehouse, reason: str, body_lines: list[AdjustmentLineIn]) -> list[AdjustmentLine]:
    lines = []
    for i, line in enumerate(body_lines):
        product = db.get(Product, line.product_id)
        if product is None or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product.")
        quantity = signed(reason, line.quantity)
        location = db.get(Location, line.location_id) if line.location_id else db.scalar(select(Location).where(Location.warehouse_id == warehouse.id, Location.is_default))
        if location is None or location.warehouse_id != warehouse.id:
            raise field_error(f"lines.{i}.locationId", "Pick a location in this warehouse.")
        batch = None
        if line.batch_id:
            batch = db.get(Batch, line.batch_id)
            if batch is None or batch.product_id != product.id:
                raise field_error(f"lines.{i}.batchId", f"That batch isn't one of {product.name}'s.")
        elif product.track_batches:
            if quantity < 0 or reason == "damaged":
                raise field_error(f"lines.{i}.batchId", f"{product.name} is tracked by batch: pick which batch.")
            batch = resolve_batch(db, product, line.batch_no, expires_on=line.expires_on)
        serials = clean_serials(product, line.serials, quantity)
        lines.append(AdjustmentLine(position=i, product_id=product.id, location_id=location.id, batch_id=batch.id if batch else None, quantity=quantity, serials=serials))
    return lines


def post_adjustment(db: DB, me: User, a: Adjustment) -> None:
    """Posts every line: one movement each."""
    kind = ADJUSTMENT_REASONS[a.reason]
    ref = Ref("adjustment", a.id, a.number)
    for line in a.lines:
        product = db.get(Product, line.product_id)
        location = db.get(Location, line.location_id)
        batch = db.get(Batch, line.batch_id) if line.batch_id else None
        if line.quantity < 0 and kind not in ("damage", "write_off"):
            # Taking stock away mustn't eat into what orders already hold.
            free = available(db, product.id, a.warehouse_id)
            if free < -line.quantity:
                raise conflict(f"Only {max(free, 0)} of {product.name} are free in {a.warehouse.name} after what orders hold.")
        if product.track_serials:
            if line.quantity > 0:
                serials_in(db, product, line.serials or [], location, batch)
            elif kind != "damage":
                serials_out(db, product, line.serials or [], a.warehouse_id, "written_off")
        post(db, me, kind=kind, product=product, quantity=line.quantity, ref=ref, location=location, batch=batch, note=REASON_LABELS[a.reason] + (f": {a.notes}" if a.notes else ""), serials=line.serials)
    a.status, a.decided_by_id, a.decided_at = "posted", me.id, datetime.now(UTC)


@router.get("/adjustments/reasons")
def reasons(_: CurrentUser) -> list[dict]:
    return [{"key": k, "label": REASON_LABELS[k], "direction": "adds" if k in ADDS else "removes" if k in REMOVES else "either"} for k in ADJUSTMENT_REASONS]


@router.get("/adjustments")
def list_adjustments(
    _: allowed("adjustments.view"),
    db: DB,
    status_: str | None = Query(None, alias="status", max_length=40),
    warehouse: str | None = Query(None, max_length=36),
    reason: str | None = Query(None, max_length=20),
) -> list[dict]:
    query = select(Adjustment).order_by(Adjustment.created_at.desc()).limit(500)
    if status_:
        query = query.where(Adjustment.status.in_(status_.split(",")))
    if warehouse:
        query = query.where(Adjustment.warehouse_id == warehouse)
    if reason:
        query = query.where(Adjustment.reason == reason)
    return [adjustment_brief(a) for a in db.scalars(query)]


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
def create_adjustment(access: CurrentAccess, _: allowed("adjustments.create"), me: CurrentUser, db: DB, body: AdjustmentIn) -> dict:
    warehouse = db.get(Warehouse, body.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    a = Adjustment(number=next_number(db, "ADJ"), warehouse_id=warehouse.id, reason=body.reason, notes=body.notes, created_by_id=me.id)
    a.lines = build_lines(db, warehouse, body.reason, body.lines)
    db.add(a)
    db.flush()
    # An approver's own adjustment needs nobody else: it's posted now.
    if access.can("adjustments.approve"):
        post_adjustment(db, me, a)
    audit(db, me, "adjustment.posted" if a.status == "posted" else "adjustment.submitted", target=a.number, target_type="adjustment", target_id=a.id)
    db.commit()
    return {"id": a.id, "number": a.number, "status": a.status}


@router.get("/adjustments/{adjustment_id}")
def read_adjustment(_: allowed("adjustments.view"), db: DB, settings: SettingsDep, adjustment_id: str) -> dict:
    return adjustment_out(found(db, Adjustment, adjustment_id, "adjustment"), settings.expiry_warning_days)


@router.post("/adjustments/{adjustment_id}/approve")
def approve_adjustment(_: allowed("adjustments.approve"), me: CurrentUser, db: DB, adjustment_id: str) -> dict:
    a = found(db, Adjustment, adjustment_id, "adjustment")
    if a.status != "pending":
        raise conflict(f"This adjustment is already {a.status}.")
    post_adjustment(db, me, a)
    audit(db, me, "adjustment.approved", target=a.number, target_type="adjustment", target_id=a.id)
    db.commit()
    return {"id": a.id, "status": a.status}


@router.post("/adjustments/{adjustment_id}/reject")
def reject_adjustment(_: allowed("adjustments.approve"), me: CurrentUser, db: DB, adjustment_id: str) -> dict:
    a = found(db, Adjustment, adjustment_id, "adjustment")
    if a.status != "pending":
        raise conflict(f"This adjustment is already {a.status}.")
    a.status, a.decided_by_id, a.decided_at = "rejected", me.id, datetime.now(UTC)
    audit(db, me, "adjustment.rejected", target=a.number, target_type="adjustment", target_id=a.id)
    db.commit()
    return {"id": a.id, "status": a.status}


# --- counts -----------------------------------------------------------------------------


class CountIn(Api):
    warehouse_id: str = Field(max_length=36)
    category_id: str | None = Field(None, max_length=36)
    notes: str | None = Field(None, max_length=4000)


class CountedIn(Api):
    line_id: str = Field(max_length=36)
    counted: int | None = Field(None, ge=0, le=10**9)


class CountedLinesIn(Api):
    lines: list[CountedIn] = Field(max_length=5000)


class ExtraLineIn(Api):
    """Something found that the system didn't expect here."""

    product_id: str = Field(max_length=36)
    location_id: str | None = Field(None, max_length=36)
    batch_id: str | None = Field(None, max_length=36)
    counted: int = Field(ge=0, le=10**9)


def count_brief(c: Count) -> dict:
    counted = [line for line in c.lines if line.counted is not None]
    return {
        "id": c.id,
        "number": c.number,
        "status": c.status,
        "warehouse": warehouse_ref(c.warehouse),
        "category": {"id": c.category.id, "name": c.category.name} if c.category else None,
        "lineCount": len(c.lines),
        "countedCount": len(counted),
        "varianceCount": sum(1 for line in counted if line.counted != line.expected),
        "varianceUnits": sum(line.counted - line.expected for line in counted),
        "varianceValue": sum((line.counted - line.expected) * line.product.cost_price for line in counted),
        "createdAt": iso(c.created_at),
        "createdBy": person(c.created_by),
        "approvedBy": person(c.approved_by),
        "approvedAt": iso(c.approved_at),
    }


def count_out(c: Count, warn: int) -> dict:
    return {
        **count_brief(c),
        "notes": c.notes,
        "submittedBy": person(c.submitted_by),
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "location": location_ref(line.location),
                "batch": batch_ref(line.batch, warn),
                "expected": line.expected,
                "counted": line.counted,
                "difference": None if line.counted is None else line.counted - line.expected,
                "unitCost": line.product.cost_price,
            }
            for line in c.lines
        ],
    }


@router.get("/counts")
def list_counts(_: allowed("counts.view"), db: DB, status_: str | None = Query(None, alias="status", max_length=40)) -> list[dict]:
    query = select(Count).order_by(Count.created_at.desc()).limit(200)
    if status_:
        query = query.where(Count.status.in_(status_.split(",")))
    return [count_brief(c) for c in db.scalars(query)]


@router.post("/counts", status_code=status.HTTP_201_CREATED)
def start_count(_: allowed("counts.create"), me: CurrentUser, db: DB, body: CountIn) -> dict:
    """Starts a count: every balance in the warehouse (or in one category) is
    written down as what's expected."""
    warehouse = db.get(Warehouse, body.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise field_error("warehouseId", "Pick a warehouse that's switched on.")
    query = select(Stock).join(Product).join(Location, Stock.location_id == Location.id).where(Stock.warehouse_id == warehouse.id, Stock.on_hand > 0).order_by(Location.code, Product.name)
    if body.category_id:
        if db.get(Category, body.category_id) is None:
            raise field_error("categoryId", "Pick a category that exists.")
        query = query.where(Product.category_id.in_(in_category(db, body.category_id)))
    c = Count(number=next_number(db, "CNT"), warehouse_id=warehouse.id, category_id=body.category_id, notes=body.notes, created_by_id=me.id)
    c.lines = [CountLine(position=i, product_id=s.product_id, location_id=s.location_id, batch_id=s.batch_id, expected=s.on_hand) for i, s in enumerate(db.scalars(query))]
    db.add(c)
    db.flush()
    audit(db, me, "count.started", target=c.number, target_type="count", target_id=c.id)
    db.commit()
    return {"id": c.id, "number": c.number}


@router.get("/counts/{count_id}")
def read_count(_: allowed("counts.view"), db: DB, settings: SettingsDep, count_id: str) -> dict:
    c = found(db, Count, count_id, "count")
    out = count_out(c, settings.expiry_warning_days)
    out["adjustmentId"] = db.scalar(select(Adjustment.id).where(Adjustment.count_id == c.id))
    return out


def open_count(db: DB, count_id: str) -> Count:
    c = found(db, Count, count_id, "count")
    if c.status != "open":
        raise conflict(f"This count is {c.status}: its figures can't change now.")
    return c


@router.put("/counts/{count_id}/lines")
def record_counts(_: allowed("counts.create"), me: CurrentUser, db: DB, count_id: str, body: CountedLinesIn) -> dict:
    """What was found, line by line. Saving again overwrites; blank is not yet counted."""
    c = open_count(db, count_id)
    lines = {line.id: line for line in c.lines}
    for i, item in enumerate(body.lines):
        line = lines.get(item.line_id)
        if line is None:
            raise field_error(f"lines.{i}.lineId", "That line isn't on this count.")
        line.counted = item.counted
    db.commit()
    return count_brief(c)


@router.post("/counts/{count_id}/lines", status_code=status.HTTP_201_CREATED)
def add_count_line(_: allowed("counts.create"), me: CurrentUser, db: DB, count_id: str, body: ExtraLineIn) -> dict:
    c = open_count(db, count_id)
    product = db.get(Product, body.product_id)
    if product is None or product.product_type == "service":
        raise field_error("productId", "Pick a stocked product.")
    location = db.get(Location, body.location_id) if body.location_id else db.scalar(select(Location).where(Location.warehouse_id == c.warehouse_id, Location.is_default))
    if location is None or location.warehouse_id != c.warehouse_id:
        raise field_error("locationId", "Pick a location in this warehouse.")
    if product.track_batches and not body.batch_id:
        raise field_error("batchId", f"{product.name} is tracked by batch: pick which batch.")
    if body.batch_id:
        batch = db.get(Batch, body.batch_id)
        if batch is None or batch.product_id != product.id:
            raise field_error("batchId", f"That batch isn't one of {product.name}'s.")
    if any(line.product_id == product.id and line.location_id == location.id and line.batch_id == body.batch_id for line in c.lines):
        raise conflict("That's already on the count. Enter the figure on its line.")
    line = CountLine(count_id=c.id, position=len(c.lines), product_id=product.id, location_id=location.id, batch_id=body.batch_id, expected=0, counted=body.counted)
    db.add(line)
    db.commit()
    return {"id": line.id}


@router.post("/counts/{count_id}/submit")
def submit_count(_: allowed("counts.create"), me: CurrentUser, db: DB, count_id: str) -> dict:
    c = open_count(db, count_id)
    missing = sum(1 for line in c.lines if line.counted is None)
    if missing:
        raise conflict(f"{missing} line{'s haven' if missing != 1 else ' hasn'}'t been counted yet. Count them (0 if none are there) first.")
    c.status, c.submitted_by_id = "submitted", me.id
    audit(db, me, "count.submitted", target=c.number, target_type="count", target_id=c.id)
    db.commit()
    return {"id": c.id, "status": c.status}


@router.post("/counts/{count_id}/reopen")
def reopen_count(_: allowed("counts.approve"), me: CurrentUser, db: DB, count_id: str) -> dict:
    """Sends it back for counting again."""
    c = found(db, Count, count_id, "count")
    if c.status != "submitted":
        raise conflict("Only a submitted count can go back for recounting.")
    c.status = "open"
    audit(db, me, "count.reopened", target=c.number, target_type="count", target_id=c.id)
    db.commit()
    return {"id": c.id, "status": c.status}


@router.post("/counts/{count_id}/approve")
def approve_count(_: allowed("counts.approve"), me: CurrentUser, db: DB, count_id: str) -> dict:
    """Every difference becomes one posted adjustment (reason: count)."""
    c = found(db, Count, count_id, "count")
    if c.status != "submitted":
        raise conflict("Submit the count before approving it.")
    differences = [line for line in c.lines if line.counted is not None and line.counted != line.expected]
    serial = [line.product.name for line in differences if line.product.track_serials]
    if serial:
        raise conflict(
            f"{', '.join(sorted(set(serial)))} {'is' if len(set(serial)) == 1 else 'are'} tracked by serial number. "
            "Adjust those with the serial numbers found or missing, then count again."
        )
    adjustment_id = None
    if differences:
        a = Adjustment(number=next_number(db, "ADJ"), warehouse_id=c.warehouse_id, reason="count", notes=f"From count {c.number}", count_id=c.id, created_by_id=me.id)
        a.lines = [
            AdjustmentLine(position=i, product_id=line.product_id, location_id=line.location_id, batch_id=line.batch_id, quantity=line.counted - line.expected)
            for i, line in enumerate(differences)
        ]
        db.add(a)
        db.flush()
        post_adjustment(db, me, a)
        adjustment_id = a.id
    c.status, c.approved_by_id, c.approved_at = "approved", me.id, datetime.now(UTC)
    audit(db, me, "count.approved", target=c.number, target_type="count", target_id=c.id)
    db.commit()
    return {"id": c.id, "status": c.status, "adjustmentId": adjustment_id}


@router.post("/counts/{count_id}/cancel")
def cancel_count(_: allowed("counts.create"), me: CurrentUser, db: DB, count_id: str) -> dict:
    c = found(db, Count, count_id, "count")
    if c.status not in ("open", "submitted"):
        raise conflict(f"This count is already {c.status}.")
    c.status = "cancelled"
    audit(db, me, "count.cancelled", target=c.number, target_type="count", target_id=c.id)
    db.commit()
    return {"id": c.id, "status": c.status}


@router.delete("/adjustments/{adjustment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adjustment(_: allowed("adjustments.create"), me: CurrentUser, db: DB, adjustment_id: str) -> Response:
    """Withdraws one still waiting. A posted adjustment is history and stays."""
    a = found(db, Adjustment, adjustment_id, "adjustment")
    if a.status != "pending":
        raise conflict("Only an adjustment still waiting can be withdrawn.")
    audit(db, me, "adjustment.withdrawn", target=a.number, target_type="adjustment", target_id=a.id)
    db.delete(a)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

