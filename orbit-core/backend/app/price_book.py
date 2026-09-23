"""The price book as kept in the database: price types, each division's
pricing rules, guarantee-letter issuers, products, prices and promos.

Loads what app/pricing.py needs, and seeds the defaults below into a new
database. The defaults are Getmeds's rules as agreed on 2026-09-18; after that
Admins change them in Settings -> Pricing rules, and seeding never
overwrites what they set.
"""

from collections import defaultdict
from dataclasses import replace
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.bundles import BundleInfo, BundleItemInfo
from app.catalogue import sales_keys
from app.models import (
    Bundle,
    BundleDivision,
    Division,
    DivisionPriceType,
    DivisionPricing,
    GuaranteeLetterIssuer,
    PriceType,
    PricingSettings,
    Product,
    Promo,
    PromoDivision,
    RetentionRule,
    TeamPrice,
    TeamPriceType,
)
from app.pricing import DivisionRules, PriceTypeInfo, ProductInfo, PromoInfo
from app.tenancy import org_get

# code, name, entry, requires notes, needs Finance approval
DEFAULT_PRICE_TYPES: list[tuple[str, str, str, bool, bool]] = [
    ("srp", "SRP", "list", False, False),
    ("patient", "Patient's Price", "list", False, False),
    ("doctor", "Doctor's Price", "list", False, False),
    ("drugstore-hospital", "Drugstore/Hospital Price", "list", False, False),
    ("distributor", "Distributor's Price", "list", False, False),
    ("special", "Special Price", "entered", True, True),
    ("government", "Government Price", "list", True, True),
]

# The divisions that quote. BID quotes with notes only. URO and B&B start with
# no price types: admins choose theirs, as do Special and Government Price.
PRICED_DIVISIONS = ("b2c", "stc", "uro", "bnb", "b2b", "hos", "bid")
DEFAULT_DIVISION_PRICE_TYPES: dict[str, dict[str, str]] = {
    "b2c": {"patient": "always", "srp": "always", "doctor": "with_rx"},
    "hos": {"drugstore-hospital": "always", "patient": "always", "doctor": "always", "srp": "always"},
    "stc": {"patient": "always", "doctor": "always", "srp": "always"},
    "b2b": {"srp": "always", "distributor": "always"},
}
NOTES_ONLY = frozenset({"bid"})
NO_GUARANTEE_LETTERS = frozenset({"b2b"})
DEFAULT_DISCOUNT_APPROVAL_BP = 1000  # manual discounts over 10% need Finance
DEFAULT_ISSUERS = [("dswd", "DSWD"), ("pcso", "PCSO")]


def seed_price_book(db: Session) -> None:
    """Adds what's missing. A division gets default price types only the first
    time it is seen, so a price type an admin switched off stays off."""
    for order, (code, name, entry, notes, approval) in enumerate(DEFAULT_PRICE_TYPES):
        if org_get(db, PriceType, code) is None:
            db.add(PriceType(code=code, name=name, entry=entry, requires_notes=notes, needs_approval=approval, sort_order=order))
    for order, (code, name) in enumerate(DEFAULT_ISSUERS):
        if org_get(db, GuaranteeLetterIssuer, code) is None:
            db.add(GuaranteeLetterIssuer(code=code, name=name, sort_order=order))
    db.flush()
    for division in PRICED_DIVISIONS:
        if org_get(db, Division, division) is None or org_get(db, DivisionPricing, division) is not None:
            continue
        db.add(
            DivisionPricing(
                division_code=division,
                uses_price_list=division not in NOTES_ONLY,
                allows_guarantee_letters=division not in NO_GUARANTEE_LETTERS,
                discount_approval_bp=DEFAULT_DISCOUNT_APPROVAL_BP,
                price_types=[
                    DivisionPriceType(price_type_code=code, rule=rule)
                    for code, rule in DEFAULT_DIVISION_PRICE_TYPES.get(division, {}).items()
                ],
            )
        )
    db.flush()


# --- loading -----------------------------------------------------------------------


def price_type_info(t: PriceType) -> PriceTypeInfo:
    return PriceTypeInfo(t.code, t.name, t.entry, t.requires_notes, t.needs_approval)


def load_price_types(db: Session, active_only: bool = True) -> dict[str, PriceTypeInfo]:
    query = select(PriceType).order_by(PriceType.sort_order, PriceType.name)
    if active_only:
        query = query.where(PriceType.is_active.is_(True))
    return {t.code: price_type_info(t) for t in db.scalars(query)}


def team_price_types(db: Session, division: str, team: str) -> set[str]:
    """The price types this team picked for itself. Empty means it hasn't, and
    follows its division."""
    return set(
        db.scalars(
            select(TeamPriceType.price_type_code).where(
                TeamPriceType.division_code == division, TeamPriceType.subdivision_code == team
            )
        )
    )


def load_rules(db: Session, division: str, team: str | None = None) -> DivisionRules:
    """A division with no rules row quotes nothing: no price types at all.

    A team's lead may narrow the division's price types to the ones their team
    actually uses (Prices, inside the module). They can only take types away,
    never add one the company hasn't set the division up for, so a rule like
    "Doctor's Price only with a prescription" holds wherever it is quoted."""
    row = db.scalar(
        select(DivisionPricing).where(DivisionPricing.division_code == division).options(selectinload(DivisionPricing.price_types))
    )
    active = set(load_price_types(db))
    if row is None:
        return DivisionRules(division, True, False, DEFAULT_DISCOUNT_APPROVAL_BP, {})
    types = {p.price_type_code: p.rule for p in row.price_types if p.price_type_code in active}
    if team:
        theirs = team_price_types(db, division, team)
        if theirs:
            types = {code: rule for code, rule in types.items() if code in theirs}
    return DivisionRules(
        division=division,
        uses_price_list=row.uses_price_list,
        allows_guarantee_letters=row.allows_guarantee_letters,
        discount_approval_bp=row.discount_approval_bp,
        price_types=types,
    )


def start_selling(db: Session, division: str) -> None:
    """Everything a new sales division needs before its first quote: pricing
    rules, a retention window and goal targets. Deliberately empty of price
    types — an admin chooses those in Settings -> Pricing, because which prices
    a division may quote is a decision, not a default."""
    from app.retention import DEFAULT_AT_RISK_DAYS, DEFAULT_LOST_DAYS

    if org_get(db, DivisionPricing, division) is None:
        db.add(DivisionPricing(division_code=division, discount_approval_bp=DEFAULT_DISCOUNT_APPROVAL_BP))
    if org_get(db, RetentionRule, division) is None:
        db.add(RetentionRule(division_code=division, at_risk_days=DEFAULT_AT_RISK_DAYS, lost_days=DEFAULT_LOST_DAYS))
    db.flush()


def load_issuers(db: Session, active_only: bool = True) -> dict[str, str]:
    query = select(GuaranteeLetterIssuer).order_by(GuaranteeLetterIssuer.sort_order, GuaranteeLetterIssuer.name)
    if active_only:
        query = query.where(GuaranteeLetterIssuer.is_active.is_(True))
    return {i.code: i.name for i in db.scalars(query)}


def product_info(p: Product) -> ProductInfo:
    return ProductInfo(p.id, p.code, p.name, p.unit, p.is_active, {x.price_type_code: x.amount_centavos for x in p.prices})


def load_team_prices(db: Session, division: str, team: str, ids: set[str] | None = None) -> dict[tuple[str, str], int]:
    """(product id, price type) -> the amount this team set. Sparse: only what
    its lead actually typed in."""
    query = select(TeamPrice).where(TeamPrice.division_code == division, TeamPrice.subdivision_code == team)
    if ids is not None:
        query = query.where(TeamPrice.product_id.in_(ids))
    return {(row.product_id, row.price_type_code): row.amount_centavos for row in db.scalars(query)}


def load_products(
    db: Session, ids: set[str] | None = None, active_only: bool = False, division: str | None = None, team: str | None = None
) -> dict[str, ProductInfo]:
    """The catalogue as one team sees it: the company's prices, with that team's
    own over the top wherever its lead set one."""
    query = select(Product).options(selectinload(Product.prices)).order_by(Product.name)
    if ids is not None:
        query = query.where(Product.id.in_(ids))
    if active_only:
        query = query.where(Product.is_active.is_(True))
    products = {p.id: product_info(p) for p in db.scalars(query)}
    if not (division and team):
        return products
    over: dict[str, dict[str, int]] = defaultdict(dict)
    for (product_id, price_type), amount in load_team_prices(db, division, team, ids).items():
        over[product_id][price_type] = amount
    return {
        id_: replace(product, prices={**product.prices, **over[id_]}) if id_ in over else product
        for id_, product in products.items()
    }


def promo_info(p: Promo) -> PromoInfo:
    return PromoInfo(
        id=p.id,
        name=p.name,
        kind=p.kind,
        percent_bp=p.percent_bp,
        amount_centavos=p.amount_centavos,
        buy_qty=p.buy_qty,
        free_qty=p.free_qty,
        tiers=tuple((t.min_qty, t.percent_bp) for t in p.tiers),
        product_ids=None if p.all_products else frozenset(x.product_id for x in p.products),
    )


def load_promos(db: Session, division: str, day: date) -> dict[str, PromoInfo]:
    """Promos a rep in this division can use today."""
    query = (
        select(Promo)
        .join(PromoDivision, PromoDivision.promo_id == Promo.id)
        .where(
            PromoDivision.division_code == division,
            Promo.is_active.is_(True),
            Promo.starts_on <= day,
            or_(Promo.ends_on.is_(None), Promo.ends_on >= day),
        )
        .options(selectinload(Promo.products), selectinload(Promo.tiers))
        .order_by(Promo.name)
    )
    return {p.id: promo_info(p) for p in db.scalars(query)}


def bundle_info(b: Bundle) -> BundleInfo:
    return BundleInfo(
        id=b.id,
        code=b.code,
        name=b.name,
        price_centavos=b.price_centavos,
        as_one_line=b.as_one_line,
        items=tuple(BundleItemInfo(x.product_id, x.qty) for x in b.items),
    )


def load_bundles(db: Session, division: str, day: date) -> dict[str, BundleInfo]:
    """Bundles a rep in this division can quote today. Same shape as promos:
    on, started, not ended, and offered to this division."""
    query = (
        select(Bundle)
        .join(BundleDivision, BundleDivision.bundle_id == Bundle.id)
        .where(
            BundleDivision.division_code == division,
            Bundle.is_active.is_(True),
            Bundle.starts_on <= day,
            or_(Bundle.ends_on.is_(None), Bundle.ends_on >= day),
        )
        .options(selectinload(Bundle.items))
        .order_by(Bundle.name)
    )
    return {b.id: bundle_info(b) for b in db.scalars(query)}


def quoting_divisions(db: Session) -> tuple[str, ...]:
    """The divisions that can be given prices, in the company's own order.

    Its sales divisions, including any added in Settings -> Teams, plus any
    other division that already has a pricing row: BID bids rather than selling
    from a price list, but which prices it may use is still its own to set, and
    a list in the code could never know that.
    """
    sales = set(sales_keys(db))
    priced = set(db.scalars(select(DivisionPricing.division_code)))
    wanted = sales | priced
    return tuple(d.code for d in db.scalars(select(Division).order_by(Division.sort_order)) if d.code in wanted)


def bundles_start_as_one_line(db: Session) -> bool:
    """Which way a newly added bundle starts. A company that has never opened
    Settings -> Pricing gets one line, which is how most sets are sold."""
    row = org_get(db, PricingSettings)
    return True if row is None else row.bundles_as_one_line


# --- shaping -----------------------------------------------------------------------


def price_type_out(t: PriceType) -> dict:
    return {
        "code": t.code,
        "name": t.name,
        "entry": t.entry,
        "requiresNotes": t.requires_notes,
        "needsApproval": t.needs_approval,
        "isActive": t.is_active,
    }


def promo_out(p: Promo, day: date | None = None) -> dict:
    state = "off"
    if p.is_active and day is not None:
        state = "upcoming" if p.starts_on > day else "ended" if p.ends_on and p.ends_on < day else "running"
    return {
        "id": p.id,
        "name": p.name,
        "kind": p.kind,
        "percentBp": p.percent_bp,
        "amountCentavos": p.amount_centavos,
        "buyQty": p.buy_qty,
        "freeQty": p.free_qty,
        "tiers": [{"minQty": t.min_qty, "percentBp": t.percent_bp} for t in p.tiers],
        "startsOn": p.starts_on.isoformat(),
        "endsOn": p.ends_on.isoformat() if p.ends_on else None,
        "productIds": None if p.all_products else sorted(x.product_id for x in p.products),
        "divisionCodes": sorted(x.division_code for x in p.divisions),
        "isActive": p.is_active,
        "state": state,
    }


def bundle_out(b: Bundle, day: date | None = None) -> dict:
    state = "off"
    if b.is_active and day is not None:
        state = "upcoming" if b.starts_on > day else "ended" if b.ends_on and b.ends_on < day else "running"
    return {
        "id": b.id,
        "code": b.code,
        "name": b.name,
        "priceCentavos": b.price_centavos,
        "asOneLine": b.as_one_line,
        "items": [{"productId": x.product_id, "qty": x.qty} for x in b.items],
        "startsOn": b.starts_on.isoformat(),
        "endsOn": b.ends_on.isoformat() if b.ends_on else None,
        "divisionCodes": sorted(x.division_code for x in b.divisions),
        "isActive": b.is_active,
        "state": state,
    }
