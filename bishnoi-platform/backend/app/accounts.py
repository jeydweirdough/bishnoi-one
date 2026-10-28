"""One account per person (feature plan step 4, agreed 2026-10-28).

The account (models.Account) holds a person's email, name, the one password, the
operator switch and whether they are suspended everywhere. Their standing at each
company is a membership (models.Identity, which kept its id so every app still
knows the person by it).

For one release the memberships and the staff records (nbpl_users) keep their own
copies of the email, name and password, so code that still writes those keeps
working: whatever is saved to them is carried to the account here, as it is
flushed. Sign-in and every password check read the account.
"""

from datetime import UTC, datetime

from sqlalchemy import event, func, inspect, select
from sqlalchemy.orm import Session

from app.models import Account, Identity, User, new_id


def account_by_email(db: Session, email: str) -> Account | None:
    with db.no_autoflush:
        return db.scalar(select(Account).where(func.lower(Account.email) == email.strip().lower()))


def account_of(db: Session, membership: Identity) -> Account | None:
    return db.get(Account, membership.account_id) if membership.account_id else account_by_email(db, membership.email)


def is_operator(db: Session, membership: Identity) -> bool:
    account = account_of(db, membership)
    return bool(account and account.is_operator and account.status == "active")


def runs_company(db: Session, membership: Identity) -> bool:
    """Whether this person administers the company: the company made them its administrator, or they
    are an operator (who administers every company by the switch on their account, never by a change
    to the company's own records). One email is one person, whatever their level (2026-10-28)."""
    return membership.is_company_admin or is_operator(db, membership)


def memberships(db: Session, account: Account) -> list[Identity]:
    """Every company's membership of this account: the most recently used first."""
    return list(db.scalars(
        select(Identity).where(Identity.account_id == account.id)
        .order_by(Identity.last_active_at.desc().nulls_last(), Identity.created_at)
    ))


def _changed(record, *names: str) -> bool:
    state = inspect(record)
    return any(state.attrs[n].history.has_changes() for n in names)


# First, so the accounts it adds are numbered with the rest (app/numbering.py).
@event.listens_for(Session, "before_flush", insert=True)
def _keep_accounts(session: Session, _context, _instances) -> None:
    pending: dict[str, Account] = {a.email.lower(): a for a in session.new if isinstance(a, Account)}

    def find(email: str, name: str) -> Account:
        key = email.strip().lower()
        account = pending.get(key) or account_by_email(session, key)
        if account is None:
            account = Account(id=new_id(), email=key, full_name=name)
            session.add(account)
            pending[key] = account
        return account

    def take_password(account: Account, hashed: str | None, changed: datetime | None) -> None:
        if hashed and hashed != account.password_hash:
            account.password_hash, account.password_changed_at = hashed, changed or datetime.now(UTC)

    for record in list(session.new) + list(session.dirty):
        if isinstance(record, Identity):
            new = record in session.new
            if new or record.account_id is None or _changed(record, "email"):
                account = find(record.email, record.full_name)
                record.account_id = account.id
                if account.password_hash is None:
                    take_password(account, record.password_hash, record.password_changed_at)
            else:
                account = session.get(Account, record.account_id)
            if account is None:
                continue
            if not new and _changed(record, "password_hash"):
                take_password(account, record.password_hash, record.password_changed_at)
            if not new and _changed(record, "full_name"):
                account.full_name = record.full_name
        elif isinstance(record, User):
            account = find(record.email, record.full_name)
            # A new staff record joins an account's password rather than replacing it.
            if account.password_hash is None or (record not in session.new and _changed(record, "password_hash")):
                take_password(account, record.password_hash, record.password_changed_at)
            # Platform Admins are operators (until step 5 retires the staff list).
            if record in session.new or _changed(record, "role", "is_active"):
                account.is_operator = record.role == "admin" and record.is_active is not False
