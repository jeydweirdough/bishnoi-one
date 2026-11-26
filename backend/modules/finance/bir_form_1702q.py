"""Official-background BIR Form 1702Q (Quarterly Income Tax Return) review PDF.

Rendering is distinct from electronic validation, filing, and payment. Per BIR
Form 1702Q instructions, amounts on the form are rounded to whole pesos
(49 centavos or less dropped; 50 centavos or more rounded up).
"""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from modules.finance.bir_form_2307 import _integer

TEMPLATES = Path(__file__).parent / "templates/bir"
STEM = "1702q-2018-01"


def round_peso(centavos: int) -> int:
    """Round centavos to whole pesos per BIR 1702Q instructions (half-up)."""
    value = _integer(centavos)
    sign = -1 if value < 0 else 1
    whole, cents = divmod(abs(value), 100)
    if cents >= 50:
        whole += 1
    return sign * whole


def prepare(report: dict) -> dict:
    d = deepcopy(report)
    if d.get("form") != "1702Q":
        raise ValueError("Unsupported income tax form.")
    quarter = int(d.get("quarter") or 0)
    if quarter not in (1, 2, 3):
        raise ValueError("BIR Form 1702Q covers Q1, Q2, and Q3 only; Q4 is filed on the Annual Income Tax Return (1702-RT).")
    rate_bp = int(d.get("rateBp") or 2500)
    if rate_bp not in (2000, 2500):
        raise ValueError("Corporate income tax rate must be 20% or 25%.")
    d["draftOnly"] = True
    d["readyForFiling"] = False
    d["electronicAcceptance"] = "not_verified"
    return d


def _fit(c: canvas.Canvas, text: str | None, x: float, top: float, width: float, size: float = 8.5) -> None:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    s = str(text or "").upper()
    while size >= 5.5 and stringWidth(s, "Helvetica", size) > width:
        size -= 0.25
    c.setFont("Helvetica", max(size, 5.5))
    c.drawString(x, c._pagesize[1] - top, s)


def _boxes(c: canvas.Canvas, text: str, centres: list[float], top: float, size: float = 9.0) -> None:
    c.setFont("Courier-Bold", size)
    h = c._pagesize[1]
    for x, ch in zip(centres, text):
        c.drawCentredString(x, h - top, ch)


def _peso_boxes(c: canvas.Canvas, centavos: int, top: float, *, last_x: float = 584.5, step: float = 14.15, max_digits: int = 12) -> None:
    whole = round_peso(centavos)
    digits = ("-" if whole < 0 else "") + str(abs(whole))
    if len(digits) > max_digits:
        raise ValueError("Amount exceeds printed 1702Q money cells.")
    c.setFont("Courier-Bold", 8.5)
    h = c._pagesize[1]
    for i, ch in enumerate(reversed(digits)):
        c.drawCentredString(last_x - step * i, h - top, ch)


def _mark_x(c: canvas.Canvas, x: float, top: float) -> None:
    c.setFont("Helvetica-Bold", 9.5)
    c.drawCentredString(x, c._pagesize[1] - top, "X")


def render(d: dict) -> bytes:
    if not d.get("draftOnly") or d.get("readyForFiling"):
        raise ValueError("Review-only form output.")
    raw = (TEMPLATES / f"{STEM}.pdf").read_bytes()
    provenance = json.loads((TEMPLATES / f"{STEM}.source.json").read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != provenance["sha256"]:
        raise ValueError("Official 1702Q template checksum changed.")

    reader = PdfReader(BytesIO(raw))
    writer = PdfWriter()
    who = d["taxpayer"]
    t = d["totals"]
    year = str(d["year"])
    quarter = int(d["quarter"])
    rate_pct = str(int(d.get("rateBp", 2500)) // 100)

    tin = re.sub(r"\D", "", who.get("tin") or "")
    if tin and len(tin) != 9:
        raise ValueError("TIN requires nine main digits and a separate five-digit branch.")
    rdo = re.sub(r"^0(\d{2}[0-9A-Z])$", r"\1", str(who.get("rdoCode") or "").strip().upper())

    # Page 1: Background + Part II Total Tax Payable
    p1 = reader.pages[0]
    w1, h1 = float(p1.mediabox.width), float(p1.mediabox.height)
    b1 = BytesIO()
    c1 = canvas.Canvas(b1, pagesize=(w1, h1), invariant=1)
    # 1 Calendar, 2 Year Ended (MM/20YY), 3 Quarter
    _mark_x(c1, 59.5, 136.0)
    _boxes(c1, "12", [34.5, 49.5], 161.5)
    _boxes(c1, year[-2:], [99.5, 114.5], 161.5)
    _mark_x(c1, (161.5, 190.5, 219.5)[quarter - 1], 149.0)
    # 6 TIN (3+3+3), 7 RDO (3)
    tin_groups = (218.0, 278.5, 339.0)
    _boxes(c1, tin, [g + i * 15.15 for g in tin_groups for i in range(3)], 192.0)
    _boxes(c1, rdo, [542.5, 557.5, 572.5], 192.0)
    # 8 Registered Name, 9 Address, 12 Itemized Deductions
    _fit(c1, who.get("registeredName"), 24.0, 223.0, 560.0, 9.0)
    _fit(c1, who.get("address"), 24.0, 271.0, 560.0, 8.0)
    _mark_x(c1, 149.0, 337.5)

    # Part II Total Tax Payable (Items 14, 16, 18, 19, 20, 25)
    tax_due = _integer(t["taxDueCentavos"])
    cwt_credits = _integer(t["cwtCreditsCentavos"])
    net_payable = _integer(t["netPayableCentavos"])
    _peso_boxes(c1, tax_due, 390.5)
    _peso_boxes(c1, tax_due, 429.5)
    _peso_boxes(c1, tax_due, 468.0)
    _peso_boxes(c1, cwt_credits, 487.0)
    _peso_boxes(c1, net_payable, 506.5)
    _peso_boxes(c1, net_payable, 603.0)

    c1.setFillColor(HexColor("#9B2525"))
    c1.setFont("Helvetica-Bold", 8)
    c1.drawCentredString(306, h1 - 10, "DRAFT / REVIEW ONLY - NOT FOR FILING - ACTUAL PAYMENTS NOT VERIFIED")
    c1.save()
    p1.merge_page(PdfReader(BytesIO(b1.getvalue())).pages[0])
    writer.add_page(p1)

    # Page 2: Part IV Schedules 2, 3, 4
    p2 = reader.pages[1]
    w2, h2 = float(p2.mediabox.width), float(p2.mediabox.height)
    b2 = BytesIO()
    c2 = canvas.Canvas(b2, pagesize=(w2, h2), invariant=1)
    p2_tin_groups = (24.0, 74.5, 125.0)
    _boxes(c2, tin, [g + i * 13.5 for g in p2_tin_groups for i in range(3)], 104.0, 8.5)
    _fit(c2, who.get("registeredName"), 236.0, 104.0, 345.0, 8.5)

    gross_sales = _integer(t["grossSalesCentavos"])
    cost_of_sales = _integer(t["costOfSalesCentavos"])
    gross_income = _integer(t["grossIncomeCentavos"])
    operating_expenses = _integer(t["operatingExpensesCentavos"])
    taxable_income = _integer(t["taxableIncomeCentavos"])
    rcit = _integer(t["rcitCentavos"])
    mcit = _integer(t["mcitCentavos"])

    # Schedule 2 (rows at 390.5 + 17.1 * index)
    _peso_boxes(c2, gross_sales, 390.5)
    _peso_boxes(c2, cost_of_sales, 407.6)
    _peso_boxes(c2, gross_income, 424.7)
    _peso_boxes(c2, gross_income, 459.0)
    _peso_boxes(c2, operating_expenses, 476.0)
    _peso_boxes(c2, taxable_income, 493.1)
    _peso_boxes(c2, taxable_income, 527.3)
    _boxes(c2, rate_pct, [559.5, 573.5], 544.5, 8.5)
    _peso_boxes(c2, rcit, 561.5)
    _peso_boxes(c2, mcit, 578.6)
    _peso_boxes(c2, tax_due, 595.7)

    # Schedule 3 MCIT
    q_tops = (630.0, 647.1, 664.2)
    _peso_boxes(c2, max(0, gross_income), q_tops[quarter - 1])
    _peso_boxes(c2, max(0, gross_income), 681.3)
    _peso_boxes(c2, mcit, 717.0)

    # Schedule 4 Tax Credits (Item 5 CWT per 2307, Item 7 Total)
    _peso_boxes(c2, cwt_credits, 820.0)
    _peso_boxes(c2, cwt_credits, 891.5)

    c2.setFillColor(HexColor("#9B2525"))
    c2.setFont("Helvetica-Bold", 8)
    c2.drawCentredString(306, h2 - 10, "DRAFT / REVIEW ONLY - NOT FOR FILING - ACTUAL PAYMENTS NOT VERIFIED")
    c2.save()
    p2.merge_page(PdfReader(BytesIO(b2.getvalue())).pages[0])
    writer.add_page(p2)

    # Page 3: Official Guidelines & ATCs
    for page in reader.pages[2:]:
        writer.add_page(page)

    writer.add_metadata({"/Title": "1702Q review draft - not for filing"})
    out = BytesIO()
    writer.write(out)
    return out.getvalue()
