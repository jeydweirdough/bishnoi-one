"""Locks for steps that move money or take a number, so two people saving at the
same moment can't both act on the same old state.

Each such step checks something (the voucher is still to release, the bill
still has that much left, the invoice still owes that much, which number is
next) and then writes. Without a lock, two requests can both pass the check
before either writes: a bill paid twice, a payment past what's owed, two
entries given the same number. So the step locks first, then reads again,
then checks:

- **PostgreSQL:** the rows it will change are locked (`SELECT ... FOR UPDATE`)
  in a fixed order, and numbers are taken under a transaction-scoped advisory
  lock per number series. Both end with the transaction.
- **SQLite:** row locks don't exist, and Python's driver only starts a
  transaction at the first write, so reads before it aren't protected at all.
  `BEGIN IMMEDIATE` takes the database's single write lock up front, so the
  reads that follow see the latest saved state and nobody else writes until
  this transaction ends.

The second request then waits, reads the new state, and gets the same plain
refusal anyone would (already released, more than is owed), never a duplicate.
"""

import zlib
from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import select, text
from sqlalchemy.orm import Session

T = TypeVar("T")

# The Finance API's own lock space (the first key), as for its migration lock
# (app/migrate.py), so other apps' advisory locks on a shared server never clash.
FINANCE_LOCKS = 4303

# How long a step waits for someone else's save before giving up (PostgreSQL).
# Giving up surfaces as the guard's "database isn't answering, try again" (app/guard.py).
LOCK_WAIT = "10s"


def _postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def begin_change(db: Session) -> None:
    """Start this request's transaction as a writer, before reading what it changes.
    Nothing pending is saved by this (a voucher being filled in stays unsaved)."""
    if _postgres(db):
        db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_WAIT}'"))
        return
    # No automatic save first: it would start an ordinary transaction, and BEGIN would then fail.
    with db.no_autoflush:
        raw = db.connection().connection.dbapi_connection
        if not raw.in_transaction:  # if it is, it has already written, so it already holds the write lock
            db.execute(text("BEGIN IMMEDIATE"))


def locked(db: Session, model: type[T], ids: Sequence[str]) -> list[T]:
    """The rows, read again under lock (fresh values replace what this session
    read before), in id order so two steps locking the same rows never deadlock.
    Only the model's own table is locked (FOR UPDATE OF): rows it loads along with
    it through an outer join can't be locked in PostgreSQL, and needn't be."""
    begin_change(db)
    ordered = sorted(set(ids))
    if not ordered:
        return []
    rows = db.scalars(select(model).where(model.id.in_(ordered)).order_by(model.id).with_for_update(of=model).execution_options(populate_existing=True)).all()
    return list(rows)


def lock_series(db: Session, prefix: str) -> None:
    """Hold the number series (e.g. JE-202610-) until this transaction ends, so
    "highest number so far + 1" can't be read by two saves at once."""
    begin_change(db)
    if _postgres(db):
        key = zlib.crc32(prefix.encode()) - 2**31  # a stable signed 32-bit key per series
        db.execute(text("SELECT pg_advisory_xact_lock(:space, :key)"), {"space": FINANCE_LOCKS, "key": key})
