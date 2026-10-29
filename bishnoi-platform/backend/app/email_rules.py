"""One email, one account; one email domain per company (decided 2026-10-29).

- A company has one email domain (getmeds.ph), set by its administrator; no two companies share
  one, and public ones (gmail.com…) are refused: they say nothing about where someone works.
- Its people are added, and their email changed, only at that domain.
- An email is one account anywhere in Bishnoi One: one company's person, or an operator (who has
  no company and goes into any). Adding an email that is already someone's reads "This email isn't
  available", never saying whose.
- Someone whose email isn't at their company's domain can't sign in until their administrator
  changes it (no grace period, decided 2026-10-29).

An operator going into a company does so through a membership made for them there (via_operator,
app/platform_admins.py): it lets them in, it isn't one of the company's people, and these rules
don't apply to it.
"""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.accounts import account_by_email, account_of, memberships
from app.api import field_error
from app.models import Account, Company, Identity, User

# Mailboxes anyone can open: never a company's domain.
PUBLIC = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.com.ph", "ymail.com", "rocketmail.com", "outlook.com", "outlook.ph",
    "hotmail.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com",
    "gmx.com", "mail.com", "zoho.com", "zohomail.com", "yandex.com", "qq.com", "163.com",
})
DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
UNAVAILABLE = "This email isn't available."


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""


def check_domain(db: Session, company: Company, value: str | None) -> str | None:
    """The company's email domain as typed (with or without its "@"), checked; "" or None clears it."""
    domain = (value or "").strip().lower().lstrip("@")
    if not domain:
        return None
    if not DOMAIN.fullmatch(domain):
        raise field_error("emailDomain", "Enter a domain like getmeds.ph, without the name before the @.")
    if domain in PUBLIC:
        raise field_error("emailDomain", f"{domain} is a public mailbox anyone can open. Use your company's own domain.")
    other = db.scalar(select(Company).where(func.lower(Company.email_domain) == domain, Company.id != company.id))
    if other is not None:
        raise field_error("emailDomain", "That domain is another company's on Bishnoi One.")
    return domain


def check_company_email(company: Company, email: str) -> None:
    """A company's people have an email at its domain (when it has set one)."""
    if company.email_domain and domain_of(email) != company.email_domain:
        raise field_error("email", f"Use a @{company.email_domain} email: {company.name}'s people sign in with it.")


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


def off_domain(db: Session, person: Identity) -> str | None:
    """Their company's domain, when their email isn't at it (they can't sign in until it's changed)."""
    if person.via_operator:
        return None
    company = db.get(Company, person.company_id)
    if company is None or not company.email_domain or domain_of(person.email) == company.email_domain:
        return None
    return company.email_domain


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
