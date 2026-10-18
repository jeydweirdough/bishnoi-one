"""Moving stock between warehouses.

    Draft → Requested → Approved → In transit → Received
                  (or Cancelled, any time before it leaves)

Dispatching takes the stock out of the source (first expired, first out),
and writes down which batches left, so the same batches arrive. While it's
on the road it is in transit: counted at neither end as on hand, and shown
at the destination as coming.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import CurrentAccess, allowed
from app.api import Api, conflict, field_error, found, iso
from app.audit import audit
from app.deps import DB, CurrentUser
from app.models import Batch, Product, Transfer, TransferLine, Warehouse
from app.out import person, product_ref, warehouse_ref
from app.paging import Limit, Offset, cut, total
from app.stock import Ref, available, clean_serials, location_in, next_number, pick_out, post, serials_arrive, serials_out

router = APIRouter(prefix="/inventory", tags=["transfers"])

View = allowed("transfers.view")


class TransferLineIn(Api):
    product_id: str = Field(max_length=36)
    quantity: int = Field(gt=0, le=10**9)


class TransferIn(Api):
    from_warehouse_id: str = Field(max_length=36)
    to_warehouse_id: str = Field(max_length=36)
    notes: str | None = Field(None, max_length=4000)
    lines: list[TransferLineIn] = Field(min_length=1, max_length=200)
    # Straight to Requested, rather than kept as a draft.
    request: bool = False


class DispatchLineIn(Api):
    line_id: str = Field(max_length=36)
    batch_id: str | None = Field(None, max_length=36)
    serials: list[str] = Field(default_factory=list, max_length=10000)


class DispatchIn(Api):
    lines: list[DispatchLineIn] = Field(default_factory=list, max_length=200)


class ReceiveIn(Api):
    # Where it goes in the destination; its default location when not given.
    location_id: str | None = Field(None, max_length=36)


def transfer_brief(t: Transfer) -> dict:
    return {
        "id": t.id,
        "number": t.number,
        "status": t.status,
        "from": warehouse_ref(t.from_warehouse),
        "to": warehouse_ref(t.to_warehouse),
        "lineCount": len(t.lines),
        "units": sum(line.quantity for line in t.lines),
        "createdAt": iso(t.created_at),
        "requestedAt": iso(t.requested_at),
        "dispatchedAt": iso(t.dispatched_at),
        "receivedAt": iso(t.received_at),
    }


def transfer_out(db: DB, t: Transfer) -> dict:
    pending = t.status in ("draft", "requested", "approved")
    return {
        **transfer_brief(t),
        "notes": t.notes,
        "createdBy": person(t.created_by),
        "requestedBy": person(t.requested_by),
        "approvedBy": person(t.approved_by),
        "approvedAt": iso(t.approved_at),
        "dispatchedBy": person(t.dispatched_by),
        "receivedBy": person(t.received_by),
        "lines": [
            {
                "id": line.id,
                "product": product_ref(line.product),
                "quantity": line.quantity,
                "available": available(db, line.product_id, t.from_warehouse_id) if pending else None,
                "picks": line.picks or [],
                "serials": line.serials or [],
            }
            for line in t.lines
        ],
    }


def check_transfer(db: DB, body: TransferIn) -> None:
    if body.from_warehouse_id == body.to_warehouse_id:
        raise field_error("toWarehouseId", "Pick a different warehouse to send it to.")
    for key, wid in (("fromWarehouseId", body.from_warehouse_id), ("toWarehouseId", body.to_warehouse_id)):
        w = db.get(Warehouse, wid)
        if w is None or not w.is_active:
            raise field_error(key, "Pick a warehouse that's switched on.")
    seen = set()
    for i, line in enumerate(body.lines):
        product = db.get(Product, line.product_id)
        if product is None or product.product_type == "service":
            raise field_error(f"lines.{i}.productId", "Pick a stocked product.")
        if line.product_id in seen:
            raise field_error(f"lines.{i}.productId", f"{product.name} is on the transfer twice. Put it on one line.")
        seen.add(line.product_id)


def set_lines(t: Transfer, body: TransferIn) -> None:
    t.lines = [TransferLine(position=i, product_id=line.product_id, quantity=line.quantity) for i, line in enumerate(body.lines)]


def ref(t: Transfer) -> Ref:
    return Ref("transfer", t.id, t.number)


@router.get("/transfers")
def list_transfers(
    _: View,
    db: DB,
    status_: str | None = Query(None, alias="status", max_length=80),
    warehouse: str | None = Query(None, max_length=36),
    q: str | None = Query(None, max_length=60),
    limit: int | None = Limit(),
    offset: int = Offset(),
) -> list[dict] | dict:
    """Newest first. Without `limit`, the latest 500 (the board's columns)."""
    query = select(Transfer).order_by(Transfer.created_at.desc())
    if status_:
        query = query.where(Transfer.status.in_(status_.split(",")))
    if warehouse:
        query = query.where(or_(Transfer.from_warehouse_id == warehouse, Transfer.to_warehouse_id == warehouse))
    if q:
        query = query.where(func.lower(Transfer.number).like(f"%{q.lower()}%"))
    if limit is not None:
        return {"items": [transfer_brief(t) for t in db.scalars(cut(query.order_by(Transfer.id), limit, offset))], "total": total(db, query)}
    return [transfer_brief(t) for t in db.scalars(query.limit(500))]


def pin(w) -> dict | None:
    return {"latitude": w.latitude, "longitude": w.longitude} if w and w.latitude is not None and w.longitude is not None else None


@router.get("/transfers/map")
def transfers_map(_: View, db: DB) -> dict:
    """Transfers as routes between warehouses: everything still open, and what
    arrived in the last 30 days. With every warehouse and its pin."""
    since = datetime.now(UTC) - timedelta(days=30)
    query = (
        select(Transfer)
        .where(or_(Transfer.status.in_(("draft", "requested", "approved", "in_transit")), (Transfer.status == "received") & (Transfer.received_at >= since)))
        .order_by(Transfer.created_at.desc())
        .limit(100)
    )
    transfers = []
    for t in db.scalars(query):
        first = t.lines[0].product.name if t.lines else None
        transfers.append({
            **transfer_brief(t),
            "approvedAt": iso(t.approved_at),
            "fromPin": pin(t.from_warehouse),
            "toPin": pin(t.to_warehouse),
            "fromAddress": t.from_warehouse.address,
            "toAddress": t.to_warehouse.address,
            "firstItem": first,
        })
    warehouses = [
        {**warehouse_ref(w), "address": w.address, "pin": pin(w)}
        for w in db.scalars(select(Warehouse).where(Warehouse.is_active).order_by(Warehouse.code))
    ]
    return {"transfers": transfers, "warehouses": warehouses}


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
def create_transfer(_: allowed("transfers.create"), me: CurrentUser, db: DB, body: TransferIn) -> dict:
    check_transfer(db, body)
    t = Transfer(number=next_number(db, "TR"), from_warehouse_id=body.from_warehouse_id, to_warehouse_id=body.to_warehouse_id, notes=body.notes, created_by_id=me.id)
    set_lines(t, body)
    if body.request:
        t.status, t.requested_by_id, t.requested_at = "requested", me.id, datetime.now(UTC)
    db.add(t)
    db.flush()
    audit(db, me, "transfer.requested" if body.request else "transfer.created", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "number": t.number}


@router.get("/transfers/{transfer_id}")
def read_transfer(_: View, db: DB, transfer_id: str) -> dict:
    return transfer_out(db, found(db, Transfer, transfer_id, "transfer"))


@router.put("/transfers/{transfer_id}")
def update_transfer(_: allowed("transfers.create"), me: CurrentUser, db: DB, transfer_id: str, body: TransferIn) -> dict:
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status not in ("draft", "requested"):
        raise conflict("Once approved, a transfer can't be changed. Cancel it and write a new one.")
    check_transfer(db, body)
    t.from_warehouse_id, t.to_warehouse_id, t.notes = body.from_warehouse_id, body.to_warehouse_id, body.notes
    set_lines(t, body)
    audit(db, me, "transfer.updated", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id}


@router.delete("/transfers/{transfer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transfer(_: allowed("transfers.create"), me: CurrentUser, db: DB, transfer_id: str) -> Response:
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status != "draft":
        raise conflict("Only a draft can be deleted. Cancel it instead.")
    audit(db, me, "transfer.deleted", target=t.number, target_type="transfer", target_id=t.id)
    db.delete(t)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/transfers/{transfer_id}/request")
def request_transfer(_: allowed("transfers.create"), me: CurrentUser, db: DB, transfer_id: str) -> dict:
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status != "draft":
        raise conflict("Only a draft can be requested.")
    t.status, t.requested_by_id, t.requested_at = "requested", me.id, datetime.now(UTC)
    audit(db, me, "transfer.requested", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "status": t.status}


@router.post("/transfers/{transfer_id}/approve")
def approve_transfer(_: allowed("transfers.approve"), me: CurrentUser, db: DB, transfer_id: str) -> dict:
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status not in ("draft", "requested"):
        raise conflict(f"This transfer is already {t.status.replace('_', ' ')}.")
    now = datetime.now(UTC)
    if t.status == "draft":
        t.requested_by_id, t.requested_at = me.id, now
    t.status, t.approved_by_id, t.approved_at = "approved", me.id, now
    audit(db, me, "transfer.approved", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "status": t.status}


@router.post("/transfers/{transfer_id}/dispatch")
def dispatch_transfer(_: allowed("transfers.dispatch"), me: CurrentUser, db: DB, transfer_id: str, body: DispatchIn) -> dict:
    """The stock leaves the source warehouse and is in transit."""
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status != "approved":
        raise conflict("A transfer is dispatched once it's approved.")
    chosen = {line.line_id: line for line in body.lines}
    if set(chosen) - {line.id for line in t.lines}:
        raise field_error("lines", "A line given isn't on this transfer.")
    short = [f"{line.product.name}: {max(available(db, line.product_id, t.from_warehouse_id), 0)} of {line.quantity}" for line in t.lines if available(db, line.product_id, t.from_warehouse_id) < line.quantity]
    if short:
        raise conflict(f"Not enough free in {t.from_warehouse.name} (after what orders hold): {'; '.join(short)}.")
    for line in t.lines:
        pick = chosen.get(line.id)
        serials = clean_serials(line.product, pick.serials if pick else [], line.quantity)
        serials_out(db, line.product, serials, t.from_warehouse_id, "in_transit")
        line.picks = pick_out(db, me, kind="transfer_out", product=line.product, warehouse_id=t.from_warehouse_id, quantity=line.quantity, ref=ref(t), batch_id=pick.batch_id if pick else None, note=f"To {t.to_warehouse.name}", serials=serials)
        line.serials = serials
    t.status, t.dispatched_by_id, t.dispatched_at = "in_transit", me.id, datetime.now(UTC)
    audit(db, me, "transfer.dispatched", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "status": t.status}


@router.post("/transfers/{transfer_id}/receive")
def receive_transfer(_: allowed("transfers.receive"), me: CurrentUser, db: DB, transfer_id: str, body: ReceiveIn) -> dict:
    """It arrives: the same batches go into the destination."""
    t = found(db, Transfer, transfer_id, "transfer")
    if t.status != "in_transit":
        raise conflict("Only a transfer in transit can be received.")
    location = location_in(db, t.to_warehouse_id, body.location_id)
    for line in t.lines:
        for i, pick in enumerate(line.picks or []):
            batch = db.get(Batch, pick["batchId"]) if pick.get("batchId") else None
            post(db, me, kind="transfer_in", product=line.product, quantity=pick["quantity"], ref=ref(t), location=location, batch=batch, note=f"From {t.from_warehouse.name}", serials=line.serials if i == 0 else None)
        serials_arrive(db, line.product, line.serials or [], location)
    t.status, t.received_by_id, t.received_at = "received", me.id, datetime.now(UTC)
    audit(db, me, "transfer.received", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "status": t.status}


@router.post("/transfers/{transfer_id}/cancel")
def cancel_transfer(access: CurrentAccess, me: CurrentUser, db: DB, transfer_id: str) -> dict:
    t = found(db, Transfer, transfer_id, "transfer")
    # A request is its writer's to withdraw; an approved one, an approver's.
    access.require("transfers.create" if t.status in ("draft", "requested") else "transfers.approve")
    if t.status in ("in_transit", "received", "cancelled"):
        raise conflict("Once it has left, a transfer can't be cancelled. Receive it, then send it back.")
    t.status = "cancelled"
    audit(db, me, "transfer.cancelled", target=t.number, target_type="transfer", target_id=t.id)
    db.commit()
    return {"id": t.id, "status": t.status}
