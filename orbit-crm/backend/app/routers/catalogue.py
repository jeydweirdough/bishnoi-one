"""The catalogue: products and services with their prices, the price types
they're priced by, promos, bundles, guarantee-letter issuers, and the CRM's own
rules for quotes.

Reading any of it needs products.view. Adding products needs
products.create, deleting them products.delete, and everything else here
(changing products, prices, promos, bundles and the rules) products.edit.
The catalogue is the company's, so a role's scope doesn't narrow it.
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
from app.models import Bundle, Issuer, PriceType, Product, ProductPrice, Promo
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
        "isActive": p.is_active,
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
    q: str | None = Query(None, max_length=100),
    active: bool | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
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
    return {"items": [product_out(p, access) for p in products], "total": total, "missingPrices": missing}


class ProductFields(Api):
    code: str | None = Field(None, min_length=1, max_length=40)
    name: str | None = Field(None, min_length=1, max_length=160)
    generic_name: str | None = Field(None, max_length=160)
    strength: str | None = Field(None, max_length=60)
    form: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, min_length=1, max_length=30)
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
def create_product(access: Create, me: CurrentUser, db: DB, body: ProductIn) -> dict:
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
    for required in ("code", "name", "unit", "is_active"):
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
    in_bundles = [b.name for b in db.scalars(select(Bundle)) if any(i["productId"] == product.id for i in b.items)]
    if in_bundles:
        raise HTTPException(status.HTTP_409_CONFLICT, f"It's in the bundle {in_bundles[0]}. Take it out of bundles first, or switch it off instead.")
    # Quotes keep their own copy of every line, so they stay as they were.
    audit(db, me, "product.deleted", target=product.name, target_type="product", target_id=product.id)
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


def promo_out(p: Promo, on: str) -> dict:
    return promo_terms(p) | {"startsOn": p.starts_on, "endsOn": p.ends_on, "isActive": p.is_active, "state": state_of(p.is_active, p.starts_on, p.ends_on, on)}


def promo_values(db: Session, body: PromoIn) -> dict:
    check_dates(body.starts_on, body.ends_on)
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
        "starts_on": body.starts_on.isoformat() if body.starts_on else None,
        "ends_on": body.ends_on.isoformat() if body.ends_on else None,
        "is_active": body.is_active,
    }


@router.get("/promos")
def list_promos(access: View, db: DB, settings: SettingsDep) -> dict:
    on = today(settings.org_timezone)
    return {"items": [promo_out(p, on) for p in db.scalars(select(Promo).order_by(Promo.created_at.desc()))], "can": {"edit": access.can("products.edit")}}


@router.post("/promos", status_code=status.HTTP_201_CREATED)
def create_promo(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: PromoIn) -> dict:
    promo = Promo(**promo_values(db, body))
    db.add(promo)
    db.flush()
    audit(db, me, "promo.created", target=promo.name, target_type="promo", target_id=promo.id)
    db.commit()
    return promo_out(promo, today(settings.org_timezone))


@router.put("/promos/{promo_id}")
def replace_promo(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, promo_id: str, body: PromoIn) -> dict:
    promo = found(db.get(Promo, promo_id), "promo")
    values = promo_values(db, body)
    fields = [k for k, v in values.items() if getattr(promo, k) != v]
    for k in fields:
        setattr(promo, k, values[k])
    if fields:
        audit(db, me, "promo.updated", target=promo.name, target_type="promo", target_id=promo.id, fields=camel(fields))
        db.commit()
    return promo_out(promo, today(settings.org_timezone))


@router.delete("/promos/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo(access: Edit, me: CurrentUser, db: DB, promo_id: str) -> Response:
    promo = found(db.get(Promo, promo_id), "promo")
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
    starts_on: date | None = None
    ends_on: date | None = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return check_code(value)


def bundle_out(b: Bundle, on: str) -> dict:
    return {
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


def bundle_values(db: Session, body: BundleIn, not_id: str | None = None) -> dict:
    check_dates(body.starts_on, body.ends_on)
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
        "starts_on": body.starts_on.isoformat() if body.starts_on else None,
        "ends_on": body.ends_on.isoformat() if body.ends_on else None,
        "is_active": body.is_active,
    }


@router.get("/bundles")
def list_bundles(access: View, db: DB, settings: SettingsDep) -> dict:
    on = today(settings.org_timezone)
    return {"items": [bundle_out(b, on) for b in db.scalars(select(Bundle).order_by(func.lower(Bundle.name)))], "can": {"edit": access.can("products.edit")}}


@router.post("/bundles", status_code=status.HTTP_201_CREATED)
def create_bundle(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, body: BundleIn) -> dict:
    bundle = Bundle(**bundle_values(db, body))
    db.add(bundle)
    db.flush()
    audit(db, me, "bundle.created", target=bundle.name, target_type="bundle", target_id=bundle.id)
    db.commit()
    return bundle_out(bundle, today(settings.org_timezone))


@router.put("/bundles/{bundle_id}")
def replace_bundle(access: Edit, me: CurrentUser, db: DB, settings: SettingsDep, bundle_id: str, body: BundleIn) -> dict:
    bundle = found(db.get(Bundle, bundle_id), "bundle")
    values = bundle_values(db, body, bundle.id)
    fields = [k for k, v in values.items() if getattr(bundle, k) != v]
    for k in fields:
        setattr(bundle, k, values[k])
    if fields:
        audit(db, me, "bundle.updated", target=bundle.name, target_type="bundle", target_id=bundle.id, fields=camel(fields))
        db.commit()
    return bundle_out(bundle, today(settings.org_timezone))


@router.delete("/bundles/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bundle(access: Edit, me: CurrentUser, db: DB, bundle_id: str) -> Response:
    bundle = found(db.get(Bundle, bundle_id), "bundle")
    audit(db, me, "bundle.deleted", target=bundle.name, target_type="bundle", target_id=bundle.id)
    db.delete(bundle)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

