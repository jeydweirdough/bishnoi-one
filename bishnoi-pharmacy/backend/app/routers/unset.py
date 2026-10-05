"""What isn't set up yet, for the sidebar's red counts.

Each count is a thing somebody has to fill in before the pharmacy works in
full: a medicine on sale at no price would be sold for nothing. Only the counts
this person may fix are sent, so a mark in their sidebar is always one they can
act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.access import CurrentAccess
from app.deps import DB
from app.models import Medicine
from app.routers.medicines import missing_a_price

router = APIRouter(tags=["unset"])


@router.get("/unset")
def unset(access: CurrentAccess, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    if access.can("medicines.edit"):
        counts["medicinePrices"] = db.scalar(select(func.count()).select_from(Medicine).where(missing_a_price())) or 0
    return {k: v for k, v in counts.items() if v}
