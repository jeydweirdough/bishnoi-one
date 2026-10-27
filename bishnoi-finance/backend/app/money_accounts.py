"""Money accounts shared by the BIR books and bank reconciliation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, LedgerSettings


def money_account_ids(db: Session) -> set[str]:
    accounts = list(db.scalars(select(Account)))
    cash = {a.id for a in accounts if a.name.strip().upper() == "CASH"}
    descendants: set[str] = set()
    frontier = cash
    while frontier:
        frontier = {a.id for a in accounts if a.parent_id in frontier} - descendants - cash
        descendants.update(frontier)
    s = db.get(LedgerSettings, 1)
    defaults = {a for a in (s.cash_account_id, s.bank_account_id, s.ewallet_account_id, s.check_account_id) if a} if s else set()
    # Inactive accounts still belong in historical books.
    return descendants | defaults
