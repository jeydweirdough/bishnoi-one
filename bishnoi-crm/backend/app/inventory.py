"""The product list and stock levels, from Bishnoi One Inventory.

Inventory owns the products: it's where they're added and changed. The CRM
brings them over (matched by Inventory's id, or at first by SKU = code), with
their SRP as the "SRP" price type; each team can still quote its own price
over it (special prices). A product that leaves Inventory is switched off
here, never deleted: quotes still name it.

The list is brought over when it's older than SYNC_EVERY and someone opens
the products (there's nothing running in the background on Vercel), or at
once with "Sync now". Stock is asked for live, kept for STOCK_FOR.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.tenants import company_header
from app.models import PriceType, Product, ProductPrice
from app.pricing import sales_settings

log = logging.getLogger(__name__)

SRP = "SRP"
SYNC_EVERY = timedelta(minutes=15)
STOCK_FOR = 60  # seconds
TIMEOUT = 10  # seconds


class Unreachable(Exception):
    """Inventory didn't answer, or refused: the message says which, for people."""


def call(settings: Settings, path: str, params: dict | None = None) -> dict:
    """GET one of Inventory's /integration endpoints."""
    url = f"{settings.inventory_api_url}/integration/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"X-Bishnoi-Key": settings.inventory_api_key.get_secret_value(), "Accept": "application/json", **company_header(settings)})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (the address is ours, from settings)
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise Unreachable("Unable to sync with Inventory: connection could not be verified. Please contact your system administrator.") from e
        raise Unreachable(f"Inventory answered with an error ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise Unreachable("Inventory can't be reached right now.") from e


def as_utc(moment: datetime | None) -> datetime | None:
    return moment.replace(tzinfo=UTC) if moment is not None and moment.tzinfo is None else moment


# --- the product list -------------------------------------------------------------------------


def srp_type(db: Session) -> PriceType:
    found = db.get(PriceType, SRP)
    if found is None:
        found = PriceType(code=SRP, name="SRP", entry="list", rule="always", sort_order=0)
        db.add(found)
        db.flush()
    return found


def attribute(attributes: dict, *names: str) -> str | None:
    """A specification by any of its usual names, whatever their case."""
    lowered = {str(k).strip().lower(): v for k, v in (attributes or {}).items()}
    for name in names:
        value = lowered.get(name)
        if value not in (None, ""):
            return str(value)[:160]
    return None


def code_of(sku: str) -> str:
    return sku.strip().upper()[:40]


def sync(db: Session, settings: Settings) -> dict:
    """Bring the product list over. Returns what changed; raises Unreachable."""
    items = call(settings, "products")["items"]
    srp_type(db)
    linked = {p.inventory_id: p for p in db.scalars(select(Product).where(Product.inventory_id.is_not(None)))}
    by_code = {p.code.upper(): p for p in db.scalars(select(Product).where(Product.inventory_id.is_(None)))}
    added = updated = 0
    seen = set()
    for item in items:
        seen.add(item["id"])
        product = linked.get(item["id"]) or by_code.pop(code_of(item["sku"]), None)
        values = {
            "inventory_id": item["id"],
            "code": code_of(item["sku"]),
            "name": item["name"][:160],
            "unit": ((item.get("unit") or {}).get("name") or "piece")[:30],
            "is_active": item.get("status") == "active",
            "generic_name": attribute(item.get("attributes"), "generic name", "generic"),
            "strength": attribute(item.get("attributes"), "strength", "dosage strength"),
            "form": attribute(item.get("attributes"), "form", "dosage form"),
            # Its FDA registration: Inventory's, as it keeps it.
            "cpr_number": (item.get("cprNumber") or None),
            "cpr_valid_until": date.fromisoformat(item["cprValidUntil"]) if item.get("cprValidUntil") else None,
        }
        if product is None:
            product = Product(**values)
            db.add(product)
            added += 1
            changed = True
        else:
            # A specification Inventory doesn't keep is left as the CRM has it.
            keep = {k for k in ("generic_name", "strength", "form") if values[k] is None}
            changed = False
            for k, v in values.items():
                if k not in keep and getattr(product, k) != v:
                    setattr(product, k, v)
                    changed = True
        srp = item.get("sellingPrice") or 0
        there = next((pp for pp in product.prices if pp.price_type_code == SRP), None)
        if srp > 0 and there is None:
            product.prices.append(ProductPrice(price_type_code=SRP, amount_centavos=srp, approval_status="approved"))
            changed = True
        elif srp > 0 and there.amount_centavos != srp:
            there.amount_centavos = srp
            there.approval_status = "approved"
            changed = True
        elif srp <= 0 and there is not None:
            product.prices.remove(there)
            changed = True
        if changed and product not in db.new:
            updated += 1
    # Gone from Inventory: off here, kept for the quotes that name it.
    gone = 0
    for inventory_id, product in linked.items():
        if inventory_id not in seen and product.is_active:
            product.is_active = False
            gone += 1
    found = sales_settings(db)
    found.inventory_synced_at, found.inventory_error = datetime.now(UTC), None
    db.commit()
    return {"added": added, "updated": updated, "switchedOff": gone, "total": len(items)}


def sync_if_stale(db: Session, settings: Settings) -> None:
    """Bring the list over if it's older than SYNC_EVERY. A failure is kept, to
    be shown, and never stops the page."""
    if not settings.inventory_linked:
        return
    last = as_utc(sales_settings(db).inventory_synced_at)
    if last is not None and datetime.now(UTC) - last < SYNC_EVERY:
        return
    try_sync(db, settings)


def try_sync(db: Session, settings: Settings) -> dict | None:
    try:
        return sync(db, settings)
    except (Unreachable, IntegrityError, KeyError, TypeError) as e:
        db.rollback()
        log.warning("Inventory sync failed: %s", e)
        found = sales_settings(db)
        # Tried: wait SYNC_EVERY before trying again by itself.
        found.inventory_synced_at = datetime.now(UTC)
        found.inventory_error = (str(e) if isinstance(e, Unreachable) else "Inventory's product list couldn't be read.")[:300]
        db.commit()
        return None


def link_out(db: Session, settings: Settings) -> dict:
    found = sales_settings(db)
    return {
        "linked": settings.inventory_linked,
        "syncedAt": as_utc(found.inventory_synced_at).isoformat() if found.inventory_synced_at else None,
        "error": found.inventory_error if settings.inventory_linked else None,
        "appUrl": settings.inventory_app_url,
    }


# --- stock -----------------------------------------------------------------------------------

_stock: dict[str, tuple[float, dict | None]] = {}


def stock(settings: Settings, codes: list[str]) -> dict[str, dict | None]:
    """How much there is of each, by code: None for one Inventory doesn't
    have. Raises Unreachable."""
    now = time.monotonic()
    wanted = list(dict.fromkeys(c.upper() for c in codes))
    missing = [c for c in wanted if c not in _stock or now - _stock[c][0] > STOCK_FOR]
    if missing:
        answer = {s["sku"].upper(): s for s in call(settings, "stock", {"skus": ",".join(missing)})["items"]}
        for c in missing:
            _stock[c] = (now, answer.get(c))
    if len(_stock) > 5000:
        for c in [c for c, (at, _) in _stock.items() if now - at > STOCK_FOR]:
            del _stock[c]
    return {c: _stock[c][1] for c in wanted}


def linked_codes(db: Session, codes: list[str]) -> list[str]:
    """Of these, the codes of products that come from Inventory."""
    upper = [c.upper() for c in codes]
    return list(db.scalars(select(Product.code).where(Product.inventory_id.is_not(None), func.upper(Product.code).in_(upper))))
