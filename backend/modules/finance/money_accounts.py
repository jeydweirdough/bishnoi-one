"""Money accounts shared by the BIR books and bank reconciliation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.finance.models import Account, BankAccount, LedgerSettings


def money_account_ids(db: Session) -> set[str]:
    accounts = list(db.scalars(select(Account)))
    cash = {a.id for a in accounts if a.name.strip().upper() == "CASH"}
    descendants: set[str] = set()
    frontier = cash
    while frontier:
        frontier = {a.id for a in accounts if a.parent_id in frontier} - descendants - cash
        descendants.update(frontier)
    bank_linked = {b.account_id for b in db.scalars(select(BankAccount)) if b.account_id}
    named_cash = {
        a.id
        for a in accounts
        if a.type == "asset"
        and (
            a.code.startswith(("0001-", "111", "121", "122"))
            or a.name.strip().lower().startswith(("cash in bank", "petty cash", "cash on hand"))
        )
    }
    s = db.get(LedgerSettings, 1)
    defaults = {a for a in (s.cash_account_id, s.bank_account_id, s.ewallet_account_id, s.check_account_id) if a} if s else set()
    # Inactive accounts still belong in historical books.
    return descendants | defaults | bank_linked | named_cash
