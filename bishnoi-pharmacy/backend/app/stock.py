"""Taking stock off a batch and putting it back, the one way it's done.

Every change to a batch's quantity goes through here, and each one writes a
movement (app.models.StockMovement) with the balance after it, so what's on
hand can always be explained line by line.

A batch can be dispensed or sold from only while it is *eligible*: available
(not quarantined or recalled), not expired, and with something left.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import conflict
from app.models import Batch, Medicine, StockMovement, User


def eligible_problem(batch: Batch, on: date) -> str | None:
    """Why this batch can't be given out today, or None."""
    if batch.status == "recalled":
        return f"Lot {batch.lot_no} has been recalled."
    if batch.status == "quarantined":
        return f"Lot {batch.lot_no} is in quarantine."
    if batch.expires_on <= on:
        return f"Lot {batch.lot_no} expired on {batch.expires_on.isoformat()}."
    if batch.qty_on_hand <= 0:
        return f"Lot {batch.lot_no} has none left."
    return None


def eligible_batches(db: Session, medicine_id: str, on: date) -> list[Batch]:
    """First expiry first out: the batch that expires soonest comes first."""
    return list(
        db.scalars(
            select(Batch)
            .where(Batch.medicine_id == medicine_id, Batch.status == "available", Batch.expires_on > on, Batch.qty_on_hand > 0)
            .order_by(Batch.expires_on, Batch.created_at)
        )
    )


def sellable(db: Session, medicine_ids: list[str] | None, on: date) -> dict[str, int]:
    """Units that can be given out today, per medicine."""
    q = (
        select(Batch.medicine_id, func.coalesce(func.sum(Batch.qty_on_hand), 0))
        .where(Batch.status == "available", Batch.expires_on > on)
        .group_by(Batch.medicine_id)
    )
    if medicine_ids is not None:
        if not medicine_ids:
            return {}
        q = q.where(Batch.medicine_id.in_(medicine_ids))
    return {m: int(n) for m, n in db.execute(q).all()}


def on_hand(db: Session, medicine_ids: list[str] | None = None) -> dict[str, int]:
    """Every unit on the shelf per medicine, whether it can be given out or not."""
    q = select(Batch.medicine_id, func.coalesce(func.sum(Batch.qty_on_hand), 0)).group_by(Batch.medicine_id)
    if medicine_ids is not None:
        if not medicine_ids:
            return {}
        q = q.where(Batch.medicine_id.in_(medicine_ids))
    return {m: int(n) for m, n in db.execute(q).all()}


def move(
    db: Session,
    batch: Batch,
    quantity: int,
    kind: str,
    *,
    by: User | None,
    reference: str | None = None,
    reason: str | None = None,
) -> StockMovement:
    """Changes a batch by `quantity` (+ in, - out) and writes the movement."""
    if batch.qty_on_hand + quantity < 0:
        raise conflict(f"Lot {batch.lot_no} has only {batch.qty_on_hand} left.")
    batch.qty_on_hand += quantity
    movement = StockMovement(
        kind=kind,
        medicine_id=batch.medicine_id,
        batch_id=batch.id,
        quantity=quantity,
        balance=batch.qty_on_hand,
        reason=reason,
        reference=reference,
        by_id=by.id if by else None,
    )
    db.add(movement)
    return movement


def take(db: Session, batch: Batch, quantity: int, kind: str, *, on: date, by: User, reference: str) -> None:
    """Gives `quantity` out of an eligible batch."""
    problem = eligible_problem(batch, on)
    if problem:
        raise conflict(problem)
    move(db, batch, -quantity, kind, by=by, reference=reference)


def allocate(db: Session, medicine: Medicine, quantity: int, on: date) -> list[tuple[Batch, int]]:
    """Which batches `quantity` units come from, soonest expiry first."""
    picked: list[tuple[Batch, int]] = []
    left = quantity
    for batch in eligible_batches(db, medicine.id, on):
        n = min(left, batch.qty_on_hand)
        picked.append((batch, n))
        left -= n
        if left == 0:
            return picked
    have = quantity - left
    raise conflict(f"Only {have} {medicine.unit}(s) of {medicine.label} can be given out today; {quantity} asked for.")
