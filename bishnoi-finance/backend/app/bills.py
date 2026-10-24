"""What a supplier bill comes to (decided 2026-10-24, BIR features from Oojeema).

Each line is charged to an account (an expense, or an asset such as stock) and
is of one VAT kind: VATable (12% input VAT, claimed against output VAT),
zero-rated, VAT-exempt, or from a supplier that isn't VAT-registered. Amounts
are as the supplier's invoice shows them: with VAT in (the usual) or without.

Expanded withholding: the bill's ATC and rate (EWT_ATCS gives the usual one)
apply to the lines marked withheld, on their amount without VAT (RR 2-98: the
tax base excludes the VAT). What's withheld is held back from the supplier and
owed to the BIR instead:

    debit  each line's account (its amount without VAT)
    debit  Input VAT (the VAT on VATable lines)
    credit Accounts payable (what the supplier is paid: the total less the withholding)
    credit Expanded withholding tax payable (the withholding)
"""

from datetime import date

from sqlalchemy.orm import Session

from app.tax.packs.ph import EWT_ATCS, VAT
from app.tax.rates import lookup

KINDS = {"vatable": "VATable", "zero_rated": "Zero-rated", "exempt": "VAT-exempt", "non_vat": "From a non-VAT supplier"}


def vat_rate(db: Session, on: date) -> int:
    return lookup(db, "PH")(VAT, on) or 1200


def work_out(db: Session, bill_date: date, lines: list[dict], *, include_vat: bool, atc: str | None, rate_bp: int) -> dict:
    """The bill's lines with their net and VAT, the totals by kind, the withholding and what's payable."""
    rate = vat_rate(db, bill_date)
    out_lines, by_kind = [], {k: 0 for k in KINDS}
    net_total = vat_total = base = 0
    for ln in lines:
        amount = int(ln.get("amountCentavos") or 0)
        kind = ln.get("kind") or "vatable"
        if kind == "vatable":
            if include_vat:
                net = round(amount * 10_000 / (10_000 + rate))
                vat = amount - net
            else:
                net, vat = amount, round(amount * rate / 10_000)
        else:
            net, vat = amount, 0
        withheld = bool(ln.get("withheld", True)) and bool(atc)
        if withheld:
            base += net
        by_kind[kind] += net
        net_total += net
        vat_total += vat
        out_lines.append({**ln, "kind": kind, "netCentavos": net, "vatCentavos": vat, "withheld": withheld})
    ewt = round(base * rate_bp / 10_000) if atc else 0
    total = net_total + vat_total
    return {
        "lines": out_lines,
        "vatRateBp": rate,
        "netCentavos": net_total,
        "byKind": {k: v for k, v in by_kind.items()},
        "inputTaxCentavos": vat_total,
        "totalCentavos": total,
        "atc": atc,
        "atcNature": EWT_ATCS[atc].nature if atc in EWT_ATCS else None,
        "ewtRateBp": rate_bp if atc else 0,
        "ewtBaseCentavos": base if atc else 0,
        "ewtCentavos": ewt,
        "payableCentavos": total - ewt,
    }
