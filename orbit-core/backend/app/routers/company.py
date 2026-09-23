"""Settings -> Company: who this company is, and how it writes things down.

Money, dates and times are read from here by every screen and by the API's own
messages, so this is the one place a company that isn't in Manila, or doesn't
pay in pesos, puts that right. Admins only.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends

from app.audit import audit
from app.deps import DB, CurrentUser, require_owner_or_recovery
from app.errors import field_errors
from app.models import Organization
from app.money import SYMBOLS, format_money
from app.routers.auth import org_out
from app.schemas import CompanyPatch
from app.tenancy import company_of

router = APIRouter(prefix="/admin/company", tags=["settings"], dependencies=[Depends(require_owner_or_recovery)])


def company_out(org: Organization) -> dict:
    """The company, plus an example of its money so the screen can show what a
    change actually looks like before it is saved."""
    return {
        **org_out(org),
        # Shown, not set here: order numbering lives in Settings -> Orders.
        "orderPrefix": org.order_prefix,
        "template": org.template,
        "example": format_money(123_456, org.currency, org.minor_units),
        # The currencies this API can draw a symbol for; anything else is shown
        # as its code, which is correct everywhere if not pretty.
        "knownCurrencies": sorted(SYMBOLS),
    }


@router.get("")
def company(db: DB) -> dict:
    return company_out(db.get(Organization, company_of(db)))


@router.patch("")
def update_company(body: CompanyPatch, db: DB, me: CurrentUser) -> dict:
    org = db.get(Organization, company_of(db))
    errors: list[tuple[tuple, str]] = []

    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            errors.append((("timezone",), "That isn't a time zone. Use one like Asia/Manila or Europe/London."))
    if body.currency is not None and not body.currency.isalpha():
        errors.append((("currency",), "Use a three-letter code, like PHP or USD."))
    if errors:
        raise field_errors(errors)

    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "currency" in changes:
        changes["currency"] = changes["currency"].upper()
    for key, value in changes.items():
        setattr(org, key, value)
    db.commit()
    audit(db, me, "company.updated", org.slug, body.model_fields_set)
    return company_out(org)
