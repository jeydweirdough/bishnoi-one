"""Finance's side of marketing requests: releasing the money, checking each
liquidation receipt by receipt, taking back the unused funds or paying back what was
over, and the categories spending is sorted into (app/funds.py has the
flow).

Anyone signed in to Finance works the requests; only its admins change the
categories. Each step that moves money posts its journal entry
(app/ledger.py) in the same transaction: the step and its entry stand or
fall together.
"""

from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import func, or_, select

from app.access import access_of, permitted
from app.audit import audit
from app.config import Settings
from app.deps import DB, SettingsDep
from app.funds import (
    RELEASE_METHODS,
    category_out,
    close,
    conflict,
    event,
    must_be,
    peso,
    request_out,
    settle,
    utcnow,
)
from app.ledger import post_check, post_reimbursed, post_release, post_returned
from app.models import (
    FUND_STATUSES,
    Account,
    ExpenseCategory,
    FundRequest,
    StoredFile,
    User,
)
from app.notify import tell_holders
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance/funds", tags=["funds"])

# One page per step; settlement (refunds and reimbursements) and history
# (settled and cancelled) are one page each.
Task = Literal["to_release", "to_liquidate", "to_check", "to_settle", "history", "to_return", "to_reimburse", "closed", "cancelled", "all"]
TASK_STATUSES = {"to_settle": ("to_return", "to_reimburse"), "history": ("closed", "cancelled")}


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.org_timezone)).date()


def found(db: DB, request_id: str) -> FundRequest:
    r = db.get(FundRequest, request_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such request.")
    return r


def step(db: DB, user: User, r: FundRequest, action: str) -> None:
    """The activity log's line for a fund step. The request keeps the full story as its events."""
    audit(db, user, f"fund.{action}", target=r.number, target_type="fund_request", target_id=r.id)


def release_hold(db: DB, r: FundRequest) -> str | None:
    """Why this can't be released yet: its requester still has an earlier cash
    advance to liquidate (sent back for correction counts). One waiting on
    Finance's review doesn't hold it: the requester has done their part."""
    earlier = db.scalar(
        select(FundRequest)
        .where(func.lower(FundRequest.requester_email) == r.requester_email.lower(), FundRequest.status == "to_liquidate", FundRequest.id != r.id)
        .order_by(FundRequest.released_at)
        .limit(1)
    )
    if earlier is None:
        return None
    due = f", due {earlier.liquidate_by:%d %b %Y}" if earlier.liquidate_by else ""
    return f"{r.requester_name} still has {earlier.number} to liquidate{due}. Release this one after that's liquidated."


def check_hold(r: FundRequest, user: User) -> str | None:
    """Why this person can't review the liquidation: whoever released the money doesn't check how it was spent."""
    if r.released_by_id is not None and r.released_by_id == user.id:
        return "You released this cash advance, so someone else reviews its liquidation."
    return None


# --- the lists --------------------------------------------------------------------------------


@router.get("/counts")
def waiting(user: permitted("funds.view"), db: DB, settings: SettingsDep) -> dict:
    """What's waiting on Finance, by step, for the sidebar."""
    by = dict(db.execute(select(FundRequest.status, func.count()).group_by(FundRequest.status)).all())
    late = db.scalar(select(func.count()).where(FundRequest.status == "to_liquidate", FundRequest.liquidate_by < today(settings))) or 0
    counts = {s: by.get(s, 0) for s in FUND_STATUSES}
    return counts | {"to_settle": counts["to_return"] + counts["to_reimburse"], "overdue": late}


@router.get("")
def list_requests(
    user: permitted("funds.view"),
    db: DB,
    settings: SettingsDep,
    task: Task = "to_release",
    q: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    query = select(FundRequest)
    if task != "all":
        query = query.where(FundRequest.status.in_(TASK_STATUSES.get(task, (task,))))
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(
            func.lower(FundRequest.number).like(like),
            func.lower(FundRequest.requester_name).like(like),
            func.lower(FundRequest.purpose).like(like),
            func.lower(FundRequest.customer_name).like(like),
        ))
    # What's waiting, oldest first; what's done, newest first.
    order = FundRequest.updated_at.desc() if task in ("closed", "cancelled", "history", "all") else FundRequest.approved_at
    on = today(settings)
    return {"items": [request_out(r, on) for r in db.scalars(query.order_by(order).limit(limit))]}


def ordered_categories(db: DB, active_only: bool = False) -> list[ExpenseCategory]:
    """Each category, then its sub-categories, in order."""
    query = select(ExpenseCategory).order_by(ExpenseCategory.sort_order, ExpenseCategory.name)
    if active_only:
        query = query.where(ExpenseCategory.is_active)
    every = list(db.scalars(query))
    out = []
    for top in (c for c in every if c.parent_id is None):
        out.append(top)
        out.extend(c for c in every if c.parent_id == top.id)
    return out


@router.get("/categories")
def list_categories(user: permitted("categories.view"), db: DB) -> dict:
    return {"items": [category_out(c) for c in ordered_categories(db)], "canEdit": access_of(user).can("categories.manage")}


class CategoryIn(Api):
    name: str = Field(min_length=1, max_length=80)
    # A sub-category's category; None for a category.
    parent_id: str | None = None
    # A category's expense account; a sub-category posts to its category's.
    account_id: str | None = None
    reimbursable: bool = True
    description: str | None = Field(None, max_length=300)
    is_active: bool = True


def category_values(db: DB, body: CategoryIn, this: ExpenseCategory | None) -> dict:
    parent = None
    if body.parent_id:
        parent = db.get(ExpenseCategory, body.parent_id)
        if parent is None or parent.parent_id is not None or (this and parent.id == this.id):
            raise field_error("parentId", "Select a category (not a sub-category) as its parent.")
        if this and db.scalar(select(ExpenseCategory.id).where(ExpenseCategory.parent_id == this.id)):
            raise field_error("parentId", "This category has sub-categories, so it cannot become a sub-category.")
    siblings = select(ExpenseCategory.id).where(
        func.lower(ExpenseCategory.name) == body.name.lower(),
        ExpenseCategory.parent_id == parent.id if parent else ExpenseCategory.parent_id.is_(None),
    )
    if this:
        siblings = siblings.where(ExpenseCategory.id != this.id)
    if db.scalar(siblings):
        raise field_error("name", "A category with this name already exists here.")
    account_id = None
    if parent is None:
        account = db.get(Account, body.account_id) if body.account_id else None
        if account is None or account.type != "expense" or not account.is_active:
            raise field_error("accountId", "Select the expense account this category posts to.")
        account_id = account.id
    return {
        "name": body.name,
        "parent_id": parent.id if parent else None,
        "account_id": account_id,
        # A sub-category follows its category's rule.
        "reimbursable": parent.reimbursable if parent else body.reimbursable,
        "description": body.description,
        "is_active": body.is_active,
    }


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def add_category(user: permitted("categories.manage"), db: DB, body: CategoryIn) -> dict:
    values = category_values(db, body, None)
    last = db.scalar(select(func.max(ExpenseCategory.sort_order))) or 0
    c = ExpenseCategory(**values, sort_order=last + 1)
    db.add(c)
    db.flush()
    audit(db, user, "category.created", target=c.name, target_type="category", target_id=c.id)
    db.commit()
    db.refresh(c)
    return category_out(c)


@router.put("/categories/{category_id}")
def change_category(user: permitted("categories.manage"), db: DB, category_id: str, body: CategoryIn) -> dict:
    c = db.get(ExpenseCategory, category_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such category.")
    for k, v in category_values(db, body, c).items():
        setattr(c, k, v)
    # Its sub-categories follow its rule.
    if c.parent_id is None:
        for sub in db.scalars(select(ExpenseCategory).where(ExpenseCategory.parent_id == c.id)):
            sub.reimbursable = c.reimbursable
    audit(db, user, "category.updated", target=c.name, target_type="category", target_id=c.id, fields=body.model_fields_set)
    db.commit()
    db.refresh(c)
    return category_out(c)


@router.get("/{request_id}")
def read_request(user: permitted("funds.view"), db: DB, settings: SettingsDep, request_id: str) -> dict:
    r = found(db, request_id)
    # Why the step at hand is held for this person, so the page can say so
    # instead of offering it. Finance's page only: the CRM reads request_out.
    holds = {
        "release": release_hold(db, r) if r.status == "to_release" else None,
        "check": check_hold(r, user) if r.status == "to_check" else None,
    }
    return request_out(r, today(settings)) | {"holds": holds}


@router.get("/{request_id}/expenses/{expense_id}/receipt")
def receipt(user: permitted("funds.view"), db: DB, request_id: str, expense_id: str) -> Response:
    return receipt_of(db, found(db, request_id), expense_id)


def receipt_of(db: DB, r: FundRequest, expense_id: str) -> Response:
    e = next((x for x in r.expenses if x.id == expense_id), None)
    f = db.get(StoredFile, e.receipt_ref) if e and e.receipt_ref else None
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no receipt for this.")
    name = (e.receipt_name or "receipt").replace('"', "")
    return Response(f.data, media_type=f.content_type, headers={"Content-Disposition": f'inline; filename="{name}"'})


# --- the steps --------------------------------------------------------------------------------


class ReleaseIn(Api):
    amount_centavos: int = Field(gt=0, lt=10**11)
    method: Literal["cash", "bank", "ewallet", "check"]
    reference: str | None = Field(None, max_length=80)
    # When the receipts are due; by default LIQUIDATE_WITHIN_DAYS from today.
    liquidate_by: date | None = None


@router.post("/{request_id}/release")
def release(user: permitted("funds.release"), db: DB, settings: SettingsDep, request_id: str, body: ReleaseIn) -> dict:
    r = found(db, request_id)
    must_be(r, "to_release")
    if hold := release_hold(db, r):
        raise conflict(hold)
    if body.amount_centavos > r.approved_centavos:
        raise field_error("amountCentavos", f"The amount exceeds the approved amount ({peso(r.approved_centavos)}).")
    on = today(settings)
    if body.liquidate_by and body.liquidate_by < on:
        raise field_error("liquidateBy", "Select today or a later date.")
    r.released_centavos = body.amount_centavos
    r.release_method, r.release_reference = body.method, body.reference
    r.released_at, r.released_by_id = utcnow(), user.id
    how = RELEASE_METHODS[body.method] + (f" ({body.reference})" if body.reference else "")
    event(r, "released", user.full_name, f"Cash advance of {peso(body.amount_centavos)} released via {how}.", body.amount_centavos)
    post_release(db, r, on, user.full_name)
    if r.liquidate:
        r.liquidate_by = body.liquidate_by or on + timedelta(days=settings.liquidate_within_days)
        r.status = "to_liquidate"
    else:
        close(r, user.full_name, "Not subject to liquidation: settled upon release.")
    step(db, user, r, "released")
    db.commit()
    return request_out(r, on)


class ReasonIn(Api):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/{request_id}/cancel")
def cancel(user: permitted("funds.cancel"), db: DB, settings: SettingsDep, request_id: str, body: ReasonIn) -> dict:
    r = found(db, request_id)
    must_be(r, "to_release")
    r.status, r.cancel_reason, r.closed_at = "cancelled", body.reason, utcnow()
    event(r, "cancelled", user.full_name, f"Release declined by Finance: {body.reason}")
    step(db, user, r, "cancelled")
    db.commit()
    return request_out(r, today(settings))


class ExpenseCheck(Api):
    # True: counts. False: refused (say why). None: not checked yet.
    accepted: bool | None = None
    refused_reason: str | None = Field(None, max_length=300)
    category_id: str | None = None


@router.patch("/{request_id}/expenses/{expense_id}")
def check_expense(user: permitted("funds.check"), db: DB, settings: SettingsDep, request_id: str, expense_id: str, body: ExpenseCheck) -> dict:
    r = found(db, request_id)
    must_be(r, "to_check")
    if hold := check_hold(r, user):
        raise conflict(hold)
    e = next((x for x in r.expenses if x.id == expense_id), None)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such receipt on this request.")
    sent = body.model_fields_set
    if "category_id" in sent:
        if body.category_id is None or db.get(ExpenseCategory, body.category_id) is None:
            raise field_error("categoryId", "Select an expense category.")
        e.category_id = body.category_id
        db.flush()
        db.refresh(e)
    if "accepted" in sent:
        if body.accepted is False and not body.refused_reason:
            raise field_error("refusedReason", "Enter the reason for rejection. The requester will see it.")
        e.accepted = body.accepted
        e.refused_reason = body.refused_reason if body.accepted is False else None
    step(db, user, r, "expense_checked")
    db.commit()
    return request_out(r, today(settings))


class NoteIn(Api):
    note: str = Field(min_length=1, max_length=500)


@router.post("/{request_id}/send-back")
def send_back(user: permitted("funds.check"), db: DB, settings: SettingsDep, request_id: str, body: NoteIn) -> dict:
    """Back to the requester to fix: a missing receipt, a wrong amount."""
    r = found(db, request_id)
    must_be(r, "to_check")
    if hold := check_hold(r, user):
        raise conflict(hold)
    r.status, r.sent_back_note = "to_liquidate", body.note
    event(r, "sent_back", user.full_name, f"Liquidation returned for correction: {body.note}")
    step(db, user, r, "sent_back")
    db.commit()
    return request_out(r, today(settings))


@router.post("/{request_id}/finish-check")
def finish_check(user: permitted("funds.check"), db: DB, settings: SettingsDep, request_id: str) -> dict:
    r = found(db, request_id)
    must_be(r, "to_check")
    if hold := check_hold(r, user):
        raise conflict(hold)
    if any(e.accepted is None for e in r.expenses):
        raise conflict("Accept or reject every expense before completing the review.")
    if any(e.category is None for e in r.expenses):
        raise conflict("Assign an expense category to every expense before completing the review.")
    r.checked_by_id = user.id
    settle(r, user.full_name)
    post_check(db, r, today(settings), user.full_name)
    step(db, user, r, "checked")
    if r.status == "to_return":
        tell_holders(db, "funds.settle", "fund.to_settle", f"{r.number}: {peso(r.return_due_centavos)} of unused funds to collect from {r.requester_name}.",
                     link=f"/funds/{r.id}", not_to=[user.id])
    elif r.status == "to_reimburse":
        tell_holders(db, "funds.settle", "fund.to_settle", f"{r.number}: {peso(r.reimburse_due_centavos)} to reimburse to {r.requester_name}.",
                     link=f"/funds/{r.id}", not_to=[user.id])
    db.commit()
    return request_out(r, today(settings))


class MoneyIn(Api):
    amount_centavos: int = Field(gt=0, lt=10**11)
    method: Literal["cash", "bank", "ewallet", "check"] = "cash"
    reference: str | None = Field(None, max_length=80)


@router.post("/{request_id}/returned")
def returned(user: permitted("funds.settle"), db: DB, settings: SettingsDep, request_id: str, body: MoneyIn) -> dict:
    """The unused funds, handed back: all of it, or some of it so far."""
    r = found(db, request_id)
    must_be(r, "to_return")
    left = r.return_due_centavos - r.returned_centavos
    if body.amount_centavos > left:
        raise field_error("amountCentavos", f"The amount exceeds the outstanding refund of {peso(left)}.")
    r.returned_centavos += body.amount_centavos
    how = RELEASE_METHODS[body.method] + (f" ({body.reference})" if body.reference else "")
    event(r, "returned", user.full_name, f"Refund received: {peso(body.amount_centavos)} via {how}.", body.amount_centavos)
    post_returned(db, r, body.amount_centavos, body.method, body.reference, today(settings), user.full_name)
    if r.returned_centavos >= r.return_due_centavos:
        close(r, user.full_name, "Refund received in full. Settled.")
    step(db, user, r, "returned")
    db.commit()
    return request_out(r, today(settings))


@router.post("/{request_id}/reimbursed")
def reimbursed(user: permitted("funds.settle"), db: DB, settings: SettingsDep, request_id: str, body: MoneyIn) -> dict:
    r = found(db, request_id)
    must_be(r, "to_reimburse")
    left = r.reimburse_due_centavos - r.reimbursed_centavos
    if body.amount_centavos > left:
        raise field_error("amountCentavos", f"The amount exceeds the outstanding reimbursement of {peso(left)}.")
    r.reimbursed_centavos += body.amount_centavos
    how = RELEASE_METHODS[body.method] + (f" ({body.reference})" if body.reference else "")
    event(r, "reimbursed", user.full_name, f"Reimbursement paid: {peso(body.amount_centavos)} via {how}.", body.amount_centavos)
    post_reimbursed(db, r, body.amount_centavos, body.method, body.reference, today(settings), user.full_name)
    if r.reimbursed_centavos >= r.reimburse_due_centavos:
        close(r, user.full_name, "Reimbursement paid in full. Settled.")
    step(db, user, r, "reimbursed")
    db.commit()
    return request_out(r, today(settings))

