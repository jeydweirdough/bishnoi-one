"""The one place stock changes.

Every change to a balance goes through `post`, which writes the movement
beside it in the same transaction, so the movements always add up to the
balances. Callers commit.

Picking follows FEFO: first expired, first out. Batches that expire soonest
go first, then the oldest, then stock with no batch.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Batch, Location, Movement, Order, OrderLine, Product, Sequence, Serial, Stock, Transfer, TransferLine, User

# How each kind moves on hand, given the movement's signed quantity:
# 1: on hand changes by the quantity; 0: on hand stays (reserve, release, damage).
ON_HAND = {
    "receive": 1,
    "issue": 1,
    "transfer_out": 1,
    "transfer_in": 1,
    "adjust": 1,
    "return_in": 1,
    "return_out": 1,
    "damage": 0,
    "write_off": 1,
    "expired": 1,
    "lost": 1,
    "reserve": 0,
    "release": 0,
}
# The sign a kind's quantity always has; None: either (adjust).
SIGN = {
    "receive": 1,
    "transfer_in": 1,
    "return_in": 1,
    "issue": -1,
    "transfer_out": -1,
    "return_out": -1,
    "damage": -1,
    "write_off": -1,
    "expired": -1,
    "lost": -1,
    "reserve": -1,
    "release": 1,
    "adjust": None,
}


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


@dataclass(frozen=True)
class Ref:
    """The document behind a movement."""

    type: str
    id: str
    number: str


def next_number(db: Session, prefix: str, today: date | None = None) -> str:
    """PO-2026-00001, then PO-2026-00002... numbered afresh each year."""
    year = (today or datetime.now(UTC).date()).year
    key = f"{prefix}-{year}"
    row = db.get(Sequence, key, with_for_update=True)
    if row is None:
        row = Sequence(key=key, last=0)
        db.add(row)
    row.last += 1
    db.flush()
    return f"{key}-{row.last:05d}"


# --- places -------------------------------------------------------------------------------


def default_location(db: Session, warehouse_id: str) -> Location:
    location = db.scalar(select(Location).where(Location.warehouse_id == warehouse_id, Location.is_default))
    if location is None:
        raise conflict("That warehouse has no default location. Give it one first.")
    return location


def location_in(db: Session, warehouse_id: str, location_id: str | None) -> Location:
    """The location asked for, which must be in that warehouse; or its default."""
    if not location_id:
        return default_location(db, warehouse_id)
    location = db.get(Location, location_id)
    if location is None or location.warehouse_id != warehouse_id:
        raise conflict("That location isn't in this warehouse.")
    if not location.is_active:
        raise conflict(f"Location {location.code} is switched off.")
    return location


# --- batches and serials ------------------------------------------------------------------


def resolve_batch(
    db: Session,
    product: Product,
    batch_no: str | None,
    *,
    manufactured_on: date | None = None,
    expires_on: date | None = None,
    supplier_id: str | None = None,
) -> Batch | None:
    """The batch stock comes in as: found by its number, or made. None for a
    product that isn't tracked by batch."""
    if not product.track_batches:
        if batch_no:
            raise conflict(f"{product.name} isn't tracked by batch, so it takes no batch number.")
        return None
    if not batch_no:
        raise conflict(f"{product.name} is tracked by batch: give its batch number.")
    batch = db.scalar(select(Batch).where(Batch.product_id == product.id, Batch.batch_no == batch_no))
    if batch is None:
        if product.track_expiry and expires_on is None:
            raise conflict(f"{product.name} is tracked by expiry: give batch {batch_no}'s expiry date.")
        batch = Batch(product_id=product.id, batch_no=batch_no, manufactured_on=manufactured_on, expires_on=expires_on, supplier_id=supplier_id)
        db.add(batch)
        db.flush()
    elif expires_on is not None and batch.expires_on is not None and expires_on != batch.expires_on:
        raise conflict(f"Batch {batch_no} of {product.name} is already on file expiring {batch.expires_on:%d %b %Y}.")
    elif batch.expires_on is None and expires_on is not None:
        batch.expires_on = expires_on
    return batch


def clean_serials(product: Product, serials: list[str], quantity: int) -> list[str]:
    """The serial numbers given for a line, checked against what it moves."""
    serials = [s.strip() for s in serials if s and s.strip()]
    if not product.track_serials:
        if serials:
            raise conflict(f"{product.name} isn't tracked by serial number.")
        return []
    if len(set(serials)) != len(serials):
        raise conflict(f"A serial number of {product.name} is given twice.")
    if len(serials) != abs(quantity):
        raise conflict(f"{product.name} is tracked by serial number: give {abs(quantity)} of them, one per unit (you gave {len(serials)}).")
    return serials


def serials_in(db: Session, product: Product, serials: list[str], location: Location, batch: Batch | None) -> None:
    """New units arrive: each serial must not already be in stock anywhere."""
    for number in serials:
        unit = db.scalar(select(Serial).where(Serial.product_id == product.id, Serial.serial_no == number))
        if unit is not None and unit.status in ("in_stock", "in_transit"):
            raise conflict(f"Serial {number} of {product.name} is already in stock.")
        if unit is None:
            unit = Serial(product_id=product.id, serial_no=number)
            db.add(unit)
        unit.status, unit.location_id, unit.batch_id = "in_stock", location.id, batch.id if batch else None


def serials_out(db: Session, product: Product, serials: list[str], warehouse_id: str, becomes: str, location: Location | None = None) -> None:
    """Units leave (issued, written off) or set off (in transit): each must be in stock in that warehouse."""
    for number in serials:
        unit = db.scalar(select(Serial).where(Serial.product_id == product.id, Serial.serial_no == number))
        here = unit is not None and unit.status == "in_stock" and unit.location_id is not None
        if here:
            place = db.get(Location, unit.location_id)
            here = place is not None and place.warehouse_id == warehouse_id
        if not here:
            raise conflict(f"Serial {number} of {product.name} isn't in stock in this warehouse.")
        unit.status = becomes
        unit.location_id = location.id if location else (unit.location_id if becomes == "in_transit" else None)


def serials_arrive(db: Session, product: Product, serials: list[str], location: Location) -> None:
    """Units that were in transit land in a location."""
    for number in serials:
        unit = db.scalar(select(Serial).where(Serial.product_id == product.id, Serial.serial_no == number))
        if unit is None or unit.status != "in_transit":
            raise conflict(f"Serial {number} of {product.name} isn't in transit.")
        unit.status, unit.location_id = "in_stock", location.id


# --- balances and movements ---------------------------------------------------------------


def balance(db: Session, product_id: str, location: Location, batch_id: str | None) -> Stock:
    q = select(Stock).where(Stock.product_id == product_id, Stock.location_id == location.id)
    q = q.where(Stock.batch_id.is_(None) if batch_id is None else Stock.batch_id == batch_id)
    row = db.scalar(q.with_for_update())
    if row is None:
        row = Stock(product_id=product_id, warehouse_id=location.warehouse_id, location_id=location.id, batch_id=batch_id, on_hand=0, damaged=0)
        db.add(row)
        db.flush()
    return row


def post(
    db: Session,
    actor: User,
    *,
    kind: str,
    product: Product,
    quantity: int,
    ref: Ref | None,
    location: Location | None = None,
    warehouse_id: str | None = None,
    batch: Batch | None = None,
    note: str | None = None,
    serials: list[str] | None = None,
) -> Movement:
    """One movement, and the balance it changes. `quantity` is signed the way
    the trail shows it: +500 received, -3 lost, -20 reserved."""
    if quantity == 0:
        raise conflict("A movement of nothing: give a quantity.")
    sign = SIGN[kind]
    if sign is not None and (quantity > 0) != (sign > 0):
        raise ValueError(f"{kind} takes a {'positive' if sign > 0 else 'negative'} quantity")
    if product.product_type == "service":
        raise conflict(f"{product.name} is a service, so it has no stock.")

    after = None
    change = quantity * ON_HAND[kind]
    if location is not None and kind not in ("reserve", "release"):
        row = balance(db, product.id, location, batch.id if batch else None)
        where = f" in {location.warehouse.name}" + (f", batch {batch.batch_no}" if batch else "")
        if kind == "damage":
            if row.on_hand - row.damaged < -quantity:
                raise conflict(f"Only {row.on_hand - row.damaged} of {product.name} are in good condition{where}.")
            row.damaged -= quantity
        elif kind == "write_off":
            if row.damaged < -quantity:
                raise conflict(f"Only {row.damaged} of {product.name} are set aside as damaged{where}.")
            row.damaged += quantity
            row.on_hand += change
        else:
            if change < 0 and row.on_hand - row.damaged < -change:
                raise conflict(f"Only {row.on_hand - row.damaged} of {product.name} are available{where}.")
            row.on_hand += change
        after = row.on_hand
        warehouse_id = location.warehouse_id
    if warehouse_id is None:
        raise ValueError("a movement needs a location or a warehouse")

    movement = Movement(
        kind=kind,
        product_id=product.id,
        warehouse_id=warehouse_id,
        location_id=location.id if location else None,
        batch_id=batch.id if batch else None,
        quantity=quantity,
        on_hand_change=change,
        on_hand_after=after,
        unit_cost=product.cost_price,
        reference_type=ref.type if ref else None,
        reference_id=ref.id if ref else None,
        reference=ref.number if ref else None,
        note=note,
        serials=serials or [],
        user_id=actor.id,
        user_name=actor.full_name,
    )
    db.add(movement)
    return movement


# --- what's spoken for ---------------------------------------------------------------------


def held(db: Session, *, product_ids: list[str] | None = None, warehouse_id: str | None = None, exclude_order: str | None = None) -> dict[tuple[str, str], dict[str, int]]:
    """Held by open orders, per (product, warehouse): reserved (confirmed) and allocated (being picked)."""
    q = (
        select(OrderLine.product_id, Order.warehouse_id, Order.status, func.sum(OrderLine.quantity))
        .join(Order)
        .where(Order.status.in_(("confirmed", "picking")))
        .group_by(OrderLine.product_id, Order.warehouse_id, Order.status)
    )
    if product_ids is not None:
        q = q.where(OrderLine.product_id.in_(product_ids))
    if warehouse_id:
        q = q.where(Order.warehouse_id == warehouse_id)
    if exclude_order:
        q = q.where(Order.id != exclude_order)
    out: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {"reserved": 0, "allocated": 0})
    for product_id, wh, state, qty in db.execute(q):
        out[(product_id, wh)]["reserved" if state == "confirmed" else "allocated"] += int(qty or 0)
    return out


def in_transit(db: Session, *, product_ids: list[str] | None = None) -> dict[tuple[str, str], int]:
    """On its way, per (product, destination warehouse)."""
    q = (
        select(TransferLine.product_id, Transfer.to_warehouse_id, func.sum(TransferLine.quantity))
        .join(Transfer)
        .where(Transfer.status == "in_transit")
        .group_by(TransferLine.product_id, Transfer.to_warehouse_id)
    )
    if product_ids is not None:
        q = q.where(TransferLine.product_id.in_(product_ids))
    return {(p, w): int(q or 0) for p, w, q in db.execute(q)}


def good_stock(db: Session, product_id: str, warehouse_id: str) -> int:
    """On hand and not damaged, in a warehouse."""
    q = select(func.coalesce(func.sum(Stock.on_hand - Stock.damaged), 0)).where(Stock.product_id == product_id, Stock.warehouse_id == warehouse_id)
    return int(db.scalar(q) or 0)


def available(db: Session, product_id: str, warehouse_id: str, *, exclude_order: str | None = None) -> int:
    """Good stock less what other orders hold."""
    hold = held(db, product_ids=[product_id], warehouse_id=warehouse_id, exclude_order=exclude_order).get((product_id, warehouse_id))
    taken = (hold["reserved"] + hold["allocated"]) if hold else 0
    return good_stock(db, product_id, warehouse_id) - taken


def fefo(db: Session, product: Product, warehouse_id: str, quantity: int, *, batch_id: str | None = None) -> list[tuple[Stock, int]]:
    """Where to take `quantity` from: first expired, first out."""
    q = (
        select(Stock)
        .outerjoin(Batch, Stock.batch_id == Batch.id)
        .join(Location, Stock.location_id == Location.id)
        .where(Stock.product_id == product.id, Stock.warehouse_id == warehouse_id, Stock.on_hand > Stock.damaged)
        .order_by(Batch.expires_on.is_(None), Batch.expires_on, Batch.received_at, Location.is_default.desc(), Location.code)
    )
    if batch_id:
        q = q.where(Stock.batch_id == batch_id)
    picks: list[tuple[Stock, int]] = []
    left = quantity
    for row in db.scalars(q):
        take = min(left, row.on_hand - row.damaged)
        picks.append((row, take))
        left -= take
        if left == 0:
            return picks
    have = quantity - left
    raise conflict(f"Only {have} of {product.name} {'are' if have != 1 else 'is'} available here{' in that batch' if batch_id else ''}; {quantity} needed.")


def pick_out(db: Session, actor: User, *, kind: str, product: Product, warehouse_id: str, quantity: int, ref: Ref, batch_id: str | None = None, note: str | None = None, serials: list[str] | None = None) -> list[dict]:
    """Takes stock out FEFO, one movement per balance touched, and says what was taken."""
    taken = []
    for row, take in fefo(db, product, warehouse_id, quantity, batch_id=batch_id):
        post(db, actor, kind=kind, product=product, quantity=-take, ref=ref, location=row.location, batch=row.batch, note=note, serials=serials if len(taken) == 0 else None)
        taken.append(pick_out_record(row, take))
    return taken


def pick_out_record(row: Stock, quantity: int) -> dict:
    return {
        "locationId": row.location_id,
        "locationCode": row.location.code,
        "batchId": row.batch_id,
        "batchNo": row.batch.batch_no if row.batch else None,
        "expiresOn": row.batch.expires_on.isoformat() if row.batch and row.batch.expires_on else None,
        "quantity": quantity,
    }
