"""BIR files: what each company's Sales DAT is made with.

The Sales DAT itself is built in the browser, from Oojeema's exports, by the
screen at Tax → BIR sales DAT (frontend/src/bir/sales-dat). Nothing is uploaded.
What it needs from here is each company's details for the file's first line,
found by the seller TIN in the exports (its first 9 digits):

- rdo: the company's Revenue District Office code, the BIR office it is
  registered at (as on its Certificate of Registration, BIR Form 2303);
- year_end_month: the month its accounting year ends (12 = December).

None means not known yet: the screen then asks for it before making the file.
`confirmed` says whether someone has checked it against the company's papers.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SalesDatCompany:
    tin: str
    name: str
    rdo: str | None
    year_end_month: int | None
    confirmed: bool
    note: str


COMPANIES: tuple[SalesDatCompany, ...] = (
    SalesDatCompany(
        tin="010065182",
        name="2MG Incorporated",
        rdo="53A",
        year_end_month=12,
        confirmed=False,
        note="As in every Sales DAT filed for March to September 2026 (decided 2026-10-22). Confirm against the Certificate of Registration (BIR Form 2303).",
    ),
    SalesDatCompany(
        tin="605059166",
        name="Getmeds Philippines, Inc.",
        rdo=None,
        year_end_month=None,
        confirmed=False,
        note="TIN from the company letterhead. RDO code and year-end not known yet.",
    ),
)


def companies_out() -> list[dict]:
    return [{"tin": c.tin, "name": c.name, "rdo": c.rdo, "yearEndMonth": c.year_end_month, "confirmed": c.confirmed, "note": c.note} for c in COMPANIES]
