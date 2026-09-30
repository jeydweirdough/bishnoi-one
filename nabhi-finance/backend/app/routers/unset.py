"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing an admin has to fill in before Finance works in full: a
default account left empty stops a fund step from posting, an expense category
with no account stops a liquidation being checked. Only admins can fix these,
so only admins are sent them, and every red mark is one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import DB, CurrentUser
from app.ledger import settings as posting_settings
from app.models import Account, ExpenseCategory, TaxProfile
from app.routers.ledger import POSTING
from app.routers.tax import profile_complete

router = APIRouter(prefix="/finance", tags=["unset"])


def posting_gaps(db: Session) -> int:
    """Default accounts left empty, or pointing at an account switched off."""
    s = posting_settings(db)
    chosen = [getattr(s, key) for key in POSTING]
    active = set(db.scalars(select(Account.id).where(Account.id.in_([c for c in chosen if c]), Account.is_active)))
    return sum(1 for c in chosen if c not in active)


def categories_without_account(db: Session) -> int:
    """Top-level expense categories (the ones that carry the account) with none, or one switched off."""
    usable = select(Account.id).where(Account.id == ExpenseCategory.account_id, Account.is_active).exists()
    return db.scalar(select(func.count()).select_from(ExpenseCategory).where(ExpenseCategory.parent_id.is_(None), ExpenseCategory.is_active, ~usable)) or 0


@router.get("/unset")
def unset(user: CurrentUser, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Empty for anyone who
    isn't an admin, and kinds with nothing missing are left out."""
    if user.role != "admin":
        return {}
    counts = {
        "postingAccounts": posting_gaps(db),
        "categoryAccounts": categories_without_account(db),
        "taxProfile": 0 if profile_complete(db.get(TaxProfile, 1)) else 1,
    }
    return {k: v for k, v in counts.items() if v}
