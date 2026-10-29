"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing an admin has to fill in before Finance works in full: a
default account left empty stops a fund step from posting, an expense category
with no account stops a liquidation being checked. Only the counts this person
may fix are sent, so a mark in their sidebar is always one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import CurrentAccess
from app.deps import DB, SettingsDep
from app.ledger import settings as posting_settings
from app.models import Account, ExpenseCategory, TaxProfile
from app.routers.invoices import issued_to_nobody
from app.routers.ledger import POSTING
from app.routers.tax import profile_complete

router = APIRouter(prefix="/finance", tags=["unset"])


# Needed only when their feature is used (cost of goods sold, step 3; equity, closing and exchange differences,
# step 16): empty, they aren't owed; set to an account switched off, they are.
OPTIONAL = {"cogs_account_id", "inventory_account_id", "capital_account_id", "drawings_account_id", "retained_earnings_account_id",
            "fx_gain_account_id", "fx_loss_account_id"}


def posting_gaps(db: Session) -> int:
    """Default accounts left empty (those every step needs), or pointing at an account switched off."""
    s = posting_settings(db)
    chosen = {key: getattr(s, key) for key in POSTING}
    active = set(db.scalars(select(Account.id).where(Account.id.in_([c for c in chosen.values() if c]), Account.is_active)))
    return sum(1 for key, c in chosen.items() if (c not in active) and not (c is None and key in OPTIONAL))


def categories_without_account(db: Session) -> int:
    """Top-level expense categories (the ones that carry the account) with none, or one switched off."""
    usable = select(Account.id).where(Account.id == ExpenseCategory.account_id, Account.is_active).exists()
    return db.scalar(select(func.count()).select_from(ExpenseCategory).where(ExpenseCategory.parent_id.is_(None), ExpenseCategory.is_active, ~usable)) or 0


@router.get("/unset")
def unset(access: CurrentAccess, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    if access.can("accounts.manage"):
        counts["postingAccounts"] = posting_gaps(db)
    if access.can("categories.manage"):
        counts["categoryAccounts"] = categories_without_account(db)
    if access.can("invoices.setup"):
        counts["invoiceSeries"] = issued_to_nobody(db)
    if access.can("tax.manage"):
        counts["taxProfile"] = 0 if profile_complete(db.get(TaxProfile, 1)) else 1
    return {k: v for k, v in counts.items() if v}


@router.get("/frame")
def frame(access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    """What every signed-in screen needs around its own content, in one request:
    the same answers as /auth/me, /finance/unset and /finance/funds/counts
    (that one only for a role that may see fund requests; null otherwise), the
    commit this API runs, for the sidebar's version line, and how many of this
    person's notifications are unread, for the bell."""
    from app.build import COMMIT, SOURCE
    from app.identity import me_out
    from app.notify import unread_count
    from app.routers.funds import waiting
    from app.routers.ledger import remind_backup

    from app.calendar_events import remind

    # Worked out as they open any page (Finance has no timers): a backup approver
    # learns of entries waiting a working day; calendar reminders fall due.
    remind_backup(db, access.user, settings)
    remind(db, access.user, settings)
    return {
        "me": me_out(access.user, settings),
        "unset": unset(access, db),
        "waiting": waiting(access.user, db, settings) if access.can("funds.view") else None,
        "build": COMMIT,
        "buildSource": SOURCE,
        "unreadNotifications": unread_count(db, access.user.id),
    }
