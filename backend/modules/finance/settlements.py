"""Shared subledger settlement lookups for credit notes, vendor credits, and advances."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.finance.models import AdvanceApplication, CreditAllocation, VendorCreditAllocation


def _active_filter(col, *, on: date | None = None, on_col=None, after: datetime | None = None):
    clauses = []
    if after is not None:
        clauses.append(or_(col.removed_at.is_(None), col.removed_at >= after))
    else:
        clauses.append(col.removed_at.is_(None))
    if on is not None and on_col is not None:
        clauses.append(on_col <= on)
    return clauses


def invoice_credits_map(
    db: Session, invoice_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    ids = list(invoice_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(CreditAllocation.invoice_id, func.sum(CreditAllocation.amount_centavos))
        .where(
            CreditAllocation.invoice_id.in_(ids),
            *_active_filter(CreditAllocation, on=on, on_col=CreditAllocation.applied_on, after=after),
        )
        .group_by(CreditAllocation.invoice_id)
    ).all()
    return {iid: int(total or 0) for iid, total in rows}


def invoice_advances_map(
    db: Session, invoice_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    ids = list(invoice_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(AdvanceApplication.target_id, func.sum(AdvanceApplication.amount_centavos))
        .where(
            AdvanceApplication.target_kind == "invoice",
            AdvanceApplication.target_id.in_(ids),
            *_active_filter(AdvanceApplication, on=on, on_col=AdvanceApplication.applied_on, after=after),
        )
        .group_by(AdvanceApplication.target_id)
    ).all()
    return {iid: int(total or 0) for iid, total in rows}


def invoice_settled_map(
    db: Session, invoice_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    c = invoice_credits_map(db, invoice_ids, on=on, after=after)
    a = invoice_advances_map(db, invoice_ids, on=on, after=after)
    out = dict(c)
    for k, v in a.items():
        out[k] = out.get(k, 0) + v
    return out


def invoice_settled(db: Session, invoice_id: str) -> int:
    return invoice_settled_map(db, [invoice_id]).get(invoice_id, 0)


def bill_credits_map(
    db: Session, bill_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    ids = list(bill_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(VendorCreditAllocation.bill_id, func.sum(VendorCreditAllocation.amount_centavos))
        .where(
            VendorCreditAllocation.bill_id.in_(ids),
            *_active_filter(VendorCreditAllocation, on=on, on_col=VendorCreditAllocation.applied_on, after=after),
        )
        .group_by(VendorCreditAllocation.bill_id)
    ).all()
    return {bid: int(total or 0) for bid, total in rows}


def bill_advances_map(
    db: Session, bill_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    ids = list(bill_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(AdvanceApplication.target_id, func.sum(AdvanceApplication.amount_centavos))
        .where(
            AdvanceApplication.target_kind == "bill",
            AdvanceApplication.target_id.in_(ids),
            *_active_filter(AdvanceApplication, on=on, on_col=AdvanceApplication.applied_on, after=after),
        )
        .group_by(AdvanceApplication.target_id)
    ).all()
    return {bid: int(total or 0) for bid, total in rows}


def bill_settled_map(
    db: Session, bill_ids: list[str] | set[str], *, on: date | None = None, after: datetime | None = None
) -> dict[str, int]:
    c = bill_credits_map(db, bill_ids, on=on, after=after)
    a = bill_advances_map(db, bill_ids, on=on, after=after)
    out = dict(c)
    for k, v in a.items():
        out[k] = out.get(k, 0) + v
    return out


def bill_settled(db: Session, bill_id: str) -> int:
    return bill_settled_map(db, [bill_id]).get(bill_id, 0)
