"""Fixed assets and budgets (feature plan step 17, 2026-10-29).

Fixed assets: what the company owns for years (vehicles, equipment, computers), depreciated straight-line: (cost −
salvage) ÷ useful months each month, from the month after it was bought, the last month taking what's left. A run
posts one entry per month end (Dr each asset's depreciation expense, Cr its accumulated depreciation), never twice
and never into a locked period.

    GET    /finance/fixed-assets                    the register: cost, accumulated, book value
    POST   /finance/fixed-assets                    one more
    POST   /finance/fixed-assets/depreciate         {through}: every month end not yet depreciated, up to that day
    POST   /finance/fixed-assets/{id}/dispose       no longer depreciated (its sale or write-off is a journal entry)

Budgets: a fiscal year's amount per account (and division), month by month.

    GET    /finance/budgets?yearEnd=                the year's budget lines
    PUT    /finance/budgets                         {yearEnd, accountId, divisionName, months | yearly}: a line (yearly is spread evenly)
    DELETE /finance/budgets/{id}
"""

from calendar import monthrange
from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import Field
from sqlalchemy import select

from app.access import permitted
from app.audit import audit
from app.deps import DB, SettingsDep
from app.ledger import Leg, post
from app.ledger import settings as posting_settings
from app.models import Account, Budget, FixedAsset
from app.routers.funds import today
from app.routers.tax import Api, field_error

router = APIRouter(prefix="/finance", tags=["fixed assets and budgets"])


def month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def next_month_end(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, monthrange(y, m)[1])


def monthly(a: FixedAsset) -> int:
    return round((a.cost_centavos - a.salvage_centavos) / a.useful_months)


def asset_out(a: FixedAsset, accounts: dict) -> dict:
    ref = lambda i: {"id": i, "code": accounts[i].code, "name": accounts[i].name} if i in accounts else None  # noqa: E731
    return {"id": a.id, "name": a.name, "costCentavos": a.cost_centavos, "salvageCentavos": a.salvage_centavos, "acquiredOn": a.acquired_on.isoformat(),
            "usefulMonths": a.useful_months, "monthlyCentavos": monthly(a), "accumulatedCentavos": a.accumulated_centavos,
            "bookValueCentavos": a.cost_centavos - a.accumulated_centavos, "depreciatedUntil": a.depreciated_until.isoformat() if a.depreciated_until else None,
            "status": a.status, "divisionName": a.division_name, "notes": a.notes,
            "assetAccount": ref(a.asset_account_id), "accumulatedAccount": ref(a.accumulated_account_id), "expenseAccount": ref(a.expense_account_id)}


@router.get("/fixed-assets")
def fixed_assets(_: permitted("journal.view"), db: DB) -> dict:
    rows = db.scalars(select(FixedAsset).order_by(FixedAsset.status, FixedAsset.acquired_on.desc())).all()
    accounts = {a.id: a for a in db.scalars(select(Account))}
    items = [asset_out(a, accounts) for a in rows]
    active = [i for i in items if i["status"] == "active"]
    return {"items": items, "totals": {"costCentavos": sum(i["costCentavos"] for i in active), "accumulatedCentavos": sum(i["accumulatedCentavos"] for i in active),
                                       "bookValueCentavos": sum(i["bookValueCentavos"] for i in active)}}


class AssetIn(Api):
    name: str = Field(min_length=1, max_length=160)
    asset_account_id: str
    accumulated_account_id: str
    expense_account_id: str
    cost_centavos: int = Field(gt=0, le=10**13)
    salvage_centavos: int = Field(0, ge=0)
    acquired_on: date
    useful_months: int = Field(ge=1, le=600)
    division_name: str | None = Field(None, max_length=120)
    notes: str | None = Field(None, max_length=500)


@router.post("/fixed-assets", status_code=status.HTTP_201_CREATED)
def add_asset(user: permitted("accounts.manage"), db: DB, settings: SettingsDep, body: AssetIn) -> dict:
    """The register only: buying it is the bill or entry that already put it in the asset account."""
    if body.acquired_on > today(settings):
        raise field_error("acquiredOn", "It can't be bought in the future.")
    if body.salvage_centavos >= body.cost_centavos:
        raise field_error("salvageCentavos", "What it's worth at the end must be less than what it cost.")
    for field, chosen, want, label in (("assetAccountId", body.asset_account_id, "asset", "the asset account it's kept in"),
                                       ("accumulatedAccountId", body.accumulated_account_id, "asset", "the accumulated depreciation account (an asset account that counts against it)"),
                                       ("expenseAccountId", body.expense_account_id, "expense", "the depreciation expense account")):
        a = db.get(Account, chosen)
        if a is None or not a.is_active or a.type != want:
            raise field_error(field, f"Pick {label}.")
    a = FixedAsset(**body.model_dump(), created_by=user.full_name)
    db.add(a)
    db.flush()
    audit(db, user, "fixed_asset.added", target=a.name, target_type="fixed_asset", target_id=a.id)
    db.commit()
    return asset_out(a, {x.id: x for x in db.scalars(select(Account))})


class RunIn(Api):
    through: date


@router.post("/fixed-assets/depreciate")
def depreciate(user: permitted("journal.post"), db: DB, settings: SettingsDep, body: RunIn) -> dict:
    """Every month end not yet depreciated, up to `through`: one entry each, never twice."""
    until = month_end(body.through)
    if until > month_end(today(settings)):
        raise field_error("through", "Depreciate up to this month at the latest.")
    lock = posting_settings(db).locked_until
    by_month: dict[date, list[tuple[FixedAsset, int]]] = {}
    for a in db.scalars(select(FixedAsset).where(FixedAsset.status == "active")):
        at = a.depreciated_until or month_end(a.acquired_on)
        left = a.cost_centavos - a.salvage_centavos - a.accumulated_centavos
        while left > 0:
            at = next_month_end(at)
            if at > until:
                break
            amount = min(monthly(a), left)
            by_month.setdefault(at, []).append((a, amount))
            left -= amount
    if lock is not None and any(m <= lock for m in by_month):
        first = min(by_month)
        raise HTTPException(status.HTTP_409_CONFLICT, f"Depreciation from {first:%B %Y} falls in a closed period (locked up to {lock:%d %b %Y}). Open it first, or begin after it.")
    accounts = {x.id: x for x in db.scalars(select(Account))}
    posted = []
    for at in sorted(by_month):
        legs = []
        for a, amount in by_month[at]:
            legs += [Leg(accounts[a.expense_account_id], debit=amount, description=f"Depreciation: {a.name}"[:200]),
                     Leg(accounts[a.accumulated_account_id], credit=amount, description=f"Depreciation: {a.name}"[:200])]
            a.accumulated_centavos += amount
            a.depreciated_until = at
        e = post(db, at, f"Depreciation for {at:%B %Y}", legs, user.full_name, source="depreciation", by_id=user.id)
        posted.append({"month": at.isoformat(), "number": e.number, "totalCentavos": sum(amount for _, amount in by_month[at])})
    audit(db, user, "fixed_assets.depreciated", target=until.isoformat(), target_type="fixed_asset", fields=[p["month"] for p in posted])
    db.commit()
    return {"entries": posted}


@router.post("/fixed-assets/{asset_id}/dispose")
def dispose(user: permitted("accounts.manage"), db: DB, asset_id: str) -> dict:
    a = db.get(FixedAsset, asset_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such asset.")
    a.status = "disposed"
    audit(db, user, "fixed_asset.disposed", target=a.name, target_type="fixed_asset", target_id=a.id)
    db.commit()
    return asset_out(a, {x.id: x for x in db.scalars(select(Account))})


# --- budgets ---------------------------------------------------------------------------------------------


def budget_out(b: Budget) -> dict:
    return {"id": b.id, "yearEnd": b.year_end.isoformat(), "account": {"id": b.account.id, "code": b.account.code, "name": b.account.name, "type": b.account.type},
            "divisionName": b.division_name or None, "months": b.months, "totalCentavos": sum(b.months)}


@router.get("/budgets")
def budgets(_: permitted("journal.view"), db: DB, year_end: date) -> dict:
    rows = db.scalars(select(Budget).where(Budget.year_end == year_end)).all()
    rows = sorted(rows, key=lambda b: (b.account.code, b.division_name))
    return {"yearEnd": year_end.isoformat(), "items": [budget_out(b) for b in rows]}


class BudgetIn(Api):
    year_end: date
    account_id: str
    division_name: str | None = Field(None, max_length=120)
    months: list[int] | None = Field(None, min_length=12, max_length=12)
    yearly_centavos: int | None = Field(None, ge=0, le=10**14)


@router.put("/budgets")
def set_budget(user: permitted("accounts.manage"), db: DB, body: BudgetIn) -> dict:
    a = db.get(Account, body.account_id)
    if a is None or a.type not in ("income", "expense"):
        raise field_error("accountId", "Budget an income or expense account.")
    if body.months is None and body.yearly_centavos is None:
        raise field_error("yearlyCentavos", "Give the year's amount, or each month's.")
    months = body.months or [body.yearly_centavos // 12 + (1 if i < body.yearly_centavos % 12 else 0) for i in range(12)]
    if any(m < 0 for m in months):
        raise field_error("months", "Amounts can't be negative.")
    division = (body.division_name or "").strip()
    b = db.scalar(select(Budget).where(Budget.year_end == body.year_end, Budget.account_id == a.id, Budget.division_name == division))
    if b is None:
        b = Budget(year_end=body.year_end, account_id=a.id, division_name=division, months=months, updated_by=user.full_name)
        db.add(b)
    b.months, b.updated_by, b.updated_at = months, user.full_name, datetime.now(UTC)
    db.flush()
    audit(db, user, "budget.set", target=f"{a.code} {a.name} {body.year_end.isoformat()}", target_type="budget", target_id=b.id)
    db.commit()
    db.refresh(b)
    return budget_out(b)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(user: permitted("accounts.manage"), db: DB, budget_id: str) -> Response:
    b = db.get(Budget, budget_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such budget line.")
    audit(db, user, "budget.deleted", target=b.account.name, target_type="budget", target_id=b.id)
    db.delete(b)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
