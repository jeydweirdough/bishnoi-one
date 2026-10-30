"""What an administrator can clean up in Finance (app/recycle_bin.py, 2026-10-30). People and roles aren't
here: they're kept on the Platform (Admin Console → People).

Posted documents go with their journal entries (an invoice's own and its payments', a bill's, a voucher's,
a fund request's), so the books stay balanced: the ledger is as if the document had never been. Anything
dated in a closed period (Ledger → Closing, locked until) refuses: open the period first. BIR expects an
issued invoice to be voided rather than deleted; deleting one asks for a second confirmation."""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvoicePayment, JournalEntry, LedgerSettings
from app.recycle_bin import Kind

P = "nbfi_"
ENTRIES = P + "journal_entries"


def _locked(db: Session) -> date | None:
    s = db.scalar(select(LedgerSettings))
    return s.locked_until if s else None


def _entry_ids(db: Session, kind: str, row: dict) -> list[str]:
    ids = [row["entry_id"]] if row.get("entry_id") else []
    if kind == "invoice":
        ids += [e for (e,) in db.execute(select(InvoicePayment.entry_id).where(InvoicePayment.invoice_id == row["id"], InvoicePayment.entry_id.is_not(None)))]
    if kind == "fund":
        ids += [e for (e,) in db.execute(select(JournalEntry.id).where(JournalEntry.fund_request_id == row["id"]))]
    return ids


def _guard_for(kind: str):
    def guard(db: Session, row: dict) -> None:
        lock = _locked(db)
        if lock is None:
            return
        days = [row["entry_date"]] if kind == "entry" and row.get("entry_date") else []
        ids = _entry_ids(db, kind, row)
        if ids:
            days += [d for (d,) in db.execute(select(JournalEntry.entry_date).where(JournalEntry.id.in_(ids)))]
        if any(d and d <= lock for d in days):
            raise HTTPException(status.HTTP_409_CONFLICT, f"It has entries in a closed period (locked up to {lock:%d %b %Y}). Open the period first (Ledger, Closing).")
    return guard


def _extra_for(kind: str):
    def extra(db: Session, row: dict) -> list[tuple[str, str, object]]:
        return [(ENTRIES, "id", e) for e in _entry_ids(db, kind, row)]
    return extra


def posted(kind: str) -> dict:
    return {"extra": _extra_for(kind), "guard": _guard_for(kind), "tables_named": {P + "journal_lines": "journal lines", P + "voucher_lines": "payment vouchers"}}


OWN_ENTRIES = (ENTRIES, P + "journal_lines")

KINDS: list[Kind] = [
    # Records
    Kind("invoices", "Sales invoices", P + "invoices", lambda r: r.get("number") or f"Draft for {r.get('customer_name') or 'a customer'}",
         owns=(P + "invoice_payments",) + OWN_ENTRIES, search=("number", "customer_name"), sub="customer_name",
         posted=lambda r: r.get("status") != "draft", **posted("invoice")),
    Kind("bills", "Supplier bills", P + "bills", lambda r: r.get("bill_number") or f"Bill {r.get('no')}", owns=(P + "bill_events", P + "bill_files") + OWN_ENTRIES,
         search=("bill_number", "po_number", "dr_number"), sub="status", posted=lambda r: bool(r.get("entry_id")), **posted("bill")),
    Kind("vouchers", "Payment vouchers", P + "payment_vouchers", lambda r: r.get("number") or f"Voucher {r.get('no')}",
         owns=(P + "voucher_lines", P + "voucher_events", P + "voucher_files") + OWN_ENTRIES, search=("number",), sub="status",
         posted=lambda r: bool(r.get("entry_id")), **posted("voucher")),
    Kind("journal-entries", "Journal entries", ENTRIES, lambda r: r.get("number") or r.get("memo"), owns=(P + "journal_lines",), search=("number", "memo", "reference"),
         sub="memo", posted=lambda r: r.get("status") == "posted", **posted("entry")),
    Kind("fund-requests", "Fund requests", P + "fund_requests", "number", owns=(P + "fund_events", P + "fund_expenses") + OWN_ENTRIES,
         search=("number", "requester_name", "purpose"), sub="requester_name", posted=lambda r: r.get("status") not in ("draft", "pending", "submitted"),
         **posted("fund")),
    Kind("sales-orders", "Sales orders", P + "sales_orders", "number", search=("number", "customer_name"), sub="customer_name"),
    Kind("bank-reconciliations", "Bank reconciliations", P + "bank_reconciliations", lambda r: f"Statement {r.get('statement_date')}", sub="status"),
    Kind("import-runs", "Import runs", P + "import_runs", lambda r: f"{r.get('kind')} import {str(r.get('created_at') or '')[:16]}", owns=(P + "import_records",)),
    Kind("import-matches", "Import matches", P + "import_matches", lambda r: r.get("source_label") or r.get("source_code"), owns=(P + "import_rules",),
         search=("source_label", "source_code"), sub="status"),
    # Set-up lists
    Kind("accounts", "Chart of accounts", P + "accounts", lambda r: f"{r.get('code')} {r.get('name')}", group="Set-up", search=("code", "name"),
         tables_named={P + "journal_lines": "journal lines"}),
    Kind("suppliers", "Suppliers", P + "suppliers", "name", group="Set-up", owns=(P + "supplier_files",), search=("name", "company_name", "tin"), sub="tin"),
    Kind("expense-categories", "Expense categories", P + "expense_categories", "name", group="Set-up", search=("name",)),
    Kind("invoice-series", "Invoice number series", P + "invoice_series", "name", group="Set-up", search=("name",)),
    Kind("bank-accounts", "Bank accounts", P + "bank_accounts", "name", group="Set-up", search=("name",)),
    Kind("fixed-assets", "Fixed assets", P + "fixed_assets", "name", group="Set-up", search=("name",), sub="status"),
    Kind("budgets", "Budget lines", P + "budgets", lambda r: f"Budget {r.get('year_end')} {r.get('division_name') or ''}".strip(), group="Set-up"),
    Kind("tax-rates", "Tax rates", P + "tax_rates", lambda r: f"{r.get('code')} from {r.get('valid_from')}", group="Set-up", search=("code",)),
    Kind("exchange-rates", "Exchange rates", P + "exchange_rates", lambda r: f"{r.get('currency')} on {r.get('on')}", group="Set-up", search=("currency",)),
]
