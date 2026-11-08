"""Importing Oojeema's Sales Journal, and Zoho expenses (2026-10-31, Plans/Plan - Q1 imports per area).
Made-up data only. Runs on SQLite and, with FINANCE_TEST_POSTGRES_ADMIN_URL, on a throwaway PostgreSQL database."""

import datetime

from sqlalchemy import func, select

from app.business_events import OutboxEvent
from app.ledger import settings as posting_settings
from app.models import ImportedExpense, ImportLink, ImportRecord, Invoice, InvoicePayment, InvoiceSeries, JournalEntry

from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_dashboard import VIEW, person
from .test_invoices import ready
from .test_payables import account
from .test_tax_api import ana, client  # noqa: F401 (fixtures)
from .test_zoho_import import confirm, csv_file, matches, propose

ROLE = ["invoices.view", "invoices.collect", "invoices.void", "invoices.create", "bir.view", "journal.view", "petty_cash.view", "petty_cash.void", "bills.view"]
HEADER = ["Transaction Date", "Customer Name", "Customer Tin", "Description", "SI/BI No", "Reference No", "Amount", "Discount", "Output VAT", "Vatable Sales",
          "Sales to Government", "VAT Exempt Sales", "Zero-Rated Sales", "Non-VAT Sales"]


def quoted(cells):
    return ",".join('"' + str(c).replace('"', '""') + '"' for c in cells)


def sale(si="SI0001", on="Jan 10, 2026", amount="112.00", vat="12.00", vatable="100.00", exempt="0.00", name="Synthetic Hospital", tin="111-222-333-00000", discount="0.00",
         government="0.00", zero="0.00", nonvat="0", reference="INV-1", description="SO-1"):
    return [on, name, tin, description, si, reference, amount, discount, vat, vatable, government, exempt, zero, nonvat]


RECEIPT_HEADER = ["Transaction Date", "CR/OR No.", "Customer Name", "Customer Address", "Customer TIN", "RV No", "INV No", "Account Name (DR)", "Cash Amount", "Check Amount",
                  "Other Charges", "CWT", "Overpayment", "Accounts Receivable"]
BANK = "Cash in Bank - Synthetic 001234567890"


def receipt(cr="COL0001", si="SI0001", on="Feb 01, 2026", cash="112.00", check="0.00", other="0.00", cwt="0.00", over="0.00", ar="112.00", name="Synthetic Hospital", account=BANK, rv="RV0001"):
    return [on, cr, name, "Synthetic Address", "111-222-333-00000", rv, si, account, cash, check, other, cwt, over, ar]


def report(title, header, rows, name, trade="2MG INCORPORATED"):
    top = [["TAXPAYER TRADE NAME", trade, "", "", "", "", "", "", "", "", "", "OOJEEMA PRO", "Date Generated:", "2026-10-31"], ["TAXPAYER NAME", "  "], ["VAT-REG TIN ", "000-000-000-00000"],
           ["TAXPAYER ADDRESS", "Synthetic Address"], [], [title], []]
    return {"name": name, "content": "\n".join(quoted(r) for r in [*top, header, *rows]) + "\n"}


def journal(*rows, receipts=(), trade="2MG INCORPORATED", header=HEADER):
    """Both journals, as the import takes them."""
    return [report("SALES JOURNAL", header, rows or (sale(),), "SalesJournal.csv", trade), report("Receipt Journal", RECEIPT_HEADER, receipts, "ReceiptJournal.csv")]


def expense_row(zoho_id="e1", number="E1", vendor="Synthetic Store", cost="2MGCC", account_name="Courier", amount="112.00", tax="12.00", total="112.00", tax_name="Vat", rate="12.00",
                inclusive="true", kind="Services", on="2026-01-15", **extra):
    return {"Expense Reference ID": zoho_id, "Expense Date": on, "Entry Number": number, "Vendor": vendor, "Currency Code": "PHP", "Total": total, "Expense Amount": amount, "Tax Amount": tax,
            "Tax Name": tax_name, "Tax Percentage": rate, "Is Inclusive Tax": inclusive, "Is Reimbursable": "false", "Expense Account": account_name, "Expense Account Code": "",
            "Paid Through": "Synthetic Fund", "Paid Through Account Code": "", "CF.Cost Centre": cost, "CF.Type": kind, "Reference#": "PCV-9", "CF.Voucher": "V-9", "CF.PIC": "Someone", "CF.Department": "Finance", **extra}


def expense_pack(rows=None):
    return [csv_file("Expense.csv", rows or [expense_row()])]


def people(client, ana):
    """Cristal proposes and imports; Malou confirms companies, accounts and money; Rommel confirms tax labels."""
    return {"cristal": person(client, ana, "Finance Deputy", VIEW + ROLE + ["imports.propose", "imports.run"]),
            "malou": person(client, ana, "Finance Head", VIEW + ROLE + ["imports.confirm"]),
            "rommel": person(client, ana, "BIR and Compliance", VIEW + ROLE + ["imports.confirm_tax"])}


def load(client, who, files):
    r = client.post("/finance/imports/matching/load", json={"files": files}, headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def done(client, t, m, **body):
    return confirm(client, t["malou"], propose(client, t["cristal"], m, **body))


def sales_ready(client, ana):
    t = people(client, ana)
    ready(client, ana)
    return t


def expenses_matched(client, ana, files=None):
    t = sales_ready(client, ana)
    files = files or expense_pack()
    assert load(client, t["cristal"], files)["pack"] == "expenses"
    for m in matches(client, t["cristal"]).values():
        if m["status"] == "confirmed":
            continue
        if m["section"] == "company":
            done(client, t, m, company="2mg" if m["sourceLabel"].startswith("2MG") else "gpi")
        elif m["role"] == "paid_through":
            done(client, t, m, accountId=account(client, ana, "1010"))
        elif m["section"] == "account":
            done(client, t, m, accountId=account(client, ana, "6500"), purchaseType="services")
        elif m["section"] == "tax":
            confirm(client, t["rommel"], propose(client, t["cristal"], m, vatKind="exempt"))
    return t, files


def preview(client, who, kind, files, expect=200):
    r = client.post(f"/finance/imports/{kind}/preview", json={"files": files}, headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def run(client, who, kind, files, plan_key, expect=200):
    r = client.post(f"/finance/imports/{kind}", json={"files": files, "planKey": plan_key}, headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def go(client, who, kind, files):
    return run(client, who, kind, files, preview(client, who, kind, files)["planKey"])


def rows(plan):
    return {r["sourceId"]: r for r in plan["rows"]}


def held(plan, source_id, words):
    row = rows(plan)[source_id]
    assert row["outcome"] == "held" and any(words in x for x in row["reasons"]), row
    return row


def balanced(db):
    for e in db.scalars(select(JournalEntry)):
        assert sum(ln.debit_centavos for ln in e.lines) == sum(ln.credit_centavos for ln in e.lines) > 0


KIND = "oojeema-sales"


def test_each_si_posts_once_with_its_own_number_columns_and_tin_and_no_series(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002", amount="150.00", vat="6.00", vatable="50.00", exempt="94.00", tin=""))
    p = preview(client, t["cristal"], KIND, files)
    assert p["counts"]["ready"] == 2 and p["figures"]["amountCentavos"] == 26200 and p["figures"]["vatCentavos"] == 1800, p
    assert "due dates" in p["notice"]
    with app.state.sessions() as db:
        series_before = db.scalar(select(InvoiceSeries.next_number))
        events_before = db.scalar(select(func.count()).select_from(OutboxEvent))
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        inv = db.scalar(select(Invoice).where(Invoice.number == "SI0001"))
        assert inv.status == "issued" and inv.series_id is None and inv.customer_tin == "111-222-333-00000" and inv.customer_id is None
        assert (inv.total_centavos, inv.tax_centavos, inv.paid_centavos, inv.reference) == (11200, 1200, 0, "INV-1") and "SO-1" in inv.notes
        assert db.scalar(select(Invoice.customer_tin).where(Invoice.number == "SI0002")) is None  # blank stays blank
        assert db.scalar(select(InvoiceSeries.next_number)) == series_before  # no number taken
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == events_before  # no other app is told
        e = db.get(JournalEntry, inv.entry_id)
        assert e.source == "invoice" and e.status == "approved"
        s = posting_settings(db)
        assert {(ln.account_id, ln.debit_centavos, ln.credit_centavos) for ln in e.lines} == {(s.receivables_account_id, 11200, 0), (s.sales_account_id, 0, 10000), (s.output_tax_account_id, 0, 1200)}
        records = {r.source_id: (r.source, r.outcome) for r in db.scalars(select(ImportRecord))}
        assert records == {"SI0001": ("oojeema", "created"), "SI0002": ("oojeema", "created")}
        assert db.scalar(select(func.count()).select_from(ImportLink)) == 2
        assert db.scalar(select(func.count()).select_from(InvoicePayment)) == 0
        balanced(db)
    # The same file again: already imported, nothing new, and an old preview can't be replayed.
    again = preview(client, t["cristal"], KIND, files)
    assert again["counts"]["imported"] == 2 and again["counts"]["ready"] == 0
    run(client, t["cristal"], KIND, files, p["planKey"], expect=409)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 2


def test_rows_outside_the_quarter_are_skipped_with_their_reason(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0009", on="Dec 30, 2025"))
    p = preview(client, t["cristal"], KIND, files)
    assert rows(p)["SI0009"]["outcome"] == "skipped" and "outside" in rows(p)["SI0009"]["reasons"][0]
    go(client, t["cristal"], KIND, files)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 1
        assert db.scalar(select(ImportRecord.outcome).where(ImportRecord.source_id == "SI0009")) == "skipped"


def test_each_hold_says_why(client, ana, app):
    t = sales_ready(client, ana)
    with app.state.sessions() as db:
        db.add(Invoice(status="issued", number="SI0007", customer_name="X", invoice_date=datetime.date(2026, 1, 1), created_by="x"))
        db.commit()
    files = journal(
        sale(),
        sale("SI0002", amount="113.00"),  # doesn't add up
        sale("SI0003", amount="212.00", vat="12.00", vatable="200.00"),  # VAT isn't 12% of VATable
        sale("SI0004", amount="89.60", discount="22.40", vat="0.00", vatable="0.00", exempt="89.60"),
        sale("SI0005", amount="112.00", vat="12.00", vatable="0.00", government="100.00"),
        sale("SI0006", amount="50.00", vat="0.00", vatable="0.00", nonvat="50.00"),
        sale("SI0007"),  # the number is already in Finance
        sale("SI000105"),  # with the series' prefix: not this series' number
        sale("SI-000102"),  # inside Finance's series
    )
    p = preview(client, t["cristal"], KIND, files)
    assert rows(p)["SI0001"]["outcome"] == "ready"
    held(p, "SI0002", "don't add up")
    held(p, "SI0003", "isn't 12%")
    held(p, "SI0004", "discount")
    held(p, "SI0005", "sale to government")
    held(p, "SI0006", "Non-VAT")
    held(p, "SI0007", "already in Finance")
    held(p, "SI-000102", "inside Finance's series")
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.number == "SI0002")) == 0
        balanced(db)


def test_a_reversal_voids_its_invoice_on_the_reversal_date(client, ana, app):
    t = sales_ready(client, ana)
    negative = dict(amount="-112.00", vat="-12.00", vatable="-100.00", exempt="-0.00")
    files = journal(sale("SI0001"), sale("SI0001", on="Mar 05, 2026", **negative), sale("SI0002"))
    p = preview(client, t["cristal"], KIND, files)
    assert rows(p)["SI0001"]["outcome"] == "ready" and p["figures"]["amountCentavos"] == 22400
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        inv = db.scalar(select(Invoice).where(Invoice.number == "SI0001"))
        assert inv.status == "void" and inv.invoice_date.isoformat() == "2026-01-10" and "2026-03-05" in inv.void_reason
        e = db.get(JournalEntry, inv.entry_id)
        back = db.get(JournalEntry, e.reversed_by_id)
        assert e.entry_date.isoformat() == "2026-01-10" and back.entry_date.isoformat() == "2026-03-05" and back.status == "approved"
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.number == "SI0001")) == 1
        balanced(db)
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r


def test_a_negative_row_needs_its_exact_original_or_it_is_held(client, ana, app):
    t = sales_ready(client, ana)
    negative = dict(amount="-112.00", vat="-12.00", vatable="-100.00")
    files = journal(
        sale("SI0001", on="Jan 12, 2026", **negative),  # no original here
        sale("SI0002"), sale("SI0002", on="Feb 01, 2026", amount="-100.00", vat="0.00", vatable="-100.00"),  # not the same amounts
        sale("SI0003"), sale("SI0003"),  # repeats, nothing explains it
        sale("SI0004", on="Jan 12, 2026"), sale("SI0004", on="Jan 11, 2026", **negative),  # reversed before it was issued
        sale("SI0005"), sale("SI0005", on="Feb 02, 2026", name="Someone Else", **negative),
        sale("SI0006", on="Dec 20, 2025"), sale("SI0006", on="Jan 05, 2026", **negative),  # its original is before the quarter
    )
    p = preview(client, t["cristal"], KIND, files)
    held(p, "SI0001", "no original in this file")
    held(p, "SI0002", "doesn't exactly undo")
    held(p, "SI0003", "repeats")
    held(p, "SI0004", "doesn't exactly undo")
    held(p, "SI0005", "doesn't exactly undo")
    held(p, "SI0006", "outside the quarter too")
    assert p["counts"]["ready"] == 0


def test_bir_lists_read_imported_sales_and_readiness_agrees(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002", amount="50.00", vat="0.00", vatable="0.00", exempt="50.00", tin=""))
    go(client, t["cristal"], KIND, files)
    q = {"year": 2026, "quarter": 1}
    journal_book = client.get("/finance/bir/books/sales-journal", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"])
    assert journal_book.status_code == 200, journal_book.text
    totals = journal_book.json()["totals"]
    assert totals["grossCentavos"] == 16200 and totals["taxCentavos"] == 1200 and totals["exemptSalesCentavos"] == 5000 and totals["taxableSalesCentavos"] == 10000
    sls = client.get("/finance/bir/lists/sls", params=q, headers=t["cristal"]).json()
    assert sls["totals"]["outputTaxCentavos"] == 1200 and sls["missingTin"] == 1
    vat = {x["key"]: x["amountCentavos"] for x in client.get("/finance/bir/returns/vat", params=q, headers=t["cristal"]).json()["lines"] if "amountCentavos" in x}
    assert vat["taxable"] == 10000 and vat["output"] == 1200 and vat["exempt"] == 5000
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0 and r["counts"]["not_set"] == 0, r


def test_an_imported_invoice_shows_where_it_came_from_and_cant_be_reissued(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002"))
    go(client, t["cristal"], KIND, files)
    with app.state.sessions() as db:
        one = db.scalar(select(Invoice).where(Invoice.number == "SI0001")).id
        two = db.scalar(select(Invoice).where(Invoice.number == "SI0002")).id
    seen = client.get(f"/finance/invoices/{one}", headers=t["cristal"]).json()
    assert seen["imported"]["source"] == "oojeema" and seen["imported"]["sourceId"] == "SI0001" and seen["imported"]["file"] == "SalesJournal.csv"
    assert seen["entryId"] and seen["imported"]["by"] == "Finance Deputy" and seen["series"] is None
    assert seen["computed"]["lines"][0]["totalCentavos"] == 11200 and seen["computed"]["buyer"]["tin"] == "111-222-333-00000"
    assert client.get("/finance/invoices?limit=5", headers=t["cristal"]).json()["items"][0]["imported"]
    assert client.post(f"/finance/invoices/{one}/reissue", json={"reason": "Wrong one"}, headers=t["cristal"]).status_code == 409
    # A payment works as on any invoice, tells no other app, and a void needs it off first.
    with app.state.sessions() as db:
        events = db.scalar(select(func.count()).select_from(OutboxEvent))
    r = client.post(f"/finance/invoices/{one}/payments", json={"paidOn": "2026-02-02", "amountCentavos": 11200, "method": "cash"}, headers=t["cristal"])
    assert r.status_code == 201, r.text
    assert client.post(f"/finance/invoices/{one}/void", json={"reason": "Wrong one"}, headers=t["cristal"]).status_code == 409
    voided = client.post(f"/finance/invoices/{two}/void", json={"reason": "Wrong one"}, headers=t["cristal"])
    assert voided.status_code == 200 and voided.json()["number"] == "SI0002"
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == events
        balanced(db)


def test_a_closed_period_holds_rather_than_stopping_the_run(client, ana, app):
    t = sales_ready(client, ana)
    with app.state.sessions() as db:
        posting_settings(db).locked_until = datetime.date(2026, 1, 31)
        db.commit()
    p = preview(client, t["cristal"], KIND, journal(sale(), sale("SI0002", on="Feb 05, 2026")))
    held(p, "SI0001", "books are closed")
    assert rows(p)["SI0002"]["outcome"] == "ready"


def test_only_the_2mg_sales_journal_is_read(client, ana, app):
    t = sales_ready(client, ana)
    r = client.post(f"/finance/imports/{KIND}/preview", json={"files": journal(trade="ANOTHER COMPANY")}, headers=t["cristal"])
    assert r.status_code == 422 and "2MG" in r.json()["detail"]
    r = client.post(f"/finance/imports/{KIND}/preview", json={"files": journal(header=[*HEADER[:-1], "Something else"])}, headers=t["cristal"])
    assert r.status_code == 422 and "Sales Journal" in r.json()["detail"]
    r = client.post(f"/finance/imports/{KIND}/preview", json={"files": journal()[:1]}, headers=t["cristal"])  # both, together
    assert r.status_code == 422 and "two files" in r.json()["detail"]


def deposit(client, ana, t, files, code="1010"):
    """The deposit accounts matched: the only labels these journals have."""
    assert load(client, t["cristal"], files)["pack"] == "oojeema"
    for m in matches(client, t["cristal"]).values():
        if m["section"] == "money" and m["status"] != "confirmed":
            done(client, t, m, accountId=account(client, ana, code))


def test_a_receipt_posts_one_payment_per_invoice_once_and_reaches_cash_receipts(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002"), receipts=[receipt(), receipt("COL0002", "SI0002", cash="0.00", check="112.00", rv="RV0002")])
    deposit(client, ana, t, files)
    p = preview(client, t["cristal"], KIND, files)
    assert p["parts"][1]["counts"]["ready"] == 2 and p["figures"]["cashCentavos"] == 22400, p
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        one, two = (db.scalar(select(InvoicePayment).join(Invoice).where(Invoice.number == n)) for n in ("SI0001", "SI0002"))
        assert (one.method, one.amount_centavos, one.paid_on.isoformat(), one.reference) == ("cash", 11200, "2026-02-01", "COL0001, RV0001") and two.method == "check"
        assert one.invoice.paid_centavos == 11200
        e = db.get(JournalEntry, one.entry_id)
        s = posting_settings(db)
        assert e.source == "invoice" and e.status == "approved"
        assert s.receivables_account_id in {ln.account_id for ln in e.lines if ln.credit_centavos}
        assert {r.source_id: r.outcome for r in db.scalars(select(ImportRecord).where(ImportRecord.kind == "receipt"))} == {"COL0001": "created", "COL0002": "created"}
        balanced(db)
    books = client.get("/finance/bir/books/cash-receipts", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"])
    assert books.status_code == 200, books.text
    assert books.json()["totals"]["cashCentavos"] == 22400
    again = preview(client, t["cristal"], KIND, files)
    assert again["parts"][1]["counts"]["imported"] == 2 and again["counts"]["ready"] == 0
    run(client, t["cristal"], KIND, files, p["planKey"], expect=409)
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r


def test_a_receipt_with_several_invoices_links_each_by_its_exact_number(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002", amount="56.00", vat="6.00", vatable="50.00"), receipts=[receipt(), receipt(si="SI0002", cash="50.00", ar="50.00")])
    deposit(client, ana, t, files)
    go(client, t["cristal"], KIND, files)
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(InvoicePayment)) == 2
        partly = db.scalar(select(Invoice).where(Invoice.number == "SI0002"))
        assert partly.paid_centavos == 5000 and partly.total_centavos - partly.paid_centavos == 600


def test_cwt_posts_with_no_atc_and_reaches_sawt(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(receipts=[receipt(cash="110.00", cwt="2.00")])
    deposit(client, ana, t, files)
    go(client, t["cristal"], KIND, files)
    with app.state.sessions() as db:
        pay = db.scalar(select(InvoicePayment))
        assert (pay.amount_centavos, pay.cwt_centavos, pay.cwt_atc) == (11000, 200, None)  # none invented
        assert pay.invoice.paid_centavos == 11200
    sawt = client.get("/finance/bir/lists/sawt", params={"year": 2026, "quarter": 1}, headers=t["cristal"]).json()
    assert sawt["totals"]["withheldCentavos"] == 200 and sawt["rows"][0]["atc"] is None
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r


def test_a_receipt_with_any_row_it_cant_post_is_held_whole(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0009", on="Dec 20, 2025"), receipts=[
        receipt("COL0001", "SI0001"), receipt("COL0001", "SI0009", cash="50.00", ar="50.00"),  # one row settles a December invoice
        receipt("COL0002", "SI0099", cash="50.00", ar="50.00"),  # older than the file
    ])
    deposit(client, ana, t, files)
    p = preview(client, t["cristal"], KIND, files)
    held(p, "COL0001", "older invoice; it needs opening balances")
    held(p, "COL0002", "older invoice; it needs opening balances")
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(InvoicePayment)) == 0  # half a receipt isn't posted
        assert db.scalar(select(func.count()).select_from(Invoice).where(Invoice.number == "SI0009")) == 0  # December isn't made an invoice


def test_held_receipts_each_say_why(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(sale(), sale("SI0002"), sale("SI0003"), sale("SI0004"), sale("SI0005"), sale("SI0006"), sale("SI0007"), sale("SI0008"), sale("SI0008", on="Mar 01, 2026", amount="-112.00", vat="-12.00", vatable="-100.00"), sale("SI0009", amount="113.00"), receipts=[
        receipt("OVER", "SI0001", cash="120.00", over="8.00"),
        receipt("OTHER", "SI0002", cash="110.00", other="2.00"),
        receipt("SUM", "SI0003", cash="100.00"),
        receipt("BOTH", "SI0004", cash="56.00", check="56.00"),
        receipt("LATE", "SI0005", on="Apr 01, 2026"),
        receipt("FIRST", "SI0006", on="Jan 02, 2026"),  # before its invoice
        receipt("NEG", "SI0007", cash="-112.00", ar="-112.00"),
        receipt("GONE", "SI0008"),  # its invoice was cancelled
        receipt("WAIT", "SI0009", cash="113.00", ar="113.00"),  # its invoice is held
    ])
    deposit(client, ana, t, files)
    p = preview(client, t["cristal"], KIND, files)
    held(p, "OVER", "overpayment")
    held(p, "OTHER", "Other Charges")
    held(p, "SUM", "don't add up")
    held(p, "BOTH", "both cash and a check")
    held(p, "LATE", "outside January 1")
    held(p, "FIRST", "before its invoice")
    held(p, "NEG", "negative row")
    held(p, "GONE", "cancelled in Oojeema")
    held(p, "WAIT", "Its invoice is held")
    assert p["parts"][1]["counts"]["ready"] == 0


def test_payments_over_an_invoice_are_all_held(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(receipts=[receipt("COL0001", cash="80.00", ar="80.00"), receipt("COL0002", cash="80.00", ar="80.00")])
    deposit(client, ana, t, files)
    p = preview(client, t["cristal"], KIND, files)
    held(p, "COL0001", "more than is owed")
    held(p, "COL0002", "more than is owed")


def test_a_cancelled_receipt_is_posted_then_taken_off_on_its_own_date(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(receipts=[receipt(), receipt(on="Mar 03, 2026", cash="-112.00", ar="-112.00")])
    deposit(client, ana, t, files)
    p = preview(client, t["cristal"], KIND, files)
    assert rows(p)["COL0001"]["outcome"] == "ready" and p["figures"]["cashCentavos"] == 0, p
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        pay = db.scalar(select(InvoicePayment))
        assert pay.removed_at.date().isoformat() == "2026-03-03" and pay.invoice.paid_centavos == 0
        e = db.get(JournalEntry, pay.entry_id)
        assert e.entry_date.isoformat() == "2026-02-01" and db.get(JournalEntry, e.reversed_by_id).entry_date.isoformat() == "2026-03-03"
        balanced(db)
    books = client.get("/finance/bir/books/cash-receipts", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert books["totals"]["cashCentavos"] == 0  # taken off, as Finance's list reads a payment taken off
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r


def test_deposit_accounts_need_a_confirmed_match_and_never_keep_a_bank_number(client, ana, app):
    t = sales_ready(client, ana)
    files = journal(receipts=[receipt()])
    p = preview(client, t["cristal"], KIND, files)
    held(p, "COL0001", "Deposit account")
    assert "001234567890" not in str(p)
    load(client, t["cristal"], files)
    assert "001234567890" not in client.get("/finance/imports/matching", headers=t["cristal"]).text
    m = next(x for x in matches(client, t["cristal"]).values() if x["section"] == "money")
    assert m["status"] == "open" and m["sourceLabel"].endswith("7890")  # enough to tell them apart
    held(preview(client, t["cristal"], KIND, files), "COL0001", "Deposit account")  # a proposal isn't enough
    propose(client, t["cristal"], m, accountId=account(client, ana, "1010"))
    held(preview(client, t["cristal"], KIND, files), "COL0001", "Deposit account")
    assert client.put(f"/finance/imports/matching/{m['id']}", json={"accountId": "missing-account"}, headers=t["malou"]).status_code == 422  # unknown accounts still refused
    confirm(client, t["malou"], matches(client, t["cristal"])[("money", m["sourceLabel"])])
    assert rows(preview(client, t["cristal"], KIND, files))["COL0001"]["outcome"] == "ready"
    r = client.post(f"/finance/imports/matching/{m['id']}/records", json={"files": files}, headers=t["cristal"])
    assert r.status_code == 200 and r.json()["total"] == 1 and "001234567890" not in r.text
    with app.state.sessions() as db:
        from app.models import ImportMatch

        assert all("001234567890" not in x.source_label for x in db.scalars(select(ImportMatch)))


def test_expense_imports_once_and_posts_without_touching_petty_cash(client, ana, app):
    t, files = expenses_matched(client, ana)
    p = preview(client, t["cristal"], "expenses", files)
    assert p["counts"]["ready"] == 1, p
    run(client, t["cristal"], "expenses", files, p["planKey"])
    with app.state.sessions() as db:
        x = db.scalar(select(ImportedExpense))
        assert (x.net_centavos, x.vat_centavos, x.total_centavos, x.paid_out_centavos, x.status) == (10000, 1200, 11200, 11200, "posted")
        assert (x.vendor, x.reference, x.source_id, x.source_file) == ("Synthetic Store", "PCV-9", "e1", "Expense.csv")
        e = db.get(JournalEntry, x.entry_id)
        assert e.source == "expense" and e.status == "approved"
        balanced(db)
    assert preview(client, t["cristal"], "expenses", files)["counts"]["imported"] == 1
    run(client, t["cristal"], "expenses", files, p["planKey"], expect=409)
    assert client.get("/finance/petty-cash?show=all", headers=t["cristal"]).json()["counts"]["all"] == 0
    # Read-only: only reading and voiding exist.
    listed = client.get("/finance/imported-expenses", headers=t["cristal"]).json()
    assert listed["counts"]["posted"] == 1 and listed["totalCentavos"] == 11200
    one = client.get(f"/finance/imported-expenses/{listed['items'][0]['id']}", headers=t["cristal"]).json()
    assert one["source"]["zohoId"] == "e1" and one["source"]["file"] == "Expense.csv" and one["entryId"] and one["items"][0]["vatLabel"] == "VAT 12%"
    assert client.post("/finance/imported-expenses", json={}, headers=t["cristal"]).status_code == 405
    assert client.put(f"/finance/imported-expenses/{one['id']}", json={}, headers=t["cristal"]).status_code == 405


def test_held_expenses_each_say_why_and_the_other_company_is_skipped(client, ana, app):
    files = expense_pack([
        expense_row(),
        expense_row("gpi", "E2", cost="GetMEDSCC"),
        expense_row("sums", "E3", tax="11.00"),
        expense_row("blankv", "E4", vendor=""),
        expense_row("notaxv", "E5", vendor="", tax_name="No Tax", rate="0.00", tax="0.00"),
        expense_row("goods", "E6", kind="Goods"),
        expense_row("reimb", "E7", **{"Is Reimbursable": "true"}),
        expense_row("usd", "E8", **{"Currency Code": "USD"}),
    ])
    t, files = expenses_matched(client, ana, files)
    load(client, t["cristal"], files)
    p = preview(client, t["cristal"], "expenses", files)
    found = rows(p)
    assert found["e1"]["outcome"] == "ready" and found["gpi"]["outcome"] == "skipped"
    held(p, "sums", "Finance works this expense out as")
    held(p, "blankv", "names no vendor")
    assert found["notaxv"]["outcome"] == "ready"  # no VAT claimed: it comes in with the vendor blank, nothing made up
    held(p, "goods", "Zoho says Goods")
    held(p, "reimb", "reimbursable")
    held(p, "usd", "PHP")


def test_an_expense_with_no_confirmed_company_or_tax_stays_held(client, ana, app):
    t = people(client, ana)
    ready(client, ana)
    files = expense_pack([expense_row(), expense_row("blank", "E2", tax_name="", rate="", tax="0.00")])
    load(client, t["cristal"], files)
    p = preview(client, t["cristal"], "expenses", files)
    held(p, "e1", "Company label")
    held(p, "blank", "Tax label “blank” isn't matched")
    assert p["counts"]["ready"] == 0
    m = matches(client, t["cristal"])
    assert m[("company", "2MGCC")]["status"] == "open"  # a cost centre is confirmed by a person, never guessed from its name


def test_expenses_reach_the_purchase_lists_and_readiness_agrees(client, ana, app):
    t, files = expenses_matched(client, ana)
    go(client, t["cristal"], "expenses", files)
    q = {"year": 2026, "quarter": 1}
    slp = client.get("/finance/bir/lists/slp", params=q, headers=t["cristal"]).json()
    assert slp["totals"]["taxableCentavos"] == 10000 and slp["totals"]["inputTaxCentavos"] == 1200 and slp["rows"][0]["name"] == "Synthetic Store" and slp["missingTin"] == 1
    assert slp["totals"]["servicesCentavos"] == 10000
    vat = {x["key"]: x["amountCentavos"] for x in client.get("/finance/bir/returns/vat", params=q, headers=t["cristal"]).json()["lines"] if "amountCentavos" in x}
    assert vat["purchases"] == 10000 and vat["input"] == 1200
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r
    assert next(c for c in r["checks"] if c["key"] == "input_vat")["otherSources"] == []


def test_withholding_stated_on_an_expense_reaches_qap_and_2307(client, ana, app):
    files = expense_pack([expense_row(**{"TDS Name": "WC160", "TDS Amount": "2.00"}), expense_row("bad", "E2", **{"TDS Name": "Something", "TDS Amount": "2.00"}),
                          expense_row("off", "E3", **{"TDS Name": "WC160", "TDS Amount": "3.00"})])
    t, files = expenses_matched(client, ana, files)
    p = preview(client, t["cristal"], "expenses", files)
    assert rows(p)["e1"]["outcome"] == "ready", p
    held(p, "bad", "doesn't state an ATC")
    held(p, "off", "withheld; Zoho shows")
    run(client, t["cristal"], "expenses", files, p["planKey"])
    with app.state.sessions() as db:
        x = db.scalar(select(ImportedExpense))
        assert (x.withheld_centavos, x.paid_out_centavos) == (200, 11000)
        balanced(db)
    q = {"year": 2026, "quarter": 1}
    qap = client.get("/finance/bir/lists/qap", params=q, headers=t["cristal"]).json()
    assert qap["rows"][0]["atc"] == "WC160" and qap["totals"]["taxCentavos"] == 200
    r = client.get("/finance/bir/readiness", params={"start": "2026-01-01", "end": "2026-03-31"}, headers=t["cristal"]).json()
    assert r["counts"]["differs"] == 0, r
    payee = qap["rows"][0]["supplierId"]
    certificate = client.get("/finance/bir/withholding/2307", params={**q, "supplierId": payee}, headers=t["cristal"])
    assert certificate.status_code == 200, certificate.text
    assert certificate.json()["certificate"]["totals"]["taxCentavos"] == 200


def test_voiding_an_imported_expense_reverses_it_and_it_stays_imported(client, ana, app):
    t, files = expenses_matched(client, ana)
    go(client, t["cristal"], "expenses", files)
    x = client.get("/finance/imported-expenses", headers=t["cristal"]).json()["items"][0]
    assert client.post(f"/finance/imported-expenses/{x['id']}/void", json={"reason": "No"}, headers=t["cristal"]).status_code == 422
    plain = person(client, ana, "Reader", VIEW + ["petty_cash.view"])
    assert client.post(f"/finance/imported-expenses/{x['id']}/void", json={"reason": "Wrong record"}, headers=plain).status_code == 403
    r = client.post(f"/finance/imported-expenses/{x['id']}/void", json={"reason": "Wrong record"}, headers=t["cristal"])
    assert r.status_code == 200 and r.json()["status"] == "void"
    assert client.post(f"/finance/imported-expenses/{x['id']}/void", json={"reason": "Wrong record"}, headers=t["cristal"]).status_code == 409
    with app.state.sessions() as db:
        e = db.get(JournalEntry, db.scalar(select(ImportedExpense)).entry_id)
        assert e.reversed_by_id and db.get(JournalEntry, e.reversed_by_id).source == "expense"
        balanced(db)
    assert client.get("/finance/imported-expenses?show=void", headers=t["cristal"]).json()["counts"]["void"] == 1
    assert preview(client, t["cristal"], "expenses", files)["counts"]["imported"] == 1


def test_permissions_and_the_wrong_file(client, ana, app):
    t = sales_ready(client, ana)
    files = journal()
    assert client.post(f"/finance/imports/{KIND}/preview", json={"files": files}, headers=t["malou"]).status_code == 403  # may confirm, not import
    noview = person(client, ana, "Importer", ["imports.run"])
    assert client.post(f"/finance/imports/{KIND}/preview", json={"files": files}, headers=noview).status_code == 403  # needs to see invoices too
    assert client.post("/finance/imports/expenses/preview", json={"files": expense_pack()}, headers=noview).status_code == 403
    assert client.get("/finance/imported-expenses", headers=noview).status_code == 403
    assert preview(client, t["cristal"], KIND, expense_pack(), expect=422)
    assert preview(client, t["cristal"], "expenses", files, expect=422)


def test_the_official_site_refuses_and_changes_nothing(client, ana, app, monkeypatch):
    t = sales_ready(client, ana)
    files = journal()
    plan = preview(client, t["cristal"], KIND, files)["planKey"]
    monkeypatch.setattr(app.state.settings, "data_environment", "official")
    for path, body in ((f"{KIND}/preview", {"files": files}), (KIND, {"files": files, "planKey": plan}), ("expenses/preview", {"files": expense_pack()}), ("expenses", {"files": expense_pack(), "planKey": plan})):
        r = client.post(f"/finance/imports/{path}", json=body, headers=t["cristal"])
        assert r.status_code == 409 and "testing site" in r.json()["detail"]
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Invoice)) == 0
        assert db.scalar(select(func.count()).select_from(ImportedExpense)) == 0


def test_loading_one_export_leaves_the_others_rows_alone(client, ana, app):
    from .test_zoho_import import pack

    t = people(client, ana)
    load(client, t["cristal"], pack())
    before = {k: m["records"] for k, m in matches(client, t["cristal"]).items()}
    load(client, t["cristal"], expense_pack())
    after = matches(client, t["cristal"])
    assert all(after[k]["records"] == n for k, n in before.items())


def test_oojeema_can_match_non_cash_accounts_without_importing_a_false_deposit(client, ana, app):
    from app.models import Account
    t = sales_ready(client, ana)
    with app.state.sessions() as db:
        expense = Account(code="TEST-PEN", name="Penalties Expense", type="expense", is_active=True)
        liability = Account(code="TEST-LIAB", name="Synthetic settlement liability", type="liability", is_active=True)
        inactive = Account(code="TEST-OFF", name="Inactive settlement", type="expense", is_active=False)
        db.add_all([expense, liability, inactive]); db.commit()
        expense_id, liability_id, inactive_id = expense.id, liability.id, inactive.id
    files = journal(sale(), receipts=[receipt(account="Penalties Expense")])
    load(client, t["cristal"], files)
    sheet = client.get("/finance/imports/matching", headers=t["cristal"]).json()
    choices = {a["id"] for a in sheet["choices"]["receiptAccounts"]}
    assert expense_id in choices and liability_id in choices and inactive_id not in choices
    assert expense_id not in {a["id"] for a in sheet["choices"]["moneyAccounts"]}
    m = next(m for m in sheet["matches"] if m["role"] == "deposit_to")
    bad = client.put(f"/finance/imports/matching/{m['id']}", json={"accountId": inactive_id}, headers=t["cristal"])
    assert bad.status_code == 422
    done(client, t, m, accountId=expense_id)
    p = preview(client, t["cristal"], KIND, files)
    held(p, "COL0001", "non-cash")
    run(client, t["cristal"], KIND, files, p["planKey"])
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(InvoicePayment)) == 0
        inv = db.scalar(select(Invoice).where(Invoice.number == "SI0001"))
        assert inv.paid_centavos == 0
        assert not db.scalar(select(func.count()).select_from(JournalEntry).join(JournalEntry.lines).where(JournalEntry.lines.property.mapper.class_.account_id == expense_id))


def test_supplier_payment_matching_still_refuses_non_cash_accounts(client, ana, app):
    from .test_zoho_import import pack, staff
    t = staff(client, ana)
    files = pack()
    load(client, t["cristal"], files)
    m = next(x for x in matches(client, t["cristal"]).values() if x["role"] == "paid_from")
    r = client.put(f"/finance/imports/matching/{m['id']}", json={"accountId": account(client, ana, "6500")}, headers=t["malou"])
    assert r.status_code == 422 and "CASH" in r.json()["detail"]
