"""An operator is everywhere (decided 2026-10-27; the operator switch since step 4,
2026-10-28): they run Bishnoi One itself, so they don't wait to be added to a company.
When one signs in, they have a membership at every active company where they had none,
marked as made for an operator (via_operator); a company added since is added for them
the next time. Such a membership only lets them in: it holds no role of the company's, isn't
one of its people, and isn't ticked as its administrator. An operator administers every company
by the switch on their account (accounts.runs_company); a membership the company itself made
(an operator who also works there) is left exactly as the company set it (2026-10-28).

Today an operator is a Platform Admin on the staff list (app/accounts.py keeps the switch
the same); Support staff aren't operators: a company adds them like anyone else.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Account, Company, Identity


def everywhere(db: Session, account: Account) -> int:
    """Their membership at each active company, as its administrator. Returns how many were added."""
    mine = {i.company_id: i for i in db.scalars(select(Identity).where(Identity.account_id == account.id))}
    added = 0
    for company in db.scalars(select(Company).where(Company.status == "active")):
        person = mine.get(company.id)
        if person is None:
            person = Identity(company_id=company.id, account_id=account.id, full_name=account.full_name, email=account.email,
                              is_company_admin=False, via_operator=True,
                              password_hash=account.password_hash, password_changed_at=account.password_changed_at or datetime.now(UTC))
            db.add(person)
            db.flush()
            audit(db, "Bishnoi One", "user.created", category="security", target=person.email, target_type="user", target_id=person.id,
                  company_id=company.id, fields=["as an operator"])
            added += 1
    return added
