"""A signed, read-only financial tool for the company assistant. No SQL from AI."""
import calendar
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import func, select
from app.api import Api
from app import bir_reports, management, platform_pass
from app.audit import audit
from app.deps import DB, SettingsDep
from app.models import Account, Invoice, JournalEntry, JournalLine

router = APIRouter(prefix="/finance/assistant", tags=["read-only assistant"])
bearer = HTTPBearer(auto_error=False)


class MonthIn(Api):
    month: str = Field(pattern=r"^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$")


@router.post("/monthly")
def monthly(body: MonthIn, db: DB, settings: SettingsDep,
            credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if not credentials:
        raise HTTPException(401, "A delegated assistant read pass is required.")
    try:
        claims = platform_pass.check_for(settings, credentials.credentials, "finance")
    except platform_pass.PassRefused:
        raise HTTPException(401, "The assistant read pass is invalid or expired.") from None
    if claims.get("kind") != "assistant-read" or claims.get("tool") != "monthly-summary":
        raise HTTPException(403, "This pass cannot use financial assistant tools.")
    # Never learn the binding from the incoming pass or mutable sign-in metadata.
    bound = settings.assistant_company_slug or settings.crm_company
    if not bound:
        raise HTTPException(503, "Finance's company binding is not configured for assistant reads.")
    if claims.get("companySlug") != bound or not claims.get("company"):
        raise HTTPException(403, "This Finance database belongs to another company.")
    permissions = claims.get("permissions", [])
    if claims.get("admin") is not True and (not isinstance(permissions, list) or "journal.view" not in permissions):
        raise HTTPException(403, "Your role cannot read company accounting reports.")
    year, month = map(int, body.month.split("-"))
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    today = datetime.now(ZoneInfo(settings.org_timezone)).date()
    end = min(last, today) if first <= today else last
    future = first > today
    invoice_count = 0 if future else db.scalar(select(func.count()).select_from(Invoice).where(Invoice.status == "issued", Invoice.invoice_date >= first, Invoice.invoice_date <= end))
    journal_count = 0 if future else db.scalar(select(func.count()).select_from(JournalLine).join(JournalEntry).join(Account, Account.id == JournalLine.account_id)
        .where(JournalEntry.status == "approved", JournalEntry.entry_date >= first, JournalEntry.entry_date <= end, Account.type.in_(("income", "expense"))))
    totals = bir_reports.income_statement(db, first, end)["totals"] if journal_count else None
    result = {
        "companyId": claims["company"], "companySlug": bound, "currency": settings.org_currency,
        "from": first.isoformat(), "to": end.isoformat(), "partial": first <= today < last,
        "revenueCentavos": management.revenue(db, first, end) if invoice_count else None,
        "incomeCentavos": totals["incomeCentavos"] if totals else None,
        "expensesCentavos": totals["expensesCentavos"] if totals else None,
        "profitCentavos": totals["netCentavos"] if totals else None,
        "issuedInvoices": invoice_count, "approvedJournalLines": journal_count,
        "definitions": {
            "revenue": "Issued invoices, excluding VAT, by invoice date; void and draft invoices excluded.",
            "expenses": "Debits minus credits on expense accounts in approved journal entries, including recorded cost of goods sold.",
            "profit": "Approved journal income minus approved journal expenses; includes other income, so it is not necessarily invoiced revenue minus expenses.",
        },
        "missing": (["No issued invoices recorded for this date range."] if not invoice_count else []) + (["No approved income/expense journal lines recorded; expenses and profit are unavailable."] if not journal_count else []),
        "sources": [
            {"label": "Finance key figures: invoiced revenue", "href": f"/finance/reports/key-figures?from={first}&to={end}"},
            {"label": "Finance profit and loss: approved journal entries", "href": f"/finance/reports/profit-and-loss?from={first}&to={end}"},
        ],
    }
    audit(db, claims["email"], "assistant.monthly_read", target=body.month, fields=["revenue", "expenses", "profit"])
    db.commit()
    return result
