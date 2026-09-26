"""Fund requests: money a salesperson or field agent asks for ahead of
spending it (a partnership dinner), their Team Lead's decision, and, once
Finance has released it, the receipts that liquidate it (app/funds.py).

- /funds: requests within reach (funds.view). ?show=mine (the default),
  approve (waiting on this person's decision) or all.
- /funds (POST): a new request (funds.create), for the person asking.
- /funds/{id}/approve, /decline: the Team Lead's (funds.approve), never on
  their own request. Approved, it goes to Finance.
- /funds/{id}/cancel: the requester's, until Finance releases the money.
- /funds/{id}/expenses, /submit: the requester's liquidation, receipt by
  receipt, while Finance waits for it.
- /funds/waiting: what's waiting on this person, for the sidebar.
- /funds/purposes, /admin/fund-purposes: what money is asked for
  (admin.settings changes them).
"""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, field_error, iso, not_found, person_out, team_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app import funds as link
from app.funds import FINISHED, FinanceRefused, FinanceUnavailable, categories, receipt_body, refresh, send, take
from app.models import Company, FundPurpose, FundRequest, User
from app.pricing import today
from app.scope import reaches, within

router = APIRouter(tags=["funds"])

View = Annotated[Access, Depends(require("funds.view"))]
Create = Annotated[Access, Depends(require("funds.create"))]
Approve = Annotated[Access, Depends(require("funds.approve"))]
Settle = Annotated[Access, Depends(require("admin.settings"))]

STATUS_LABELS = {
    "pending": "For approval",
    "declined": "Declined",
    "cancelled": "Cancelled",
    "approved": "Approved: sending to Finance",
    "to_release": "Approved: for release",
    "to_liquidate": "Released: for liquidation",
    "to_check": "Liquidation under review",
    "to_return": "Refund due",
    "to_reimburse": "Reimbursement due",
    "closed": "Settled",
}
OPEN = tuple(s for s in STATUS_LABELS if s not in FINISHED)
RECEIPT_KINDS = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}
MAX_RECEIPT_BYTES = 4 * 1024 * 1024


def finance_error(e: Exception) -> HTTPException:
    if isinstance(e, FinanceRefused):
        return HTTPException(e.status if e.status != 404 else status.HTTP_409_CONFLICT, str(e))
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


# --- purposes ---------------------------------------------------------------------------------


def purpose_out(p: FundPurpose) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "liquidate": p.liquidate, "isActive": p.is_active, "sortOrder": p.sort_order}


@router.get("/funds/purposes")
def list_purposes(access: View, db: DB, every: bool = False) -> dict:
    query = select(FundPurpose).order_by(FundPurpose.sort_order, FundPurpose.name)
    if not (every and access.can("admin.settings")):
        query = query.where(FundPurpose.is_active)
    return {"items": [purpose_out(p) for p in db.scalars(query)], "canEdit": access.can("admin.settings")}


class PurposeIn(Api):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    liquidate: bool = True
    is_active: bool = True


@router.post("/admin/fund-purposes", status_code=status.HTTP_201_CREATED)
def add_purpose(access: Settle, me: CurrentUser, db: DB, body: PurposeIn) -> dict:
    if db.scalar(select(FundPurpose.id).where(func.lower(FundPurpose.name) == body.name.lower())):
        raise field_error("name", "A purpose with this name already exists.")
    last = db.scalar(select(func.max(FundPurpose.sort_order))) or 0
    p = FundPurpose(**body.model_dump(), sort_order=last + 1)
    db.add(p)
    db.flush()
    audit(db, me, "fund_purpose.created", target=p.name, target_type="fund_purpose", target_id=p.id)
    db.commit()
    return purpose_out(p)


@router.put("/admin/fund-purposes/{purpose_id}")
def change_purpose(access: Settle, me: CurrentUser, db: DB, purpose_id: str, body: PurposeIn) -> dict:
    p = db.get(FundPurpose, purpose_id)
    if p is None:
        raise not_found("purpose")
    if db.scalar(select(FundPurpose.id).where(func.lower(FundPurpose.name) == body.name.lower(), FundPurpose.id != p.id)):
        raise field_error("name", "A purpose with this name already exists.")
    fields = [k for k, v in body.model_dump().items() if getattr(p, k) != v]
    for k in fields:
        setattr(p, k, getattr(body, k))
    if fields:
        audit(db, me, "fund_purpose.updated", target=p.name, target_type="fund_purpose", target_id=p.id, fields=fields)
    db.commit()
    return purpose_out(p)


# --- requests ---------------------------------------------------------------------------------


def may_approve(r: FundRequest, access: Access) -> bool:
    # Nobody decides on their own request, however high their role.
    return access.can("funds.approve") and reaches(r, access) and r.owner_id != access.user_id


def fund_out(r: FundRequest, access: Access) -> dict:
    mine = r.owner_id == access.user_id
    finance = r.finance or {}
    return {
        "id": r.id,
        "number": r.number,
        "purpose": {"id": r.purpose_id, "name": r.purpose_name},
        "liquidate": r.liquidate,
        "amountCentavos": r.amount_centavos,
        "approvedCentavos": r.approved_centavos,
        "neededOn": r.needed_on,
        "details": r.details,
        "company": {"id": r.company.id, "name": r.company.name} if r.company else None,
        "status": r.status,
        "statusLabel": STATUS_LABELS[r.status],
        "owner": person_out(r.owner),
        "team": team_out(r.owner.team),
        "decision": None if r.decided_at is None else {"by": person_out(r.decided_by), "at": iso(r.decided_at), "note": r.decision_note},
        # Finance's copy: the release, the receipts, what it came to, and its record.
        "finance": finance or None,
        "financeSyncedAt": iso(r.finance_synced_at),
        "financeError": r.finance_error,
        "createdAt": iso(r.created_at),
        "can": {
            "approve": r.status == "pending" and may_approve(r, access),
            "cancel": mine and r.status in ("pending", "approved", "to_release"),
            "liquidate": mine and r.status == "to_liquidate",
        },
    }


def get_request(db: Session, access: Access, request_id: str) -> FundRequest:
    r = db.get(FundRequest, request_id)
    if r is None or not reaches(r, access):
        raise not_found("request")
    return r


def next_number(db: Session, on: str) -> str:
    prefix = f"FR-{on[:4]}{on[5:7]}-"
    last = db.scalar(select(func.max(FundRequest.number)).where(FundRequest.number.like(f"{prefix}%")))
    return f"{prefix}{(int(last.rsplit('-', 1)[1]) + 1 if last else 1):04d}"


@router.get("/funds/waiting")
def waiting(access: View, db: DB) -> dict:
    """What's waiting on this person: requests to decide on, and their own
    money to account for. As last heard from Finance (the lists ask again)."""
    to_approve = 0
    if access.can("funds.approve"):
        query = within(select(func.count()).select_from(FundRequest), FundRequest, access)
        to_approve = db.scalar(query.where(FundRequest.status == "pending", FundRequest.owner_id != access.user_id)) or 0
    mine = dict(db.execute(
        select(FundRequest.status, func.count()).where(FundRequest.owner_id == access.user_id).group_by(FundRequest.status)
    ).all())
    return {"toApprove": to_approve, "toLiquidate": mine.get("to_liquidate", 0), "toReturn": mine.get("to_return", 0)}


@router.get("/funds")
def list_requests(
    access: View,
    db: DB,
    settings: SettingsDep,
    show: Literal["mine", "approve", "all"] = "mine",
    state: Literal["open", "done", "any"] = "open",
    q: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=200),
) -> dict:
    query = within(select(FundRequest), FundRequest, access)
    if show == "mine":
        query = query.where(FundRequest.owner_id == access.user_id)
    elif show == "approve":
        if not access.can("funds.approve"):
            return {"items": [], "financeError": None}
        query = query.where(FundRequest.status == "pending", FundRequest.owner_id != access.user_id)
    if state == "open":
        query = query.where(FundRequest.status.in_(OPEN))
    elif state == "done":
        query = query.where(FundRequest.status.in_(FINISHED))
    if q:
        like = f"%{q.lower()}%"
        query = query.join(User, User.id == FundRequest.owner_id).where(or_(
            func.lower(FundRequest.number).like(like),
            func.lower(FundRequest.purpose_name).like(like),
            func.lower(FundRequest.details).like(like),
            func.lower(User.full_name).like(like),
        ))
    order = FundRequest.created_at if show == "approve" else FundRequest.created_at.desc()
    items = list(db.scalars(query.order_by(order).limit(limit)).unique())
    problem = refresh(db, settings, items)
    return {"items": [fund_out(r, access) for r in items], "financeError": problem}


class RequestIn(Api):
    purpose_id: str
    amount_centavos: int = Field(gt=0, lt=10**11)
    needed_on: date | None = None
    details: str = Field(min_length=1, max_length=5000)
    company_id: str | None = None


@router.post("/funds", status_code=status.HTTP_201_CREATED)
def create_request(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: RequestIn) -> dict:
    purpose = db.get(FundPurpose, body.purpose_id)
    if purpose is None or not purpose.is_active:
        raise field_error("purposeId", "Select a purpose.")
    on = today(settings.org_timezone)
    if body.needed_on and body.needed_on.isoformat() < on:
        raise field_error("neededOn", "Select today or a later date.")
    company = None
    if body.company_id:
        company = db.get(Company, body.company_id)
        if company is None or not reaches(company, access):
            raise field_error("companyId", "Select a customer from the list.")
    r = FundRequest(
        number=next_number(db, on),
        purpose_id=purpose.id,
        purpose_name=purpose.name,
        liquidate=purpose.liquidate,
        amount_centavos=body.amount_centavos,
        needed_on=body.needed_on.isoformat() if body.needed_on else None,
        details=body.details,
        company_id=company.id if company else None,
        owner_id=me.id,
        team_id=me.team_id,
        created_by_id=me.id,
    )
    db.add(r)
    db.flush()
    audit(db, me, "fund_request.created", target=r.number, target_type="fund_request", target_id=r.id)
    db.commit()
    db.refresh(r)
    return fund_out(r, access)


@router.get("/funds/categories")
def expense_categories(access: View, settings: SettingsDep) -> dict:
    """What spending is sorted into: Finance's list, for the liquidation form."""
    try:
        return {"items": categories(settings)}
    except (FinanceUnavailable, FinanceRefused) as e:
        raise finance_error(e) from e


@router.get("/funds/{request_id}")
def read_request(access: View, db: DB, settings: SettingsDep, request_id: str) -> dict:
    r = get_request(db, access, request_id)
    problem = refresh(db, settings, [r], fresh=True)
    return fund_out(r, access) | {"financeProblem": problem}


class DecisionIn(Api):
    # Approved for less than asked, when the Team Lead says so.
    approved_centavos: int | None = Field(None, gt=0, lt=10**11)
    # Whether receipts and unused funds come back: the purpose's, unless changed here.
    liquidate: bool | None = None
    note: str | None = Field(None, max_length=500)


@router.post("/funds/{request_id}/approve")
def approve(access: Approve, me: CurrentUser, db: DB, settings: SettingsDep, request_id: str, body: DecisionIn) -> dict:
    r = get_request(db, access, request_id)
    if not may_approve(r, access):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot approve your own request.")
    if r.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request has already been approved or declined.")
    amount = body.approved_centavos or r.amount_centavos
    if amount > r.amount_centavos:
        raise field_error("approvedCentavos", "The approved amount cannot exceed the amount requested.")
    r.status, r.approved_centavos = "approved", amount
    if body.liquidate is not None:
        r.liquidate = body.liquidate
    r.decided_by_id, r.decided_at, r.decision_note = me.id, datetime.now(UTC), body.note
    db.flush()
    db.refresh(r)
    audit(db, me, "fund_request.approved", target=r.number, target_type="fund_request", target_id=r.id)
    send(settings, r)
    db.commit()
    return fund_out(r, access)


class NoteIn(Api):
    note: str = Field(min_length=1, max_length=500)


@router.post("/funds/{request_id}/decline")
def decline(access: Approve, me: CurrentUser, db: DB, request_id: str, body: NoteIn) -> dict:
    r = get_request(db, access, request_id)
    if not may_approve(r, access):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot decline your own request.")
    if r.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "This request has already been approved or declined.")
    r.status = "declined"
    r.decided_by_id, r.decided_at, r.decision_note = me.id, datetime.now(UTC), body.note
    audit(db, me, "fund_request.declined", target=r.number, target_type="fund_request", target_id=r.id)
    db.commit()
    db.refresh(r)
    return fund_out(r, access)


class CancelIn(Api):
    reason: str | None = Field(None, max_length=500)


def own(db: Session, access: Access, settings: Settings, request_id: str) -> FundRequest:
    """The requester's own request, as Finance has it now."""
    r = get_request(db, access, request_id)
    if r.owner_id != access.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the requester can do that.")
    refresh(db, settings, [r], fresh=True)
    return r


@router.post("/funds/{request_id}/cancel")
def cancel(access: View, me: CurrentUser, db: DB, settings: SettingsDep, request_id: str, body: CancelIn) -> dict:
    r = own(db, access, settings, request_id)
    if r.status in ("pending", "approved") and not (r.status == "approved" and r.finance):
        r.status = "cancelled"
    elif r.status == "to_release":
        try:
            take(r, link.call(settings, "POST", f"requests/{r.id}/cancel", {"by": me.full_name, "reason": body.reason}))
        except (FinanceUnavailable, FinanceRefused) as e:
            raise finance_error(e) from e
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "The cash advance has been released and can no longer be cancelled. Submit a liquidation instead.")
    audit(db, me, "fund_request.cancelled", target=r.number, target_type="fund_request", target_id=r.id)
    db.commit()
    return fund_out(r, access)


async def read_receipt(upload: UploadFile) -> tuple[bytes, str]:
    data = await upload.read(MAX_RECEIPT_BYTES + 1)
    if len(data) > MAX_RECEIPT_BYTES:
        raise field_error("receipt", "The file exceeds 4 MB. Retake the photo or scan it at a lower resolution.")
    kind = next((v for magic, v in RECEIPT_KINDS.items() if data.startswith(magic)), None)
    if kind is None and data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1"):
        kind = "image/heic"
    if kind is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        kind = "image/webp"
    if kind is None:
        raise field_error("receipt", "Attach the official receipt as a JPG, PNG or PDF file.")
    return data, kind


@router.post("/funds/{request_id}/expenses", status_code=status.HTTP_201_CREATED)
async def add_expense(
    access: View,
    me: CurrentUser,
    db: DB,
    settings: SettingsDep,
    request_id: str,
    spent_on: Annotated[date, Form(alias="spentOn")],
    description: Annotated[str, Form(min_length=1, max_length=200)],
    category_id: Annotated[str, Form(alias="categoryId", min_length=1, max_length=36)],
    amount_centavos: Annotated[int, Form(alias="amountCentavos", gt=0, lt=10**11)],
    no_receipt_reason: Annotated[str | None, Form(alias="noReceiptReason", max_length=300)] = None,
    receipt: Annotated[UploadFile | None, File()] = None,
) -> dict:
    r = own(db, access, settings, request_id)
    if r.status != "to_liquidate":
        raise HTTPException(status.HTTP_409_CONFLICT, "Expenses can be added only after release and before the liquidation is submitted.")
    body = {
        "spentOn": spent_on.isoformat(),
        "description": description.strip(),
        "categoryId": category_id,
        "amountCentavos": amount_centavos,
        "by": me.full_name,
    }
    if receipt is not None and receipt.filename:
        data, kind = await read_receipt(receipt)
        body["receipt"] = receipt_body(re.sub(r"[^\w.\- ]", "", receipt.filename) or "receipt", kind, data)
    elif no_receipt_reason and no_receipt_reason.strip():
        body["noReceiptReason"] = no_receipt_reason.strip()
    else:
        raise field_error("receipt", "Attach the official receipt, or state why there is none.")
    try:
        take(r, link.call(settings, "POST", f"requests/{r.id}/expenses", body))
    except (FinanceUnavailable, FinanceRefused) as e:
        raise finance_error(e) from e
    db.commit()
    return fund_out(r, access)


@router.delete("/funds/{request_id}/expenses/{expense_id}")
def remove_expense(access: View, db: DB, settings: SettingsDep, request_id: str, expense_id: str) -> dict:
    r = own(db, access, settings, request_id)
    try:
        take(r, link.call(settings, "DELETE", f"requests/{r.id}/expenses/{expense_id}"))
    except (FinanceUnavailable, FinanceRefused) as e:
        raise finance_error(e) from e
    db.commit()
    return fund_out(r, access)


@router.post("/funds/{request_id}/submit")
def submit(access: View, me: CurrentUser, db: DB, settings: SettingsDep, request_id: str) -> dict:
    """The liquidation is complete: over to Finance to check."""
    r = own(db, access, settings, request_id)
    try:
        take(r, link.call(settings, "POST", f"requests/{r.id}/submit", {"by": me.full_name}))
    except (FinanceUnavailable, FinanceRefused) as e:
        raise finance_error(e) from e
    audit(db, me, "fund_request.liquidated", target=r.number, target_type="fund_request", target_id=r.id)
    db.commit()
    return fund_out(r, access)


@router.get("/funds/{request_id}/expenses/{expense_id}/receipt")
def read_receipt_file(access: View, db: DB, settings: SettingsDep, request_id: str, expense_id: str) -> Response:
    r = get_request(db, access, request_id)
    try:
        data, content_type = link.call(settings, "GET", f"requests/{r.id}/expenses/{expense_id}/receipt", raw=True)
    except (FinanceUnavailable, FinanceRefused) as e:
        raise finance_error(e) from e
    name = next((e["receipt"]["name"] for e in (r.finance or {}).get("expenses", []) if e["id"] == expense_id and e.get("receipt")), "receipt")
    return Response(data, media_type=content_type, headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(name)}"})
