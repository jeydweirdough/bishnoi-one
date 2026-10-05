"""Record numbers people can say out loud: BUG-2026-00421, INC-2026-0007.

The kind's letters, the year, and the record's place in that year. The next
one is the highest so far plus one; the number is unique in the database, so
two made at the same moment can't share it (the second is retried).
"""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute, Session

# Each kind of ticket's number starts with its own letters: BUG-2026-00421.
TICKET_PREFIXES = {"bug": "BUG", "complaint": "CMP", "issue": "SYS", "feature": "FEA", "support": "SUP"}


def next_number(db: Session, column: InstrumentedAttribute, prefix: str, width: int) -> str:
    year = datetime.now(UTC).year
    start = f"{prefix}-{year}-"
    taken = db.scalars(select(column).where(column.like(f"{start}%"))).all()
    highest = max((int(n.removeprefix(start)) for n in taken if n.removeprefix(start).isdigit()), default=0)
    return f"{start}{highest + 1:0{width}d}"


def insert_numbered(db: Session, make: Callable[[str], object], column: InstrumentedAttribute, prefix: str, width: int):
    """Adds the record `make(number)` builds, with the next free number."""
    for _ in range(5):
        record = make(next_number(db, column, prefix, width))
        try:
            with db.begin_nested():
                db.add(record)
            return record
        except IntegrityError:
            continue
    raise RuntimeError(f"Couldn't find a free {prefix} number.")
