"""What isn't set up yet, for the sidebar's red counts.

Each count is a record with something left out that the app needs: a document
with no expiry date can never raise a renewal alert, a lease with no rent can't
be budgeted. Only the counts this person may fix are sent, so a mark in their
sidebar is always one they can act on.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.access import CurrentAccess
from app.deps import DB
from app.models import CorporateDocument, PropertyRecord
from app.routers.admin import missing_an_expiry, missing_rent

router = APIRouter(prefix="/admin", tags=["unset"])


@router.get("/unset")
def unset(access: CurrentAccess, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds are left out when
    this person can't fix them, and when nothing is missing."""
    counts: dict[str, int] = {}
    if access.can("properties.edit"):
        counts["propertyRent"] = db.scalar(select(func.count()).select_from(PropertyRecord).where(missing_rent())) or 0
    if access.can("documents.edit"):
        counts["documentExpiry"] = db.scalar(select(func.count()).select_from(CorporateDocument).where(missing_an_expiry())) or 0
    return {k: v for k, v in counts.items() if v}
