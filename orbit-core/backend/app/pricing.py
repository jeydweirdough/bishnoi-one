"""Prices a quote and checks it against the division's pricing rules.

Pure: no database and no I/O, so every rule can be tested on its own. The
price book (app/price_book.py) loads what this needs; the routers turn a
PricingError into field errors.

The rules, as configured per division in Settings -> Pricing rules:
- a quote uses one price type, and only one the division is allowed;
- a price type marked "with Rx" is only for quotes with a prescription, and a
  quote with a prescription must use it (B2C: Doctor's Price);
- some price types need notes (Special, Government) and some need Finance's
  approval;
- a guarantee-letter payer (DSWD, PCSO...) is only for divisions that take
  guarantee letters, and needs the letter's details;
- manual discounts above the division's limit need Finance's approval.

Amounts are whole centavos. Percentages are basis points (1250 = 12.5%).
Everything rounds half up to the centavo, per line.
"""

from dataclasses import dataclass

from app.bundles import BundleError, BundleInfo, contents, share_price
from app.schemas import QuoteIn

BP = 10_000  # basis points in 100%
SELF = "self"  # payer: the customer pays; no guarantee letter


def share(amount: int, bp: int) -> int:
    """`bp` basis points of `amount`, rounded half up to the centavo."""
    return (amount * bp + BP // 2) // BP


@dataclass(frozen=True)
class PriceTypeInfo:
    code: str
    name: str
    entry: str  # "list": from the price list; "entered": typed on the quote
    requires_notes: bool
    needs_approval: bool


@dataclass(frozen=True)
class DivisionRules:
    division: str
    uses_price_list: bool
    allows_guarantee_letters: bool
    discount_approval_bp: int
    # active price type code -> "always" | "with_rx"
    price_types: dict[str, str]


@dataclass(frozen=True)
class ProductInfo:
    id: str
    code: str
    name: str
    unit: str
    is_active: bool
    prices: dict[str, int]  # price type code -> centavos


@dataclass(frozen=True)
class PromoInfo:
    id: str
    name: str
    kind: str  # percent | amount | free_goods | tiered
    percent_bp: int | None = None
    amount_centavos: int | None = None
    buy_qty: int | None = None
    free_qty: int | None = None
    tiers: tuple[tuple[int, int], ...] = ()  # (min quantity, basis points), ascending
    product_ids: frozenset[str] | None = None  # None: every product

    def covers(self, product_id: str) -> bool:
        return self.product_ids is None or product_id in self.product_ids

    def apply(self, quantity: int, gross: int) -> tuple[int, int]:
        """(centavos off, free units) for a line. Raises ValueError, worded for
        the rep, when the quantity doesn't qualify."""
        if self.kind == "percent":
            return share(gross, self.percent_bp or 0), 0
        if self.kind == "amount":
            return min(gross, (self.amount_centavos or 0) * quantity), 0
        if self.kind == "free_goods":
            buy, free = self.buy_qty or 1, self.free_qty or 0
            if quantity < buy:
                raise ValueError(f"Order at least {buy} for this promo.")
            return 0, (quantity // buy) * free
        if self.kind == "tiered":
            reached = [bp for min_qty, bp in self.tiers if quantity >= min_qty]
            if not reached:
                raise ValueError(f"Order at least {self.tiers[0][0]} for this promo." if self.tiers else "This promo has no tiers.")
            return share(gross, reached[-1]), 0
        raise ValueError("This promo can't be used.")


@dataclass(frozen=True)
class PricedLine:
    product_id: str
    product_code: str
    product_name: str
    unit: str
    quantity: int
    free_quantity: int
    unit_price: int
    gross: int
    promo_id: str | None
    promo_name: str | None
    promo_discount: int
    discount_kind: str | None
    discount_value: int | None
    discount: int
    total: int
    # Set when the line came from a bundle. On a one-line bundle `product_id` is
    # empty and `contents` names what is in the set; on an itemised one each
    # line is an ordinary product line that remembers where it came from.
    bundle_id: str | None = None
    bundle_name: str | None = None
    contents: str = ""


@dataclass(frozen=True)
class PricedQuote:
    price_type: PriceTypeInfo
    lines: tuple[PricedLine, ...]
    gross: int
    promo_discount: int
    discount: int
    total: int
    # Why Finance must approve it: "price" (the price type needs approval),
    # "discount" (manual discounts over the division's limit). Empty: no approval.
    approval_reasons: tuple[str, ...]


class PricingError(Exception):
    def __init__(self, errors: list[tuple[tuple[str | int, ...], str]]) -> None:
        super().__init__("; ".join(message for _, message in errors))
        self.errors = errors


def bundle_lines(
    bundle: BundleInfo,
    sets: int,
    products: dict[str, ProductInfo],
    price_type: PriceTypeInfo,
) -> list[PricedLine]:
    """A bundle on the quote, as the lines the customer will read.

    One line if that's how the bundle is set up, otherwise one per product with
    the set price shared across them. Both add up to the same total, and neither
    takes a promo or a manual discount: the set price is the price.

    Raises BundleError, worded for the rep, if the set can't be priced at all.
    """
    if bundle.as_one_line:
        # Priced whole, so it needs no per-item prices: what the set costs is
        # what the company decided, not something worked out from its parts. Its
        # contents still travel on the line, for the picking list and the print.
        for item in bundle.items:
            product = products.get(item.product_id)
            if product is None or not product.is_active:
                raise BundleError(f"{bundle.name} contains a product that is no longer sold.")
        if not bundle.items:
            raise BundleError(f"{bundle.name} has no products in it yet.")
        total = bundle.price_centavos * sets
        return [
            PricedLine(
                product_id="",
                product_code=bundle.code,
                product_name=bundle.name,
                unit="set",
                quantity=sets,
                free_quantity=0,
                unit_price=bundle.price_centavos,
                gross=total,
                promo_id=None,
                promo_name=None,
                promo_discount=0,
                discount_kind=None,
                discount_value=None,
                discount=0,
                total=total,
                bundle_id=bundle.id,
                bundle_name=bundle.name,
                contents=contents(bundle, products),
            )
        ]

    shared = share_price(bundle, sets, products, price_type.code, price_type.name)
    lines = []
    for product_id, units, amount in shared:
        product = products[product_id]  # share_price has already checked every one
        lines.append(
            PricedLine(
                product_id=product.id,
                product_code=product.code,
                product_name=product.name,
                unit=product.unit,
                quantity=units,
                free_quantity=0,
                # What this line works out to per unit, so the quote's arithmetic
                # reads straight down the page. Rounding lives in the line total.
                unit_price=amount // units if units else amount,
                gross=amount,
                promo_id=None,
                promo_name=None,
                promo_discount=0,
                discount_kind=None,
                discount_value=None,
                discount=0,
                total=amount,
                bundle_id=bundle.id,
                bundle_name=bundle.name,
                contents="",
            )
        )
    return lines


def price_quote(
    quote: QuoteIn,
    rules: DivisionRules,
    price_types: dict[str, PriceTypeInfo],
    products: dict[str, ProductInfo],
    promos: dict[str, PromoInfo],
    issuers: dict[str, str],
    paperwork: bool = True,
    bundles: dict[str, BundleInfo] | None = None,
) -> PricedQuote:
    """`promos` and `bundles` are the ones that apply to this division today;
    `issuers` the active guarantee-letter issuers (code -> name).
    `paperwork=False` prices without checking notes and the payer, for a preview
    while the rep types."""
    bundles = bundles or {}
    errors: list[tuple[tuple[str | int, ...], str]] = []

    if not rules.uses_price_list:
        raise PricingError([(("priceType",), "This division quotes with notes only, not a price list.")])

    price_type = price_types.get(quote.price_type) if quote.price_type in rules.price_types else None
    rule = rules.price_types.get(quote.price_type)
    with_rx = [code for code, r in rules.price_types.items() if r == "with_rx" and code in price_types]
    if price_type is None:
        errors.append((("priceType",), "Pick one of this division's prices."))
    elif quote.rx and with_rx and rule != "with_rx":
        errors.append((("priceType",), f"With an Rx, use {' or '.join(price_types[c].name for c in with_rx)}."))
    elif not quote.rx and rule == "with_rx":
        errors.append((("priceType",), f"{price_type.name} is only for quotes with an Rx."))

    if paperwork and price_type and price_type.requires_notes and not quote.notes:
        errors.append((("notes",), f"{price_type.name} needs notes."))

    if paperwork and quote.payer != SELF:
        if quote.payer not in issuers:
            errors.append((("payer",), "Pick who pays."))
        elif not rules.allows_guarantee_letters:
            errors.append((("payer",), "This division doesn't take guarantee letters."))
        elif quote.letter is None:
            errors.append((("letter",), f"Add the {issuers[quote.payer]} guarantee letter's number, date and amount."))

    lines: list[PricedLine] = []
    seen: set[str] = set()
    seen_bundles: set[str] = set()
    for i, line in enumerate(quote.lines):
        at = ("lines", i)

        if line.bundle_id:
            if price_type is None:
                continue
            bundle = bundles.get(line.bundle_id)
            if bundle is None:
                errors.append(((*at, "bundleId"), "That bundle isn't offered here, or it has ended."))
                continue
            if bundle.id in seen_bundles:
                errors.append(((*at, "bundleId"), "This bundle is already on the quote."))
                continue
            seen_bundles.add(bundle.id)
            try:
                lines.extend(bundle_lines(bundle, line.quantity, products, price_type))
            except BundleError as exc:
                errors.append(((*at, "bundleId"), str(exc)))
            continue

        product = products.get(line.product_id)
        if product is None or not product.is_active:
            errors.append(((*at, "productId"), "Pick a product from the price list."))
            continue
        if product.id in seen:
            errors.append(((*at, "productId"), "This product is already on the quote."))
            continue
        seen.add(product.id)
        if price_type is None:
            continue

        if price_type.entry == "list":
            unit_price = product.prices.get(price_type.code)
            if unit_price is None:
                errors.append(((*at, "productId"), f"{product.name} has no {price_type.name} yet. Ask Inventory to add it."))
                continue
        else:
            unit_price = line.unit_price_centavos
            if not unit_price:
                errors.append(((*at, "unitPriceCentavos"), f"Enter the {price_type.name} per unit."))
                continue
        gross = unit_price * line.quantity

        promo = None
        promo_discount = free = 0
        if line.promo_id:
            promo = promos.get(line.promo_id)
            if promo is None or not promo.covers(product.id):
                errors.append(((*at, "promoId"), "That promo doesn't apply to this product here, or it has ended."))
                continue
            try:
                promo_discount, free = promo.apply(line.quantity, gross)
            except ValueError as exc:
                errors.append(((*at, "promoId"), str(exc)))
                continue

        discount = 0
        base = gross - promo_discount
        if line.discount:
            if line.discount.kind == "percent":
                discount = share(base, line.discount.value)
            else:
                discount = line.discount.value
            if discount > base:
                errors.append(((*at, "discount"), "The discount is more than the line is worth."))
                continue

        lines.append(
            PricedLine(
                product_id=product.id,
                product_code=product.code,
                product_name=product.name,
                unit=product.unit,
                quantity=line.quantity,
                free_quantity=free,
                unit_price=unit_price,
                gross=gross,
                promo_id=promo.id if promo else None,
                promo_name=promo.name if promo else None,
                promo_discount=promo_discount,
                discount_kind=line.discount.kind if line.discount else None,
                discount_value=line.discount.value if line.discount else None,
                discount=discount,
                total=base - discount,
            )
        )

    if errors:
        raise PricingError(errors)
    assert price_type is not None

    gross = sum(line.gross for line in lines)
    discount = sum(line.discount for line in lines)
    reasons = []
    if price_type.needs_approval:
        reasons.append("price")
    if discount and discount * BP > rules.discount_approval_bp * gross:
        reasons.append("discount")
    return PricedQuote(
        price_type=price_type,
        lines=tuple(lines),
        gross=gross,
        promo_discount=sum(line.promo_discount for line in lines),
        discount=discount,
        total=sum(line.total for line in lines),
        approval_reasons=tuple(reasons),
    )
