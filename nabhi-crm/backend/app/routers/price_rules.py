"""Price rules: the order a quote line is priced in, price groups, and the
dated conditions (group prices, volume scales, surcharges). See
app/conditions.py for how they apply.

Reading needs products.view; changing needs products.edit.
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, select

from app.access import Access, require
from app.api import Api, camel, field_error, iso, not_found
from app.audit import audit
from app.conditions import ADJUSTMENTS, PRICE_SOURCES, check_procedure, procedure_of, running
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Company, PriceCondition, PriceGroup, PriceType, Product
from app.pricing import FULL, sales_settings, today
from app.routers.catalogue import check_code

router = APIRouter(prefix="/pricing", tags=["price rules"])

View = Annotated[Access, Depends(require("products.view"))]
Edit = Annotated[Access, Depends(require("products.edit"))]


def condition_out(c: PriceCondition, on: str, products: dict[str, str], groups: dict[str, str]) -> dict:
    state = "off" if not c.is_active else "upcoming" if c.starts_on and on < c.starts_on else "ended" if c.ends_on and c.ends_on < on else "running"
    return {
        "id": c.id,
        "kind": c.kind,
        "name": c.name,
        "product": {"id": c.product_id, "name": products.get(c.product_id, "a product no longer here")} if c.product_id else None,
        "priceGroup": {"code": c.price_group_code, "name": groups.get(c.price_group_code, c.price_group_code)} if c.price_group_code else None,
        "priceType": c.price_type_code,
        "amountCentavos": c.amount_centavos,
        "percentBp": c.percent_bp,
        "tiers": c.tiers or [],
        "startsOn": c.starts_on,
        "endsOn": c.ends_on,
        "isActive": c.is_active,
        "state": state,
        "running": running(c, on),
        "updatedAt": iso(c.updated_at),
    }


def rules_out(db: DB, settings: SettingsDep, access: Access) -> dict:
    on = today(settings.org_timezone)
    s = sales_settings(db)
    groups = list(db.scalars(select(PriceGroup).order_by(PriceGroup.sort_order, func.lower(PriceGroup.name))))
    group_names = {g.code: g.name for g in groups}
    members = dict(db.execute(select(Company.price_group_code, func.count()).where(Company.price_group_code.is_not(None)).group_by(Company.price_group_code)).all())
    products = dict(db.execute(select(Product.id, Product.name)).all())
    conditions = db.scalars(select(PriceCondition).order_by(PriceCondition.kind, func.lower(PriceCondition.name)))
    return {
        "procedure": procedure_of(s),
        "sources": [{"key": k, "name": v} for k, v in PRICE_SOURCES.items()],
        "adjustments": [{"key": k, "name": v} for k, v in ADJUSTMENTS.items()],
        "pricesIncludeTax": s.prices_include_tax,
        "financeLinked": settings.finance_linked,
        "groups": [{"code": g.code, "name": g.name, "isActive": g.is_active, "customers": members.get(g.code, 0)} for g in groups],
        "conditions": [condition_out(c, on, products, group_names) for c in conditions],
        "today": on,
        "can": {"edit": access.can("products.edit")},
    }


@router.get("/rules")
def read_rules(access: View, db: DB, settings: SettingsDep) -> dict:
    return rules_out(db, settings, access)


class ProcedureIn(Api):
    price: list[str] = Field(min_length=1, max_length=len(PRICE_SOURCES))
    adjust: list[str] = Field(default_factory=list, max_length=len(ADJUSTMENTS))
    tax: bool = False
    prices_include_tax: bool = True


@router.put("/procedure")
def set_procedure(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: ProcedureIn) -> dict:
    check_procedure(body.price, body.adjust)
    if body.tax and not settings.finance_linked:
        raise field_error("tax", "Link the CRM to Finance first (FINANCE_API_URL and FINANCE_API_KEY): Finance works out the tax.")
    s = sales_settings(db)
    s.pricing_procedure = {"price": body.price, "adjust": body.adjust, "tax": body.tax}
    s.prices_include_tax = body.prices_include_tax
    audit(db, me, "pricing.procedure_changed", target="Price rules", target_type="settings", fields=["procedure"])
    db.commit()
    return rules_out(db, settings, access)


# --- price groups ------------------------------------------------------------------------------


class GroupIn(Api):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return check_code(value)


class GroupPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    is_active: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=999)


@router.post("/groups", status_code=status.HTTP_201_CREATED)
def create_group(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: GroupIn) -> dict:
    if db.get(PriceGroup, body.code):
        raise field_error("code", "A price group already has this code.")
    if db.scalar(select(PriceGroup.code).where(func.lower(PriceGroup.name) == body.name.lower())):
        raise field_error("name", "A price group already has this name.")
    db.add(PriceGroup(code=body.code, name=body.name))
    audit(db, me, "price_group.created", target=body.name, target_type="price_group", target_id=body.code)
    db.commit()
    return rules_out(db, settings, access)


@router.patch("/groups/{code}")
def update_group(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, code: str, body: GroupPatch) -> dict:
    group = db.get(PriceGroup, code)
    if group is None:
        raise not_found("price group")
    wanted = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in wanted and db.scalar(select(PriceGroup.code).where(func.lower(PriceGroup.name) == wanted["name"].lower(), PriceGroup.code != code)):
        raise field_error("name", "A price group already has this name.")
    fields = [k for k, v in wanted.items() if getattr(group, k) != v]
    for k in fields:
        setattr(group, k, wanted[k])
    if fields:
        audit(db, me, "price_group.updated", target=group.name, target_type="price_group", target_id=code, fields=camel(fields))
        db.commit()
    return rules_out(db, settings, access)


@router.delete("/groups/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(access: Edit, me: CurrentUser, db: DB, code: str) -> Response:
    group = db.get(PriceGroup, code)
    if group is None:
        raise not_found("price group")
    customers = db.scalar(select(func.count()).select_from(Company).where(Company.price_group_code == code)) or 0
    if customers:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{customers} customer{'s are' if customers != 1 else ' is'} in this group. Switch it off instead, or move them first.")
    audit(db, me, "price_group.deleted", target=group.name, target_type="price_group", target_id=code)
    db.delete(group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- conditions ------------------------------------------------------------------------------------


class Tier(Api):
    min_qty: int = Field(ge=1, le=1_000_000)
    percent_bp: int = Field(ge=1, le=FULL)


class ConditionIn(Api):
    kind: Literal["group_price", "volume", "surcharge"]
    name: str = Field(min_length=1, max_length=120)
    product_id: str | None = Field(None, max_length=36)
    price_group_code: str | None = Field(None, max_length=40)
    price_type_code: str | None = Field(None, max_length=40)
    amount_centavos: int | None = Field(None, ge=0, le=10_000_000_000)
    percent_bp: int | None = Field(None, ge=1, le=FULL)
    tiers: list[Tier] = Field(default_factory=list, max_length=10)
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _shape(self) -> "ConditionIn":
        if self.kind == "group_price":
            if not self.product_id:
                raise ValueError("A group price is for one product: pick it.")
            if not self.price_group_code:
                raise ValueError("A group price is for one price group: pick it.")
            if self.amount_centavos is None:
                raise ValueError("Enter the group's price, like 1,250.00.")
        if self.kind == "volume" and not self.tiers:
            raise ValueError("A volume scale needs at least one tier.")
        if self.kind == "surcharge" and (self.amount_centavos is None) == (self.percent_bp is None):
            raise ValueError("A surcharge is either an amount per unit or a percent: give one.")
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("It can't end before it starts.")
        return self


def condition_values(db: DB, body: ConditionIn) -> dict:
    if body.product_id and db.get(Product, body.product_id) is None:
        raise field_error("productId", "Pick a product from the list.")
    if body.price_group_code and db.get(PriceGroup, body.price_group_code) is None:
        raise field_error("priceGroupCode", "Pick a price group from the list.")
    if body.price_type_code and db.get(PriceType, body.price_type_code) is None:
        raise field_error("priceTypeCode", "Pick a price type from the list.")
    keep = {"group_price": ("amount_centavos",), "volume": ("tiers",), "surcharge": ("amount_centavos", "percent_bp")}[body.kind]
    return {
        "kind": body.kind,
        "name": body.name,
        "product_id": body.product_id,
        "price_group_code": body.price_group_code,
        "price_type_code": body.price_type_code if body.kind == "group_price" else None,
        "amount_centavos": body.amount_centavos if "amount_centavos" in keep else None,
        "percent_bp": body.percent_bp if "percent_bp" in keep and body.amount_centavos is None else None,
        "tiers": sorted(({"minQty": t.min_qty, "percentBp": t.percent_bp} for t in body.tiers), key=lambda t: t["minQty"]) if body.kind == "volume" else [],
        "starts_on": body.starts_on.isoformat() if body.starts_on else None,
        "ends_on": body.ends_on.isoformat() if body.ends_on else None,
        "is_active": body.is_active,
    }


@router.post("/conditions", status_code=status.HTTP_201_CREATED)
def create_condition(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: ConditionIn) -> dict:
    c = PriceCondition(**condition_values(db, body))
    db.add(c)
    db.flush()
    audit(db, me, "price_rule.created", target=c.name, target_type="price_rule", target_id=c.id)
    db.commit()
    return rules_out(db, settings, access)


@router.put("/conditions/{condition_id}")
def replace_condition(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, condition_id: str, body: ConditionIn) -> dict:
    c = db.get(PriceCondition, condition_id)
    if c is None:
        raise not_found("price rule")
    values = condition_values(db, body)
    fields = [k for k, v in values.items() if getattr(c, k) != v]
    for k in fields:
        setattr(c, k, values[k])
    if fields:
        audit(db, me, "price_rule.updated", target=c.name, target_type="price_rule", target_id=c.id, fields=camel(fields))
        db.commit()
    return rules_out(db, settings, access)


@router.delete("/conditions/{condition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_condition(access: Edit, me: CurrentUser, db: DB, condition_id: str) -> Response:
    """Quotes already made keep the prices they were given."""
    c = db.get(PriceCondition, condition_id)
    if c is None:
        raise not_found("price rule")
    audit(db, me, "price_rule.deleted", target=c.name, target_type="price_rule", target_id=c.id)
    db.delete(c)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
