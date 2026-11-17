"""One email, one account (decided 2026-10-29).

- An email is one account anywhere in Bishnoi One: one company's person, or an operator (who has
  no company and goes into any). Adding an email that is already someone's reads "This email isn't
  available", never saying whose.
- Any email will do (Gmail too): whoever manages a company's employees adds them with the email they
  were given (the one-email-domain-per-company rule was removed on 2026-11-17, owner's decision).

An operator going into a company does so through a membership made for them there (via_operator,
app/platform_admins.py): it lets them in, it isn't one of the company's people, and these rules
don't apply to it.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts import account_by_email, account_of, memberships
from app.api import field_error
from app.models import Account, Identity, User

UNAVAILABLE = "This email isn't available."


def home(db: Session, account: Account) -> Identity | None:
    """The company this account belongs to: its active membership the company made (not an operator's)."""
    return next((m for m in memberships(db, account) if not m.via_operator and m.status == "active"), None)


def check_available(db: Session, email: str, company_id: str | None, but_account: str | None = None) -> None:
    """Refused when the email is already an operator's, or a person's at another company."""
    account = account_by_email(db, email)
    if account is None or account.id == but_account:
        return
    if account.is_operator or db.scalar(select(User.id).where(func.lower(User.email) == email.lower(), User.is_active, User.role == "admin")):
        raise field_error("email", UNAVAILABLE)
    for m in memberships(db, account):
        if not m.via_operator and m.status == "active" and m.company_id != company_id:
            raise field_error("email", UNAVAILABLE)


def change_email(db: Session, person: Identity, new: str) -> str:
    """Their account's email, and every copy of it, becomes `new` (checked by the caller). Returns the old one.
    The account keeps its id, password, signature and history; they sign in with the new email."""
    new = new.strip().lower()
    account = account_of(db, person)
    old = person.email
    if account is None:
        person.email = new
        return old
    old = account.email
    account.email = new
    db.flush()  # first, so the memberships below find the account under its new email (app/accounts.py)
    for row in memberships(db, account):
        row.email = new
    staff = db.scalar(select(User).where(func.lower(User.email) == old.lower()))
    if staff is not None:
        staff.email = new
    db.flush()
    return old
