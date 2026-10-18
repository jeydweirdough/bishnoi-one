"""Every person's employee ID, given as they're saved: EMP-0001, EMP-0002...

Nobody types one: the next free number is taken when a person is added,
however they're added (the users screen, a sheet of people, the first
administrator, the tools), so no two people ever hold the same one. The
column is unique as well, so the database refuses a duplicate even if two
people were added at the same moment. IDs given before this (and the demo's)
stay as they are: customers are transferred to a person by theirs.
"""

import re

from sqlalchemy import event, select
from sqlalchemy.orm import Session

PREFIX = "EMP-"
_NUMBER = re.compile(rf"^{PREFIX}(\d+)$")


def code(number: int) -> str:
    return f"{PREFIX}{number:04d}"


def highest(session: Session, model) -> int:
    """The highest EMP- number held so far, 0 with none."""
    held = session.scalars(select(model.employee_id).where(model.employee_id.like(f"{PREFIX}%"))).all()
    return max((int(m.group(1)) for c in held if c and (m := _NUMBER.match(c))), default=0)


def given_employee_ids(model) -> None:
    """Give new people of this model the next free employee IDs, as they're saved."""

    @event.listens_for(Session, "before_flush")
    def _give(session: Session, _context, _instances) -> None:
        new = [r for r in session.new if isinstance(r, model) and not r.employee_id]
        if not new:
            return
        with session.no_autoflush:
            last = highest(session, model)
        for n, person in enumerate(new, last + 1):
            person.employee_id = code(n)
