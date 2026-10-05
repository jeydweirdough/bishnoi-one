"""The audit log: who changed what, and when (app.models.AuditEntry).

Written in the same transaction as the change it describes. It names the
fields that changed, never their values.
"""

import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models import AuditEntry, User

log = logging.getLogger("inventory.audit")


def audit(
    db: Session,
    actor: User | str,
    action: str,
    *,
    target: str = "",
    target_type: str | None = None,
    target_id: str | None = None,
    fields: Iterable[str] = (),
) -> None:
    """Adds one line, e.g. audit(db, me, "user.updated", target="ana@x", fields=["role"]).
    The caller commits, so the line and the change stand or fall together."""
    who = actor if isinstance(actor, str) else actor.email
    names = sorted(set(fields))
    db.add(
        AuditEntry(
            actor_id=None if isinstance(actor, str) else actor.id,
            actor=who[:254],
            action=action,
            target_type=target_type,
            target_id=target_id,
            target=target[:200],
            fields=names,
        )
    )
    log.info("%s %s by %s%s", action, target, who, f" ({', '.join(names)})" if names else "")
