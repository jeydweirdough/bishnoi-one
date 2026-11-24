"""BIR readiness: each tax list set against the books for the same period (built 2026-10-29).

The tax lists (app/bir_reports.py) read invoices and bills; the books read every journal entry.
Where they differ, a return built from the lists would disagree with the ledger: the gap Oojeema
shows (its Purchase Journal, SLP and QAP leave out journal entries to VAT and withholding accounts;
its aging never ties to the ledger). So each check shows both figures, the difference, and the
entries that reach the account from somewhere the tax list doesn't read (a journal entry typed by
hand, a marketing liquidation...). It explains; it never adjusts anything or claims a tax rule.
"""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.finance import bir_reports as bir
from modules.finance.ledger import settings as posting_settings
from modules.finance.models import Account, Bill, ImportedExpense, ImportedExpenseLine, Invoice, InvoicePayment, JournalEntry, JournalLine, PaymentVoucher, PettyCashVoucher, Supplier

SOURCE_NAMES = {"invoice": "Sales invoices and collections", "credit_note": "Customer credit notes",
                "bill": "Supplier bills", "vendor_credit": "Supplier vendor credits",
                "voucher": "Payment vouchers", "advance": "Supplier prepayments and customer deposits",
                "fund": "Marketing requests and liquidations", "manual": "Journal entries typed by hand", "admin": "Setup",
                "pack": "Imported pack", "petty_cash": "Petty cash vouchers", "expense": "Imported expenses",
                "oojeema_gl": "Oojeema journal entries outside subledgers",
                "oojeema_closing": "Tax closings, remittances & reclassifications"}
CLOSING_MARKERS = ("2550-Q", "0619-", "TO CLOSE ", "TO SET UP EWT", "INCOME TAX EXPENSE", "PAYMENT OF EWT")
ENTRIES_LISTED = 50


def _closing_entry_ids(db: Session, entry_ids: set[str]) -> set[str]:
    if not entry_ids:
        return set()
    hits: set[str] = set()
    for eid, memo, desc in db.execute(
        select(JournalEntry.id, JournalEntry.memo, JournalLine.description)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(JournalEntry.id.in_(entry_ids), JournalEntry.source == "oojeema_gl")
    ):
        text = f"{memo or ''} {desc or ''}".upper()
        if any(marker in text for marker in CLOSING_MARKERS):
            hits.add(eid)
    return hits


def _subledger_links(db: Session) -> dict[str, set[str]]:
    def col(model):
        return {eid for (eid,) in db.execute(select(model.entry_id).where(model.entry_id.is_not(None)))}

    return {
        "invoice_sale": col(Invoice),
        "invoice_collection": col(InvoicePayment),
        "bill": col(Bill),
        "voucher": col(PaymentVoucher),
    }


def lines_on(db: Session, accounts: set[str], start: date | None, end: date) -> list[tuple]:
    q = (select(JournalEntry, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos))
         .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
         .where(JournalLine.account_id.in_(accounts), JournalEntry.status == "approved", JournalEntry.entry_date <= end)
         .group_by(JournalEntry.id).order_by(JournalEntry.entry_date, JournalEntry.number))
    if start is not None:
        q = q.where(JournalEntry.entry_date >= start)
    return [(e, int(d or 0), int(c or 0)) for e, d, c in db.execute(q)]


def check(db, key, title, says, list_figure, accounts, start, end, credit_normal, expected, list_name, causes, *, linked_ids: set[str] = frozenset(), closing_ids: set[str] = frozenset()):
    """One comparison. `start` None: the balance at `end` (aging); else the movement in the period."""
    found = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_(accounts)))} if accounts else {}
    if not found:
        return {"key": key, "title": title, "says": says, "status": "not_set", "listName": list_name, "listCentavos": list_figure,
                "booksCentavos": None, "closingCentavos": 0, "beforeClosingCentavos": None,
                "differenceCentavos": None, "accounts": [], "otherSources": [], "causes": [],
                "message": "The account isn't set under Accounting → Default accounts, so the books can't be compared."}
    rows = lines_on(db, set(found), start, end)
    books = sum((c - d) if credit_normal else (d - c) for _, d, c in rows)
    others: dict[str, dict] = {}
    closing_centavos = 0
    for e, d, c in rows:
        # Imported Oojeema GL entries linked directly to an invoice, bill, collection or voucher belong
        # to that tax list; only unlinked JVs and closing entries sit outside the subledgers.
        if e.source in expected or (e.source == "oojeema_gl" and e.id in linked_ids):
            continue
        delta = (c - d) if credit_normal else (d - c)
        bucket = "oojeema_closing" if (e.source == "oojeema_gl" and e.id in closing_ids) else e.source
        if bucket == "oojeema_closing" and start is not None:
            closing_centavos += delta
        o = others.setdefault(bucket, {"source": bucket, "name": SOURCE_NAMES.get(bucket, bucket), "entries": 0, "centavos": 0, "listed": []})
        o["entries"] += 1
        o["centavos"] += delta
        if len(o["listed"]) < ENTRIES_LISTED:
            o["listed"].append({"id": e.id, "number": e.number, "date": e.entry_date.isoformat(), "memo": e.memo, "centavos": delta})
    difference = list_figure - books
    before_closing = books - closing_centavos if (start is not None and closing_centavos) else None
    return {"key": key, "title": title, "says": says, "status": "agrees" if difference == 0 else "differs", "listName": list_name,
            "listCentavos": list_figure, "booksCentavos": books, "closingCentavos": closing_centavos, "beforeClosingCentavos": before_closing,
            "differenceCentavos": difference,
            "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in sorted(found.values(), key=lambda x: x.code)],
            "otherSources": sorted(others.values(), key=lambda o: -abs(o["centavos"])),
            "causes": causes if difference else [], "message": None}


REVIEW_LISTED = 50


def withholding_review(db: Session, start: date, end: date) -> dict:
    """Whether every local purchase in the period says what was withheld, or why nothing was (Batch A, 2026-11-05).

    The EWT check above compares totals; two zeros agree even when tax should have been withheld (Codex's review of
    Sir Mel's recording 11). This lists the posted bill lines and petty cash receipts from local suppliers with no
    withholding code and no reason, the bills whose supplier has no origin set, and, apart, the imported Zoho
    expenses with no withholding (history brought in as it was, which carries no reason)."""
    missing: list[dict] = []
    no_origin: dict[str, dict] = {}
    foreign = 0
    bills = db.scalars(select(Bill).where(Bill.status == "recorded", Bill.bill_date >= start, Bill.bill_date <= end).order_by(Bill.bill_date, Bill.no))
    for b in bills:
        origin = b.supplier.origin
        if origin is None:
            no_origin.setdefault(b.supplier.id, {"id": b.supplier.id, "name": b.supplier.name, "bills": 0})["bills"] += 1
        for n, ln in enumerate(b.lines, start=1):
            if origin == "foreign":
                foreign += 1
            elif not ln.get("withholding") and not ln.get("noWithholding"):
                missing.append({"kind": "bill", "id": b.id, "label": f"Bill {b.no} · {b.supplier.name}", "line": n,
                                "date": b.bill_date.isoformat(), "centavos": ln.get("amountCentavos", 0), "href": f"/bills/{b.id}"})
    vouchers = db.scalars(select(PettyCashVoucher).where(PettyCashVoucher.status == "posted", PettyCashVoucher.voucher_date >= start,
                                                         PettyCashVoucher.voucher_date <= end).order_by(PettyCashVoucher.voucher_date))
    for v in vouchers:
        for ln in v.lines:
            if not ln.withholding and not ln.no_withholding_reason:
                missing.append({"kind": "petty_cash", "id": v.id, "label": f"Petty cash {v.number} · {ln.store}", "line": ln.position,
                                "date": ln.spent_on.isoformat(), "centavos": ln.amount_centavos, "href": f"/petty-cash/{v.id}"})
    imported = db.scalar(select(func.count()).select_from(ImportedExpenseLine).join(ImportedExpense, ImportedExpense.id == ImportedExpenseLine.expense_id)
                         .where(ImportedExpense.status == "posted", ImportedExpense.expense_date >= start, ImportedExpense.expense_date <= end,
                                ImportedExpenseLine.withholding.is_(None))) or 0
    return {"status": "reviewed" if not missing and not no_origin else "needs_review",
            "missingCount": len(missing), "missing": missing[:REVIEW_LISTED],
            "originNotSet": sorted(no_origin.values(), key=lambda s: s["name"].lower()),
            "foreignLines": foreign, "importedWithoutWithholding": imported}


def tamp_audit(db: Session, start: date, end: date) -> dict:
    """Read-only TAMP audit check comparing local SLP purchases against QAP withholding per supplier."""
    origins = {s.id: s.origin for s in db.scalars(select(Supplier))}
    by_supplier: dict[str, dict] = {}
    for pu in bir.bills_between(db, start, end):
        origin = origins.get(pu.payee_id)
        if origin == "foreign":
            continue
        row = by_supplier.setdefault(
            pu.payee_id,
            {
                "supplierId": pu.payee_id,
                "name": pu.name,
                "tin": pu.tin,
                "origin": origin or "unset",
                "netCentavos": 0,
                "vatCentavos": 0,
                "ewtCentavos": 0,
                "purchases": 0,
            },
        )
        row["netCentavos"] += pu.net
        row["vatCentavos"] += pu.vat
        row["ewtCentavos"] += pu.withheld
        if pu.source != "vendor_credit":
            row["purchases"] += 1
    flagged = sorted(
        (r for r in by_supplier.values() if r["netCentavos"] > 0 and r["ewtCentavos"] == 0),
        key=lambda r: (-r["netCentavos"], r["name"].lower()),
    )
    return {
        "status": "review" if flagged else "ok",
        "unwithheldCount": len(flagged),
        "unwithheldTotalCentavos": sum(r["netCentavos"] for r in flagged),
        "suppliers": flagged[:REVIEW_LISTED],
        "note": "Read-only TAMP check (BIR Top Withholding Agent rule): compares local recorded purchases (SLP) against QAP EWT withheld per supplier so ₱0-EWT local suppliers are reviewed before filing.",
    }


VOID_CAUSE = ("A document voided in a later period: the tax list leaves it out of its own period, while the books keep "
              "it there and reverse it on the day it was voided. Which period should carry it is a question for Sir Mel.")


def readiness(db: Session, start: date, end: date, zone: ZoneInfo) -> dict:
    from modules.finance.payables_asof import total_owed_on as payables_owed
    from modules.finance.receivables_asof import total_owed_on as receivables_owed

    s = posting_settings(db)
    one = lambda account_id: {account_id} if account_id else set()  # noqa: E731
    sales = bir.sales_journal(db, start, end)["totals"]
    purchases = bir.purchase_journal(db, start, end)["totals"]
    receipts = bir.cash_receipts(db, start, end)["totals"]
    other = "Entries from other sources reach this account but not the tax list (listed below)."
    # Bills may post to a supplier's own payables account (e.g. AP - Trade), not only the default.
    payables = one(s.payables_account_id) | {a for (a,) in db.execute(select(Bill.payables_account_id).where(Bill.payables_account_id.is_not(None)).distinct())}
    all_accts = list(db.scalars(select(Account)))
    receivables_accts = one(s.receivables_account_id) | {
        a.id for a in all_accts
        if a.code == "0002-000" or (a.type == "asset" and a.name.strip().lower() in ("accounts receivable", "accounts receivable - trade"))
    }
    input_vat_accts = one(s.input_tax_account_id) | {a.id for a in all_accts if a.code.startswith(("1600-", "1601-", "1602-", "1603-")) or a.name.strip().lower().startswith("input vat")}
    ewt_accts = one(s.withholding_account_id) | {a.id for a in all_accts if a.code.startswith(("2302-", "2303-", "2304-", "2305-", "2306-", "2307-")) or "1601-e" in a.name.lower()}
    sub_links = _subledger_links(db)
    oojeema_ids = {eid for (eid,) in db.execute(select(JournalEntry.id).where(JournalEntry.source == "oojeema_gl", JournalEntry.status == "approved", JournalEntry.entry_date <= end))}
    closing_ids = _closing_entry_ids(db, oojeema_ids)
    checks = [
        check(db, "output_vat", "Output VAT", "Sales journal output VAT against the Output VAT account.",
              sales.get("taxCentavos", 0), one(s.output_tax_account_id), start, end, True, {"invoice", "credit_note"}, "Sales journal",
              [other, VOID_CAUSE], linked_ids=sub_links["invoice_sale"], closing_ids=closing_ids),
        check(db, "input_vat", "Input VAT", "Purchase journal input VAT (what SLP and 2550Q read) against the Input VAT account(s).",
              purchases["inputTaxCentavos"], input_vat_accts, start, end, False, {"bill", "petty_cash", "expense", "vendor_credit"}, "Purchase journal",
              [other, VOID_CAUSE, "Import VAT, or VAT on receipts recorded outside supplier bills, petty cash vouchers and imported expenses, never reaches the purchase lists."],
              linked_ids=sub_links["bill"], closing_ids=closing_ids),
        check(db, "ewt", "Tax withheld from suppliers (EWT)", "Purchase journal tax withheld (what QAP, 0619-E and 1601-EQ read) against the withholding tax payable account(s).",
              purchases["ewtCentavos"], ewt_accts, start, end, True, {"bill", "petty_cash", "expense", "vendor_credit"}, "Purchase journal / QAP",
              [other, VOID_CAUSE], linked_ids=sub_links["bill"], closing_ids=closing_ids),
        check(db, "cwt", "Tax withheld by customers (CWT)", "Cash receipts tax withheld (what SAWT reads) against the creditable withholding tax account.",
              receipts["cwtCentavos"], one(s.cwt_account_id), start, end, False, {"invoice"}, "Cash receipts / SAWT",
              [other, "A collection taken off in a later period: the books reverse it on the day it was taken off."],
              linked_ids=sub_links["invoice_collection"], closing_ids=closing_ids),
        check(db, "receivables", "What customers owe at the period's end", "Receivables aging as of the last day against the receivables account balance(s).",
              receivables_owed(db, end, zone), receivables_accts, None, end, False, {"invoice", "credit_note", "advance"}, "Receivables aging",
              [other, "Opening balances or adjustments posted to receivables without an invoice never appear in the aging."],
              linked_ids=sub_links["invoice_sale"] | sub_links["invoice_collection"], closing_ids=closing_ids),
        check(db, "payables", "What we owe suppliers at the period's end", "Payables aging as of the last day against the payables account balance(s).",
              payables_owed(db, end), payables, None, end, True, {"bill", "voucher", "vendor_credit", "advance"}, "Payables aging",
              [other, "Opening balances, or supplier payments recorded by journal entry instead of a voucher, never appear in the aging (Oojeema's own AP aging is about 16% above its ledger for this reason)."],
              linked_ids=sub_links["bill"] | sub_links["voucher"], closing_ids=closing_ids),
    ]
    counts = {k: sum(1 for c in checks if c["status"] == k) for k in ("agrees", "differs", "not_set")}
    return {"from": start.isoformat(), "to": end.isoformat(), "checks": checks, "counts": counts,
            "withholdingReview": withholding_review(db, start, end),
            "tampAudit": tamp_audit(db, start, end),
            "note": "Read-only. A difference isn't automatically an error in either: it says where a return built from the tax lists "
                    "would disagree with the books, and why. Treatment questions go to Sir Mel."}
