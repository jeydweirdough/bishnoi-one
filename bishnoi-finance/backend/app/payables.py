"""Payables: what a supplier's bill comes to, and the tax withheld from it.

**Confirm with Rommel (BIR) before relying on it for filing.** The withholding codes
below are the expanded withholding tax (EWT) the BIR's RR 2-98, as amended by RR
11-2018, sets for the payments a distributor makes most, as understood in 2026; each
supplier keeps one as their usual code (Aubrey Q11), and a bill's line can use another.
The 1% on goods and 2% on services apply when the company is a top withholding agent.

A bill's line is an amount with or without VAT (the bill says which). With VAT, the
VAT is taken out of it at the day's rate (Finance's dated rates, PH_VAT12): ₱11,200
is ₱10,000 and ₱1,200 VAT. Tax is withheld on the amount before VAT, so at 1% that
bill pays the supplier ₱11,100 and ₱100 goes to the BIR (for the supplier's 2307).
"""

import re
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.tax import rates as rate_book
from app.tax.packs.ph import VAT

# code: (what it's for, rate in basis points: 100 = 1%)
WITHHOLDING: dict[str, tuple[str, int]] = {
    "WC158": ("Goods, from a company (top withholding agent)", 100),
    "WI158": ("Goods, from an individual (top withholding agent)", 100),
    "WC160": ("Services, from a company (top withholding agent)", 200),
    "WI160": ("Services, from an individual (top withholding agent)", 200),
    "WC120": ("Contractors, companies", 200),
    "WI120": ("Contractors, individuals", 200),
    "WC100": ("Rent, to a company", 500),
    "WI100": ("Rent, to an individual", 500),
    "WI010": ("Professional fees, individual, gross up to ₱3M", 500),
    "WI011": ("Professional fees, individual, gross over ₱3M", 1000),
    "WC010": ("Professional fees, company, gross up to ₱720,000", 1000),
    "WC011": ("Professional fees, company, gross over ₱720,000", 1500),
    "WC140": ("Brokerage fees, company, gross over ₱720,000", 1500),
}

# A line's VAT: 12% (taken out, or added), zero-rated, exempt, or none (a non-VAT supplier).
VAT_KINDS = {"vat": "VAT 12%", "zero": "Zero-rated", "exempt": "VAT-exempt", "none": "No VAT"}
PURCHASE_TYPES = {"services": "Services", "capital_goods": "Capital goods", "other_goods": "Other goods", "importation": "Importation"}


# Where a supplier is (Sir Mel, recording 12, 2026-11-04): withholding is for local suppliers only; a foreign one
# has none (an import's VAT is paid at Customs instead). Decided by the user 2026-11-05: a name with "Ltd" or
# "Limited" makes a supplier foreign, every other local. That fills the field; a person can change it.
ORIGINS = {"local": "Local", "foreign": "Foreign"}
FOREIGN_NAME = re.compile(r"\b(ltd|limited)\b", re.IGNORECASE)


def origin_by_name(name: str) -> str:
    return "foreign" if FOREIGN_NAME.search(name or "") else "local"


# Why a local supplier's line has no withholding (Batch A, 2026-11-05): every such line says so, so a missing
# withholding never looks the same as "not needed". Foreign is filled in by itself; "other" needs a note.
NO_WITHHOLDING = {"foreign": "Foreign supplier", "not_covered": "Payee not covered or exempt", "other": "Other (see note)"}


def withholding_decision(origin: str | None, code: str | None, reason: str | None, note: str | None, *, complete: bool) -> tuple[str | None, str | None, str | None]:
    """A line's withholding choice, checked: (code, reason, note), or a message saying what's wrong.

    A foreign supplier's line can't have withholding, and says so by itself. A local supplier's line has a code,
    or a reason (with a note for "other"). `complete`: whether a missing choice is refused (submitting) or kept
    for later (a draft). Raises ValueError with the message."""
    note = (note or "").strip() or None
    if origin == "foreign":
        if code:
            raise ValueError("This is a foreign supplier: no tax is withheld from them. Clear the withholding code.")
        return None, "foreign", None
    if code:
        return code, None, None
    if reason is None or reason == "foreign":
        if complete:
            raise ValueError("Pick a withholding code, or say why none is withheld.")
        return None, None, note
    if reason not in NO_WITHHOLDING:
        raise ValueError("Pick a reason from the list.")
    if reason == "other" and not note:
        raise ValueError("Say why no tax is withheld in the note.")
    return None, reason, note


def withholding_out() -> list[dict]:
    return [{"code": code, "name": name, "rateBp": bp} for code, (name, bp) in WITHHOLDING.items()]


def no_withholding_out() -> list[dict]:
    return [{"key": key, "label": label} for key, label in NO_WITHHOLDING.items() if key != "foreign"]


def share(amount: int, bp: int) -> int:
    """bp basis points of amount, to the nearest centavo (halves up)."""
    return (amount * bp + 5_000) // 10_000


@dataclass
class Worked:
    lines: list[dict]
    net: int
    vat: int
    withheld: int
    total: int
    payable: int
    vat_bp: int


def work_out(db: Session, lines: list[dict], on: date, include_vat: bool) -> Worked:
    """Each line's amount before VAT, its VAT and what's withheld, and the bill's totals."""
    vat_bp = rate_book.lookup(db, "PH")(VAT, on)
    if vat_bp is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There's no VAT rate for the bill's date. Check Tax, Rates.")
    out, net, vat, withheld = [], 0, 0, 0
    for line in lines:
        amount, kind, code = line["amountCentavos"], line["vat"], line.get("withholding")
        if kind == "vat":
            if include_vat:
                base = (amount * 10_000 * 2 + (10_000 + vat_bp)) // (2 * (10_000 + vat_bp))
                tax = amount - base
            else:
                base, tax = amount, share(amount, vat_bp)
        else:
            base, tax = amount, 0
        held = share(base, WITHHOLDING[code][1]) if code else 0
        out.append(line | {"netCentavos": base, "vatCentavos": tax, "withheldCentavos": held})
        net, vat, withheld = net + base, vat + tax, withheld + held
    return Worked(out, net, vat, withheld, net + vat, net + vat - withheld, vat_bp)
