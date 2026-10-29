"""Import matching and importing Zoho bills and supplier payments (2026-10-29,
Plans/Plan - Import matching and first bill import). Made-up data only.

Runs on SQLite and, with FINANCE_TEST_POSTGRES_ADMIN_URL, on a throwaway PostgreSQL database
(official Finance runs on PostgreSQL)."""

import io
import csv

from sqlalchemy import func, select

from app.models import Bill, ImportRecord, JournalEntry, PaymentVoucher, ZohoDelivery

from .test_concurrent_saves import app  # noqa: F401 (the SQLite / PostgreSQL fixture)
from .test_dashboard import VIEW, person
from .test_payables import SUPPLIER, account, supplier
from .test_tax_api import ana, client  # noqa: F401 (fixtures)

PAYABLES = ["suppliers.view", "bills.view", "vouchers.view"]
NAME = "Synthetic Supplier Inc."


def csv_file(name, rows):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
    return {"name": name, "content": out.getvalue()}


def bill_row(bill_id, number, company="2MG", total="56.00", tax="6.00", item="50.00", tax_name="VAT", rate="12.00", account_name="Office Supplies"):
    return {"Bill ID": bill_id, "Bill Date": "2026-01-06", "Bill Number": number, "Vendor Name": NAME, "Bill Status": "Overdue",
            "Currency Code": "PHP", "CF.Company": company, "SubTotal": item, "Total": total, "Due Date": "2026-02-06",
            "Is Inclusive Tax": "false", "Account": account_name, "Account Code": "", "Accounts Payable": "Accounts Payable",
            "Item Name": "Synthetic cost", "Item Total": item, "Tax Amount": tax, "Tax Name": tax_name, "Tax Percentage": rate}


def payment_row(pay_id, bill_id, number, amount="28.00", withheld="0.00", mode="Bank Transfer"):
    return {"VendorPayment ID": pay_id, "Date": "2026-02-03", "Payment Number": number, "Vendor Name": NAME, "Payment Status": "Paid",
            "Currency Code": "PHP", "Amount": amount, "Unused Amount": "0.00", "Bank Charges": "0.00", "PIPayment ID": f"a-{pay_id}",
            "Bill ID": bill_id, "Bill Number": "x", "Mode": mode, "Bill Date": "2026-01-06", "Bill Payment Applied Date": "2026-02-03",
            "Bill Amount": amount, "Withholding Tax Amount": withheld, "Paid Through": "Synthetic Bank", "Paid Through Account Code": "",
            "Reference Number": "REF-1"}


def pack(bills=None, payments=None):
    bills = bills or [bill_row("b1", "SI-1"), bill_row("b2", "SI-2", company="Getmeds")]
    payments = payments or [payment_row("v1", "b1", "VP-1")]
    return [csv_file("Bill.csv", bills), csv_file("Vendor_Payment.csv", payments)]


def staff(client, ana):
    """Cristal proposes and imports; Malou confirms companies, accounts and money; Rommel confirms tax labels."""
    return {
        "cristal": person(client, ana, "Finance Deputy", VIEW + PAYABLES + ["imports.propose", "imports.run"]),
        "malou": person(client, ana, "Finance Head", VIEW + PAYABLES + ["imports.confirm"]),
        "rommel": person(client, ana, "BIR and Compliance", VIEW + PAYABLES + ["imports.confirm_tax"]),
    }


def matches(client, who):
    r = client.get("/finance/imports/matching", headers=who)
    assert r.status_code == 200, r.text
    return {(m["section"], m["sourceLabel"]): m for m in r.json()["matches"]}


def propose(client, who, m, **body):
    r = client.put(f"/finance/imports/matching/{m['id']}", json=body, headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def confirm(client, who, m, expect=200):
    r = client.post(f"/finance/imports/matching/{m['id']}/confirm", headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def matched(client, ana, files=None):
    """The made-up export loaded and every label proposed and confirmed by the right people."""
    t = staff(client, ana)
    supplier(client, ana, name=NAME)
    files = files or pack()
    r = client.post("/finance/imports/matching/load", json={"files": files}, headers=t["cristal"])
    assert r.status_code == 200, r.text
    m = matches(client, t["cristal"])
    expense, bank = account(client, ana, "6500"), account(client, ana, "1010")
    for (section, label), row in m.items():
        if row["status"] == "confirmed":  # filled in automatically (company labels, VAT 12%)
            continue
        if section == "account":
            confirm(client, t["malou"], propose(client, t["cristal"], row, accountId=expense, purchaseType="other_goods"))
        elif section == "tax":
            confirm(client, t["rommel"], propose(client, t["cristal"], row, vatKind="vat"))
        elif section == "money":
            confirm(client, t["malou"], propose(client, t["cristal"], row, accountId=bank))
    return t, files


def preview(client, who, kind, files):
    r = client.post(f"/finance/imports/{kind}/preview", json={"files": files}, headers=who)
    assert r.status_code == 200, r.text
    return r.json()


def run(client, who, kind, files, plan_key, expect=200):
    r = client.post(f"/finance/imports/{kind}", json={"files": files, "planKey": plan_key}, headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def test_loading_saves_each_label_once_and_nothing_is_matched_by_guess(client, ana, app):
    t = staff(client, ana)
    for _ in range(2):  # loading again updates counts, never duplicates
        r = client.post("/finance/imports/matching/load", json={"files": pack()}, headers=t["cristal"])
        assert r.status_code == 200, r.text
    m = matches(client, t["malou"])
    assert set(m) == {("company", "2MG"), ("company", "Getmeds"), ("account", "Office Supplies"), ("tax", "VAT"), ("money", "Synthetic Bank")}
    # What's already known is filled in; nothing else is chosen for Finance.
    assert m[("company", "2MG")]["company"] == "2mg" and m[("company", "Getmeds")]["company"] == "gpi"
    assert m[("tax", "VAT")]["vatKind"] == "vat" and m[("tax", "VAT")]["automatic"]
    assert m[("money", "Synthetic Bank")]["status"] == "open" and m[("money", "Synthetic Bank")]["accountId"] is None
    assert m[("account", "Office Supplies")]["status"] == "open"
    assert m[("company", "2MG")]["records"] == 1 and m[("company", "2MG")]["amountCentavos"] == 5600
    # A later export without a label: it stays, with 0 records.
    client.post("/finance/imports/matching/load", json={"files": pack(bills=[bill_row("b1", "SI-1")])}, headers=t["cristal"])
    m = matches(client, t["malou"])
    assert m[("company", "Getmeds")]["records"] == 0 and m[("company", "2MG")]["records"] == 1


def test_one_step_for_whoever_may_confirm_and_a_proposal_for_everyone_else(client, ana, app):
    t = staff(client, ana)
    files = pack(bills=[bill_row("b1", "SI-1", tax_name="No Tax", rate="0.00", tax="0.00", total="50.00")])
    client.post("/finance/imports/matching/load", json={"files": files}, headers=t["cristal"])
    m = matches(client, t["cristal"])
    bank, expense = account(client, ana, "1010"), account(client, ana, "6500")
    # Malou may confirm accounts and banks: her save is final, in one step.
    done = propose(client, t["malou"], m[("money", "Synthetic Bank")], accountId=bank)
    assert done["status"] == "confirmed" and done["confirmedBy"] == "Finance Head"
    # Cristal may only propose: hers waits; she can't confirm it, Malou can.
    waiting = propose(client, t["cristal"], m[("account", "Office Supplies")], accountId=expense, purchaseType="services")
    assert waiting["status"] == "proposed" and waiting["confirmedBy"] is None
    confirm(client, t["cristal"], waiting, expect=403)
    assert confirm(client, t["malou"], waiting)["status"] == "confirmed"
    # An unclear tax label is BIR and Compliance's call: Malou can't set it as final, Rommel can.
    tax = m[("tax", "No Tax")]
    assert tax["status"] == "open"  # not filled in: "No Tax" could be exempt, zero-rated or a non-VAT supplier
    r = client.put(f"/finance/imports/matching/{tax['id']}", json={"vatKind": "exempt"}, headers=t["malou"])
    assert r.status_code == 403  # no propose tick and not hers to confirm
    assert propose(client, t["rommel"], tax, vatKind="none")["status"] == "confirmed"


def test_bills_import_once_posting_like_any_bill_without_approvals_or_zoho_sending(client, ana, app):
    t, files = matched(client, ana)
    p = preview(client, t["cristal"], "bills", files)
    assert p["counts"] == {"ready": 1, "held": 0, "skipped": 1, "imported": 0}, p
    done = run(client, t["cristal"], "bills", files, p["planKey"])
    assert done["counts"]["ready"] == 1
    with app.state.sessions() as db:
        b = db.scalar(select(Bill).where(Bill.zoho_ref == "b1"))
        assert b.status == "recorded" and b.payable_centavos == 5600 and b.vat_centavos == 600 and b.approved_by is None
        assert b.lines[0]["purchaseType"] == "other_goods" and b.lines[0]["vat"] == "vat"
        assert [e.kind for e in b.events] == ["imported"]
        e = db.get(JournalEntry, b.entry_id)
        assert e.source == "bill" and sum(l.debit_centavos for l in e.lines) == sum(l.credit_centavos for l in e.lines) == 5600
        assert db.scalar(select(func.count()).select_from(ZohoDelivery)) == 0  # came from Zoho: never queued back
        assert db.scalar(select(func.count()).select_from(Bill).where(Bill.zoho_ref == "b2")) == 0  # GPI's
        outcomes = {r.source_id: r.outcome for r in db.scalars(select(ImportRecord))}
        assert outcomes == {"b1": "created", "b2": "skipped"}
    # The same files again: already imported, nothing new; an old preview can't be replayed.
    again = preview(client, t["cristal"], "bills", files)
    assert again["counts"]["imported"] == 1 and again["counts"]["ready"] == 0
    run(client, t["cristal"], "bills", files, p["planKey"], expect=409)


def test_supplier_payments_import_after_their_bills_and_pay_them(client, ana, app):
    t, files = matched(client, ana)
    early = preview(client, t["cristal"], "supplier-payments", files)
    assert early["counts"]["held"] == 1 and "isn't in Finance" in early["rows"][0]["reasons"][0]
    run(client, t["cristal"], "bills", files, preview(client, t["cristal"], "bills", files)["planKey"])
    p = preview(client, t["cristal"], "supplier-payments", files)
    assert p["counts"]["ready"] == 1, p
    run(client, t["cristal"], "supplier-payments", files, p["planKey"])
    with app.state.sessions() as db:
        v = db.scalar(select(PaymentVoucher).where(PaymentVoucher.zoho_ref == "v1"))
        b = db.scalar(select(Bill).where(Bill.zoho_ref == "b1"))
        assert v.status == "released" and v.total_centavos == 2800 and b.paid_centavos == 2800 and v.paid_on.isoformat() == "2026-02-03"
        assert "REF-1" in v.notes and v.bank_reference is None  # Zoho's reference is kept as said, not claimed as the bank's
        assert db.get(JournalEntry, v.entry_id).source == "voucher"
        assert db.scalar(select(func.count()).select_from(ZohoDelivery)) == 0


def test_unclear_records_are_held_with_their_reason_not_forced(client, ana, app):
    files = pack(
        bills=[bill_row("b1", "SI-1"), bill_row("b3", "SI-3", total="57.00"), bill_row("b4", "SI-4"), bill_row("b5", "SI-5", company="Unknown Co")],
        payments=[payment_row("v4", "b4", "VP-4", withheld="1.00"), payment_row("v6", "b1", "VP-6", mode="Check")],
    )
    t, files = matched(client, ana, files)
    rows = {r["sourceId"]: r for r in preview(client, t["cristal"], "bills", files)["rows"]}
    assert rows["b1"]["outcome"] == "ready"
    assert rows["b3"]["outcome"] == "held"  # Zoho's total doesn't come out of its own lines
    assert rows["b4"]["outcome"] == "held" and any("Sir Mel" in x for x in rows["b4"]["reasons"])  # tax withheld on its payment
    assert rows["b5"]["outcome"] == "held" and any("isn't confirmed" in x for x in rows["b5"]["reasons"])  # label still open
    run(client, t["cristal"], "bills", files, preview(client, t["cristal"], "bills", files)["planKey"])
    pays = {r["sourceId"]: r for r in preview(client, t["cristal"], "supplier-payments", files)["rows"]}
    assert pays["v4"]["outcome"] == "held" and any("withheld tax" in x for x in pays["v4"]["reasons"])
    assert pays["v6"]["outcome"] == "held" and any("check number" in x for x in pays["v6"]["reasons"])


def test_imports_need_the_run_tick_and_both_files(client, ana, app):
    t, files = matched(client, ana)
    r = client.post("/finance/imports/bills/preview", json={"files": files}, headers=t["malou"])
    assert r.status_code == 403
    r = client.post("/finance/imports/bills/preview", json={"files": [files[0], files[0]]}, headers=t["cristal"])
    assert r.status_code == 422


def test_the_official_site_refuses_imports_and_changes_nothing(client, ana, app, monkeypatch):
    t, files = matched(client, ana)
    monkeypatch.setattr(app.state.settings, "data_environment", "official")
    r = client.post("/finance/imports/bills/preview", json={"files": files}, headers=t["cristal"])
    assert r.status_code == 409 and "testing site" in r.json()["detail"]
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Bill).where(Bill.zoho_ref.is_not(None))) == 0
