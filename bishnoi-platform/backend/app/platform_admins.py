"""A Platform Admin is everywhere (decided 2026-10-27): they run Bishnoi One itself,
so they don't wait to be added to a company. When one signs in, they have a Bishnoi
One account at every active company, as its administrator, with their one password
(app/passwords.py); a company added since is added for them the next time.

Support staff (role "member") aren't: a company adds them like anyone else.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Company, Identity, User
from app.passwords import account_hash


def admin_staff(db: Session, email: str) -> User | None:
    staff = db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    return staff if staff is not None and staff.is_active and staff.role == "admin" else None


def everywhere(db: Session, staff: User) -> int:
    """Their account at each active company, as its administrator. Returns how many were added."""
    password = account_hash(db, staff.email) or staff.password_hash
    mine = {i.company_id: i for i in db.scalars(select(Identity).where(func.lower(Identity.email) == staff.email.lower()))}
    added = 0
    for company in db.scalars(select(Company).where(Company.status == "active")):
        person = mine.get(company.id)
        if person is None:
            person = Identity(company_id=company.id, full_name=staff.full_name, email=staff.email.lower(), is_company_admin=True,
                              password_hash=password, password_changed_at=datetime.now(UTC))
            db.add(person)
            db.flush()
            audit(db, "Bishnoi One", "user.created", category="security", target=person.email, target_type="user", target_id=person.id,
                  company_id=company.id, fields=["isCompanyAdmin", "as a Platform Admin"])
            added += 1
        elif not person.is_company_admin:
            person.is_company_admin = True
            audit(db, "Bishnoi One", "user.updated", category="security", target=person.email, target_type="user", target_id=person.id,
                  company_id=company.id, fields=["isCompanyAdmin", "as a Platform Admin"])
    return added
