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

from app import bir_reports as bir
from app.ledger import settings as posting_settings
from app.models import Account, Bill, ImportedExpense, ImportedExpenseLine, JournalEntry, JournalLine, PettyCashVoucher

SOURCE_NAMES = {"invoice": "Sales invoices and collections", "bill": "Supplier bills", "voucher": "Payment vouchers",
                "fund": "Marketing requests and liquidations", "manual": "Journal entries typed by hand", "admin": "Setup",
                "pack": "Imported pack", "petty_cash": "Petty cash vouchers", "expense": "Imported expenses"}
ENTRIES_LISTED = 50


def lines_on(db: Session, accounts: set[str], start: date | None, end: date) -> list[tuple]:
    q = (select(JournalEntry, func.sum(JournalLine.debit_centavos), func.sum(JournalLine.credit_centavos))
         .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
         .where(JournalLine.account_id.in_(accounts), JournalEntry.status == "approved", JournalEntry.entry_date <= end)
         .group_by(JournalEntry.id).order_by(JournalEntry.entry_date, JournalEntry.number))
    if start is not None:
        q = q.where(JournalEntry.entry_date >= start)
    return [(e, int(d or 0), int(c or 0)) for e, d, c in db.execute(q)]


def check(db, key, title, says, list_figure, accounts, start, end, credit_normal, expected, list_name, causes):
    """One comparison. `start` None: the balance at `end` (aging); else the movement in the period."""
    found = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_(accounts)))} if accounts else {}
    if not found:
        return {"key": key, "title": title, "says": says, "status": "not_set", "listName": list_name, "listCentavos": list_figure,
                "booksCentavos": None, "differenceCentavos": None, "accounts": [], "otherSources": [], "causes": [],
                "message": "The account isn't set under Accounting → Default accounts, so the books can't be compared."}
    rows = lines_on(db, set(found), start, end)
    books = sum((c - d) if credit_normal else (d - c) for _, d, c in rows)
    others: dict[str, dict] = {}
    for e, d, c in rows:
        if e.source in expected:
            continue
        o = others.setdefault(e.source, {"source": e.source, "name": SOURCE_NAMES.get(e.source, e.source), "entries": 0, "centavos": 0, "listed": []})
        o["entries"] += 1
        o["centavos"] += (c - d) if credit_normal else (d - c)
        if len(o["listed"]) < ENTRIES_LISTED:
            o["listed"].append({"id": e.id, "number": e.number, "date": e.entry_date.isoformat(), "memo": e.memo, "centavos": (c - d) if credit_normal else (d - c)})
    difference = list_figure - books
    return {"key": key, "title": title, "says": says, "status": "agrees" if difference == 0 else "differs", "listName": list_name,
            "listCentavos": list_figure, "booksCentavos": books, "differenceCentavos": difference,
            "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in found.values()],
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


VOID_CAUSE = ("A document voided in a later period: the tax list leaves it out of its own period, while the books keep "
              "it there and reverse it on the day it was voided. Which period should carry it is a question for Sir Mel.")


def readiness(db: Session, start: date, end: date, zone: ZoneInfo) -> dict:
    from app.payables_asof import total_owed_on as payables_owed
    from app.receivables_asof import total_owed_on as receivables_owed

    s = posting_settings(db)
    one = lambda account_id: {account_id} if account_id else set()  # noqa: E731
    sales = bir.sales_journal(db, start, end)["totals"]
    purchases = bir.purchase_journal(db, start, end)["totals"]
    receipts = bir.cash_receipts(db, start, end)["totals"]
    other = "Entries from other sources reach this account but not the tax list (listed below)."
    # Bills may post to a supplier's own payables account (e.g. AP - Trade), not only the default.
    payables = one(s.payables_account_id) | {a for (a,) in db.execute(select(Bill.payables_account_id).where(Bill.payables_account_id.is_not(None)).distinct())}
    checks = [
        check(db, "output_vat", "Output VAT", "Sales journal output VAT against the Output VAT account.",
              sales.get("taxCentavos", 0), one(s.output_tax_account_id), start, end, True, {"invoice"}, "Sales journal",
              [other, VOID_CAUSE]),
        check(db, "input_vat", "Input VAT", "Purchase journal input VAT (what SLP and 2550Q read) against the Input VAT account.",
              purchases["inputTaxCentavos"], one(s.input_tax_account_id), start, end, False, {"bill", "petty_cash", "expense"}, "Purchase journal",
              [other, VOID_CAUSE, "Import VAT, or VAT on receipts recorded outside supplier bills, petty cash vouchers and imported expenses, never reaches the purchase lists."]),
        check(db, "ewt", "Tax withheld from suppliers (EWT)", "Purchase journal tax withheld (what QAP, 0619-E and 1601-EQ read) against the withholding tax payable account.",
              purchases["ewtCentavos"], one(s.withholding_account_id), start, end, True, {"bill", "petty_cash", "expense"}, "Purchase journal / QAP",
              [other, VOID_CAUSE]),
        check(db, "cwt", "Tax withheld by customers (CWT)", "Cash receipts tax withheld (what SAWT reads) against the creditable withholding tax account.",
              receipts["cwtCentavos"], one(s.cwt_account_id), start, end, False, {"invoice"}, "Cash receipts / SAWT",
              [other, "A collection taken off in a later period: the books reverse it on the day it was taken off."]),
        check(db, "receivables", "What customers owe at the period's end", "Receivables aging as of the last day against the receivables account balance.",
              receivables_owed(db, end, zone), one(s.receivables_account_id), None, end, False, {"invoice"}, "Receivables aging",
              [other, "Opening balances or adjustments posted to receivables without an invoice never appear in the aging."]),
        check(db, "payables", "What we owe suppliers at the period's end", "Payables aging as of the last day against the payables account balance(s).",
              payables_owed(db, end), payables, None, end, True, {"bill", "voucher"}, "Payables aging",
              [other, "Opening balances, or supplier payments recorded by journal entry instead of a voucher, never appear in the aging (Oojeema's own AP aging is about 16% above its ledger for this reason)."]),
    ]
    counts = {k: sum(1 for c in checks if c["status"] == k) for k in ("agrees", "differs", "not_set")}
    return {"from": start.isoformat(), "to": end.isoformat(), "checks": checks, "counts": counts,
            "withholdingReview": withholding_review(db, start, end),
            "note": "Read-only. A difference isn't automatically an error in either: it says where a return built from the tax lists "
                    "would disagree with the books, and why. Treatment questions go to Sir Mel."}
