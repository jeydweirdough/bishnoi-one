"""Inventory: products, their prices, and promos and discounts.

Company-wide, not per division: a product has one SRP, one Patient's Price and
so on. Which of those prices a division may quote is a pricing rule (Settings
-> Pricing rules), not Inventory's call. Viewing needs Inventory "view";
adding needs "create" and changing needs "edit". Products and promos are
switched off, never deleted, so old quotes keep making sense.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query as Param, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.access import Access
from app.audit import audit
from app.config import Settings
from app.deps import DB, CurrentAccess, CurrentUser, SettingsDep
from app.errors import Loc, conflict, field_errors
from app.fields import check_values, fields as company_fields, fields_out
from app.models import (
    Bundle,
    BundleDivision,
    BundleItem,
    Division,
    PriceType,
    Product,
    ProductPrice,
    Promo,
    PromoDivision,
    PromoProduct,
    PromoTier,
    utcnow,
)
from app.price_book import bundle_out, promo_out, quoting_divisions
from app.schemas import BundleIn, BundlePatch, PricesIn, ProductIn, ProductPatch, PromoIn, PromoPatch


router = APIRouter(prefix="/inventory", tags=["inventory"])

INVENTORY = "inventory"

# Temporary, and all of it goes together. Generic name, Strength and Form are
# ordinary product fields now (migration 0016 moved their values into
# `details` under these keys), but the web app and the price list still send
# and read them by name, so what a form sends is folded into `details` and the
# three columns are kept in step behind it. What removes this: the web app
# posting and reading `details` instead, after which the columns go too.
PHARMA_KEYS = ("generic_name", "strength", "form")
# What a write may touch on a product's own fields, `details` and the three above.
DETAIL_KEYS = frozenset({"details", *PHARMA_KEYS})


def require(access: Access, action: str) -> None:
    access.require(INVENTORY, action)


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"No such {what}.")


def list_price_codes(db: Session) -> set[str]:
    """Price types that live on the price list. Entered ones (Special Price) are typed per quote."""
    return set(db.scalars(select(PriceType.code).where(PriceType.entry == "list")))


def product_out(p: Product) -> dict:
    details = dict(p.details or {})
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "details": details,
        "genericName": details.get("generic_name"),
        "strength": details.get("strength"),
        "form": details.get("form"),
        "unit": p.unit,
        "isActive": p.is_active,
        "prices": {x.price_type_code: x.amount_centavos for x in p.prices},
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
    }


def load_product(db: Session, product_id: str) -> Product:
    product = db.scalar(select(Product).where(Product.id == product_id).options(selectinload(Product.prices)))
    if product is None:
        raise not_found("product")
    return product


def check_prices(db: Session, prices: dict) -> None:
    allowed = list_price_codes(db)
    bad = [code for code in prices if code not in allowed]
    if bad:
        raise field_errors([(("prices", code), "That isn't a price-list price.") for code in bad])


def set_details(db: Session, product: Product, written: dict) -> None:
    """The product's own field values, after a create or an edit.

    `details` is the whole set, so leaving it out changes none of them; the
    three pharma names are single fields folded into it, so an old client can
    change one without sending the rest, and a null for one of those clears
    that field the way an empty form box does."""
    given = written.get("details")
    kept = dict(given) if given is not None else dict(product.details or {})
    for key in PHARMA_KEYS:
        if key in written:
            if written[key] is None:
                kept.pop(key, None)
            else:
                kept[key] = written[key]
    product.details = check_values(db, "product", kept)
    for key in PHARMA_KEYS:
        value = product.details.get(key)
        setattr(product, key, value if isinstance(value, str) else None)


def set_prices(product: Product, prices: dict[str, int | None]) -> None:
    current = {x.price_type_code: x for x in product.prices}
    for code, amount in prices.items():
        if amount is None:
            if code in current:
                product.prices.remove(current[code])
        elif code in current:
            current[code].amount_centavos = amount
        else:
            product.prices.append(ProductPrice(price_type_code=code, amount_centavos=amount))


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


# --- overview ------------------------------------------------------------------------


@router.get("/summary")
def summary(access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    require(access, "view")
    day = today(settings)
    list_codes = list_price_codes(db)
    products = db.scalars(select(Product).where(Product.is_active.is_(True)).options(selectinload(Product.prices))).all()
    running = db.scalar(
        select(func.count())
        .select_from(Promo)
        .where(Promo.is_active.is_(True), Promo.starts_on <= day, or_(Promo.ends_on.is_(None), Promo.ends_on >= day))
    )
    active_types = set(db.scalars(select(PriceType.code).where(PriceType.is_active.is_(True), PriceType.code.in_(list_codes))))
    return {
        "counts": {
            "products": len(products),
            # Active products missing one or more active list prices.
            "missingPrices": sum(1 for p in products if active_types - {x.price_type_code for x in p.prices}),
            "runningPromos": running or 0,
        }
    }


@router.get("/reference")
def reference(access: CurrentAccess, db: DB) -> dict:
    """What the Inventory forms pick from: price-list price types, the divisions
    that quote, and the company's own product fields.

    The fields are here rather than only in Settings because the product form
    needs them and the people who fill it in aren't admins."""
    require(access, "view")
    types = db.scalars(select(PriceType).where(PriceType.entry == "list").order_by(PriceType.sort_order, PriceType.name))
    divisions = db.scalars(select(Division).where(Division.code.in_(quoting_divisions(db))).order_by(Division.sort_order))
    return {
        "priceTypes": [{"code": t.code, "name": t.name, "isActive": t.is_active} for t in types],
        "divisions": [{"code": d.code, "name": d.name} for d in divisions],
        "fields": fields_out(db, "product", active_only=True),
    }


# --- products ------------------------------------------------------------------------


@router.get("/products")
def list_products(
    access: CurrentAccess,
    db: DB,
    q: Annotated[str | None, Param(max_length=80)] = None,
    state: Literal["active", "off", "all"] = "active",
) -> list[dict]:
    require(access, "view")
    query = select(Product).options(selectinload(Product.prices)).order_by(func.lower(Product.name))
    if state != "all":
        query = query.where(Product.is_active.is_(state == "active"))
    if q and q.strip():
        # A bound parameter, so it's never SQL; escaping % and _ keeps it from being a wildcard either.
        typed = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{typed}%"
        matches = [
            func.lower(Product.name).like(like, escape="\\"),
            func.lower(Product.code).like(like, escape="\\"),
            func.lower(func.coalesce(Product.generic_name, "")).like(like, escape="\\"),
        ]
        # A company's own fields are whatever it named them, so there is no
        # column to search: each one is read out of the JSON by its key, which
        # SQLite and Postgres both do. One LIKE over the whole JSON text would
        # be shorter, but it would match the field keys as well as their
        # values, so searching "_" would find every product that has any field.
        matches += [
            func.lower(func.coalesce(Product.details[f.key].as_string(), "")).like(like, escape="\\")
            for f in company_fields(db, "product")
        ]
        query = query.where(or_(*matches))
    return [product_out(p) for p in db.scalars(query)]


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductIn, access: CurrentAccess, db: DB, me: CurrentUser) -> dict:
    require(access, "create")
    check_prices(db, body.prices)
    code = body.code.upper()
    if db.scalar(select(Product).where(func.upper(Product.code) == code)):
        raise conflict("Another product already has that code.")
    product = Product(code=code, name=body.name, unit=body.unit)
    set_details(db, product, body.model_dump(include=DETAIL_KEYS, exclude_none=True))
    set_prices(product, dict(body.prices))
    db.add(product)
    db.commit()
    audit(db, me, "product.added", code)
    return product_out(load_product(db, product.id))


@router.get("/products/{product_id}")
def read_product(product_id: str, access: CurrentAccess, db: DB) -> dict:
    require(access, "view")
    return product_out(load_product(db, product_id))


@router.patch("/products/{product_id}")
def update_product(product_id: str, body: ProductPatch, access: CurrentAccess, db: DB, me: CurrentUser) -> dict:
    require(access, "edit")
    product = load_product(db, product_id)
    changes = body.model_dump(exclude_unset=True)
    if "code" in changes:
        changes["code"] = changes["code"].upper()
        taken = db.scalar(select(Product).where(func.upper(Product.code) == changes["code"], Product.id != product_id))
        if taken:
            raise conflict("Another product already has that code.")
    for key, value in changes.items():
        if key not in DETAIL_KEYS:
            setattr(product, key, value)
    if DETAIL_KEYS & changes.keys():
        set_details(db, product, changes)
    db.commit()
    audit(db, me, "product.updated", product.code, changes)
    return product_out(load_product(db, product_id))


@router.put("/products/{product_id}/prices")
def update_prices(product_id: str, body: PricesIn, access: CurrentAccess, db: DB, me: CurrentUser) -> dict:
    require(access, "edit")
    product = load_product(db, product_id)
    check_prices(db, body.prices)
    set_prices(product, body.prices)
    product.updated_at = utcnow()  # prices live in their own table; the product shows when they last changed
    db.commit()
    audit(db, me, "product.prices_changed", product.code)
    return product_out(load_product(db, product_id))


# --- promos --------------------------------------------------------------------------


def check_promo(db: Session, body: PromoIn) -> None:
    errors: list[tuple[Loc, str]] = []
    needed = {
        "percent": [("percentBp", body.percent_bp, "Enter the percent off.")],
        "amount": [("amountCentavos", body.amount_centavos, "Enter the amount off per unit.")],
        "free_goods": [
            ("buyQty", body.buy_qty, "Enter how many to buy."),
            ("freeQty", body.free_qty, "Enter how many come free."),
        ],
        "tiered": [],
    }[body.kind]
    errors += [((field,), message) for field, value, message in needed if value is None]
    if body.kind == "tiered":
        quantities = [t.min_qty for t in body.tiers]
        if not quantities:
            errors.append((("tiers",), "Add at least one tier."))
        elif len(set(quantities)) != len(quantities):
            errors.append((("tiers",), "Each tier needs its own minimum quantity."))
    if body.ends_on and body.ends_on < body.starts_on:
        errors.append((("endsOn",), "The end date is before the start date."))
    # The company's own sales divisions, not a list in the code: a division
    # added in Settings -> Teams can be given a promo the day it exists.
    if set(body.division_codes) - set(quoting_divisions(db)):
        errors.append((("divisionCodes",), "Pick divisions that quote."))
    if body.product_ids is not None:
        if not body.product_ids:
            errors.append((("productIds",), "Pick at least one product, or choose every product."))
        else:
            found = set(db.scalars(select(Product.id).where(Product.id.in_(body.product_ids))))
            if found != set(body.product_ids):
                errors.append((("productIds",), "Some of those products don't exist."))
    if errors:
        raise field_errors(errors)


def fill_promo(promo: Promo, body: PromoIn) -> None:
    promo.name = body.name
    promo.kind = body.kind
    # Only the fields the kind uses are kept, so a changed kind leaves nothing stale.
    promo.percent_bp = body.percent_bp if body.kind == "percent" else None
    promo.amount_centavos = body.amount_centavos if body.kind == "amount" else None
    promo.buy_qty = body.buy_qty if body.kind == "free_goods" else None
    promo.free_qty = body.free_qty if body.kind == "free_goods" else None
    promo.starts_on = body.starts_on
    promo.ends_on = body.ends_on
    promo.all_products = body.product_ids is None
    promo.tiers = [PromoTier(min_qty=t.min_qty, percent_bp=t.percent_bp) for t in body.tiers] if body.kind == "tiered" else []
    promo.products = [PromoProduct(product_id=pid) for pid in sorted(set(body.product_ids or []))]
    promo.divisions = [PromoDivision(division_code=code) for code in sorted(set(body.division_codes))]


def load_promo(db: Session, promo_id: str) -> Promo:
    promo = db.scalar(
        select(Promo)
        .where(Promo.id == promo_id)
        .options(selectinload(Promo.products), selectinload(Promo.divisions), selectinload(Promo.tiers))
    )
    if promo is None:
        raise not_found("promo")
    return promo


@router.get("/promos")
def list_promos(
    access: CurrentAccess, db: DB, settings: SettingsDep, state: Literal["current", "ended", "off", "all"] = "current"
) -> list[dict]:
    require(access, "view")
    day = today(settings)
    query = (
        select(Promo)
        .options(selectinload(Promo.products), selectinload(Promo.divisions), selectinload(Promo.tiers))
        .order_by(Promo.starts_on.desc(), Promo.name)
    )
    promos = [promo_out(p, day) for p in db.scalars(query)]
    wanted = {"current": ("running", "upcoming"), "ended": ("ended",), "off": ("off",)}.get(state)
    return [p for p in promos if wanted is None or p["state"] in wanted]


@router.post("/promos", status_code=status.HTTP_201_CREATED)
def create_promo(body: PromoIn, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    require(access, "create")
    check_promo(db, body)
    promo = Promo()
    fill_promo(promo, body)
    db.add(promo)
    db.commit()
    audit(db, me, "promo.added", body.name)
    return promo_out(load_promo(db, promo.id), today(settings))


@router.get("/promos/{promo_id}")
def read_promo(promo_id: str, access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    require(access, "view")
    return promo_out(load_promo(db, promo_id), today(settings))


@router.put("/promos/{promo_id}")
def replace_promo(promo_id: str, body: PromoIn, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    """Quotes copy the promo's effect when they're made, so editing a promo never changes an old quote."""
    require(access, "edit")
    promo = load_promo(db, promo_id)
    check_promo(db, body)
    fill_promo(promo, body)
    db.commit()
    audit(db, me, "promo.changed", promo_id)
    return promo_out(load_promo(db, promo_id), today(settings))


@router.patch("/promos/{promo_id}")
def switch_promo(promo_id: str, body: PromoPatch, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    require(access, "edit")
    promo = load_promo(db, promo_id)
    promo.is_active = body.is_active
    db.commit()
    audit(db, me, "promo.switched_on" if body.is_active else "promo.switched_off", promo_id)
    return promo_out(load_promo(db, promo_id), today(settings))


# --- bundles --------------------------------------------------------------------------
#
# A set of products at one price, kept here because a person looks for it beside
# promos. It is not one: a promo is picked on top of a product line, a bundle
# instead of a product, and a bundle's products carry how many of each are in the
# set. What it costs is app/bundles.py; this is only the keeping of it.


def check_bundle(db: Session, body: BundleIn, bundle_id: str | None = None) -> None:
    errors: list[tuple[Loc, str]] = []
    if body.ends_on and body.ends_on < body.starts_on:
        errors.append((("endsOn",), "The end date is before the start date."))

    taken = db.scalar(select(Bundle.id).where(func.lower(Bundle.code) == body.code.lower()))
    if taken is not None and taken != bundle_id:
        errors.append((("code",), "Another bundle already uses that code."))

    if set(body.division_codes) - set(quoting_divisions(db)):
        errors.append((("divisionCodes",), "Pick divisions that quote."))

    ids = [item.product_id for item in body.items]
    if len(set(ids)) != len(ids):
        errors.append((("items",), "Each product goes in once, with how many of it the set contains."))
    else:
        found = set(db.scalars(select(Product.id).where(Product.id.in_(ids), Product.is_active.is_(True))))
        if found != set(ids):
            errors.append((("items",), "Some of those products don't exist, or are no longer sold."))
    if errors:
        raise field_errors(errors)


def fill_bundle(bundle: Bundle, body: BundleIn) -> None:
    bundle.code = body.code
    bundle.name = body.name
    bundle.price_centavos = body.price_centavos
    bundle.as_one_line = body.as_one_line
    bundle.starts_on = body.starts_on
    bundle.ends_on = body.ends_on
    # The order they were entered in is the order the quote lists them.
    bundle.items = [BundleItem(product_id=item.product_id, qty=item.qty, sort_order=i) for i, item in enumerate(body.items)]
    bundle.divisions = [BundleDivision(division_code=code) for code in sorted(set(body.division_codes))]


def load_bundle(db: Session, bundle_id: str) -> Bundle:
    bundle = db.scalar(
        select(Bundle).where(Bundle.id == bundle_id).options(selectinload(Bundle.items), selectinload(Bundle.divisions))
    )
    if bundle is None:
        raise not_found("bundle")
    return bundle


@router.get("/bundles")
def list_bundles(
    access: CurrentAccess, db: DB, settings: SettingsDep, state: Literal["current", "ended", "off", "all"] = "current"
) -> list[dict]:
    require(access, "view")
    day = today(settings)
    query = (
        select(Bundle)
        .options(selectinload(Bundle.items), selectinload(Bundle.divisions))
        .order_by(Bundle.starts_on.desc(), Bundle.name)
    )
    bundles = [bundle_out(b, day) for b in db.scalars(query)]
    wanted = {"current": ("running", "upcoming"), "ended": ("ended",), "off": ("off",)}.get(state)
    return [b for b in bundles if wanted is None or b["state"] in wanted]


@router.post("/bundles", status_code=status.HTTP_201_CREATED)
def create_bundle(body: BundleIn, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    require(access, "create")
    check_bundle(db, body)
    bundle = Bundle()
    fill_bundle(bundle, body)
    db.add(bundle)
    db.commit()
    audit(db, me, "bundle.added", body.name)
    return bundle_out(load_bundle(db, bundle.id), today(settings))


@router.get("/bundles/{bundle_id}")
def read_bundle(bundle_id: str, access: CurrentAccess, db: DB, settings: SettingsDep) -> dict:
    require(access, "view")
    return bundle_out(load_bundle(db, bundle_id), today(settings))


@router.put("/bundles/{bundle_id}")
def replace_bundle(bundle_id: str, body: BundleIn, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    """Quotes copy what a bundle worked out to when they're made, so editing one
    never changes a quote already given."""
    require(access, "edit")
    bundle = load_bundle(db, bundle_id)
    check_bundle(db, body, bundle_id)
    fill_bundle(bundle, body)
    db.commit()
    audit(db, me, "bundle.changed", bundle_id)
    return bundle_out(load_bundle(db, bundle_id), today(settings))


@router.patch("/bundles/{bundle_id}")
def switch_bundle(bundle_id: str, body: BundlePatch, access: CurrentAccess, db: DB, settings: SettingsDep, me: CurrentUser) -> dict:
    require(access, "edit")
    bundle = load_bundle(db, bundle_id)
    bundle.is_active = body.is_active
    db.commit()
    audit(db, me, "bundle.switched_on" if body.is_active else "bundle.switched_off", bundle_id)
    return bundle_out(load_bundle(db, bundle_id), today(settings))
