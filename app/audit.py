"""The audit log: who changed what, and when (app.models.AuditEntry).

Written right after the change it describes, in the same company. It names
the fields that changed, never their values, so it can be shown to admins
without leaking what a customer's phone number or a price was.
"""

import logging
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models import AuditEntry, Profile

log = logging.getLogger("crm.audit")


def audit(
    db: Session,
    actor: Profile | str,
    action: str,
    target: str = "",
    fields: Iterable[str] = (),
    *,
    on_behalf_of: Profile | None = None,
) -> None:
    """Records one change, e.g. audit(db, me, "product.updated", "AMOX-500", ["name", "unit"]).

    `on_behalf_of` names the person whose screens were being used, when a
    Developer Admin was looking through them. The line then reads
    "jun@x (as ada@y)": the log has to say who was actually at the keyboard, or
    it is not a log."""
    who = actor if isinstance(actor, str) else actor.email
    if on_behalf_of is not None:
        who = f"{who} (as {on_behalf_of.email})"
    names = sorted(set(fields))
    db.add(AuditEntry(actor_id=None if isinstance(actor, str) else actor.id, actor=who, action=action, target=target[:200], fields=names))
    db.commit()
    log.info("%s %s by %s%s", action, target, who, f" ({', '.join(names)})" if names else "")
