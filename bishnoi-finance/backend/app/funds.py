"""Funds released to people in other apps, and how each was spent.

A request arrives here once it's approved where it was made (the CRM: the
requester's Team Lead). From then on it's Finance's:

    to_release ─ release ─┬─ not liquidated ───────────────────────────► closed
                          └─ to_liquidate ─ submit ─► to_check ─ finish ─┬─► to_return ─ unused funds in ──► closed
                                  ▲                      │               ├─► to_reimburse ─ paid ───► closed
                                  └──── send back ───────┘               └─► closed (nothing either way)
    to_release ─ cancel ─► cancelled

What a liquidation comes to: the money released, less what was spent on
reimbursable categories (the rest is the person's own). Left over is unused funds
to hand back; short is what Finance reimburses. A receipt Finance refuses
doesn't count either.
"""

import base64
import binascii
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ExpenseCategory, FundEvent, FundExpense, FundRequest, StoredFile

RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}
MAX_RECEIPT_BYTES = 4 * 1024 * 1024
RELEASE_METHODS = {"cash": "Cash", "bank": "Bank transfer", "ewallet": "E-wallet (GCash, Maya)", "check": "Check"}
STATUS_LABELS = {
    "to_release": "For release",
    "to_liquidate": "Released: pending liquidation",
    "to_check": "For liquidation review",
    "to_return": "Refund due",
    "to_reimburse": "Reimbursement due",
    "closed": "Settled",
    "cancelled": "Cancelled",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment).isoformat()


def conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def must_be(r: FundRequest, *statuses: str) -> None:
    if r.status not in statuses:
        raise conflict(f"This request is now {STATUS_LABELS[r.status].lower()}; the action is no longer available.")


def event(r: FundRequest, kind: str, who: str, text: str, amount: int | None = None) -> None:
    r.events.append(FundEvent(kind=kind, who=who[:120], text=text[:500], amount_centavos=amount, at=utcnow()))


def peso(centavos: int) -> str:
    return f"₱{centavos / 100:,.2f}"


# --- what it comes to -------------------------------------------------------------------------


@dataclass
class Tally:
    spent: int  # every receipt sent in
    covered: int  # reimbursable, and not refused
    own: int  # on a category that isn't reimbursable
    refused: int  # refused by Finance
    balance: int  # released − covered: above zero, unused funds; below, owed to them


def counts(e: FundExpense) -> bool:
    """A receipt counts against the money unless it's refused (one not
    checked yet counts, so the requester sees what it will likely come to)."""
    return e.accepted is not False


def tally(r: FundRequest) -> Tally:
    spent = sum(e.amount_centavos for e in r.expenses)
    refused = sum(e.amount_centavos for e in r.expenses if not counts(e))
    covered = sum(e.amount_centavos for e in r.expenses if counts(e) and e.category is not None and e.category.covered)
    own = spent - refused - covered
    return Tally(spent=spent, covered=covered, own=own, refused=refused, balance=(r.released_centavos or 0) - covered)


def settle(r: FundRequest, who: str) -> None:
    """The check is done: what it came to, and what's next."""
    t = tally(r)
    r.covered_centavos = t.covered
    r.return_due_centavos = max(t.balance, 0)
    r.reimburse_due_centavos = max(-t.balance, 0)
    r.checked_at = utcnow()
    if t.balance > 0:
        r.status = "to_return"
        event(r, "checked", who, f"Liquidation reviewed: {peso(t.covered)} charged to company expense; refund due of {peso(t.balance)}.", t.balance)
    elif t.balance < 0:
        r.status = "to_reimburse"
        event(r, "checked", who, f"Liquidation reviewed: {peso(t.covered)} charged to company expense; reimbursement due of {peso(-t.balance)}.", -t.balance)
    else:
        close(r, who, f"Liquidation reviewed: {peso(t.covered)} charged to company expense, equal to the cash advance. Fully liquidated.")


def close(r: FundRequest, who: str, text: str) -> None:
    r.status = "closed"
    r.closed_at = utcnow()
    event(r, "closed", who, text)


def overdue(r: FundRequest, today: date) -> bool:
    return r.status == "to_liquidate" and r.liquidate_by is not None and r.liquidate_by < today


# --- receipts ----------------------------------------------------------------------------------


def store_receipt(db: Session, content_type: str, data: bytes) -> str:
    if content_type not in RECEIPT_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A receipt is a photo (JPG, PNG, WebP, HEIC) or a PDF.")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The receipt's file is empty.")
    if len(data) > MAX_RECEIPT_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The receipt is over 4 MB: take the photo again at a lower size.")
    ref = secrets.token_hex(16)
    db.add(StoredFile(ref=ref, content_type=content_type, data=data))
    return ref


def decode(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The receipt's file couldn't be read.") from e


# --- as the screens see it ---------------------------------------------------------------------


def category_out(c: ExpenseCategory) -> dict:
    """A category or a sub-category. A sub-category's account and rule are its
    category's, so `reimbursable` and `account` say what applies to it."""
    account = c.top.account if c.top.account_id else None
    return {
        "id": c.id,
        "name": c.name,
        "label": c.label,
        "parentId": c.parent_id,
        "reimbursable": c.covered,
        "account": {"id": account.id, "code": account.code, "name": account.name} if account else None,
        "description": c.description,
        "isActive": c.is_active,
        "sortOrder": c.sort_order,
    }


def expense_out(e: FundExpense) -> dict:
    return {
        "id": e.id,
        "spentOn": e.spent_on.isoformat(),
        "description": e.description,
        "category": {"id": e.category.id, "name": e.category.label, "reimbursable": e.category.covered} if e.category else None,
        "amountCentavos": e.amount_centavos,
        "receipt": {"name": e.receipt_name or "receipt"} if e.receipt_ref else None,
        "noReceiptReason": e.no_receipt_reason,
        "accepted": e.accepted,
        "refusedReason": e.refused_reason,
        "counts": counts(e),
        "covered": counts(e) and e.category is not None and e.category.covered,
    }


def request_out(r: FundRequest, today: date) -> dict:
    t = tally(r)
    return {
        "id": r.id,
        "sourceApp": r.source_app,
        "sourceId": r.source_id,
        "number": r.number,
        "requester": {"name": r.requester_name, "email": r.requester_email, "team": r.team_name},
        "purpose": r.purpose,
        "details": r.details,
        "customerName": r.customer_name,
        "neededOn": r.needed_on.isoformat() if r.needed_on else None,
        "liquidate": r.liquidate,
        "requestedCentavos": r.requested_centavos,
        "approvedCentavos": r.approved_centavos,
        "approval": {"by": r.approved_by_name, "at": iso(r.approved_at), "note": r.approval_note},
        "status": r.status,
        "statusLabel": STATUS_LABELS[r.status],
        "release": None if r.released_at is None else {
            "amountCentavos": r.released_centavos,
            "method": r.release_method,
            "methodLabel": RELEASE_METHODS.get(r.release_method or "", r.release_method),
            "reference": r.release_reference,
            "at": iso(r.released_at),
            "liquidateBy": r.liquidate_by.isoformat() if r.liquidate_by else None,
        },
        "overdue": overdue(r, today),
        "liquidatedAt": iso(r.liquidated_at),
        "checkedAt": iso(r.checked_at),
        "sentBackNote": r.sent_back_note,
        "expenses": [expense_out(e) for e in r.expenses],
        # What it comes to so far; once checked, what it came to.
        "tally": {
            "spentCentavos": t.spent,
            "coveredCentavos": t.covered,
            "ownCentavos": t.own,
            "refusedCentavos": t.refused,
            "balanceCentavos": t.balance,
        },
        "returnDueCentavos": r.return_due_centavos,
        "returnedCentavos": r.returned_centavos,
        "reimburseDueCentavos": r.reimburse_due_centavos,
        "reimbursedCentavos": r.reimbursed_centavos,
        "closedAt": iso(r.closed_at),
        "cancelReason": r.cancel_reason,
        "events": [
            {"at": iso(e.at), "kind": e.kind, "who": e.who, "text": e.text, "amountCentavos": e.amount_centavos}
            for e in r.events
        ],
        # What it posted to the journal.
        "entries": [{"id": j.id, "number": j.number, "date": j.entry_date.isoformat(), "memo": j.memo, "totalCentavos": sum(ln.debit_centavos for ln in j.lines)} for j in r.entries],
        "createdAt": iso(r.created_at),
        "updatedAt": iso(r.updated_at),
    }
