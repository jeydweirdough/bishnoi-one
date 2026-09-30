"""What isn't set up yet, for the sidebar's red counts.

Each count is a record with something left out that the app needs: a document
with no expiry date can never raise a renewal alert, a lease with no rent can't
be budgeted. The executive screens are open to everyone signed in, and so are
these counts.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import DB, CurrentUser
from app.models import CorporateDocument, PropertyRecord
from app.routers.admin import missing_an_expiry, missing_rent

router = APIRouter(prefix="/admin", tags=["unset"])


@router.get("/unset")
def unset(user: CurrentUser, db: DB) -> dict[str, int]:
    """How many of each thing isn't set yet, by kind. Kinds with nothing missing are left out."""
    counts = {
        "propertyRent": db.scalar(select(func.count()).select_from(PropertyRecord).where(missing_rent())) or 0,
        "documentExpiry": db.scalar(select(func.count()).select_from(CorporateDocument).where(missing_an_expiry())) or 0,
    }
    return {k: v for k, v in counts.items() if v}
