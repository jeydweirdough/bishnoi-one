"""Pricing a quote: what a team may quote with, and what a set of lines comes to.

The screens show a live total while the rep types, but it is always this that
decides: the preview and the saved quote are priced by the same code, so the
two never disagree. The order a line is priced in is the admin's, from the
price rules (app/conditions.py); tax comes from Finance (app/finance.py).

Money is whole centavos; percentages are basis points (1250 = 12.5%).
"""

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conditions import Conditions, load as load_conditions, procedure_of, volume_bp
from app.models import Bundle, Issuer, PriceGroup, PriceType, Product, Promo, SalesSettings, TeamPrice, TeamPriceType

FULL = 10_000  # 100%, in basis points


def today(timezone: str) -> str:
    """The date where the company is, as YYYY-MM-DD."""
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def running(starts_on: str | None, ends_on: str | None, on: str) -> bool:
    return (starts_on is None or starts_on <= on) and (ends_on is None or on <= ends_on)


def state_of(is_active: bool, starts_on: str | None, ends_on: str | None, on: str) -> str:
    if not is_active:
        return "off"
    if starts_on and on < starts_on:
        return "upcoming"
    if ends_on and ends_on < on:
        return "ended"
    return "running"


def letterhead(settings, s: SalesSettings) -> dict:
    """The company's address, TIN and phone for quotes: the Admin Console's Company profile when connected
    to Bishnoi One (settings.org_letterhead), else what this CRM keeps (Settings, Company and quotes)."""
    if settings.org_letterhead is not None:
        return settings.org_letterhead
    return {"address": s.company_address, "tin": s.company_tin, "contact": s.company_contact}


def sales_settings(db: Session) -> SalesSettings:
    found = db.get(SalesSettings, 1)
    if found is None:  # made by the migration; this is only a safety net
        found = SalesSettings(id=1)
        db.add(found)
        db.flush()
    return found


def share(amount: int, bp: int) -> int:
    """bp of amount, rounded half up."""
    return (amount * bp + FULL // 2) // FULL


@dataclass
class PriceBook:
    """Everything one team may quote with today."""

    settings: SalesSettings
    price_types: list[PriceType]
    products: dict[str, Product]
    # product id -> price type code -> centavos, the team's own over the company's
    prices: dict[str, dict[str, int]]
    promos: dict[str, Promo]
    bundles: dict[str, Bundle]
    issuers: list = field(default_factory=list)
    # product id -> price type code -> where that price came from (a PRICE_SOURCES key)
    sources: dict[str, dict[str, str]] = field(default_factory=dict)
    conditions: Conditions = field(default_factory=Conditions)
    procedure: dict = field(default_factory=dict)
    # The customer's price group, and its name for the screens.
    group: str | None = None
    group_name: str | None = None
    approved_srp: dict[str, bool] = field(default_factory=dict)

    def price_type(self, code: str) -> PriceType | None:
        return next((t for t in self.price_types if t.code == code), None)

    def has_approved_srp(self, product_id: str) -> bool:
        return self.approved_srp.get(product_id, False)


def team_price_types(db: Session, team_id: str | None) -> list[PriceType]:
    """The active price types, narrowed to the team's choice if it made one."""
    types = list(db.scalars(select(PriceType).where(PriceType.is_active).order_by(PriceType.sort_order, PriceType.name)))
    if team_id:
        chosen = set(db.scalars(select(TeamPriceType.price_type_code).where(TeamPriceType.team_id == team_id)))
        if chosen:
            types = [t for t in types if t.code in chosen]
    return types


def price_book(db: Session, team_id: str | None, on: str, group: str | None = None) -> PriceBook:
    """Everything a quote for this team's customer, in this price group, may
    use today. Each product's price at each price type is the first the
    procedure's price sources have (app/conditions.py)."""
    settings = sales_settings(db)
    procedure = procedure_of(settings)
    conditions = load_conditions(db, on)
    types = team_price_types(db, team_id)
    listed = {t.code for t in types if t.entry == "list"}
    products = {p.id: p for p in db.scalars(select(Product).where(Product.is_active).order_by(Product.name))}
    by_source: dict[str, dict[str, dict[str, int]]] = {
        "list_price": {
            p.id: {
                pp.price_type_code: pp.amount_centavos
                for pp in p.prices
                if pp.price_type_code in listed and pp.approval_status == "approved" and pp.amount_centavos > 0
            }
            for p in products.values()
        },
        "team_price": {p: {} for p in products},
        "group_price": {p: {} for p in products},
    }
    if team_id:
        for own in db.scalars(select(TeamPrice).where(TeamPrice.team_id == team_id)):
            if own.product_id in products and own.price_type_code in listed and own.approval_status == "approved" and own.amount_centavos > 0:
                by_source["team_price"][own.product_id][own.price_type_code] = own.amount_centavos
    if group:
        for product_id in products:
            for code in listed:
                c = conditions.group_price(product_id, group, code)
                if c is not None and c.amount_centavos is not None:
                    by_source["group_price"][product_id][code] = c.amount_centavos
    prices: dict[str, dict[str, int]] = {p: {} for p in products}
    sources: dict[str, dict[str, str]] = {p: {} for p in products}
    for product_id in products:
        for code in listed:
            for source in procedure["price"]:
                amount = by_source[source][product_id].get(code)
                if amount is not None:
                    prices[product_id][code], sources[product_id][code] = amount, source
                    break

    approved_srp = {
        p.id: any(
            pp.price_type_code == "SRP" and pp.approval_status == "approved" and pp.amount_centavos > 0
            for pp in p.prices
        )
        for p in products.values()
    }

    promos = {
        p.id: p
        for p in db.scalars(select(Promo).where(Promo.is_active).order_by(Promo.name))
        # Per division: only the quote's own team's, and none for a quote with no team.
        if running(p.starts_on, p.ends_on, on) and team_id in (p.team_ids or [])
    }
    bundles = {
        b.id: b
        for b in db.scalars(select(Bundle).where(Bundle.is_active).order_by(Bundle.name))
        if running(b.starts_on, b.ends_on, on) and team_id in (b.team_ids or []) and all(i["productId"] in products for i in b.items)
    }
    issuers = list(db.scalars(select(Issuer).where(Issuer.is_active).order_by(Issuer.name)))
    group_row = db.get(PriceGroup, group) if group else None
    return PriceBook(
        settings, types, products, prices, promos, bundles, issuers,
        sources=sources, conditions=conditions, procedure=procedure,
        group=group if group_row else None, group_name=group_row.name if group_row else None,
        approved_srp=approved_srp,
    )


def promo_terms(p: Promo) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "kind": p.kind,
        "percentBp": p.percent_bp,
        "amountCentavos": p.amount_centavos,
        "buyQty": p.buy_qty,
        "freeQty": p.free_qty,
        "tiers": p.tiers or [],
        "productIds": p.product_ids,
        # Its last day, for the tag's "ends in 3 days". None: no end set.
        "endsOn": p.ends_on,
    }


def price_list_out(book: PriceBook) -> dict:
    return {
        "procedure": book.procedure,
        "priceGroup": {"code": book.group, "name": book.group_name} if book.group else None,
        "usesPriceList": bool(book.price_types),
        "allowsGuaranteeLetters": book.settings.allows_guarantee_letters,
        "discountApprovalBp": book.settings.discount_approval_bp,
        "priceTypes": [
            {"code": t.code, "name": t.name, "entry": t.entry, "rule": t.rule, "requiresNotes": t.requires_notes, "needsApproval": t.needs_approval}
            for t in book.price_types
        ],
        "issuers": [{"code": i.code, "name": i.name} for i in book.issuers] if book.settings.allows_guarantee_letters else [],
        "products": [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "genericName": p.generic_name,
                "strength": p.strength,
                "form": p.form,
                "unit": p.unit,
                "hasApprovedSrp": book.has_approved_srp(p.id),
                "prices": book.prices[p.id],
                # Where each price comes from: "group_price", "team_price" or "list_price".
                "priceSources": book.sources.get(p.id, {}),
            }
            for p in book.products.values()
        ],
        "promos": [promo_terms(p) for p in book.promos.values()] if "promo" in book.procedure.get("adjust", []) else [],
        "bundles": [
            {"id": b.id, "code": b.code, "name": b.name, "priceCentavos": b.price_centavos, "asOneLine": b.as_one_line, "items": b.items, "endsOn": b.ends_on}
            for b in book.bundles.values()
        ],
    }


# --- pricing the lines -------------------------------------------------------------------


class Problems:
    """Field errors gathered while pricing, sent back all at once."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, loc: list, message: str) -> None:
        self.items.append({"type": "value_error", "loc": ["body", *loc], "msg": message})

    def raise_if_any(self) -> None:
        if self.items:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, self.items)


def promo_off(promo: Promo, quantity: int, gross: int) -> tuple[int, int]:
    """(discount, free units) a promo gives a line."""
    if promo.kind == "percent":
        return share(gross, promo.percent_bp or 0), 0
    if promo.kind == "amount":
        return min(gross, (promo.amount_centavos or 0) * quantity), 0
    if promo.kind == "free_goods":
        buy, free = promo.buy_qty or 0, promo.free_qty or 0
        return 0, (quantity // buy) * free if buy > 0 else 0
    # tiered: the best tier the quantity reaches
    reached = [t["percentBp"] for t in promo.tiers or [] if quantity >= t["minQty"]]
    return (share(gross, max(reached)) if reached else 0), 0


def blank_line() -> dict:
    return {
        "productId": "",
        "productCode": "",
        "productName": "",
        "unit": "",
        "quantity": 0,
        "freeQuantity": 0,
        "unitPriceCentavos": 0,
        "grossCentavos": 0,
        "promoId": None,
        "promoName": None,
        "promoDiscountCentavos": 0,
        "discountKind": None,
        "discountValue": None,
        "discountCentavos": 0,
        "volumeDiscountCentavos": 0,
        "surchargeCentavos": 0,
        "priceSource": None,
        "totalCentavos": 0,
        "bundleId": None,
        "bundleName": None,
        "contents": "",
    }


def price_lines(book: PriceBook, price_type_code: str, rx: bool, lines: list[dict]) -> dict:
    """Prices the lines, or raises the field errors that stop it.

    A line is {productId, quantity, unitPriceCentavos, promoId, discount} or
    {bundleId, quantity}."""
    problems = Problems()
    kind = book.price_type(price_type_code)
    if kind is None:
        problems.add(["priceType"], "Pick one of the prices offered.")
        problems.raise_if_any()
    with_rx = [t for t in book.price_types if t.rule == "with_rx"]
    if kind.rule == "with_rx" and not rx:
        problems.add(["priceType"], f"{kind.name} is only for quotes with a prescription.")
    elif rx and with_rx and kind.rule != "with_rx":
        problems.add(["priceType"], f"With a prescription, quote at {' or '.join(t.name for t in with_rx)}.")
    if not lines:
        problems.add(["lines"], "Add at least one product.")
    entered = kind.entry == "entered"
    limit = book.settings.discount_approval_bp
    over_limit = False
    under_margin = False
    MARGIN_FLOOR_BP = 4800  # 48% Gross Margin floor per sales playbook
    out: list[dict] = []

    for i, raw in enumerate(lines):
        quantity = raw.get("quantity") or 0
        if raw.get("bundleId"):
            bundle = book.bundles.get(raw["bundleId"])
            if bundle is None:
                problems.add(["lines", i, "bundleId"], "That bundle isn't on offer.")
                continue
            if entered:
                problems.add(["lines", i, "bundleId"], f"Bundles can't be quoted at {kind.name}.")
                continue
            items = []
            for item in bundle.items:
                unit = book.prices[item["productId"]].get(kind.code)
                if unit is None:
                    break
                items.append((book.products[item["productId"]], item["qty"], unit))
            if len(items) != len(bundle.items):
                problems.add(["lines", i, "bundleId"], f"Something in this bundle has no {kind.name}.")
                continue
            total = bundle.price_centavos * quantity
            gross = sum(unit * qty * quantity for _, qty, unit in items)
            if bundle.as_one_line:
                list_value = max(gross, total)
                out.append(
                    blank_line()
                    | {
                        "productCode": bundle.code,
                        "productName": bundle.name,
                        "unit": "set",
                        "quantity": quantity,
                        "unitPriceCentavos": bundle.price_centavos,
                        "grossCentavos": list_value,
                        "promoDiscountCentavos": list_value - total,
                        "totalCentavos": total,
                        "bundleId": bundle.id,
                        "bundleName": bundle.name,
                        "contents": ", ".join(f"{qty} × {p.name}" for p, qty, _ in items),
                    }
                )
            else:
                # Each item takes its share of the set price by its list value; the last takes what's left.
                left = total
                for n, (product, qty, unit) in enumerate(items):
                    item_gross = unit * qty * quantity
                    part = left if n == len(items) - 1 else (total * item_gross // gross if gross else 0)
                    left -= part
                    item_list = max(item_gross, part)
                    out.append(
                        blank_line()
                        | {
                            "productId": product.id,
                            "productCode": product.code,
                            "productName": product.name,
                            "unit": product.unit,
                            "quantity": qty * quantity,
                            "unitPriceCentavos": unit,
                            "grossCentavos": item_list,
                            "promoDiscountCentavos": item_list - part,
                            "totalCentavos": part,
                            "bundleId": bundle.id,
                            "bundleName": bundle.name,
                        }
                    )
            continue

        product = book.products.get(raw.get("productId") or "")
        if product is None:
            problems.add(["lines", i, "productId"], "Pick a product from the list.")
            continue
        if not book.has_approved_srp(product.id):
            problems.add(["lines", i, "productId"], f"{product.name} cannot be quoted: its SRP has not been curated and approved by Finance.")
            continue
        if entered:
            unit = raw.get("unitPriceCentavos")
            if not unit or unit < 1:
                problems.add(["lines", i, "unitPriceCentavos"], "Enter an amount like 1,250.00.")
                continue
        else:
            unit = book.prices[product.id].get(kind.code)
            if unit is None:
                problems.add(["lines", i, "productId"], f"{product.name} has no approved {kind.name}.")
                continue
        gross = unit * quantity
        line = blank_line() | {
            "productId": product.id,
            "productCode": product.code,
            "productName": product.name,
            "unit": product.unit,
            "quantity": quantity,
            "unitPriceCentavos": unit,
            "grossCentavos": gross,
            "priceSource": "entered" if entered else book.sources.get(product.id, {}).get(kind.code, "list_price"),
        }
        steps = book.procedure.get("adjust", [])
        promo_id, discount = raw.get("promoId"), raw.get("discount")
        if promo_id and "promo" not in steps:
            problems.add(["lines", i, "promoId"], "Promos are switched off in the price rules.")
            continue
        if discount and "manual" not in steps:
            problems.add(["lines", i, "discount"], "Reps' own discounts are switched off in the price rules.")
            continue
        amount = gross
        broken = False
        # The adjustments, in the admin's order, each on what the line comes to so far.
        for step in steps:
            if step == "volume":
                c = book.conditions.volume(product.id, book.group)
                bp = volume_bp(c, quantity) if c else 0
                if bp:
                    line["volumeDiscountCentavos"] = share(amount, bp)
                    line["volumeName"] = c.name
                    amount -= line["volumeDiscountCentavos"]
            elif step == "promo" and promo_id:
                promo = book.promos.get(promo_id)
                if promo is None or (promo.product_ids is not None and product.id not in promo.product_ids):
                    problems.add(["lines", i, "promoId"], "That promo doesn't apply to this product now.")
                    broken = True
                    break
                off, free = promo_off(promo, quantity, amount)
                off = min(off, amount)
                line |= {"promoId": promo.id, "promoName": promo.name, "promoDiscountCentavos": off, "freeQuantity": free}
                amount -= off
            elif step == "manual" and discount:
                value = discount["value"]
                if discount["kind"] == "percent":
                    if not 0 < value <= FULL:
                        problems.add(["lines", i, "discount"], "A percent from 0.01 to 100.")
                        broken = True
                        break
                    off = share(amount, value)
                    over_limit |= value > limit
                else:
                    if not 0 < value <= amount:
                        problems.add(["lines", i, "discount"], "More than the line comes to.")
                        broken = True
                        break
                    off = value
                    over_limit |= amount > 0 and value * FULL > limit * amount
                line |= {"discountKind": discount["kind"], "discountValue": value, "discountCentavos": off}
                amount -= off
            elif step == "surcharge":
                c = book.conditions.surcharge(product.id, book.group)
                if c:
                    added = (c.amount_centavos or 0) * quantity if c.amount_centavos is not None else share(amount, c.percent_bp or 0)
                    if added:
                        line["surchargeCentavos"] = added
                        line["surchargeName"] = c.name
                        amount += added
        if broken:
            continue
        line["totalCentavos"] = amount
        # 48% Gross Margin floor check (Playbook guardrail)
        cost_unit = product.extra.get("cost_centavos") if product.extra else None
        if cost_unit is not None and cost_unit > 0 and amount > 0:
            if (amount - cost_unit * quantity) * FULL < MARGIN_FLOOR_BP * amount:
                under_margin = True
        elif entered:
            srp = book.prices.get(product.id, {}).get("SRP") or book.prices.get(product.id, {}).get("TRADE")
            if srp and srp > 0 and unit < share(srp, FULL - MARGIN_FLOOR_BP):
                under_margin = True
        if discount:
            if discount["kind"] == "percent" and discount["value"] > MARGIN_FLOOR_BP:
                under_margin = True
            elif discount["kind"] == "amount" and gross > 0 and discount["value"] * FULL > MARGIN_FLOOR_BP * gross:
                under_margin = True
        out.append(line)

    problems.raise_if_any()
    reasons = (
        (["price"] if kind.needs_approval or entered else [])
        + (["discount"] if over_limit else [])
        + (["margin"] if under_margin else [])
    )
    return {
        "priceType": kind.code,
        "priceTypeName": kind.name,
        "lines": out,
        "grossCentavos": sum(x["grossCentavos"] for x in out),
        "promoDiscountCentavos": sum(x["promoDiscountCentavos"] for x in out),
        "discountCentavos": sum(x["discountCentavos"] for x in out),
        "volumeDiscountCentavos": sum(x["volumeDiscountCentavos"] for x in out),
        "surchargeCentavos": sum(x["surchargeCentavos"] for x in out),
        "totalCentavos": sum(x["totalCentavos"] for x in out),
        "approvalReasons": reasons,
        "priceGroup": {"code": book.group, "name": book.group_name} if book.group else None,
    }
