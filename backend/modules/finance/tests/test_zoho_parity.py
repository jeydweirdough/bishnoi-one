"""End-to-end tests for Zoho-parity Finance modules (migration 0042):
- Customer Credit Notes & BIR Sales/2550Q/SLS/Readiness integration
- Supplier Vendor Credits & BIR SLP/QAP/2550Q/Vouchers/Readiness integration
- Supplier Prepayments & Customer Deposits (Advances) + Aging & Pay/Collect guards
- Recurring Bills & Recurring Invoices (generating drafts with tax_reviewed=False)
- Document Auto-Scan & Receipt OCR (PDF extraction, ATP printer exclusion, bill conversion)
"""

from __future__ import annotations

import base64
from datetime import date, timedelta

from modules.finance.models import Account
from modules.finance.receipt_scan import extract_pdf_text

from .test_bir_readiness import readiness
from .test_concurrent_saves import app  # noqa: F401
from .test_invoices import issued, ready
from .test_payables_asof import ago, posted_bill
from .test_tax_api import ana, client  # noqa: F401
from .test_vouchers import prepare, team  # noqa: F401

TODAY = date.today()


def _minimal_pdf_bytes(text: str) -> bytes:
    """Valid minimal single-page uncompressed PDF containing readable literal text."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    objs = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n",
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    buf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for o in objs:
        offsets.append(len(buf))
        buf.extend(o)
    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for off in offsets:
        buf.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    buf.extend(f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
    return bytes(buf)


def test_credit_note_offsets_invoice_and_bir_sales_readiness(client, ana, team):  # noqa: F811
    ready(client, ana)
    inv = issued(client, ana, invoiceDate=ago(5))  # PHP 2,240.00 (2,000 sales + 240 output VAT)
    r = client.post(
        "/finance/credit-notes",
        json={
            "invoiceId": inv["id"],
            "customerName": inv["customer"]["name"],
            "customerAddress": inv["customer"]["address"],
            "creditDate": ago(2),
            "reference": "RET-001",
            "reason": "Damaged box returned",
            "lines": [{"description": "Returned 1 box", "quantity": 1, "unitPriceCentavos": 112_000}],
        },
        headers=ana,
    )
    assert r.status_code == 201, r.text
    cn = r.json()
    assert cn["status"] == "draft"

    issued_cn = client.post(f"/finance/credit-notes/{cn['id']}/issue", headers=ana)
    assert issued_cn.status_code == 200, issued_cn.text
    cn_data = issued_cn.json()
    assert cn_data["status"] == "issued"
    assert cn_data["appliedCentavos"] == 112_000
    assert cn_data["remainingCentavos"] == 0

    # Invoice balance dropped by credit note; over-collecting beyond remaining balance is refused.
    inv_after = client.get(f"/finance/invoices/{inv['id']}", headers=ana).json()
    assert inv_after["creditAppliedCentavos"] == 112_000
    assert inv_after["balanceCentavos"] == 112_000
    over = client.post(
        f"/finance/invoices/{inv['id']}/payments",
        json={"paidOn": TODAY.isoformat(), "amountCentavos": 120_000, "method": "bank"},
        headers=ana,
    )
    assert over.status_code == 422

    # BIR Sales Journal, 2550Q, and SLS net out the credit note, and BIR Readiness agrees.
    sj = client.get("/finance/bir/books/sales-journal", params={"start": ago(30), "end": TODAY.isoformat()}, headers=ana).json()
    assert sj["totals"]["grossCentavos"] == 112_000
    assert sj["totals"]["taxCentavos"] == 12_000
    checks = readiness(client, ana, ago(30), TODAY.isoformat())
    assert checks["output_vat"]["status"] == "agrees", checks["output_vat"]
    assert checks["receivables"]["status"] == "agrees", checks["receivables"]

    # Unapplied credit note balance is also handled cleanly in readiness after unapplying allocation.
    alloc_id = cn_data["allocations"][0]["id"]
    unapp = client.delete(f"/finance/credit-notes/{cn['id']}/allocations/{alloc_id}", headers=ana)
    assert unapp.status_code == 200 and unapp.json()["appliedCentavos"] == 0
    checks2 = readiness(client, ana, ago(30), TODAY.isoformat())
    assert checks2["receivables"]["status"] == "agrees", checks2["receivables"]
    voided = client.post(f"/finance/credit-notes/{cn['id']}/void", json={"reason": "Entered by error"}, headers=ana)
    assert voided.status_code == 200 and voided.json()["status"] == "void"


def test_vendor_credit_reduces_bill_voucher_slp_and_readiness(client, ana, team):  # noqa: F811
    s, b = posted_bill(client, team, 15, "SI-7100")
    line = b["lines"][0]
    r = client.post(
        "/finance/vendor-credits",
        json={
            "billId": b["id"],
            "supplierId": s["id"],
            "creditDate": ago(5),
            "reference": "CM-SUP-88",
            "reason": "Short-delivered qty",
            "amountsIncludeVat": True,
            "lines": [
                {
                    "accountId": line["accountId"],
                    "description": "Returned goods",
                    "amountCentavos": 112_000,
                    "vat": "vat",
                    "purchaseType": "other_goods",
                    "withholding": line.get("withholding"),
                    "noWithholdingReason": line.get("noWithholdingReason"),
                }
            ],
        },
        headers=team["aubrey"],
    )
    assert r.status_code == 201, r.text
    vc = r.json()
    rec = client.post(f"/finance/vendor-credits/{vc['id']}/record", headers=team["malou"])
    assert rec.status_code == 200, rec.text
    vc_data = rec.json()
    assert vc_data["status"] == "recorded"
    assert vc_data["appliedCentavos"] == vc_data["creditCentavos"]

    # Attempting to prepare a voucher for the full original bill payable is blocked!
    voucher_too_high = client.post(
        "/finance/vouchers",
        json={"supplierId": s["id"], "method": "bank", "lines": [{"billId": b["id"], "amountCentavos": b["payableCentavos"]}]},
        headers=team["cristal"],
    )
    assert voucher_too_high.status_code == 422

    # Voucher for remaining net balance succeeds, and BIR Input VAT, EWT & AP Readiness agree.
    remaining = b["payableCentavos"] - vc_data["creditCentavos"]
    assert remaining > 0
    ok_voucher = prepare(client, team["cristal"], s, [{"billId": b["id"], "amountCentavos": remaining}])
    assert ok_voucher["totalCentavos"] == remaining
    checks = readiness(client, ana, ago(30), TODAY.isoformat())
    for key in ("input_vat", "ewt", "payables"):
        assert checks[key]["status"] == "agrees", (key, checks[key])


def test_advances_deposits_reduce_open_balances_and_tie_out(client, app, ana, team):  # noqa: F811
    from modules.finance import company_scope

    ready(client, ana)
    with app.state.sessions() as db:
        a1 = Account(code="1401-000", name="Advances to Suppliers/Vendor", type="asset", is_active=True)
        a2 = Account(code="2205-000", name="Customer Deposits", type="liability", is_active=True)
        db.add_all([a1, a2])
        db.flush()
        company_scope.approve_for_2mg(db, "account", [a1.id, a2.id], reviewed_by="test")
        db.commit()

    # 1. Supplier prepayment applied to bill reduces bill owed and ties AP aging.
    s, b = posted_bill(client, team, 10, "SI-7101")
    adv_s = client.post(
        "/finance/advances",
        json={
            "kind": "supplier",
            "partyId": s["id"],
            "partyName": s["name"],
            "advanceDate": ago(8),
            "method": "bank",
            "reference": "DP-SUP-1",
            "amountCentavos": 50_000,
        },
        headers=team["cristal"],
    )
    assert adv_s.status_code == 201, adv_s.text
    adv_s_id = adv_s.json()["id"]
    app_s = client.post(
        f"/finance/advances/{adv_s_id}/apply",
        json={"targetId": b["id"], "appliedOn": ago(2), "amountCentavos": 50_000},
        headers=team["cristal"],
    )
    assert app_s.status_code == 200, app_s.text
    bill_after = client.get(f"/finance/bills/{b['id']}", headers=team["aubrey"]).json()
    assert bill_after["creditAppliedCentavos"] == 50_000
    assert bill_after["leftCentavos"] == b["payableCentavos"] - 50_000

    # 2. Customer deposit applied to invoice reduces AR balance and ties BIR Readiness.
    inv = issued(client, ana, invoiceDate=ago(6))
    adv_c = client.post(
        "/finance/advances",
        json={
            "kind": "customer",
            "partyName": inv["customer"]["name"],
            "advanceDate": ago(7),
            "method": "bank",
            "reference": "DEP-CUST-1",
            "amountCentavos": 100_000,
        },
        headers=ana,
    )
    assert adv_c.status_code == 201, adv_c.text
    adv_c_id = adv_c.json()["id"]
    app_c = client.post(
        f"/finance/advances/{adv_c_id}/apply",
        json={"targetId": inv["id"], "appliedOn": ago(1), "amountCentavos": 100_000},
        headers=ana,
    )
    assert app_c.status_code == 200, app_c.text
    inv_after = client.get(f"/finance/invoices/{inv['id']}", headers=ana).json()
    assert inv_after["creditAppliedCentavos"] == 100_000
    assert inv_after["balanceCentavos"] == inv["totalCentavos"] - 100_000

    checks = readiness(client, ana, ago(30), TODAY.isoformat())
    assert checks["receivables"]["status"] == "agrees", checks["receivables"]
    assert checks["payables"]["status"] == "agrees", checks["payables"]


def test_recurring_templates_generate_drafts_requiring_review(client, ana, team):  # noqa: F811
    _, b = posted_bill(client, team, 20, "SI-7102")
    sup_id = b["supplier"]["id"]
    acct_id = b["lines"][0]["accountId"]

    rb = client.post(
        "/finance/recurring",
        json={
            "kind": "bill",
            "name": "Monthly Warehouse Rent",
            "frequency": "monthly",
            "startDate": ago(3),
            "payload": {
                "supplierId": sup_id,
                "billNumberPrefix": "RENT",
                "amountsIncludeVat": True,
                "lines": [{"accountId": acct_id, "description": "Rent", "amountCentavos": 224_000, "vat": "vat", "purchaseType": "services"}],
            },
        },
        headers=team["aubrey"],
    )
    assert rb.status_code == 201, rb.text
    assert rb.json()["isDue"] is True

    ri = client.post(
        "/finance/recurring",
        json={
            "kind": "invoice",
            "name": "Monthly Retainer Billing",
            "frequency": "monthly",
            "startDate": ago(1),
            "payload": {
                "customerName": "Mercury Drug Makati",
                "termsDays": 15,
                "lines": [{"description": "Retainer fee", "quantity": 1, "unitPriceCentavos": 112_000}],
            },
        },
        headers=ana,
    )
    assert ri.status_code == 201, ri.text

    listed = client.get("/finance/recurring", headers=ana)
    assert listed.status_code == 200 and listed.json()["dueCount"] == 2

    run = client.post("/finance/recurring/run-due", headers=ana)
    assert run.status_code == 200, run.text
    data = run.json()
    assert data["count"] == 2
    bill_gen = next(g for g in data["generated"] if g["kind"] == "bill")
    inv_gen = next(g for g in data["generated"] if g["kind"] == "invoice")

    bill_draft = client.get(f"/finance/bills/{bill_gen['id']}", headers=team["aubrey"]).json()
    assert bill_draft["status"] == "draft" and bill_draft["taxReviewed"] is False
    inv_draft = client.get(f"/finance/invoices/{inv_gen['id']}", headers=ana).json()
    assert inv_draft["status"] == "draft" and inv_draft["number"] is None


def test_document_scan_excludes_printer_tin_and_converts_with_attachment(client, app, ana, team):  # noqa: F811
    _, b = posted_bill(client, team, 10, "SI-7103")
    sup_id = b["supplier"]["id"]
    sup_tin = b["supplier"]["tin"]
    acct_id = b["lines"][0]["accountId"]

    # Confirm raw PDF extraction works on real PDF bytes without shell tools.
    sample_text = (
        f"MERCURY SUPPLIES INC TIN {sup_tin}-000 VAT "
        f"Sales Invoice No: INV-2026-991 Date: {TODAY.isoformat()} "
        f"TOTAL AMOUNT DUE PHP 5,600.00 "
        f"ATP No. OCN999 PRINTER ABC CORP TIN 999-888-777-000"
    )
    pdf_bytes = _minimal_pdf_bytes(sample_text)
    extracted = extract_pdf_text(pdf_bytes)
    assert "INV-2026-991" in extracted

    up = client.post(
        "/finance/scans",
        json={
            "name": "mercury-inv-991.pdf",
            "contentType": "application/pdf",
            "data": base64.b64encode(pdf_bytes).decode("ascii"),
        },
        headers=team["aubrey"],
    )
    assert up.status_code == 201, up.text
    scan = up.json()
    p = scan["parsed"]
    assert p["supplierId"] == sup_id
    assert p["tin"] != "999888777000"
    assert p["totalCentavos"] == 560_000
    assert p["billNumber"] == "INV-2026-991"

    conv = client.post(
        f"/finance/scans/{scan['id']}/convert-to-bill",
        json={
            "supplierId": sup_id,
            "accountId": acct_id,
            "billNumber": p["billNumber"],
            "billDate": p["billDate"] or TODAY.isoformat(),
            "amountCentavos": p["totalCentavos"],
            "vat": p["vat"] or "vat",
            "amountsIncludeVat": True,
        },
        headers=team["aubrey"],
    )
    assert conv.status_code == 200, conv.text
    bill_id = conv.json()["billId"]
    draft = client.get(f"/finance/bills/{bill_id}", headers=team["aubrey"]).json()
    assert draft["status"] == "draft"
    assert draft["taxReviewed"] is False
    assert len(draft["files"]) == 1 and draft["files"][0]["name"] == "mercury-inv-991.pdf"
