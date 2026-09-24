"""How records are shown to the screens, in the few shapes every router shares."""

from datetime import UTC, date, datetime

from app.api import iso
from app.models import Batch, Location, Product, Supplier, User, Warehouse


def day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def today() -> date:
    return datetime.now(UTC).date()


def person(user: User | None) -> dict | None:
    return {"id": user.id, "name": user.full_name} if user else None


def product_ref(p: Product) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "unit": p.unit_code,
        "trackBatches": p.track_batches,
        "trackExpiry": p.track_expiry,
        "trackSerials": p.track_serials,
    }


def warehouse_ref(w: Warehouse | None) -> dict | None:
    return {"id": w.id, "code": w.code, "name": w.name} if w else None


def location_ref(loc: Location | None) -> dict | None:
    return {"id": loc.id, "code": loc.code, "name": loc.name} if loc else None


def supplier_ref(s: Supplier | None) -> dict | None:
    return {"id": s.id, "code": s.code, "name": s.name} if s else None


def expiry_state(expires_on: date | None, warning_days: int) -> str | None:
    """expired, expiring (within the warning), ok; None when it doesn't expire."""
    if expires_on is None:
        return None
    left = (expires_on - today()).days
    return "expired" if left < 0 else "expiring" if left <= warning_days else "ok"


def batch_ref(b: Batch | None, warning_days: int = 90) -> dict | None:
    if b is None:
        return None
    return {
        "id": b.id,
        "batchNo": b.batch_no,
        "manufacturedOn": day(b.manufactured_on),
        "expiresOn": day(b.expires_on),
        "expiry": expiry_state(b.expires_on, warning_days),
        "receivedAt": iso(b.received_at),
    }
