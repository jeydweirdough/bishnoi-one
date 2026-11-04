"""Imported expenses: the Q1 Zoho expenses, to read (decided 2026-10-31, Plans/Plan - Q1 imports per area).

History only: there is no add or edit here, and no way to attach a receipt. People who may see petty cash see
these (petty_cash.view); whoever may void petty cash may void one (petty_cash.void), which reverses its entry on
the day it's voided and keeps the record. Importing them is app/routers/imports.py.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select

from app.access import access_of, permitted
from app.audit import audit
from app.deps import DB, SettingsDep
from app.ledger import Leg, post
from app.models import ImportedExpense, JournalEntry
from app.payables import PURCHASE_TYPES, VAT_KINDS, WITHHOLDING
from app.routers.funds import today
from app.routers.tax import Api

router = APIRouter(tags=["imported expenses"])

SHOWS = ("posted", "void")
LIMIT = 200


def summary(x: ImportedExpense) -> dict:
    return {"id": x.id, "number": x.number, "status": x.status, "date": x.expense_date.isoformat(), "vendor": x.vendor, "reference": x.reference,
            "lines": len(x.lines), "accounts": sorted({ln.source_account for ln in x.lines}), "paidFrom": x.paid_from.name, "totalCentavos": x.total_centavos,
            "vatCentavos": x.vat_centavos, "withheldCentavos": x.withheld_centavos}


def detail(x: ImportedExpense, user) -> dict:
    can = access_of(user).can
    return summary(x) | {
        "source": {"file": x.source_file, "zohoId": x.source_id, "by": x.imported_by, "at": x.imported_at.isoformat()},
        "voucher": x.voucher, "department": x.department, "personInCharge": x.person_in_charge, "vendorTin": x.vendor_tin,
        "amountsIncludeVat": x.amounts_include_vat, "netCentavos": x.net_centavos, "paidOutCentavos": x.paid_out_centavos, "entryId": x.entry_id,
        "voidedBy": x.voided_by, "voidedAt": x.voided_at.isoformat() if x.voided_at else None, "voidReason": x.void_reason,
        "canVoid": x.status == "posted" and can("petty_cash.void"),
        "items": [{"id": ln.id, "position": ln.position, "sourceAccount": ln.source_account, "sourceTax": ln.source_tax or "blank", "description": ln.description,
                   "account": {"id": ln.account.id, "code": ln.account.code, "name": ln.account.name},
                   "purchaseTypeLabel": PURCHASE_TYPES[ln.purchase_type], "vatLabel": VAT_KINDS[ln.vat], "withholding": ln.withholding,
                   "withholdingRateBp": WITHHOLDING[ln.withholding][1] if ln.withholding in WITHHOLDING else None,
                   "netCentavos": ln.net_centavos, "vatCentavos": ln.vat_centavos, "withheldCentavos": ln.withheld_centavos} for ln in x.lines],
    }


@router.get("/imported-expenses")
def list_expenses(_: permitted("petty_cash.view"), db: DB, show: str = Query("posted", pattern="^(posted|void|all)$"), q: str | None = Query(None, max_length=100)) -> dict:
    counts = dict(db.execute(select(ImportedExpense.status, func.count()).group_by(ImportedExpense.status)).all())
    query = select(ImportedExpense)
    if show != "all":
        query = query.where(ImportedExpense.status == show)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(func.lower(ImportedExpense.number).like(like) | func.lower(ImportedExpense.vendor).like(like)
                            | func.lower(func.coalesce(ImportedExpense.reference, "")).like(like))
    rows = list(db.scalars(query.order_by(ImportedExpense.expense_date.desc(), ImportedExpense.number).limit(LIMIT)))
    total = db.scalar(select(func.coalesce(func.sum(ImportedExpense.total_centavos), 0)).where(ImportedExpense.status == "posted"))
    return {"items": [summary(x) for x in rows], "limited": len(rows) == LIMIT, "counts": {k: counts.get(k, 0) for k in SHOWS} | {"all": sum(counts.values())},
            "totalCentavos": int(total or 0)}


def found(db: DB, expense_id: str) -> ImportedExpense:
    x = db.get(ImportedExpense, expense_id)
    if x is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such imported expense.")
    return x


@router.get("/imported-expenses/{expense_id}")
def read(user: permitted("petty_cash.view"), db: DB, expense_id: str) -> dict:
    return detail(found(db, expense_id), user)


class ReasonIn(Api):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/imported-expenses/{expense_id}/void")
def void(user: permitted("petty_cash.void"), db: DB, settings: SettingsDep, expense_id: str, body: ReasonIn) -> dict:
    """Taken back out of the books: its entry reversed today; the record kept. It isn't imported again."""
    x = found(db, expense_id)
    if x.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "This imported expense is already void.")
    reason = body.reason.strip()
    entry = db.get(JournalEntry, x.entry_id) if x.entry_id else None
    if entry is not None and not entry.reversed_by_id:
        legs = [Leg(ln.account, debit=ln.credit_centavos, credit=ln.debit_centavos, description=ln.description) for ln in entry.lines]
        post(db, today(settings), f"Void of imported expense {x.number}: {reason}"[:300], legs, user.full_name, reference=(x.reference or x.number)[:80],
             source="expense", reverses=entry, by_id=user.id)
    x.status, x.void_reason, x.voided_at, x.voided_by = "void", reason, datetime.now(UTC), user.full_name[:120]
    audit(db, user, "expense.import_voided", target=x.number, target_type="imported_expense", target_id=x.id)
    db.commit()
    return detail(x, user)
