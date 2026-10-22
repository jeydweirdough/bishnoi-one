"""Finance's notifications: what's waiting on someone, or was done to their work.

Made in the same request as what they're about (Finance has no background jobs),
and sent by what a role may do, not by name, so they follow role changes. Never
to the person who did it. Shown under the bell (app/routers/notifications.py).
Decided 2026-10-22 (Plans/Plan - Journal approval and notifications).
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import permissions_of
from app.models import Notification, User


def holders(db: Session, permission: str) -> list[User]:
    """Everyone active whose role may do this."""
    return [u for u in db.scalars(select(User).where(User.is_active)) if permission in permissions_of(u.role)]


def tell(db: Session, people: Iterable[User | str | None], kind: str, text: str, link: str | None = None, *, not_to: Iterable[str | None] = ()) -> int:
    """One notification each (a person, or their id), leaving out `not_to` (ids). How many were made."""
    skip = {i for i in not_to if i}
    made = set()
    for p in people:
        user_id = p.id if isinstance(p, User) else p
        if not user_id or user_id in skip or user_id in made:
            continue
        db.add(Notification(user_id=user_id, kind=kind, text=text[:300], link=link))
        made.add(user_id)
    return len(made)


def tell_holders(db: Session, permission: str, kind: str, text: str, link: str | None = None, *, not_to: Iterable[str | None] = ()) -> int:
    return tell(db, holders(db, permission), kind, text, link, not_to=not_to)
