"""What the other Bishnoi One apps ask Finance: tax, and marketing requests. Only for an
app holding one of INTEGRATION_KEYS, sent in the X-Bishnoi-Key header (the same
way the CRM reads Inventory), so a quote, a pharmacy sale and an invoice are
all taxed by Finance's one set of rules, and money is released by Finance
whichever app asked for it.
"""

import hmac
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import select

from app.deps import DB, SettingsDep
from app.funds import category_out, decode, event, must_be, peso, request_out, store_receipt, utcnow
from app.models import ExpenseCategory, FundExpense, FundRequest, StoredFile
from app.notify import done, tell_holders
from app.routers.funds import ordered_categories, receipt_of, today
from app.routers.tax import Api, SaleBody, field_error, setup_out, work_out


def calling_app(
    settings: SettingsDep,
    x_bishnoi_key: Annotated[str | None, Header()] = None,
    # The header's name before the rename to Bishnoi One: still taken until every app is redeployed.
    x_nabhi_key: Annotated[str | None, Header()] = None,
) -> str:
    """The name of the app whose key came with the request."""
    x_bishnoi_key = x_bishnoi_key or x_nabhi_key
    if x_bishnoi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_bishnoi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Bishnoi One app's key (X-Bishnoi-Key).")


router = APIRouter(prefix="/integration/tax", tags=["integration"], dependencies=[Depends(calling_app)])


@router.get("/setup")
def setup(db: DB, settings: SettingsDep) -> dict:
    """The categories a product can have and the buyers there are, for the
    caller's own forms. Read-only: the registration and rates are Finance's."""
    return setup_out(db, settings, False)


@router.post("/compute")
def compute(db: DB, settings: SettingsDep, body: SaleBody) -> dict:
    return work_out(db, settings, body)


# --- funds: the requests other apps approve, and the receipts their people send ---------------
#
# The calling app knows its requests by its own ids; Finance keeps them with
# the app's name, so two apps' ids never meet.

funds_router = APIRouter(prefix="/integration/funds", tags=["integration"])
Caller = Annotated[str, Depends(calling_app)]


def theirs(db: DB, caller: str, source_id: str) -> FundRequest:
    r = db.scalar(select(FundRequest).where(FundRequest.source_app == caller, FundRequest.source_id == source_id))
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finance has no such request.")
    return r


@funds_router.get("/categories")
def categories(caller: Caller, db: DB) -> dict:
    """What spending can be sorted into, for the requester's liquidation form."""
    return {"items": [category_out(c) for c in ordered_categories(db, active_only=True)]}


class ApprovedIn(Api):
    source_id: str = Field(min_length=1, max_length=36)
    number: str = Field(min_length=1, max_length=30)
    requester_name: str = Field(min_length=1, max_length=120)
    requester_email: str = Field(min_length=3, max_length=254)
    team_name: str | None = Field(None, max_length=80)
    purpose: str = Field(min_length=1, max_length=80)
    details: str | None = Field(None, max_length=5000)
    customer_name: str | None = Field(None, max_length=200)
    needed_on: date | None = None
    liquidate: bool
    requested_centavos: int = Field(gt=0, lt=10**11)
    approved_centavos: int = Field(gt=0, lt=10**11)
    approved_by_name: str = Field(min_length=1, max_length=120)
    approved_at: datetime
    approval_note: str | None = Field(None, max_length=500)


@funds_router.post("/requests", status_code=status.HTTP_201_CREATED)
def receive(caller: Caller, db: DB, settings: SettingsDep, body: ApprovedIn) -> dict:
    """An approved request, to be released. Sent again (the answer was lost on
    the way), it's the same request, not a second one."""
    there = db.scalar(select(FundRequest).where(FundRequest.source_app == caller, FundRequest.source_id == body.source_id))
    if there is None:
        there = FundRequest(source_app=caller, **body.model_dump())
        event(there, "approved", body.approved_by_name, f"Approved for {peso(body.approved_centavos)} and forwarded to Finance.", body.approved_centavos)
        db.add(there)
        db.flush()
        team = f" ({there.team_name})" if there.team_name else ""
        tell_holders(db, "funds.release", "fund.to_release",
                     f"{there.number}: {peso(there.approved_centavos)} for {there.requester_name}{team} is ready for release.", link=f"/funds/{there.id}")
        db.commit()
    return request_out(there, today(settings))


@funds_router.get("/requests")
def read_many(caller: Caller, db: DB, settings: SettingsDep, ids: str = Query(..., max_length=20000)) -> dict:
    """Where each of these requests is, by the caller's ids. One Finance
    doesn't have is left out."""
    wanted = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))[:200]
    found = db.scalars(select(FundRequest).where(FundRequest.source_app == caller, FundRequest.source_id.in_(wanted))) if wanted else []
    on = today(settings)
    return {"items": {r.source_id: request_out(r, on) for r in found}}


@funds_router.get("/requests/{source_id}")
def read_one(caller: Caller, db: DB, settings: SettingsDep, source_id: str) -> dict:
    return request_out(theirs(db, caller, source_id), today(settings))


class Receipt(Api):
    name: str = Field(min_length=1, max_length=160)
    content_type: str = Field(min_length=1, max_length=100)
    # The file, base64.
    data: str = Field(min_length=1, max_length=6_000_000)


class ExpenseIn(Api):
    spent_on: date
    description: str = Field(min_length=1, max_length=200)
    category_id: str
    amount_centavos: int = Field(gt=0, lt=10**11)
    receipt: Receipt | None = None
    no_receipt_reason: str | None = Field(None, max_length=300)
    # Who is sending it, as the calling app knows them.
    by: str = Field(min_length=1, max_length=120)


@funds_router.post("/requests/{source_id}/expenses", status_code=status.HTTP_201_CREATED)
def add_expense(caller: Caller, db: DB, settings: SettingsDep, source_id: str, body: ExpenseIn) -> dict:
    r = theirs(db, caller, source_id)
    must_be(r, "to_liquidate")
    category = db.get(ExpenseCategory, body.category_id)
    if category is None or not category.is_active:
        raise field_error("categoryId", "Select an expense category.")
    if body.receipt is None and not body.no_receipt_reason:
        raise field_error("noReceiptReason", "Attach the official receipt, or state why there is none.")
    if body.spent_on > today(settings):
        raise field_error("spentOn", "The expense date cannot be in the future.")
    ref = store_receipt(db, body.receipt.content_type, decode(body.receipt.data)) if body.receipt else None
    r.expenses.append(FundExpense(
        spent_on=body.spent_on,
        description=body.description,
        category_id=category.id,
        amount_centavos=body.amount_centavos,
        receipt_ref=ref,
        receipt_name=body.receipt.name if body.receipt else None,
        no_receipt_reason=None if body.receipt else body.no_receipt_reason,
    ))
    db.commit()
    db.refresh(r)
    return request_out(r, today(settings))


@funds_router.delete("/requests/{source_id}/expenses/{expense_id}")
def remove_expense(caller: Caller, db: DB, settings: SettingsDep, source_id: str, expense_id: str) -> dict:
    r = theirs(db, caller, source_id)
    must_be(r, "to_liquidate")
    e = next((x for x in r.expenses if x.id == expense_id), None)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such receipt on this request.")
    if e.receipt_ref and (f := db.get(StoredFile, e.receipt_ref)):
        db.delete(f)
    r.expenses.remove(e)
    db.commit()
    return request_out(r, today(settings))


@funds_router.get("/requests/{source_id}/expenses/{expense_id}/receipt")
def expense_receipt(caller: Caller, db: DB, source_id: str, expense_id: str) -> Response:
    return receipt_of(db, theirs(db, caller, source_id), expense_id)


class ByIn(Api):
    by: str = Field(min_length=1, max_length=120)
    reason: str | None = Field(None, max_length=500)


@funds_router.post("/requests/{source_id}/submit")
def submit(caller: Caller, db: DB, settings: SettingsDep, source_id: str, body: ByIn) -> dict:
    """The liquidation is complete: Finance checks it. None spent is a
    liquidation too: all of it comes back as unused funds."""
    r = theirs(db, caller, source_id)
    must_be(r, "to_liquidate")
    r.status, r.liquidated_at, r.sent_back_note = "to_check", utcnow(), None
    spent = sum(e.amount_centavos for e in r.expenses)
    count = len(r.expenses)
    event(r, "submitted", body.by, f"Liquidation submitted: {count} expense{'s' if count != 1 else ''} totalling {peso(spent)}.", spent)
    # Not to whoever released it: someone else reviews it.
    tell_holders(db, "funds.check", "fund.to_check", f"{r.number}: {r.requester_name}'s liquidation ({peso(spent)}) is waiting for review.",
                 link=f"/funds/{r.id}", not_to=[r.released_by_id])
    db.commit()
    return request_out(r, today(settings))


@funds_router.post("/requests/{source_id}/cancel")
def cancel(caller: Caller, db: DB, settings: SettingsDep, source_id: str, body: ByIn) -> dict:
    """Not needed after all: only before the money is released."""
    r = theirs(db, caller, source_id)
    must_be(r, "to_release")
    r.status, r.cancel_reason, r.closed_at = "cancelled", body.reason or "Cancelled by the requester.", utcnow()
    event(r, "cancelled", body.by, f"Request cancelled by the requester: {r.cancel_reason}")
    done(db, "fund.to_release", f"/funds/{r.id}")  # nothing to release any more
    db.commit()
    return request_out(r, today(settings))


# --- customers: what the CRM shows of a customer's standing ---------------------------------
#
# The CRM works out each B2B customer's credit status, yearly contribution and
# the products they carry from what Finance billed them (decided 2026-10-19).
# It asks by its own customer ids, which Finance keeps on each invoice.

customers_router = APIRouter(prefix="/integration/customers", tags=["integration"], dependencies=[Depends(calling_app)])

# An open invoice due within this many days counts as approaching its due date.
APPROACHING_DAYS = 5
YEAR_DAYS = 365


@customers_router.get("")
def standing(db: DB, settings: SettingsDep, ids: str = Query(..., max_length=20000)) -> dict:
    """For each of these customers (the CRM's ids): what's still owed and how
    late, when the next open invoice falls due, what was billed over the last
    12 months, and what was billed, by line. A customer with no invoices is left out."""
    from datetime import timedelta

    from app.models import Invoice

    wanted = list(dict.fromkeys(i.strip() for i in ids.split(",") if i.strip()))[:500]
    on = today(settings)
    since = on - timedelta(days=YEAR_DAYS)
    out: dict[str, dict] = {}
    rows = db.scalars(select(Invoice).where(Invoice.customer_id.in_(wanted), Invoice.status == "issued")) if wanted else []
    for inv in rows:
        c = out.setdefault(inv.customer_id, {
            "owedCentavos": 0, "overdueCentavos": 0, "oldestDaysLate": 0, "openInvoices": 0, "nextDueOn": None,
            "billedYearCentavos": 0, "invoicesYear": 0, "lines": {},
        })
        due = inv.invoice_date + timedelta(days=inv.terms_days)
        owed = max(0, inv.total_centavos - inv.paid_centavos)
        if owed:
            late = (on - due).days
            c["owedCentavos"] += owed
            c["openInvoices"] += 1
            if late > 0:
                c["overdueCentavos"] += owed
                c["oldestDaysLate"] = max(c["oldestDaysLate"], late)
            elif c["nextDueOn"] is None or due.isoformat() < c["nextDueOn"]:
                c["nextDueOn"] = due.isoformat()
        if inv.invoice_date >= since:
            c["billedYearCentavos"] += inv.total_centavos
            c["invoicesYear"] += 1
            for line in inv.lines or []:
                key = (str(line.get("ref") or "").strip() or str(line.get("description") or "").strip())[:120]
                if not key:
                    continue
                seen = c["lines"].setdefault(key, {"ref": line.get("ref"), "description": line.get("description"), "invoices": 0, "lastOn": None})
                seen["invoices"] += 1
                if seen["lastOn"] is None or inv.invoice_date.isoformat() > seen["lastOn"]:
                    seen["lastOn"] = inv.invoice_date.isoformat()
    for c in out.values():
        c["lines"] = sorted(c["lines"].values(), key=lambda x: (-x["invoices"], x["description"] or ""))
        c["approaching"] = c["nextDueOn"] is not None and c["nextDueOn"] <= (on + timedelta(days=APPROACHING_DAYS)).isoformat()
    return {"on": on.isoformat(), "customers": out}
