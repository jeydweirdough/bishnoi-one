"""The catalogue: products and services with their prices, the price types
they're priced by, promos, bundles, guarantee-letter issuers, and the CRM's own
rules for quotes.

Reading any of it needs products.view. Adding products needs
products.create, deleting them products.delete, and everything else here
(changing products, prices, promos, bundles and the rules) products.edit.
The catalogue is the company's, so a role's scope doesn't narrow it, except
for promos and bundles: those belong to divisions (teams). Someone who reaches
every record sees them all; anyone else sees, and quotes, only their own
division's.
"""

import re
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.access import Access, require
from app.api import Api, camel, changed, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.extra import check_extra, check_required
from app.inventory import SRP, Unreachable, link_out, linked_codes, stock, sync_if_stale, try_sync
from app.models import Bundle, Issuer, PriceType, Product, ProductPrice, Promo, Team
from app.pricing import FULL, promo_terms, sales_settings, state_of, today

router = APIRouter(tags=["catalogue"])

View = Annotated[Access, Depends(require("products.view"))]
Create = Annotated[Access, Depends(require("products.create"))]
Edit = Annotated[Access, Depends(require("products.edit"))]
Delete = Annotated[Access, Depends(require("products.delete"))]

CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*")


def check_code(value: str | None) -> str | None:
    if value is not None and not CODE.fullmatch(value):
        raise ValueError("Use letters, numbers, dots, dashes or underscores, with no spaces.")
    return value.upper() if value else value


def found(record, what: str):
    if record is None:
        raise not_found(what)
    return record


def check_dates(starts_on: date | None, ends_on: date | None) -> None:
    if starts_on and ends_on and ends_on < starts_on:
        raise field_error("endsOn", "It can't end before it starts.")


# --- the rules: price types, issuers, settings -------------------------------------------


def price_type_out(t: PriceType) -> dict:
    return {
        "code": t.code,
        "name": t.name,
        "entry": t.entry,
        "rule": t.rule,
        "requiresNotes": t.requires_notes,
        "needsApproval": t.needs_approval,
        "isActive": t.is_active,
        "sortOrder": t.sort_order,
    }


def rules_out(db: Session, access: Access) -> dict:
    s = sales_settings(db)
    return {
        "priceTypes": [price_type_out(t) for t in db.scalars(select(PriceType).order_by(PriceType.sort_order, PriceType.name))],
        "issuers": [{"code": i.code, "name": i.name, "isActive": i.is_active} for i in db.scalars(select(Issuer).order_by(Issuer.name))],
        "settings": {
            "discountApprovalBp": s.discount_approval_bp,
            "allowsGuaranteeLetters": s.allows_guarantee_letters,
            "atRiskDays": s.at_risk_days,
            "lostDays": s.lost_days,
        },
        "can": {"edit": access.can("products.edit")},
    }


@router.get("/pricing")
def read_rules(access: View, db: DB) -> dict:
    return rules_out(db, access)


class PriceTypeFields(Api):
    name: str | None = Field(None, min_length=1, max_length=80)
    entry: Literal["list", "entered"] | None = None
    rule: Literal["always", "with_rx"] | None = None
    requires_notes: bool | None = None
    needs_approval: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(None, ge=0, le=999)


class PriceTypeIn(PriceTypeFields):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return check_code(value)


@router.post("/pricing/price-types", status_code=status.HTTP_201_CREATED)
def create_price_type(access: Edit, me: CurrentUser, db: DB, body: PriceTypeIn) -> dict:
    if db.get(PriceType, body.code):
        raise field_error("code", "A price type already has this code.")
    db.add(PriceType(**body.model_dump(exclude_none=True)))
    audit(db, me, "price_type.created", target=body.name, target_type="price_type", target_id=body.code)
    db.commit()
    return rules_out(db, access)


@router.patch("/pricing/price-types/{code}")
def update_price_type(access: Edit, me: CurrentUser, db: DB, code: str, body: PriceTypeFields) -> dict:
    kind = found(db.get(PriceType, code), "price type")
    wanted = {k: v for k, v in changed(body).items() if v is not None}
    fields = [k for k, v in wanted.items() if getattr(kind, k) != v]
    for k in fields:
        setattr(kind, k, wanted[k])
    if fields:
        audit(db, me, "price_type.updated", target=kind.name, target_type="price_type", target_id=code, fields=camel(fields))
        db.commit()
    return rules_out(db, access)


class IssuerIn(Api):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return check_code(value)


class IssuerPatch(Api):
    name: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None


@router.post("/pricing/issuers", status_code=status.HTTP_201_CREATED)
def create_issuer(access: Edit, me: CurrentUser, db: DB, body: IssuerIn) -> dict:
    if db.get(Issuer, body.code):
        raise field_error("code", "An issuer already has this code.")
    db.add(Issuer(code=body.code, name=body.name))
    audit(db, me, "issuer.created", target=body.name, target_type="issuer", target_id=body.code)
    db.commit()
    return rules_out(db, access)


@router.patch("/pricing/issuers/{code}")
def update_issuer(access: Edit, me: CurrentUser, db: DB, code: str, body: IssuerPatch) -> dict:
    issuer = found(db.get(Issuer, code), "issuer")
    wanted = {k: v for k, v in changed(body).items() if v is not None}
    fields = [k for k, v in wanted.items() if getattr(issuer, k) != v]
    for k in fields:
        setattr(issuer, k, wanted[k])
    if fields:
        audit(db, me, "issuer.updated", target=issuer.name, target_type="issuer", target_id=code, fields=camel(fields))
        db.commit()
    return rules_out(db, access)


class SettingsPatch(Api):
    discount_approval_bp: int | None = Field(None, ge=0, le=FULL)
    allows_guarantee_letters: bool | None = None
    at_risk_days: int | None = Field(None, ge=1, le=3650)
    lost_days: int | None = Field(None, ge=1, le=3650)


@router.patch("/pricing/settings")
def update_settings(access: Edit, me: CurrentUser, db: DB, body: SettingsPatch) -> dict:
    s = sales_settings(db)
    wanted = {k: v for k, v in changed(body).items() if v is not None}
    at_risk, lost = wanted.get("at_risk_days", s.at_risk_days), wanted.get("lost_days", s.lost_days)
    if lost <= at_risk:
        raise field_error("lostDays", "Lost has to come after at risk.")
    fields = [k for k, v in wanted.items() if getattr(s, k) != v]
    for k in fields:
        setattr(s, k, wanted[k])
    if fields:
        audit(db, me, "sales_settings.updated", target="CRM rules", target_type="settings", fields=camel(fields))
    db.commit()
    return rules_out(db, access)


# --- products ------------------------------------------------------------------------------


def product_out(p: Product, access: Access) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "genericName": p.generic_name,
        "strength": p.strength,
        "form": p.form,
        "unit": p.unit,
        "vatCategory": p.vat_category,
        "isActive": p.is_active,
        # Its code, name, unit, state and SRP are Inventory's, changed there.
        "fromInventory": p.inventory_id is not None,
        "prices": {pp.price_type_code: pp.amount_centavos for pp in p.prices},
        "extra": p.extra or {},
        "updatedAt": iso(p.updated_at),
        "can": {"edit": access.can("products.edit"), "delete": access.can("products.delete")},
    }


def get_product(db: Session, product_id: str) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("product")
    return product


@router.get("/products")
def list_products(
    access: View,
    db: DB,
    settings: SettingsDep,
    q: str | None = Query(None, max_length=100),
    active: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    sync_if_stale(db, settings)
    query = select(Product)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(Product.name).like(like), func.lower(Product.code).like(like), func.lower(Product.generic_name).like(like)))
    if active is not None:
        query = query.where(Product.is_active == active)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    products = db.scalars(query.order_by(func.lower(Product.name)).limit(limit).offset(offset)).all()
    listed = [t.code for t in db.scalars(select(PriceType).where(PriceType.entry == "list", PriceType.is_active))]
    missing = sum(1 for p in db.scalars(select(Product).where(Product.is_active)) if any(c not in {x.price_type_code for x in p.prices} for c in listed))
    return {"items": [product_out(p, access) for p in products], "total": total, "missingPrices": missing, "inventory": link_out(db, settings)}


@router.post("/products/sync")
def sync_products(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    """Bring the product list over from Inventory now."""
    if not settings.inventory_linked:
        raise HTTPException(status.HTTP_409_CONFLICT, "The CRM isn't linked to Inventory (INVENTORY_API_URL, INVENTORY_API_KEY).")
    result = try_sync(db, settings)
    if result is None:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, link_out(db, settings)["error"])
    audit(db, me, "product.synced", target=f"From Inventory: {result['added']} added, {result['updated']} changed, {result['switchedOff']} switched off", target_type="product")
    db.commit()
    return result | {"inventory": link_out(db, settings)}


@router.get("/stock")
def product_stock(access: View, db: DB, settings: SettingsDep, codes: str = Query(..., max_length=20000)) -> dict:
    """How much of these products Inventory has, overall and per warehouse,
    by code. A product kept only here has none listed."""
    if not settings.inventory_linked:
        return {"linked": False, "items": {}, "error": None}
    wanted = linked_codes(db, [c for c in codes.split(",") if c.strip()][:500])
    try:
        return {"linked": True, "items": stock(settings, wanted) if wanted else {}, "error": None}
    except Unreachable as e:
        return {"linked": True, "items": {}, "error": str(e)}


class ProductFields(Api):
    code: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=160)
    generic_name: str | None = Field(None, max_length=160)
    strength: str | None = Field(None, max_length=60)
    form: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, min_length=1, max_length=30)
    # For VAT, as Finance's tax pack names it (the price rules' tax step).
    vat_category: Literal["standard", "zero_rated", "exempt"] | None = None
    is_active: bool | None = None
    # price type code -> centavos; null clears that price.
    prices: dict[str, int | None] | None = None
    # Added fields' values, by key (Settings → Forms). A null clears one.
    extra: dict[str, Any] | None = None

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return check_code(value)

    @field_validator("prices")
    @classmethod
    def _prices(cls, value: dict | None) -> dict | None:
        if value and any(v is not None and not 0 < v < 10**11 for v in value.values()):
            raise ValueError("Prices are amounts above zero.")
        return value


class ProductIn(ProductFields):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)


def set_prices(db: Session, product: Product, prices: dict[str, int | None]) -> list[str]:
    known = {t.code for t in db.scalars(select(PriceType))}
    unknown = [c for c in prices if c not in known]
    if unknown:
        raise field_error("prices", f"There's no price type {unknown[0]}.")
    current = {pp.price_type_code: pp for pp in product.prices}
    touched = []
    for code, amount in prices.items():
        there = current.get(code)
        if amount is None and there:
            product.prices.remove(there)
        elif amount is not None and there is None:
            product.prices.append(ProductPrice(price_type_code=code, amount_centavos=amount))
        elif amount is not None and there.amount_centavos != amount:
            there.amount_centavos = amount
        else:
            continue
        touched.append(code)
    return touched


def code_taken(db: Session, model, code: str, not_id: str | None = None) -> bool:
    query = select(model.id).where(func.upper(model.code) == code.upper())
    if not_id:
        query = query.where(model.id != not_id)
    return db.scalar(query) is not None


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(access: Create, me: CurrentUser, db: DB, settings: SettingsDep, body: ProductIn) -> dict:
    if settings.inventory_linked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Products are added in Inventory: the CRM brings them over from there.")
    if code_taken(db, Product, body.code):
        raise field_error("code", "Another product has this code.")
    product = Product(**body.model_dump(exclude={"prices", "extra"}, exclude_none=True), extra=check_extra(db, "product", body.extra))
    check_required(db, "product", product)
    db.add(product)
    set_prices(db, product, body.prices or {})
    db.flush()
    audit(db, me, "product.created", target=product.name, target_type="product", target_id=product.id)
    db.commit()
    db.refresh(product)
    return product_out(product, access)


@router.get("/products/{product_id}")
def read_product(access: View, db: DB, product_id: str) -> dict:
    return product_out(get_product(db, product_id), access)


@router.patch("/products/{product_id}")
def update_product(access: Edit, me: CurrentUser, db: DB, product_id: str, body: ProductFields) -> dict:
    product = get_product(db, product_id)
    wanted = changed(body)
    prices = wanted.pop("prices", None)
    if product.inventory_id:
        for k in ("code", "name", "unit", "is_active"):
            if k in wanted and wanted[k] != getattr(product, k):
                raise field_error(camel([k])[0], "This comes from Inventory: change it there.")
        if prices and SRP in prices:
            raise field_error("prices", "The SRP comes from Inventory: change it there, or give a team its own price.")
    for required in ("code", "name", "unit", "is_active", "vat_category"):
        if required in wanted and wanted[required] is None:
            raise field_error(camel([required])[0], "This is required.")
    if wanted.get("code") and code_taken(db, Product, wanted["code"], product.id):
        raise field_error("code", "Another product has this code.")
    if "extra" in wanted:
        wanted["extra"] = check_extra(db, "product", wanted["extra"], product.extra)
    fields = [k for k, v in wanted.items() if getattr(product, k) != v]
    for k in fields:
        setattr(product, k, wanted[k])
    touched = set_prices(db, product, prices) if prices else []
    check_required(db, "product", product)
    if fields or touched:
        audit(db, me, "product.updated", target=product.name, target_type="product", target_id=product.id, fields=camel(fields) + (["prices"] if touched else []))
        db.commit()
        db.refresh(product)
    return product_out(product, access)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(access: Delete, me: CurrentUser, db: DB, product_id: str) -> Response:
    product = get_product(db, product_id)
    if product.inventory_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "It comes from Inventory: discontinue it there, and it's switched off here.")
    in_bundles = [b.name for b in db.scalars(select(Bundle)) if any(i["productId"] == product.id for i in b.items)]
    if in_bundles:
        raise HTTPException(status.HTTP_409_CONFLICT, f"It's in the bundle {in_bundles[0]}. Take it out of bundles first, or switch it off instead.")
    # Quotes keep their own copy of every line, so they stay as they were.
    audit(db, me, "product.deleted", target=product.name, target_type="product", target_id=product.id)
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- divisions: whose promos and bundles are whose -----------------------------------------


def reach_of(access: Access) -> set[str] | None:
    """The divisions this person's promos and bundles come from. None: every one."""
    if access.scope == "all":
        return None
    return {access.team_id} if access.team_id else set()


def sees(record: Promo | Bundle, access: Access) -> bool:
    reach = reach_of(access)
    return reach is None or bool(reach & set(record.team_ids or []))


def reachable(db: Session, model, record_id: str, what: str, access: Access):
    """A promo or bundle this person may see; outside their division it doesn't exist for them."""
    record = db.get(model, record_id)
    if record is None or not sees(record, access):
        raise not_found(what)
    return record


def team_names(db: Session) -> dict[str, str]:
    return dict(db.execute(select(Team.id, Team.name)).all())


def divisions_out(team_ids: list[str] | None, names: dict[str, str]) -> dict:
    ids = [t for t in team_ids or [] if t in names]
    return {"teamIds": ids, "teams": [{"id": t, "name": names[t]} for t in ids]}


def team_options(db: Session, access: Access) -> list[dict]:
    """The divisions this person may give a promo or bundle to."""
    reach = reach_of(access)
    q = select(Team).where(Team.is_active).order_by(func.lower(Team.name))
    return [{"id": t.id, "name": t.name} for t in db.scalars(q) if reach is None or t.id in reach]


def check_teams(db: Session, access: Access, team_ids: list[str], current: list[str] | None = None) -> list[str]:
    ids = list(dict.fromkeys(team_ids))
    teams = {t.id: t for t in db.scalars(select(Team).where(Team.id.in_(ids)))}
    # A switched-off division keeps what it had, but gets nothing new.
    if len(teams) != len(ids) or any(not t.is_active and t.id not in (current or []) for t in teams.values()):
        raise field_error("teamIds", "Pick divisions from the list.")
    reach = reach_of(access)
    if reach is not None and not set(ids) <= reach:
        raise field_error("teamIds", "You can only set them for your own division.")
    return ids


# --- promos --------------------------------------------------------------------------------


class Tier(Api):
    min_qty: int = Field(ge=1, le=100_000)
    percent_bp: int = Field(ge=1, le=FULL)


class PromoIn(Api):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["percent", "amount", "free_goods", "tiered"]
    percent_bp: int | None = Field(None, ge=1, le=FULL)
    amount_centavos: int | None = Field(None, ge=1)
    buy_qty: int | None = Field(None, ge=1, le=10_000)
    free_qty: int | None = Field(None, ge=1, le=10_000)
    tiers: list[Tier] = Field(default_factory=list, max_length=10)
    # None: every product.
    product_ids: list[str] | None = Field(None, max_length=500)
    # The divisions it's for: at least one.
    team_ids: list[str] = Field(min_length=1, max_length=50)
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _terms(self) -> "PromoIn":
        need = {"percent": ["percent_bp"], "amount": ["amount_centavos"], "free_goods": ["buy_qty", "free_qty"], "tiered": []}[self.kind]
        for name in need:
            if getattr(self, name) is None:
                raise ValueError(f"A {self.kind.replace('_', ' ')} promo needs {name.replace('_', ' ')}.")
        if self.kind == "tiered" and not self.tiers:
            raise ValueError("A tiered promo needs at least one tier.")
        return self


def promo_out(p: Promo, on: str, names: dict[str, str]) -> dict:
    return (
        promo_terms(p)
        | divisions_out(p.team_ids, names)
        | {"startsOn": p.starts_on, "endsOn": p.ends_on, "isActive": p.is_active, "state": state_of(p.is_active, p.starts_on, p.ends_on, on)}
    )


def promo_values(db: Session, access: Access, body: PromoIn, current: list[str] | None = None) -> dict:
    check_dates(body.starts_on, body.ends_on)
    team_ids = check_teams(db, access, body.team_ids, current)
    if body.product_ids is not None:
        body.product_ids = list(dict.fromkeys(body.product_ids))
        known = set(db.scalars(select(Product.id).where(Product.id.in_(body.product_ids))))
        if len(known) != len(body.product_ids) or not known:
            raise field_error("productIds", "Pick products from the list, or leave it for every product.")
    keep = {"percent": ["percent_bp"], "amount": ["amount_centavos"], "free_goods": ["buy_qty", "free_qty"], "tiered": ["tiers"]}[body.kind]
    return {
        "name": body.name,
        "kind": body.kind,
        "percent_bp": body.percent_bp if "percent_bp" in keep else None,
        "amount_centavos": body.amount_centavos if "amount_centavos" in keep else None,
        "buy_qty": body.buy_qty if "buy_qty" in keep else None,
        "free_qty": body.free_qty if "free_qty" in keep else None,
        "tiers": sorted(({"minQty": t.min_qty, "percentBp": t.percent_bp} for t in body.tiers), key=lambda t: t["minQty"]) if body.kind == "tiered" else [],
        "product_ids": body.product_ids,
        "team_ids": team_ids,
        "starts_on": body.starts_on.isoformat() if body.starts_on else None,
        "ends_on": body.ends_on.isoformat() if body.ends_on else None,
        "is_active": body.is_active,
    }


@router.get("/promos")
def list_promos(access: View, db: DB, settings: SettingsDep) -> dict:
    on, names = today(settings.org_timezone), team_names(db)
    promos = [p for p in db.scalars(select(Promo).order_by(Promo.created_at.desc())) if sees(p, access)]
    return {"items": [promo_out(p, on, names) for p in promos], "teams": team_options(db, access), "can": {"edit": access.can("products.edit")}}


@router.post("/promos", status_code=status.HTTP_201_CREATED)
def create_promo(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: PromoIn) -> dict:
    promo = Promo(**promo_values(db, access, body))
    db.add(promo)
    db.flush()
    audit(db, me, "promo.created", target=promo.name, target_type="promo", target_id=promo.id)
    db.commit()
    return promo_out(promo, today(settings.org_timezone), team_names(db))


@router.put("/promos/{promo_id}")
def replace_promo(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, promo_id: str, body: PromoIn) -> dict:
    promo = reachable(db, Promo, promo_id, "promo", access)
    values = promo_values(db, access, body, promo.team_ids)
    fields = [k for k, v in values.items() if getattr(promo, k) != v]
    for k in fields:
        setattr(promo, k, values[k])
    if fields:
        audit(db, me, "promo.updated", target=promo.name, target_type="promo", target_id=promo.id, fields=camel(fields))
        db.commit()
    return promo_out(promo, today(settings.org_timezone), team_names(db))


@router.delete("/promos/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo(access: Edit, me: CurrentUser, db: DB, promo_id: str) -> Response:
    promo = reachable(db, Promo, promo_id, "promo", access)
    audit(db, me, "promo.deleted", target=promo.name, target_type="promo", target_id=promo.id)
    db.delete(promo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- bundles -------------------------------------------------------------------------------


class BundleItem(Api):
    product_id: str = Field(max_length=36)
    qty: int = Field(ge=1, le=10_000)


class BundleIn(Api):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    price_centavos: int = Field(ge=1)
    as_one_line: bool = True
    items: list[BundleItem] = Field(min_length=1, max_length=30)
    # The divisions it's for: at least one.
    team_ids: list[str] = Field(min_length=1, max_length=50)
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return check_code(value)


def bundle_out(b: Bundle, on: str, names: dict[str, str]) -> dict:
    return divisions_out(b.team_ids, names) | {
        "id": b.id,
        "code": b.code,
        "name": b.name,
        "priceCentavos": b.price_centavos,
        "asOneLine": b.as_one_line,
        "items": b.items,
        "startsOn": b.starts_on,
        "endsOn": b.ends_on,
        "isActive": b.is_active,
        "state": state_of(b.is_active, b.starts_on, b.ends_on, on),
    }


def bundle_values(db: Session, access: Access, body: BundleIn, not_id: str | None = None, current: list[str] | None = None) -> dict:
    check_dates(body.starts_on, body.ends_on)
    team_ids = check_teams(db, access, body.team_ids, current)
    if code_taken(db, Bundle, body.code, not_id):
        raise field_error("code", "Another bundle has this code.")
    ids = [i.product_id for i in body.items]
    if len(set(ids)) != len(ids):
        raise field_error("items", "Each product once; set its quantity instead.")
    if len(set(db.scalars(select(Product.id).where(Product.id.in_(ids))))) != len(ids):
        raise field_error("items", "Pick products from the list.")
    return {
        "code": body.code,
        "name": body.name,
        "price_centavos": body.price_centavos,
        "as_one_line": body.as_one_line,
        "items": [{"productId": i.product_id, "qty": i.qty} for i in body.items],
        "team_ids": team_ids,
        "starts_on": body.starts_on.isoformat() if body.starts_on else None,
        "ends_on": body.ends_on.isoformat() if body.ends_on else None,
        "is_active": body.is_active,
    }


@router.get("/bundles")
def list_bundles(access: View, db: DB, settings: SettingsDep) -> dict:
    on, names = today(settings.org_timezone), team_names(db)
    bundles = [b for b in db.scalars(select(Bundle).order_by(func.lower(Bundle.name))) if sees(b, access)]
    return {"items": [bundle_out(b, on, names) for b in bundles], "teams": team_options(db, access), "can": {"edit": access.can("products.edit")}}


@router.post("/bundles", status_code=status.HTTP_201_CREATED)
def create_bundle(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: BundleIn) -> dict:
    bundle = Bundle(**bundle_values(db, access, body))
    db.add(bundle)
    db.flush()
    audit(db, me, "bundle.created", target=bundle.name, target_type="bundle", target_id=bundle.id)
    db.commit()
    return bundle_out(bundle, today(settings.org_timezone), team_names(db))


@router.put("/bundles/{bundle_id}")
def replace_bundle(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, bundle_id: str, body: BundleIn) -> dict:
    bundle = reachable(db, Bundle, bundle_id, "bundle", access)
    values = bundle_values(db, access, body, bundle.id, bundle.team_ids)
    fields = [k for k, v in values.items() if getattr(bundle, k) != v]
    for k in fields:
        setattr(bundle, k, values[k])
    if fields:
        audit(db, me, "bundle.updated", target=bundle.name, target_type="bundle", target_id=bundle.id, fields=camel(fields))
        db.commit()
    return bundle_out(bundle, today(settings.org_timezone), team_names(db))


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bundle(access: Edit, me: CurrentUser, db: DB, bundle_id: str) -> Response:
    bundle = reachable(db, Bundle, bundle_id, "bundle", access)
    audit(db, me, "bundle.deleted", target=bundle.name, target_type="bundle", target_id=bundle.id)
    db.delete(bundle)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

