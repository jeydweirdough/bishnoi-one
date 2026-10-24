"""Finance's notifications: what's waiting on someone, or was done to their work.

Made in the same request as what they're about (Finance has no background jobs),
and sent by what a role may do, not by name, so they follow role changes. Never
to the person who did it. Shown under the bell (/finance/notifications in
app/routers/finance.py). Decided 2026-10-22 (Plans/Plan - Journal approval and
notifications; Plans/Plan - Fewer notifications and approvals):

- Once someone acts on an item, everyone's notification about it is done
  (`done`), so the bell only lists what still waits.
- Only what needs the person counts in the red number (ACTIONABLE); news such as
  "your entry was approved" is listed but not counted.
- Several of a kind show as one line ("4 journal entries are waiting for your
  approval": GROUPS).
"""

from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.access import permissions_of
from app.models import Notification, User, utcnow

# What asks something of the person: these count in the bell's red number.
# (News, not counted: entry.approved, calendar.on, calendar.shared, calendar.done.)
ACTIONABLE = (
    "entry.waiting", "entry.rejected", "fund.to_release", "fund.to_check", "fund.to_settle", "calendar.reminder",
    # Supplier bills and payment vouchers (2026-10-23, Aubrey's flow): waiting on a step, or back
    # with whoever made it.
    "bill.to_approve", "bill.to_check", "bill.returned", "bill.ready",
    "voucher.to_release", "voucher.returned",
)

# Several unread of one of these kinds show as one line, linking to the list.
GROUPS = {
    "entry.waiting": ("{n} journal entries are waiting for your approval.", "/ledger?status=waiting"),
    "fund.to_release": ("{n} cash advances are ready for release.", "/funds"),
    "fund.to_check": ("{n} liquidations are waiting for review.", "/funds/review"),
    "fund.to_settle": ("{n} refunds and reimbursements are waiting to be settled.", "/funds/settlement"),
    "calendar.reminder": ("{n} reminders from your calendar.", "/calendar"),
    "bill.to_approve": ("{n} supplier bills are waiting for your approval.", "/bills?show=to_approve"),
    "bill.to_check": ("{n} supplier bills are waiting for their tax withheld to be checked.", "/bills?show=to_check"),
    "bill.returned": ("{n} supplier bills were returned to you for correction.", "/bills?show=returned"),
    "bill.ready": ("{n} supplier bills are approved and ready to pay.", "/bills?show=ready"),
    "voucher.to_release": ("{n} payment vouchers are ready to release.", "/vouchers?show=to_release"),
    "voucher.returned": ("{n} payment vouchers were returned to you for correction.", "/vouchers?show=returned"),
}


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


def done(db: Session, kind: str, link: str) -> None:
    """Someone acted on the item at `link`: everyone's unread notification of this kind about it is done."""
    db.execute(
        update(Notification)
        .where(Notification.kind == kind, Notification.link == link, Notification.read_at.is_(None))
        .values(read_at=utcnow())
        .execution_options(synchronize_session=False)
    )


def unread_count(db: Session, user_id: str) -> int:
    """For the bell's red number: what needs this person and they haven't read."""
    return db.scalar(
        select(func.count()).where(Notification.user_id == user_id, Notification.read_at.is_(None), Notification.kind.in_(ACTIONABLE))
    ) or 0
