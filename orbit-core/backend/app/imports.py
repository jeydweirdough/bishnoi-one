"""Bringing a spreadsheet into Orbit.

Two steps, always. First a **dry run**: every row is checked and judged, and
nothing is written. The person reads what would happen — this many new, this
many changed, these refused and why — and only then applies it. An import that
writes as it goes and stops half way leaves a mess nobody can describe.

The rules are the ones the screens use. A price type this company doesn't keep
is refused here exactly as it would be refused on the product form, because an
import is not a back door.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.fields import clean_value, fields
from app.models import PriceType, Product, ProductPrice

from app.sheets import Sheet
from app.tenancy import org_get

# field key -> what a column might be called. Order matters: the first alias
# that matches wins, so the plainest name goes first.
PRODUCT_COLUMNS: dict[str, tuple[str, ...]] = {
    "code": ("code", "item code", "product code", "sku", "item"),
    "name": ("name", "product", "product name", "description", "item name"),
    "unit": ("unit", "uom", "packing", "pack size", "unit of measure"),
}

NEW, CHANGED, SAME, REFUSED = "new", "changed", "same", "refused"

# The same shape the product form accepts (app/schemas.py ProductFields), so a
# code that can be typed in can also be imported, and neither lets in anything
# the other would refuse.
PRODUCT_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


@dataclass
class RowResult:
    line: int
    outcome: str
    what: str
    # Only when refused: worded for the person who has to fix the sheet.
    why: str = ""


@dataclass
class ImportResult:
    rows: list[RowResult] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {NEW: 0, CHANGED: 0, SAME: 0, REFUSED: 0})
    # Columns the sheet has that nothing was mapped to, so a person can see
    # what is being ignored rather than wondering later.
    unused_columns: list[str] = field(default_factory=list)

    def add(self, row: RowResult) -> None:
        self.rows.append(row)
        self.counts[row.outcome] += 1

    def out(self) -> dict:
        return {
            "counts": self.counts,
            "unusedColumns": self.unused_columns,
            "rows": [{"line": r.line, "outcome": r.outcome, "what": r.what, "why": r.why} for r in self.rows],
            "wouldWrite": self.counts[NEW] + self.counts[CHANGED],
        }


def money_from(text: str) -> int | None:
    """A price as whole minor units. "₱1,234.50", "1234.5" and "1,234" all mean
    the same thing; anything else is not a price."""
    cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
    if not cleaned or cleaned.count(".") > 1:
        return None
    try:
        return round(float(cleaned) * 100)
    except ValueError:
        return None


def import_products(db: Session, sheet: Sheet, mapping: dict[str, str], apply: bool) -> ImportResult:
    """`mapping` is field key -> column name, as the person confirmed it. Price
    columns are mapped as `price:<price type code>`."""
    result = ImportResult()
    known_types = {t.code for t in db.scalars(select(PriceType))}
    custom = {f.key for f in fields(db, "product", active_only=True)}

    used = {column for column in mapping.values() if column}
    result.unused_columns = [c for c in sheet.columns if c not in used]

    price_columns = {key.removeprefix("price:"): column for key, column in mapping.items() if key.startswith("price:")}
    detail_columns = {key.removeprefix("field:"): column for key, column in mapping.items() if key.startswith("field:")}

    seen: set[str] = set()
    for i, row in enumerate(sheet.rows, start=2):  # 1 is the header, as the person sees it
        code = row.get(mapping.get("code", ""), "").strip()
        name = row.get(mapping.get("name", ""), "").strip()
        label = code or name or "(blank row)"

        if not code:
            result.add(RowResult(i, REFUSED, label, "No product code in this row."))
            continue
        if not PRODUCT_CODE.fullmatch(code) or not 2 <= len(code) <= 40:
            result.add(RowResult(i, REFUSED, label, "That product code has characters Orbit can't use."))
            continue
        if code in seen:
            result.add(RowResult(i, REFUSED, label, "This code is in the sheet twice."))
            continue
        seen.add(code)
        if not name:
            result.add(RowResult(i, REFUSED, label, "No product name in this row."))
            continue

        prices: dict[str, int] = {}
        bad_price = None
        for price_type, column in price_columns.items():
            text = row.get(column, "").strip()
            if not text:
                continue
            if price_type not in known_types:
                bad_price = f"This company doesn't keep a price type called {price_type}."
                break
            amount = money_from(text)
            if amount is None or amount < 0:
                bad_price = f'"{text}" in {column} isn\'t a price.'
                break
            prices[price_type] = amount
        if bad_price:
            result.add(RowResult(i, REFUSED, label, bad_price))
            continue

        details = {key: row.get(column, "").strip() for key, column in detail_columns.items() if row.get(column, "").strip()}
        unknown = set(details) - custom
        if unknown:
            result.add(RowResult(i, REFUSED, label, f"This company has no product field called {sorted(unknown)[0]}."))
            continue
        # The same check the product form makes, but judging a row rather than
        # refusing the whole request: one bad cell shouldn't stop the other 500.
        by_key = {f.key: f for f in fields(db, "product")}
        problem = next(
            (p for p in (clean_value(by_key[k], v)[1] for k, v in details.items() if k in by_key) if p is not None), None
        )
        if problem is not None:
            result.add(RowResult(i, REFUSED, label, problem))
            continue
        existing = db.scalar(select(Product).where(Product.code == code))
        unit = row.get(mapping.get("unit", ""), "").strip()
        if existing is None:
            result.add(RowResult(i, NEW, f"{code} — {name}"))
            if apply:
                product = Product(code=code, name=name, unit=unit or "Each", details=details)
                db.add(product)
                db.flush()
                for price_type, amount in prices.items():
                    db.add(ProductPrice(product_id=product.id, price_type_code=price_type, amount_centavos=amount))
            continue

        current_prices = {p.price_type_code: p.amount_centavos for p in existing.prices}
        changes = (
            existing.name != name
            or (unit and existing.unit != unit)
            or any(current_prices.get(t) != a for t, a in prices.items())
            or any(existing.details.get(k) != v for k, v in details.items())
        )
        result.add(RowResult(i, CHANGED if changes else SAME, f"{code} — {name}"))
        if apply and changes:
            existing.name = name
            if unit:
                existing.unit = unit
            if details:
                existing.details = {**existing.details, **details}
            for price_type, amount in prices.items():
                row_for = org_get(db, ProductPrice, existing.id, price_type)
                if row_for is None:
                    db.add(ProductPrice(product_id=existing.id, price_type_code=price_type, amount_centavos=amount))
                else:
                    row_for.amount_centavos = amount

    return result


def product_guesses(db: Session, columns: list[str]) -> dict[str, tuple[str, ...]]:
    """What to look for in the sheet's columns: the fields every product has,
    this company's own price types, and its own product fields."""
    wanted = dict(PRODUCT_COLUMNS)
    for price_type in db.scalars(select(PriceType).where(PriceType.entry == "list")):
        wanted[f"price:{price_type.code}"] = (price_type.name, price_type.code, f"{price_type.name} price")
    for custom in fields(db, "product", active_only=True):
        wanted[f"field:{custom.key}"] = (custom.label, custom.key)
    return wanted


def label_for(db: Session, key: str) -> str:
    """What the mapping screen calls each thing it is looking for."""
    if key.startswith("price:"):
        code = key.removeprefix("price:")
        price_type = org_get(db, PriceType, code)
        return price_type.name if price_type else code
    if key.startswith("field:"):
        custom = next((f for f in fields(db, "product") if f.key == key.removeprefix("field:")), None)
        return custom.label if custom else key.removeprefix("field:")
    return {"code": "Product code", "name": "Product name", "unit": "Unit"}.get(key, key)


def required_for(key: str) -> bool:
    return key in ("code", "name")


def mapping_out(db: Session, sheet: Sheet, kind: str = "products") -> dict:
    """What the screen shows: the columns found, a guess at each field, and a
    few rows so a person can see they picked the right file."""
    from app.sheets import guess

    wanted = product_guesses(db, sheet.columns)
    guessed = guess(sheet.columns, wanted)
    return {
        "kind": kind,
        "columns": sheet.columns,
        "otherTabs": sheet.other_tabs,
        "rowCount": len(sheet.rows),
        "sample": sheet.rows[:5],
        "fields": [
            {"key": key, "label": label_for(db, key), "required": required_for(key), "column": guessed.get(key)}
            for key in wanted
        ],
    }
