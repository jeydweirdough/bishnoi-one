"""The number each of this app's main records gets, from 40000001 up (the
record_numbers migration). On Postgres the database gives it (a sequence
per table), so two made at once never share one. SQLite has no sequences, so
there the next number is given here, as each is saved."""

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

FIRST = 40000001


def numbered(*models) -> None:
    """Number these models' new records on SQLite, as they're saved."""

    @event.listens_for(Session, "before_flush")
    def _number(session: Session, _context, _instances) -> None:
        bind = session.get_bind()
        if bind.dialect.name != "sqlite":
            return
        nexts: dict[type, int] = {}
        for record in session.new:
            model = type(record)
            if model not in models or getattr(record, "no", None) is not None:
                continue
            if model not in nexts:
                with session.no_autoflush:
                    nexts[model] = (session.execute(select(func.max(model.no))).scalar() or FIRST - 1) + 1
            record.no = nexts[model]
            nexts[model] += 1
