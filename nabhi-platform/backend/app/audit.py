"""The audit log: who did what, and when (app.models.AuditEntry).

Written in the same transaction as the change it describes. It names the
fields that changed, never their values.

Each line has a category, which is how Activity & Audit files it:
- admin: a change to the platform (a company, an application, someone's access)
- security: signing in and out, sessions ended, staff roles and passwords
- support: tickets and incidents moving along
- system: what the platform did by itself (the first admin, a health check)
"""

import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models import AuditEntry, User

log = logging.getLogger("platform.audit")


def audit(
    db: Session,
    actor: User | str,
    action: str,
    *,
    category: str = "admin",
    target: str = "",
    target_type: str | None = None,
    target_id: str | None = None,
    fields: Iterable[str] = (),
    company_id: str | None = None,
    application_id: str | None = None,
    address: str | None = None,
) -> None:
    """Adds one line, e.g. audit(db, me, "company.updated", target="GetMeds", fields=["status"]).
    The caller commits, so the line and the change stand or fall together."""
    who = actor if isinstance(actor, str) else actor.email
    names = sorted(set(fields))
    db.add(
        AuditEntry(
            actor_id=None if isinstance(actor, str) else actor.id,
            actor=who[:254],
            action=action,
            category=category,
            target_type=target_type,
            target_id=target_id,
            target=target[:200],
            fields=names,
            company_id=company_id,
            application_id=application_id,
            address=address[:64] if address else None,
        )
    )
    log.info("%s %s by %s%s", action, target, who, f" ({', '.join(names)})" if names else "")
