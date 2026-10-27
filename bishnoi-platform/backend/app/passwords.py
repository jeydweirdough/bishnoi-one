"""One password per person (decided 2026-10-27): their Bishnoi One account's.

A person has an account row at each company they work for (nbpl_identities), and
may also be Platform staff (nbpl_users, the Admin Console). Those used to keep
passwords of their own, so resetting one left the other as it was. Now every
change goes through set_for(), which writes the same password to all of them,
and the console's own sign-in checks the account's password when there is an
account. Staff with no account yet keep their staff password until they have one.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Identity, User


def account_hash(db: Session, email: str) -> str | None:
    """The person's account password (the same at every company of theirs), or None without an account."""
    return db.scalar(
        select(Identity.password_hash)
        .where(func.lower(Identity.email) == email.lower(), Identity.password_hash.is_not(None))
        .order_by(Identity.password_changed_at.desc().nulls_last())
        .limit(1)
    )


def hash_for_sign_in(db: Session, staff: User) -> str:
    """What a staff sign-in is checked against: the account's password when they have one."""
    return account_hash(db, staff.email) or staff.password_hash


def set_for(db: Session, email: str, hashed: str, now: datetime) -> None:
    """The new password, everywhere this person signs in: each company's account, and the console."""
    for row in db.scalars(select(Identity).where(func.lower(Identity.email) == email.lower())):
        row.password_hash, row.password_changed_at = hashed, now
    staff = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if staff is not None:
        staff.password_hash, staff.password_changed_at = hashed, now
