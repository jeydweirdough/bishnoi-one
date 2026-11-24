"""Clean Philippine BIR receipt/invoice text extraction and parser (no mock vendors or fake guesses).

- Extracts text from digital PDFs using `pypdf`.
- Excludes printer ATP/OCN footer TINs so printer stamps aren't confused with suppliers.
- Matches strictly against active `nbfi_suppliers` records by TIN or name.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.finance.models import Supplier

PRINTER_MARKERS = ("PRINTER", "ACCREDITATION", "OCN", "ATP", "AUTHORITY TO PRINT", "PTU", "SERIAL", "MASTERPRESS", "BUNDY")


def extract_pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        return ""


def _digits9(tin: str | None) -> str:
    return re.sub(r"\D", "", str(tin or ""))[:9]


def _parse_date(text: str) -> str | None:
    patterns = [
        (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
        (r"\b(\d{2}/\d{2}/\d{4})\b", "%m/%d/%Y"),
        (r"\b(\d{2}-\d{2}-\d{4})\b", "%m-%d-%Y"),
        (r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b", None),
    ]
    for rx, fmt in patterns:
        for m in re.finditer(rx, text):
            raw = m.group(1).replace(",", "")
            try:
                if fmt:
                    dt = datetime.strptime(raw, fmt).date()
                else:
                    for f in ("%b %d %Y", "%B %d %Y"):
                        try:
                            dt = datetime.strptime(raw, f).date()
                            break
                        except ValueError:
                            dt = None
                    if dt is None:
                        continue
                if date(2020, 1, 1) <= dt <= date.today():
                    return dt.isoformat()
            except ValueError:
                continue
    return None


def _money_to_centavos(raw: str) -> int | None:
    cleaned = re.sub(r"[,₱P\s]", "", raw, flags=re.I)
    try:
        val = round(float(cleaned) * 100)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_amounts(text: str) -> tuple[int | None, int | None, bool]:
    lines = text.splitlines()
    total_c: int | None = None
    for ln in reversed(lines):
        if re.search(r"\b(TOTAL\s*AMOUNT\s*DUE|TOTAL\s*DUE|AMOUNT\s*DUE|NET\s*PAYABLE|GRAND\s*TOTAL|TOTAL\s*SALES|TOTAL)\b", ln, re.I):
            nums = re.findall(r"(?:₱|PHP|P)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})", ln, re.I)
            if nums:
                total_c = _money_to_centavos(nums[-1])
                if total_c:
                    break
    if total_c is None:
        all_nums = [_money_to_centavos(x) for x in re.findall(r"\b(\d{1,3}(?:,\d{3})*\.\d{2})\b", text)]
        valid = [n for n in all_nums if n and n < 50_000_000_00]
        if valid:
            total_c = max(valid)

    upper = text.upper()
    is_exempt = bool(re.search(r"\b(VAT[\s\-]?EXEMPT|NON[\s\-]?VAT|ZERO[\s\-]?RATED)\b", upper)) and "VATABLE" not in upper
    vat_c: int | None = None
    for ln in lines:
        if re.search(r"\b(12%\s*VAT|VAT\s*AMOUNT|OUTPUT\s*VAT|ADDED\s*TAX|VATABLE\s*VAT)\b", ln, re.I) and "EXEMPT" not in ln.upper():
            nums = re.findall(r"(\d{1,3}(?:,\d{3})*\.\d{2})", ln)
            if nums:
                vat_c = _money_to_centavos(nums[-1])
                break
    if vat_c is None and total_c and not is_exempt:
        net = round(total_c / 1.12)
        vat_c = total_c - net
    return total_c, vat_c, not is_exempt


def _extract_tins(text: str) -> list[str]:
    """Extract vendor TINs while filtering out BIR printer/ATP stamp TINs."""
    candidates: list[str] = []
    upper = text.upper()
    for m in re.finditer(r"\b(\d{3}[-\s]?\d{3}[-\s]?\d{3}(?:[-\s]?\d{3,5})?)\b", text):
        prefix = upper[max(0, m.start() - 60) : m.start()]
        # Printer Accreditation/ATP/OCN blocks place printer TINs right after printer keywords.
        if any(marker in prefix for marker in PRINTER_MARKERS):
            continue
        d9 = _digits9(m.group(1))
        if len(d9) == 9 and d9 != "010065182":  # Exclude 2MG's own TIN
            candidates.append(d9)
    return list(dict.fromkeys(candidates))


def _extract_bill_number(text: str) -> str | None:
    patterns = [
        r"(?:SALES\s*INVOICE|OFFICIAL\s*RECEIPT|INVOICE|SI|OR|INV)\s*(?:NO\.?\s*:?|#\s*:?|:)\s*([A-Z0-9\-]{3,30})",
        r"\b((?:SI|OR|INV|BI|BL)[-\s]?\d{3,15}(?:-\d{1,8})?)\b",
    ]
    for rx in patterns:
        m = re.search(rx, text, re.I)
        if m:
            return m.group(1).strip().upper()
    return None


def parse_receipt(db: Session, raw_text: str) -> dict:
    text = (raw_text or "").strip()
    warnings: list[str] = []
    if not text:
        return {
            "supplierId": None, "supplierName": None, "tin": None,
            "billNumber": None, "billDate": None, "totalCentavos": None,
            "vatCentavos": None, "netCentavos": None, "vat": "vat",
            "confidence": "manual",
            "warnings": ["No readable text was extracted (scanned image without text or unreadable file). Enter details side-by-side."],
        }

    tins = _extract_tins(text)
    matched_supplier: Supplier | None = None
    active_suppliers = list(db.scalars(select(Supplier).where(Supplier.is_active).order_by(func.length(Supplier.name).desc())))
    if tins:
        by_tin = {_digits9(s.tin): s for s in active_suppliers if _digits9(s.tin)}
        for t in tins:
            if t in by_tin:
                matched_supplier = by_tin[t]
                break
    if matched_supplier is None:
        upper = text.upper()
        for s in active_suppliers:
            clean_sup = re.sub(r"[^A-Z0-9 ]", "", s.name.upper()).strip()
            if len(clean_sup) >= 6 and clean_sup in re.sub(r"[^A-Z0-9 ]", "", upper):
                matched_supplier = s
                break

    bill_number = _extract_bill_number(text)
    bill_date = _parse_date(text)
    total_c, vat_c, is_vat = _extract_amounts(text)
    net_c = (total_c - (vat_c or 0)) if total_c else None

    if matched_supplier is None:
        warnings.append("Supplier was not matched to your directory — verify and pick the supplier manually.")
    if not bill_number:
        warnings.append("Invoice/OR number was not detected clearly.")
    if not bill_date:
        warnings.append("Invoice date was not detected clearly.")
    if not total_c:
        warnings.append("Total amount was not detected clearly.")

    found_count = sum(1 for x in (matched_supplier, bill_number, bill_date, total_c) if x)
    confidence = "high" if found_count >= 3 else ("medium" if found_count >= 1 else "low")
    return {
        "supplierId": matched_supplier.id if matched_supplier else None,
        "supplierName": matched_supplier.name if matched_supplier else None,
        "tin": matched_supplier.tin if matched_supplier else (f"{tins[0][:3]}-{tins[0][3:6]}-{tins[0][6:9]}" if tins else None),
        "billNumber": bill_number,
        "billDate": bill_date,
        "totalCentavos": total_c,
        "vatCentavos": vat_c,
        "netCentavos": net_c,
        "vat": "vat" if is_vat else "exempt",
        "confidence": confidence,
        "warnings": warnings,
    }
