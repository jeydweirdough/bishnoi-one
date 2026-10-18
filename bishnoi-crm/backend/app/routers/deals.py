"""Deals (benchmarks decision D2): business expected from a customer.

A deal is on a customer, owned by whoever works it, and moves through stages
an administrator keeps (Settings → Deal stages). Each open stage gives a deal
entering it a probability and a forecast category; the forecast category is
the deal's own after that, so a rep can say "commit" while the stage still
says "proposal". Won and lost are closing steps of their own: losing asks why.
A won deal leads to a quote, and a quote made for it can be what wins it.

Needs deals.view / create / edit / delete, within the person's reach (own,
team or all records, as everywhere in the CRM). The stages and the lead source
and lost reason lists are read by anyone signed in and changed with
admin.settings.
"""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app import clidp
from app.access import Access, require
from app.api import Api, camel, changed, field_error, iso, not_found, person_out
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentUser, SettingsDep
from app.likely import likely
from app.models import DEAL_PRIORITIES, Activity, Company, Contact, Deal, DealStage, Quote
from app.pricing import price_lines, sales_settings, today
from app.routers.quotes import book_for
from app.scope import owner_for, reaches, within

router = APIRouter(tags=["deals"])

View = Annotated[Access, Depends(require("deals.view"))]
Create = Annotated[Access, Depends(require("deals.create"))]
Edit = Annotated[Access, Depends(require("deals.edit"))]
Delete = Annotated[Access, Depends(require("deals.delete"))]
Manage = Annotated[Access, Depends(require("admin.settings"))]

# A deal still open can be in any of these; "closed" is only for a won one.
OpenCategory = Literal["pipeline", "best_case", "commit", "omitted"]
CATEGORY_LABELS = {"pipeline": "Pipeline", "best_case": "Best case", "commit": "Commit", "closed": "Closed", "omitted": "Omitted"}

STARTING_LISTS = {
    "sources": ["Referral", "Field visit", "Event", "Website", "Existing customer", "Other"],
    "lostReasons": ["Price", "Went with a competitor", "No budget", "No decision", "Timing", "Other"],
}


# --- the lists: stages, lead sources, lost reasons ---------------------------------------


def stage_out(s: DealStage, used: int = 0) -> dict:
    return {
        "code": s.code,
        "name": s.name,
        "outcome": s.outcome,
        "probability": s.probability,
        "forecastCategory": s.forecast_category,
        "sortOrder": s.sort_order,
        "isActive": s.is_active,
        "deals": used,
    }


def all_stages(db: Session) -> list[dict]:
    used = dict(db.execute(select(Deal.stage_code, func.count()).group_by(Deal.stage_code)).all())
    return [stage_out(s, used.get(s.code, 0)) for s in db.scalars(select(DealStage).order_by(DealStage.sort_order, DealStage.name))]


def stage_of(db: Session, outcome: str) -> DealStage:
    """The won or the lost stage: always there."""
    return db.scalar(select(DealStage).where(DealStage.outcome == outcome).limit(1))


def open_stage(db: Session, code: str | None, field: str = "stageCode") -> DealStage:
    """An open stage on offer, or the first one when none is asked for."""
    if code:
        stage = db.get(DealStage, code)
        if stage is None or not stage.is_active or stage.outcome != "open":
            raise field_error(field, "Pick a stage from the list.")
        return stage
    stage = db.scalar(select(DealStage).where(DealStage.is_active, DealStage.outcome == "open").order_by(DealStage.sort_order).limit(1))
    if stage is None:
        raise field_error(field, "There are no open deal stages. An administrator adds them in Settings → Deal stages.")
    return stage


def deal_lists(db: Session) -> dict:
    saved = sales_settings(db).deal_lists or {}
    return {key: saved.get(key, starting) for key, starting in STARTING_LISTS.items()}


@router.get("/deal-stages")
def list_stages(me: CurrentUser, db: DB) -> list[dict]:
    return all_stages(db)


@router.get("/deal-lists")
def read_lists(me: CurrentUser, db: DB) -> dict:
    return deal_lists(db)


class StageFields(Api):
    name: str | None = Field(None, min_length=1, max_length=60)
    probability: int | None = Field(None, ge=0, le=100)
    forecast_category: OpenCategory | None = None
    sort_order: int | None = Field(None, ge=0, le=999)
    is_active: bool | None = None


class StageIn(StageFields):
    name: str = Field(min_length=1, max_length=60)


def stage_name_taken(db: Session, name: str, not_code: str | None = None) -> bool:
    query = select(DealStage.code).where(func.lower(DealStage.name) == name.lower())
    if not_code:
        query = query.where(DealStage.code != not_code)
    return db.scalar(query) is not None


@router.post("/admin/deal-stages", status_code=status.HTTP_201_CREATED)
def create_stage(access: Manage, me: CurrentUser, db: DB, body: StageIn) -> list[dict]:
    if stage_name_taken(db, body.name):
        raise field_error("name", "There's a stage with this name already.")
    base = re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")[:30] or "stage"
    code, n = base, 2
    while db.get(DealStage, code):
        code, n = f"{base}_{n}", n + 1
    # A new open stage goes after the open ones, before won and lost.
    last_open = db.scalar(select(func.max(DealStage.sort_order)).where(DealStage.outcome == "open")) or 0
    for closed in db.scalars(select(DealStage).where(DealStage.outcome != "open", DealStage.sort_order > last_open)):
        closed.sort_order += 1
    db.add(
        DealStage(
            code=code,
            name=body.name,
            outcome="open",
            probability=body.probability if body.probability is not None else 50,
            forecast_category=body.forecast_category or "pipeline",
            sort_order=body.sort_order if body.sort_order is not None else last_open + 1,
            is_active=body.is_active is not False,
        )
    )
    audit(db, me, "deal_stage.created", target=body.name, target_type="deal_stage", target_id=code)
    db.commit()
    return all_stages(db)


@router.patch("/admin/deal-stages/{code}")
def update_stage(access: Manage, me: CurrentUser, db: DB, code: str, body: StageFields) -> list[dict]:
    stage = db.get(DealStage, code)
    if stage is None:
        raise not_found("deal stage")
    wanted = {k: v for k, v in changed(body).items() if v is not None}
    if stage.outcome != "open":
        # Won and lost are what closing means: only their names are anyone's to change.
        extra = set(wanted) - {"name"}
        if extra:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{stage.name} closes a deal: it can be renamed, nothing else.")
    if "name" in wanted and stage_name_taken(db, wanted["name"], code):
        raise field_error("name", "There's a stage with this name already.")
    if wanted.get("is_active") is False and stage.is_active:
        others = db.scalar(select(func.count()).select_from(DealStage).where(DealStage.is_active, DealStage.outcome == "open", DealStage.code != code)) or 0
        if not others:
            raise HTTPException(status.HTTP_409_CONFLICT, "Keep at least one open stage switched on, or deals couldn't be added.")
    fields = [k for k, v in wanted.items() if getattr(stage, k) != v]
    for k in fields:
        setattr(stage, k, wanted[k])
    if fields:
        audit(db, me, "deal_stage.updated", target=stage.name, target_type="deal_stage", target_id=code, fields=camel(fields))
        db.commit()
    return all_stages(db)


@router.delete("/admin/deal-stages/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(access: Manage, me: CurrentUser, db: DB, code: str) -> Response:
    stage = db.get(DealStage, code)
    if stage is None:
        raise not_found("deal stage")
    if stage.outcome != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, f"{stage.name} closes a deal, so it stays. Rename it instead.")
    used = db.scalar(select(func.count()).select_from(Deal).where(Deal.stage_code == code)) or 0
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{used} {'deal is' if used == 1 else 'deals are'} at this stage. Switch it off instead, or move them first.")
    if stage.is_active and not db.scalar(select(func.count()).select_from(DealStage).where(DealStage.is_active, DealStage.outcome == "open", DealStage.code != code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Keep at least one open stage switched on, or deals couldn't be added.")
    audit(db, me, "deal_stage.deleted", target=stage.name, target_type="deal_stage", target_id=code)
    db.delete(stage)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ListsIn(Api):
    sources: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(max_length=50)
    lost_reasons: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(min_length=1, max_length=50)


@router.put("/admin/deal-lists")
def save_lists(access: Manage, me: CurrentUser, db: DB, body: ListsIn) -> dict:
    def clean(items: list[str]) -> list[str]:
        seen, out = set(), []
        for item in (i.strip() for i in items):
            if item and item.lower() not in seen:
                seen.add(item.lower())
                out.append(item)
        return out

    rules = sales_settings(db)
    lists = {"sources": clean(body.sources), "lostReasons": clean(body.lost_reasons)}
    if lists != deal_lists(db):
        rules.deal_lists = lists
        audit(db, me, "deal_lists.updated", target="Deal lists", target_type="settings", target_id="deal_lists")
        db.commit()
    return deal_lists(db)


# --- one deal ----------------------------------------------------------------------------


def state_of(deal: Deal) -> str:
    return deal.stage.outcome  # open, won or lost


def deal_out(db: Session, deal: Deal, access: Access, *, full: bool = False) -> dict:
    inside = reaches(deal, access)
    state = state_of(deal)
    out = {
        "id": deal.id,
        "no": deal.no,
        "name": deal.name,
        "company": {"id": deal.company.id, "name": deal.company.name},
        "contact": {"id": deal.contact.id, "name": deal.contact.full_name} if deal.contact else None,
        "stage": {"code": deal.stage.code, "name": deal.stage.name},
        "state": state,
        "probability": deal.probability,
        "forecastCategory": deal.forecast_category,
        "valueCentavos": deal.value_centavos,
        "weightedCentavos": deal.value_centavos * deal.probability // 100,
        "expectedCloseOn": deal.expected_close_on,
        "leadSource": deal.lead_source,
        "priority": deal.priority,
        "owner": person_out(deal.owner),
        "createdBy": person_out(deal.created_by),
        "closedAt": iso(deal.closed_at),
        "lostReason": deal.lost_reason,
        "competitor": deal.competitor,
        "createdAt": iso(deal.created_at),
        "updatedAt": iso(deal.updated_at),
        "can": {
            "edit": inside and access.can("deals.edit"),
            "delete": inside and access.can("deals.delete"),
            "quote": inside and access.can("quotes.create") and state != "lost",
        },
    }
    if full:
        quotes = db.scalars(select(Quote).where(Quote.deal_id == deal.id).order_by(Quote.created_at.desc())).all()
        out |= {
            "notes": deal.notes,
            "priceType": deal.price_type,
            "lines": deal.lines,
            # A bid or deal with a product whose CLIDP has run out, or isn't on file where it's needed.
            "clidpWarnings": clidp.warnings(db, [l.get("productCode") for l in deal.lines or []], deal.company, date.today().isoformat()),
            "wonQuoteId": deal.won_quote_id,
            "quotes": [
                {
                    "id": q.id,
                    "number": q.number,
                    "totalCentavos": q.total_centavos,
                    "approvalStatus": q.approval_status,
                    "createdAt": iso(q.created_at),
                }
                for q in quotes
            ],
        }
    return out


def get_deal(db: Session, access: Access, deal_id: str) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None or not reaches(deal, access):
        raise not_found("deal")
    return deal


def linked(db: Session, access: Access, company_id: str | None, contact_id: str | None) -> tuple[Company, Contact | None]:
    """The customer a deal is with, and a contact there; both within reach."""
    company = db.get(Company, company_id) if company_id else None
    if company is None or not reaches(company, access):
        raise field_error("companyId", "Pick a customer you can see.")
    contact = db.get(Contact, contact_id) if contact_id else None
    if contact_id and (contact is None or not reaches(contact, access)):
        raise field_error("contactId", "Pick a contact you can see.")
    if contact and contact.company_id != company.id:
        raise field_error("contactId", f"{contact.full_name} isn't with {company.name}.")
    return company, contact


class LineIn(Api):
    product_id: str = Field(min_length=1, max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    # The promo it's sold under, from the customer's price list; it goes on to the quote.
    promo_id: str | None = Field(None, max_length=36)


def priced(
    db: Session, settings: Settings, company: Company, price_type: str | None, lines: list[LineIn], *, kept_promos: bool = False
) -> tuple[list[dict], int]:
    """The products on a deal, priced by the price rules for this customer (no tax).

    kept_promos: the lines are the deal's own, re-priced (a new price type): a
    promo that has ended since, or that the price rules no longer take, is
    let go rather than stopping the change."""
    if not lines:
        return [], 0
    if not price_type:
        raise field_error("priceType", "Pick the price the products are valued at.")
    book = book_for(db, company, None, today(settings.org_timezone))
    takes = "promo" in book.procedure.get("adjust", [])

    def promo_of(l: LineIn) -> str | None:
        if not l.promo_id or (kept_promos and (not takes or l.promo_id not in book.promos)):
            return None
        return l.promo_id

    result = price_lines(book, price_type, False, [{"productId": l.product_id, "quantity": l.quantity, "promoId": promo_of(l)} for l in lines])
    kept = [
        {
            "productId": l["productId"],
            "productCode": l["productCode"],
            "productName": l["productName"],
            "unit": l["unit"],
            "quantity": l["quantity"],
            "freeQuantity": l["freeQuantity"],
            "unitPriceCentavos": l["unitPriceCentavos"],
            "grossCentavos": l["grossCentavos"],
            "promoId": l["promoId"],
            "promoName": l["promoName"],
            "promoDiscountCentavos": l["promoDiscountCentavos"],
            "totalCentavos": l["totalCentavos"],
        }
        for l in result["lines"]
    ]
    return kept, result["totalCentavos"]


def check_source(db: Session, source: str | None) -> str | None:
    if source and source not in deal_lists(db)["sources"]:
        raise field_error("leadSource", "Pick a lead source from the list.")
    return source


Priority = Literal["urgent", "high", "normal", "low"]
Sort = Literal["name", "created", "value", "close", "priority", "stage"]


def next_steps(db: Session, company_ids: list[str]) -> dict[str, dict]:
    """For each customer, the soonest meeting or task still to do: the next step with them."""
    if not company_ids:
        return {}
    out: dict[str, dict] = {}
    rows = db.scalars(
        select(Activity)
        .where(Activity.company_id.in_(company_ids), Activity.done_at.is_(None), Activity.kind.in_(("meeting", "task")))
        .order_by(Activity.at)
    )
    for a in rows:
        out.setdefault(a.company_id, {"at": iso(a.at), "kind": a.kind, "subject": a.subject})
    return out


class DealFields(Api):
    name: str | None = Field(None, min_length=1, max_length=160)
    contact_id: str | None = Field(None, max_length=36)
    stage_code: str | None = Field(None, max_length=40)
    probability: int | None = Field(None, ge=0, le=100)
    forecast_category: OpenCategory | None = None
    value_centavos: int | None = Field(None, ge=0)
    expected_close_on: date | None = None
    lead_source: str | None = Field(None, max_length=60)
    priority: Priority | None = None
    price_type: str | None = Field(None, max_length=40)
    lines: list[LineIn] | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=5000)
    owner_id: str | None = Field(None, max_length=36)


class DealIn(DealFields):
    # Both filled in when left out: the name from the products and the customer,
    # the close CLOSE_IN_DAYS from today. A rep says only what they decide.
    name: str | None = Field(None, min_length=1, max_length=160)
    company_id: str = Field(min_length=1, max_length=36)
    expected_close_on: date | None = None


CLOSE_IN_DAYS = 30  # a new deal's expected close, when none is given


def deal_name(company: Company, lines: list[dict], on: str) -> str:
    """What's being bought, for whom: "Amoxicillin and Cefalexin for Davao Care
    Hospital", or with no products "Davao Care Hospital · November 2026"."""
    names = [l["productName"] for l in lines if l.get("productName")]
    if names:
        what = names[0] if len(names) == 1 else f"{names[0]} and {names[1]}" if len(names) == 2 else f"{names[0]} and {len(names) - 1} more"
        return f"{what} for {company.name}"[:160]
    closing = date.fromisoformat(on)
    return f"{company.name} · {closing.strftime('%B %Y')}"[:160]


@router.get("/deals/likely")
def how_likely(access: View, me: CurrentUser, db: DB, settings: SettingsDep, stage: str = Query(max_length=40), owner: str | None = Query(None, max_length=36)) -> dict:
    """A deal's probability at this stage for this owner (app/likely.py), before it's saved."""
    found = db.get(DealStage, stage)
    if found is None:
        raise not_found("stage")
    value, why = likely(db, owner or me.id, found, date.fromisoformat(today(settings.org_timezone)))
    return {"probability": value, "why": why}


@router.get("/deals")
def list_deals(
    access: View,
    db: DB,
    settings: SettingsDep,
    state: Literal["open", "won", "lost", "closed"] | None = None,
    stage: str | None = Query(None, max_length=40),
    priority: Literal["urgent", "high", "normal", "low", "none"] | None = None,
    sort: Sort | None = None,
    desc: bool = False,
    company: str | None = Query(None, max_length=36),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    team: str | None = Query(None, max_length=36, description="a team's id: its people's deals"),
    closing: Literal["overdue", "this_month", "next_month", "this_quarter"] | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    query = within(select(Deal).join(Deal.stage), Deal, access)
    if state == "closed":
        query = query.where(DealStage.outcome.in_(("won", "lost")))
    elif state:
        query = query.where(DealStage.outcome == state)
    if stage:
        query = query.where(Deal.stage_code == stage)
    if priority:
        query = query.where(Deal.priority.is_(None) if priority == "none" else Deal.priority == priority)
    if company:
        query = query.where(Deal.company_id == company)
    query = owner_filter(query, access, owner, team)
    if closing:
        on = date.fromisoformat(today(settings.org_timezone))
        if closing == "overdue":
            query = query.where(DealStage.outcome == "open", Deal.expected_close_on < on.isoformat())
        else:
            start, end = closing_window(on, closing)
            query = query.where(Deal.expected_close_on >= start, Deal.expected_close_on < end)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Deal.name).like(like), Deal.company_id.in_(select(Company.id).where(func.lower(Company.name).like(like)))))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    found = query.subquery()
    value = db.scalar(select(func.coalesce(func.sum(found.c.value_centavos), 0))) or 0
    if sort:
        column = {
            "name": func.lower(Deal.name),
            "created": Deal.created_at,
            "value": Deal.value_centavos,
            "close": Deal.expected_close_on,
            # Urgent first; not said last.
            "priority": case({p: n for n, p in enumerate(DEAL_PRIORITIES)}, value=Deal.priority, else_=len(DEAL_PRIORITIES)),
            "stage": DealStage.sort_order,
        }[sort]
        order = (column.desc() if desc else column.asc(), Deal.name)
    else:
        order = (Deal.closed_at.desc(),) if state in ("won", "lost", "closed") else (Deal.expected_close_on.asc(), Deal.name)
    items = db.scalars(query.order_by(*order).limit(limit).offset(offset)).unique().all()
    steps = next_steps(db, list({d.company_id for d in items}))
    return {
        "items": [deal_out(db, d, access) | {"nextStep": steps.get(d.company_id)} for d in items],
        "total": total,
        "valueCentavos": value,
    }


@router.get("/deals-summary")
def summary(
    access: View,
    db: DB,
    settings: SettingsDep,
    state: Literal["open", "closed"] = "open",
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    team: str | None = Query(None, max_length=36),
) -> dict:
    """The figures above the deals: their value, weighted and expected this
    month (open deals) or won and lost (closed ones); and the deals by
    probability, stage and priority, for the charts."""
    query = owner_filter(within(select(Deal).join(Deal.stage), Deal, access), access, owner, team)
    query = query.where(DealStage.outcome == "open") if state == "open" else query.where(DealStage.outcome.in_(("won", "lost")))
    deals = db.scalars(query).unique().all()
    month = today(settings.org_timezone)[:7]
    start, end, _ = period_bounds(month)
    this_month = [d for d in deals if start <= d.expected_close_on < end]
    bands = [("80–100%", 80, 100), ("51–79%", 51, 79), ("0–50%", 0, 50)]
    stages = db.scalars(select(DealStage).order_by(DealStage.sort_order)).all()
    by_stage = [
        {"code": s.code, "name": s.name, "outcome": s.outcome, "count": sum(1 for d in deals if d.stage_code == s.code), "valueCentavos": sum(d.value_centavos for d in deals if d.stage_code == s.code)}
        for s in stages
    ]
    won = [d for d in deals if d.stage.outcome == "won"]
    return {
        "state": state,
        "count": len(deals),
        "valueCentavos": sum(d.value_centavos for d in deals),
        "weightedCentavos": sum(d.value_centavos * d.probability // 100 for d in deals),
        "thisMonthCentavos": sum(d.value_centavos * d.probability // 100 for d in this_month),
        "wonCentavos": sum(d.value_centavos for d in won),
        "wonCount": len(won),
        "lostCount": len(deals) - len(won) if state == "closed" else 0,
        "byProbability": [{"label": label, "count": sum(1 for d in deals if lo <= d.probability <= hi)} for label, lo, hi in bands],
        "byStage": [s for s in by_stage if s["count"]],
        "byPriority": [{"priority": p, "count": sum(1 for d in deals if d.priority == p)} for p in DEAL_PRIORITIES]
        + [{"priority": None, "count": sum(1 for d in deals if d.priority is None)}],
    }


@router.get("/deals/{deal_id}")
def read_deal(access: View, db: DB, deal_id: str) -> dict:
    return deal_out(db, get_deal(db, access, deal_id), access, full=True)


@router.post("/deals", status_code=status.HTTP_201_CREATED)
def create_deal(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: DealIn) -> dict:
    company, contact = linked(db, access, body.company_id, body.contact_id)
    stage = open_stage(db, body.stage_code)
    owner = owner_for(db, access, body.owner_id)
    lines, value = priced(db, settings, company, body.price_type, body.lines or [])
    close_on = (body.expected_close_on or date.fromisoformat(today(settings.org_timezone)) + timedelta(days=CLOSE_IN_DAYS)).isoformat()
    deal = Deal(
        name=(body.name or "").strip() or deal_name(company, lines, close_on),
        company_id=company.id,
        contact_id=contact.id if contact else None,
        stage_code=stage.code,
        probability=body.probability if body.probability is not None else likely(db, owner.id, stage, date.fromisoformat(today(settings.org_timezone)))[0],
        forecast_category=body.forecast_category or stage.forecast_category,
        value_centavos=value if lines else (body.value_centavos or 0),
        expected_close_on=close_on,
        # Not given: the customer's own (how they first came to us).
        lead_source=check_source(db, body.lead_source) if "lead_source" in body.model_fields_set else company.lead_source,
        priority=body.priority,
        price_type=body.price_type if lines else None,
        lines=lines,
        notes=body.notes,
        owner_id=owner.id,
        team_id=owner.team_id,
        created_by_id=me.id,
    )
    db.add(deal)
    db.flush()
    audit(db, me, "deal.created", target=deal.name, target_type="deal", target_id=deal.id)
    db.commit()
    db.refresh(deal)
    return deal_out(db, deal, access, full=True)


@router.patch("/deals/{deal_id}")
def update_deal(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, deal_id: str, body: DealFields) -> dict:
    deal = get_deal(db, access, deal_id)
    wanted = changed(body)
    for key in ("name", "expected_close_on"):
        if key in wanted and wanted[key] is None:
            raise field_error(camel([key])[0], "This can't be left empty.")
    if state_of(deal) != "open" and set(wanted) & {"stage_code", "probability", "forecast_category"}:
        raise HTTPException(status.HTTP_409_CONFLICT, "This deal is closed. Reopen it to change its stage or forecast.")
    if "contact_id" in wanted:
        _, contact = linked(db, access, deal.company_id, wanted["contact_id"])
        wanted["contact_id"] = contact.id if contact else None
    if "stage_code" in wanted:
        stage = open_stage(db, wanted["stage_code"])
        wanted["stage_code"] = stage.code
        # A deal entering a stage takes its probability and forecast category,
        # unless they were given with the move.
        if stage.code != deal.stage_code:
            wanted.setdefault("probability", likely(db, deal.owner_id, stage, date.fromisoformat(today(settings.org_timezone)))[0])
            wanted.setdefault("forecast_category", stage.forecast_category)
    for key in ("probability", "forecast_category"):
        if key in wanted and wanted[key] is None:
            wanted.pop(key)
    if "owner_id" in wanted:
        owner = owner_for(db, access, wanted.pop("owner_id"))
        if owner.id != deal.owner_id:
            wanted["owner_id"], wanted["team_id"] = owner.id, owner.team_id
    if "expected_close_on" in wanted:
        wanted["expected_close_on"] = wanted["expected_close_on"].isoformat()
    if "lead_source" in wanted:
        check_source(db, wanted["lead_source"])
    if "lines" in wanted or "price_type" in wanted:
        kept = "lines" not in wanted
        lines_in = body.lines if not kept else [LineIn(product_id=l["productId"], quantity=l["quantity"], promo_id=l.get("promoId")) for l in deal.lines]
        price_type = wanted.get("price_type", deal.price_type)
        lines, value = priced(db, settings, deal.company, price_type, lines_in or [], kept_promos=kept)
        wanted["lines"], wanted["price_type"] = lines, (price_type if lines else None)
        if lines:
            wanted["value_centavos"] = value
    elif deal.lines and "value_centavos" in wanted:
        raise field_error("valueCentavos", "The value comes from the products on the deal. Change them instead.")
    if "value_centavos" in wanted and wanted["value_centavos"] is None:
        wanted["value_centavos"] = 0

    fields = [k for k, v in wanted.items() if getattr(deal, k) != v]
    for key in fields:
        setattr(deal, key, wanted[key])
    if fields:
        action = "deal.stage_changed" if "stage_code" in fields else "deal.updated"
        audit(db, me, action, target=deal.name, target_type="deal", target_id=deal.id, fields=camel([f for f in fields if f != "team_id"]))
        db.commit()
        db.refresh(deal)
    return deal_out(db, deal, access, full=True)


class WinIn(Api):
    # The quote that won it: made for this customer, and within reach. Its
    # total becomes the deal's value.
    quote_id: str | None = Field(None, max_length=36)


class LoseIn(Api):
    reason: str = Field(min_length=1, max_length=80)
    competitor: str | None = Field(None, max_length=120)


def close(deal: Deal, stage: DealStage, settings: Settings) -> None:
    deal.stage_code = stage.code
    deal.stage = stage
    deal.probability = stage.probability
    deal.forecast_category = stage.forecast_category
    deal.closed_at = datetime.now(UTC)
    # The day it really closed, so the forecast counts it in that period.
    deal.expected_close_on = datetime.now(ZoneInfo(settings.org_timezone)).date().isoformat()


@router.post("/deals/{deal_id}/win")
def win_deal(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, deal_id: str, body: WinIn) -> dict:
    deal = get_deal(db, access, deal_id)
    if state_of(deal) != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This deal is closed already. Reopen it first.")
    if body.quote_id:
        quote = db.get(Quote, body.quote_id)
        if quote is None or not reaches(quote, access) or quote.company_id != deal.company_id:
            raise field_error("quoteId", f"Pick a quote made for {deal.company.name}.")
        if quote.approval_status in ("pending", "rejected"):
            raise field_error("quoteId", "That quote isn't approved.")
        quote.deal_id = deal.id
        deal.won_quote_id = quote.id
        deal.value_centavos = quote.total_centavos
    close(deal, stage_of(db, "won"), settings)
    deal.lost_reason = deal.competitor = None
    audit(db, me, "deal.won", target=deal.name, target_type="deal", target_id=deal.id)
    db.commit()
    db.refresh(deal)
    return deal_out(db, deal, access, full=True)


@router.post("/deals/{deal_id}/lose")
def lose_deal(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, deal_id: str, body: LoseIn) -> dict:
    deal = get_deal(db, access, deal_id)
    if state_of(deal) != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This deal is closed already. Reopen it first.")
    if body.reason not in deal_lists(db)["lostReasons"]:
        raise field_error("reason", "Pick a reason from the list.")
    close(deal, stage_of(db, "lost"), settings)
    deal.lost_reason, deal.competitor, deal.won_quote_id = body.reason, body.competitor, None
    audit(db, me, "deal.lost", target=deal.name, target_type="deal", target_id=deal.id)
    db.commit()
    db.refresh(deal)
    return deal_out(db, deal, access, full=True)


class ReopenIn(Api):
    stage_code: str | None = Field(None, max_length=40)
    expected_close_on: date


@router.post("/deals/{deal_id}/reopen")
def reopen_deal(access: Edit, me: CurrentUser, db: DB, deal_id: str, body: ReopenIn) -> dict:
    deal = get_deal(db, access, deal_id)
    if state_of(deal) == "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This deal is open already.")
    stage = open_stage(db, body.stage_code)
    deal.stage_code, deal.stage = stage.code, stage
    deal.probability, deal.forecast_category = stage.probability, stage.forecast_category
    deal.expected_close_on = body.expected_close_on.isoformat()
    deal.closed_at = deal.lost_reason = deal.competitor = deal.won_quote_id = None
    audit(db, me, "deal.reopened", target=deal.name, target_type="deal", target_id=deal.id)
    db.commit()
    db.refresh(deal)
    return deal_out(db, deal, access, full=True)


@router.delete("/deals/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(access: Delete, me: CurrentUser, db: DB, deal_id: str) -> Response:
    deal = get_deal(db, access, deal_id)
    audit(db, me, "deal.deleted", target=deal.name, target_type="deal", target_id=deal.id)
    # Its quotes stay; they just aren't for a deal any more (the foreign key says so too).
    for quote in db.scalars(select(Quote).where(Quote.deal_id == deal.id)):
        quote.deal_id = None
    db.delete(deal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the pipeline and the forecast -------------------------------------------------------


def closing_window(on: date, which: str) -> tuple[str, str]:
    """[start, end) of this month, next month or this quarter, as YYYY-MM-DD."""
    def month_start(y: int, m: int) -> date:
        return date(y + (m - 1) // 12, (m - 1) % 12 + 1, 1)

    if which == "this_month":
        return month_start(on.year, on.month).isoformat(), month_start(on.year, on.month + 1).isoformat()
    if which == "next_month":
        return month_start(on.year, on.month + 1).isoformat(), month_start(on.year, on.month + 2).isoformat()
    first = (on.month - 1) // 3 * 3 + 1
    return month_start(on.year, first).isoformat(), month_start(on.year, first + 3).isoformat()


# A range of days, both ends included: 2026-07-01..2026-10-15. At most this many days.
LONGEST_RANGE = 3 * 366


def range_label(first: date, last: date) -> str:
    """1 Jul – 15 Oct 2026, or 1 Dec 2025 – 15 Jan 2026 across years."""
    if first == last:
        return f"{first.day} {first:%b %Y}"
    left = f"{first.day} {first:%b}" if first.year == last.year else f"{first.day} {first:%b %Y}"
    return f"{left} – {last.day} {last:%b %Y}"


def period_bounds(period: str) -> tuple[str, str, str]:
    """A month (2026-10), a quarter (2026-Q4) or a range of days
    (2026-07-01..2026-10-15, both included): its [start, end) and its label."""
    if m := re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", period):
        try:
            first, last = date.fromisoformat(m[1]), date.fromisoformat(m[2])
        except ValueError:
            raise field_error("period", "Pick real dates.") from None
        if last < first:
            raise field_error("period", "The range ends before it starts.")
        if (last - first).days > LONGEST_RANGE:
            raise field_error("period", "Pick at most three years.")
        return first.isoformat(), (last + timedelta(days=1)).isoformat(), range_label(first, last)
    if m := re.fullmatch(r"(\d{4})-(\d{2})", period):
        y, mo = int(m[1]), int(m[2])
        if 1 <= mo <= 12:
            start = date(y, mo, 1)
            end = date(y + mo // 12, mo % 12 + 1, 1)
            return start.isoformat(), end.isoformat(), start.strftime("%B %Y")
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", period):
        y, q = int(m[1]), int(m[2])
        start = date(y, (q - 1) * 3 + 1, 1)
        end = date(y + (1 if q == 4 else 0), 1 if q == 4 else q * 3 + 1, 1)
        return start.isoformat(), end.isoformat(), f"Q{q} {y}"
    raise field_error("period", "A period is a month like 2026-10, a quarter like 2026-Q4, or days like 2026-07-01..2026-10-15.")


def owner_filter(query: Select, access: Access, owner: str | None, team: str | None = None) -> Select:
    """One person's deals ('me', or their id), or one team's: within reach either way."""
    if owner:
        query = query.where(Deal.owner_id == (access.user_id if owner == "me" else owner))
    if team:
        query = query.where(Deal.team_id == team)
    return query


@router.get("/deals-board")
def board(
    access: View,
    db: DB,
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    team: str | None = Query(None, max_length=36, description="a team's id: its people's deals"),
    period: str | None = Query(None, max_length=7, description="close in this month (2026-10) or quarter (2026-Q4)"),
) -> dict:
    """The pipeline: open deals by stage, each column with its count and value."""
    query = owner_filter(within(select(Deal).join(Deal.stage), Deal, access).where(DealStage.outcome == "open"), access, owner, team)
    if period:
        start, end, _ = period_bounds(period)
        query = query.where(Deal.expected_close_on >= start, Deal.expected_close_on < end)
    deals = db.scalars(query.order_by(Deal.expected_close_on, Deal.name)).unique().all()
    stages = db.scalars(select(DealStage).where(DealStage.outcome == "open").order_by(DealStage.sort_order)).all()
    columns = []
    for s in stages:
        mine = [d for d in deals if d.stage_code == s.code]
        if not s.is_active and not mine:
            continue
        columns.append(
            {
                "stage": stage_out(s),
                "count": len(mine),
                "valueCentavos": sum(d.value_centavos for d in mine),
                "weightedCentavos": sum(d.value_centavos * d.probability // 100 for d in mine),
                "deals": [deal_out(db, d, access) for d in mine],
            }
        )
    return {"columns": columns}


@router.get("/deals-forecast")
def forecast(
    access: View,
    db: DB,
    settings: SettingsDep,
    period: str | None = Query(None, max_length=7, description="a month (2026-10) or a quarter (2026-Q4); this month when not given"),
    owner: str | None = Query(None, max_length=36, description="'me', or a person's id"),
    team: str | None = Query(None, max_length=36, description="a team's id: its people's deals"),
) -> dict:
    """What each person expects to close in a period, by forecast category.
    Won is what closed in the period; the rest is open deals expected to close
    in it. Omitted and lost deals are left out."""
    period = period or today(settings.org_timezone)[:7]
    start, end, label = period_bounds(period)
    query = within(select(Deal).join(Deal.stage), Deal, access).where(Deal.expected_close_on >= start, Deal.expected_close_on < end)
    deals = db.scalars(owner_filter(query, access, owner, team)).unique().all()
    blank = lambda: {"pipeline": 0, "best_case": 0, "commit": 0, "won": 0, "weighted": 0, "count": 0}  # noqa: E731
    people: dict[str, dict] = {}
    totals = blank()
    for d in deals:
        if d.stage.outcome == "lost" or (d.stage.outcome == "open" and d.forecast_category == "omitted"):
            continue
        row = people.setdefault(d.owner_id, {"owner": person_out(d.owner), **blank()})
        key = "won" if d.stage.outcome == "won" else d.forecast_category
        for target in (row, totals):
            target[key] += d.value_centavos
            target["count"] += 1
            if d.stage.outcome == "open":
                target["weighted"] += d.value_centavos * d.probability // 100

    def out(r: dict) -> dict:
        return {
            "pipelineCentavos": r["pipeline"],
            "bestCaseCentavos": r["best_case"],
            "commitCentavos": r["commit"],
            "wonCentavos": r["won"],
            "weightedCentavos": r["weighted"],
            "deals": r["count"],
        }

    rows = sorted(people.values(), key=lambda r: r["owner"]["name"] if r["owner"] else "")
    return {
        "period": period,
        "label": label,
        "start": start,
        "end": end,
        "people": [{"owner": r["owner"], **out(r)} for r in rows],
        "totals": out(totals),
    }
