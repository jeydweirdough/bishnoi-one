"""Bank reconciliation (decided 2026-10-24, from Oojeema's features): a bank
statement matched against the books, for one cash or bank account.

Start one with the statement's date and ending balance. Every movement the
books show on that account up to the date, not cleared by an earlier
statement, is listed; tick those the bank shows. The cleared balance (the last
statement's balance, plus what's ticked in, less what's ticked out) must come to
the statement's ending balance before it's finished. What the bank shows that
the books don't (charges, interest) is entered as a journal entry first; it then
appears to be ticked.

    GET    /finance/bank/accounts
    POST   /finance/bank/reconciliations           {accountId, statementDate, statementBalanceCentavos}
    GET    /finance/bank/reconciliations/{id}
    PUT    /finance/bank/reconciliations/{id}/cleared   {lineIds}
    POST   /finance/bank/reconciliations/{id}/finish
    DELETE /finance/bank/reconciliations/{id}      (an open one)
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access import permitted
from app.audit import audit
from app.deps import DB
from app.models import Account, BankReconciliation, JournalEntry, JournalLine, LedgerSettings
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance/bank", tags=["bank"])


def money_accounts(db: Session) -> list[Account]:
    """The accounts money moves through (the default cash, bank, e-wallet and check accounts), and any other asset named a bank or cash."""
    s = db.get(LedgerSettings, 1)
    ids = {a for a in (s.cash_account_id, s.bank_account_id, s.ewallet_account_id, s.check_account_id) if a} if s else set()
    q = select(Account).where(Account.is_active, Account.type == "asset")
    return [a for a in db.scalars(q.order_by(Account.code)) if a.id in ids or any(w in a.name.lower() for w in ("bank", "cash"))]


def last_done(db: Session, account_id: str) -> BankReconciliation | None:
    return db.scalar(
        select(BankReconciliation).where(BankReconciliation.account_id == account_id, BankReconciliation.status == "done")
        .order_by(BankReconciliation.statement_date.desc(), BankReconciliation.finished_at.desc()).limit(1)
    )


def book_balance(db: Session, account_id: str, upto: date | None = None) -> int:
    q = select(func.coalesce(func.sum(JournalLine.debit_centavos - JournalLine.credit_centavos), 0)).join(JournalEntry).where(JournalLine.account_id == account_id)
    if upto:
        q = q.where(JournalEntry.entry_date <= upto)
    return int(db.scalar(q) or 0)


@router.get("/accounts")
def accounts(_: permitted("bank.view"), db: DB) -> dict:
    out = []
    for a in money_accounts(db):
        done = last_done(db, a.id)
        open_one = db.scalar(select(BankReconciliation.id).where(BankReconciliation.account_id == a.id, BankReconciliation.status == "open"))
        out.append({
            "id": a.id, "code": a.code, "name": a.name, "bookBalanceCentavos": book_balance(db, a.id),
            "lastReconciled": done.statement_date.isoformat() if done else None,
            "lastStatementBalanceCentavos": done.statement_balance_centavos if done else None,
            "openId": open_one,
        })
    history = db.scalars(select(BankReconciliation).order_by(BankReconciliation.created_at.desc()).limit(30)).all()
    return {"accounts": out, "history": [summary_out(r) for r in history]}


def summary_out(r: BankReconciliation) -> dict:
    return {
        "id": r.id, "account": {"id": r.account.id, "code": r.account.code, "name": r.account.name}, "status": r.status,
        "statementDate": r.statement_date.isoformat(), "statementBalanceCentavos": r.statement_balance_centavos,
        "createdBy": r.created_by, "finishedBy": r.finished_by, "finishedAt": r.finished_at.isoformat() if r.finished_at else None,
    }


class StartIn(Api):
    account_id: str = Field(max_length=36)
    statement_date: date
    statement_balance_centavos: int


@router.post("/reconciliations", status_code=status.HTTP_201_CREATED)
def start(user: permitted("bank.reconcile"), db: DB, body: StartIn) -> dict:
    a = db.get(Account, body.account_id)
    if a is None or a not in money_accounts(db):
        raise field_error("accountId", "Pick a cash or bank account.")
    if db.scalar(select(BankReconciliation.id).where(BankReconciliation.account_id == a.id, BankReconciliation.status == "open")):
        raise field_error("accountId", f"{a.name} has a reconciliation in progress: finish or discard it first.")
    done = last_done(db, a.id)
    if done and body.statement_date <= done.statement_date:
        raise field_error("statementDate", f"{a.name} is reconciled up to {done.statement_date:%b %d, %Y}: pick a later statement.")
    r = BankReconciliation(account_id=a.id, statement_date=body.statement_date, statement_balance_centavos=body.statement_balance_centavos,
                           opening_balance_centavos=done.statement_balance_centavos if done else 0, cleared=[], created_by=user.full_name)
    db.add(r)
    db.flush()
    audit(db, user, "bank.reconciliation_started", target=f"{a.name} to {body.statement_date:%Y-%m-%d}", target_type="reconciliation", target_id=r.id)
    db.commit()
    return {"id": r.id}


def found(db: Session, rec_id: str) -> BankReconciliation:
    r = db.get(BankReconciliation, rec_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such reconciliation.")
    return r


def candidates(db: Session, r: BankReconciliation) -> list[tuple[JournalLine, JournalEntry]]:
    """The account's movements up to the statement's date that no earlier statement cleared (and, once done, those this one cleared)."""
    q = select(JournalLine, JournalEntry).join(JournalEntry).where(JournalLine.account_id == r.account_id)
    if r.status == "open":
        q = q.where(JournalLine.reconciliation_id.is_(None), JournalEntry.entry_date <= r.statement_date)
    else:
        q = q.where(JournalLine.reconciliation_id == r.id)
    return list(db.execute(q.order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.position)).all())


def detail_out(db: Session, r: BankReconciliation) -> dict:
    rows = candidates(db, r)
    ticked = set(r.cleared) if r.status == "open" else {ln.id for ln, _ in rows}
    cleared_in = sum(ln.debit_centavos for ln, _ in rows if ln.id in ticked)
    cleared_out = sum(ln.credit_centavos for ln, _ in rows if ln.id in ticked)
    cleared_balance = r.opening_balance_centavos + cleared_in - cleared_out
    return {
        **summary_out(r),
        "openingBalanceCentavos": r.opening_balance_centavos,
        "bookBalanceCentavos": book_balance(db, r.account_id, r.statement_date),
        "lines": [
            {"id": ln.id, "date": e.entry_date.isoformat(), "number": e.number, "memo": ln.description or e.memo, "reference": e.reference,
             "inCentavos": ln.debit_centavos, "outCentavos": ln.credit_centavos, "cleared": ln.id in ticked}
            for ln, e in rows
        ],
        "clearedInCentavos": cleared_in, "clearedOutCentavos": cleared_out, "clearedBalanceCentavos": cleared_balance,
        "differenceCentavos": r.statement_balance_centavos - cleared_balance,
    }


@router.get("/reconciliations/{rec_id}")
def read(_: permitted("bank.view"), db: DB, rec_id: str) -> dict:
    return detail_out(db, found(db, rec_id))


class ClearedIn(Api):
    line_ids: list[int] = Field(default_factory=list, max_length=5000)


@router.put("/reconciliations/{rec_id}/cleared")
def set_cleared(_: permitted("bank.reconcile"), db: DB, rec_id: str, body: ClearedIn) -> dict:
    r = found(db, rec_id)
    if r.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This statement is already reconciled.")
    allowed = {ln.id for ln, _ in candidates(db, r)}
    r.cleared = sorted(set(body.line_ids) & allowed)
    db.commit()
    return detail_out(db, r)


@router.post("/reconciliations/{rec_id}/finish")
def finish(user: permitted("bank.reconcile"), db: DB, rec_id: str) -> dict:
    r = found(db, rec_id)
    if r.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This statement is already reconciled.")
    d = detail_out(db, r)
    if d["differenceCentavos"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "The cleared balance doesn't match the statement yet: tick what the bank shows, or enter its charges and interest as journal entries first.")
    for ln in db.scalars(select(JournalLine).where(JournalLine.id.in_(r.cleared))):
        ln.reconciliation_id = r.id
    r.status, r.finished_at, r.finished_by = "done", datetime.now(UTC), user.full_name
    audit(db, user, "bank.reconciled", target=f"{r.account.name} to {r.statement_date:%Y-%m-%d}", target_type="reconciliation", target_id=r.id)
    db.commit()
    return detail_out(db, r)


@router.delete("/reconciliations/{rec_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard(user: permitted("bank.reconcile"), db: DB, rec_id: str) -> Response:
    r = found(db, rec_id)
    if r.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "A finished reconciliation stays.")
    audit(db, user, "bank.reconciliation_discarded", target=f"{r.account.name} to {r.statement_date:%Y-%m-%d}", target_type="reconciliation", target_id=r.id)
    db.delete(r)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
