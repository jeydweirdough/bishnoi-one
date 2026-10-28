"""One password per person (decided 2026-10-27), kept on their account (step 4, 2026-10-28).

Everything that checks a password reads the account (app/accounts.py). A change goes
through set_for(), which also writes the copies the memberships and the staff record
keep for one release, so nothing reading them sees an old one.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts import account_by_email
from app.models import Identity, User


def account_hash(db: Session, email: str) -> str | None:
    """The person's password, or None when they have no account or no password yet."""
    account = account_by_email(db, email)
    return account.password_hash if account else None


def hash_for_sign_in(db: Session, staff: User) -> str:
    """What a staff sign-in is checked against: the account's password."""
    return account_hash(db, staff.email) or staff.password_hash


def set_for(db: Session, email: str, hashed: str, now: datetime) -> None:
    """The new password, everywhere this person signs in."""
    account = account_by_email(db, email)
    if account is not None:
        account.password_hash, account.password_changed_at = hashed, now
    for row in db.scalars(select(Identity).where(func.lower(Identity.email) == email.lower())):
        row.password_hash, row.password_changed_at = hashed, now
    staff = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if staff is not None:
        staff.password_hash, staff.password_changed_at = hashed, now
