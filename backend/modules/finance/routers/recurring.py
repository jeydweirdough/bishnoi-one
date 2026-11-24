"""Recurring bill & recurring invoice schedules (migration 0042).

Generates standard DRAFT bills/invoices on schedule so human review & approvals stay enforced.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field
from sqlalchemy import func, select

from modules.finance import company_scope
from modules.finance.access import permitted
from modules.finance.audit import audit
from modules.finance.deps import DB, SettingsDep
from modules.finance.models import Account, Bill, Invoice, RecurringTemplate, Supplier
from modules.finance.payables import work_out as bill_work_out
from modules.finance.routers.funds import today
from modules.finance.routers.tax import Api, BuyerBody, LineBody, SaleBody, field_error, iso, work_out as sale_work_out

router = APIRouter(prefix="/recurring", tags=["recurring"])


def advance_date(d: date, frequency: str) -> date:
    if frequency == "weekly":
        return d + timedelta(days=7)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[frequency]
    total_m = (d.year * 12 + (d.month - 1)) + months
    y, m0 = divmod(total_m, 12)
    m = m0 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


class RecurringIn(Api):
    kind: Literal["bill", "invoice"]
    name: str = Field(min_length=1, max_length=160)
    frequency: Literal["weekly", "monthly", "quarterly", "yearly"] = "monthly"
    start_date: date
    end_date: date | None = None
    payload: dict


class RecurringPatch(Api):
    is_active: bool | None = None


def _template_out(t: RecurringTemplate, on: date) -> dict:
    due = t.is_active and t.next_run_date <= on and (t.end_date is None or t.next_run_date <= t.end_date)
    return {
        "id": t.id,
        "kind": t.kind,
        "name": t.name,
        "frequency": t.frequency,
        "startDate": t.start_date.isoformat(),
        "endDate": t.end_date.isoformat() if t.end_date else None,
        "nextRunDate": t.next_run_date.isoformat(),
        "isActive": t.is_active,
        "isDue": due,
        "payload": t.payload,
        "generatedCount": t.generated_count,
        "lastRunAt": iso(t.last_run_at),
        "createdBy": t.created_by,
        "createdAt": iso(t.created_at),
    }


def _generate_one(db: DB, settings, actor_name: str, t: RecurringTemplate, run_on: date) -> dict:
    p = t.payload or {}
    if t.kind == "bill":
        sup = db.get(Supplier, p.get("supplierId"))
        if sup is None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Supplier for recurring template '{t.name}' no longer exists.")
        lines = p.get("lines") or []
        if not lines:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Template '{t.name}' has no lines.")
        bill_num = f"{p.get('billNumberPrefix') or 'REC'}-{run_on:%Y%m%d}"[:60]
        include_vat = bool(p.get("amountsIncludeVat", True))
        w = bill_work_out(db, lines, run_on, include_vat)
        b = Bill(
            supplier_id=sup.id,
            bill_number=bill_num,
            bill_date=run_on,
            due_date=run_on + timedelta(days=int(sup.terms_days or 30)),
            amounts_include_vat=include_vat,
            notes=p.get("notes") or f"Generated from recurring schedule: {t.name}",
            lines=lines,
            tax_reviewed=False,
            net_centavos=w.net, vat_centavos=w.vat, withheld_centavos=w.withheld,
            total_centavos=w.total, payable_centavos=w.payable,
            created_by=f"{actor_name} (recurring)",
        )
        db.add(b)
        db.flush()
        result = {"kind": "bill", "id": b.id, "href": f"/bills/{b.id}", "label": f"Bill draft {b.no} ({sup.name})"}
    else:
        lines = p.get("lines") or []
        if not lines:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Template '{t.name}' has no lines.")
        inv = Invoice(
            customer_id=p.get("customerId"),
            customer_name=p.get("customerName") or "Customer",
            customer_tin=p.get("customerTin"),
            customer_address=p.get("customerAddress"),
            treatment=p.get("treatment") or "regular",
            invoice_date=run_on,
            terms_days=int(p.get("termsDays") or 30),
            reference=p.get("reference") or t.name[:80],
            notes=p.get("notes") or f"Generated from recurring schedule: {t.name}",
            lines=lines,
            created_by=f"{actor_name} (recurring)",
        )
        sale_work_out(
            db, settings,
            SaleBody(
                treatment=inv.treatment, on=run_on,
                buyer=BuyerBody(name=inv.customer_name, tin=inv.customer_tin, address=inv.customer_address),
                lines=[LineBody(**{k: v for k, v in ln.items() if k != "accountId"}) for ln in lines],
            ),
        )
        db.add(inv)
        db.flush()
        result = {"kind": "invoice", "id": inv.id, "href": f"/invoices/{inv.id}", "label": f"Invoice draft ({inv.customer_name})"}
    t.generated_count += 1
    t.last_run_at = datetime.now(UTC)
    t.next_run_date = advance_date(t.next_run_date, t.frequency)
    if t.end_date and t.next_run_date > t.end_date:
        t.is_active = False
    return result


@router.get("")
def list_recurring(_: permitted("bills.view"), db: DB, settings: SettingsDep, kind: Literal["bill", "invoice"] | None = Query(None)) -> dict:
    on = today(settings)
    q = select(RecurringTemplate).order_by(RecurringTemplate.is_active.desc(), RecurringTemplate.next_run_date.asc())
    if kind:
        q = q.where(RecurringTemplate.kind == kind)
    items = [_template_out(t, on) for t in db.scalars(q)]
    due_count = sum(1 for item in items if item["isDue"])
    sup_q = select(Supplier).where(Supplier.is_active).order_by(func.lower(Supplier.name))
    if company_scope.configured(db, "supplier"):
        sup_q = sup_q.where(company_scope.usable_clause("supplier", Supplier.id))
    acct_q = select(Account).where(Account.is_active, Account.type.in_(("expense", "asset"))).order_by(Account.code)
    inc_q = select(Account).where(Account.is_active, Account.type == "income").order_by(Account.code)
    if company_scope.configured(db, "account"):
        acct_q = acct_q.where(company_scope.usable_clause("account", Account.id))
        inc_q = inc_q.where(company_scope.usable_clause("account", Account.id))
    suppliers = [{"id": s.id, "name": s.name} for s in db.scalars(sup_q)]
    accounts = [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in db.scalars(acct_q)]
    income_accounts = [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in db.scalars(inc_q)]
    return {"items": items, "dueCount": due_count, "today": on.isoformat(), "suppliers": suppliers, "accounts": accounts, "incomeAccounts": income_accounts}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_recurring(user: permitted("bills.create"), db: DB, settings: SettingsDep, body: RecurringIn) -> dict:
    if body.end_date and body.end_date < body.start_date:
        raise field_error("endDate", "End date can't be before start date.")
    lines = (body.payload or {}).get("lines") or []
    if not lines:
        raise field_error("payload", "Add at least one line item.")
    if body.kind == "bill" and not (body.payload or {}).get("supplierId"):
        raise field_error("payload", "Pick a supplier for a recurring bill.")
    if body.kind == "invoice" and not (body.payload or {}).get("customerName"):
        raise field_error("payload", "Enter a customer name for a recurring invoice.")
    t = RecurringTemplate(
        kind=body.kind, name=body.name.strip(), frequency=body.frequency,
        start_date=body.start_date, end_date=body.end_date, next_run_date=body.start_date,
        payload=body.payload, created_by=user.full_name,
    )
    db.add(t)
    db.flush()
    audit(db, user, "recurring.created", target=t.name, target_type="recurring", target_id=t.id)
    db.commit()
    return _template_out(t, today(settings))


@router.patch("/{template_id}")
def patch_recurring(user: permitted("bills.create"), db: DB, settings: SettingsDep, template_id: str, body: RecurringPatch) -> dict:
    t = db.get(RecurringTemplate, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such recurring template.")
    if body.is_active is not None:
        t.is_active = body.is_active
    db.commit()
    return _template_out(t, today(settings))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(user: permitted("bills.create"), db: DB, template_id: str) -> None:
    t = db.get(RecurringTemplate, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such recurring template.")
    db.delete(t)
    db.commit()


@router.post("/run-due")
def run_due_recurring(user: permitted("bills.create"), db: DB, settings: SettingsDep) -> dict:
    on = today(settings)
    due = db.scalars(
        select(RecurringTemplate).where(RecurringTemplate.is_active, RecurringTemplate.next_run_date <= on)
        .order_by(RecurringTemplate.next_run_date)
    ).all()
    created = []
    for t in due:
        if t.end_date and t.next_run_date > t.end_date:
            t.is_active = False
            continue
        created.append(_generate_one(db, settings, user.full_name, t, min(t.next_run_date, on)))
    db.commit()
    return {"generated": created, "count": len(created)}


@router.post("/{template_id}/generate")
def generate_now(user: permitted("bills.create"), db: DB, settings: SettingsDep, template_id: str) -> dict:
    t = db.get(RecurringTemplate, template_id)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such recurring template.")
    on = today(settings)
    created = _generate_one(db, settings, user.full_name, t, min(t.next_run_date, on) if t.next_run_date <= on else on)
    db.commit()
    return created
