"""Zoho's vendor export, cleaned for Bishnoi One (2026-10-27).

    python scripts/zoho_vendors.py <Vendors.csv> <review.csv>

Writes one row per vendor to review: duplicates merged, test records marked, TINs
and phones cleaned, and each vendor sorted into what it is:

    supplier  sells the company its products: goes to Inventory (purchase orders) and Finance
    payee     everything else paid (fuel, food, utilities, government): Finance only
    test      someone's test record: nowhere

The sorting is a guess from the name; correct the `kind` column before importing.
Then each app takes the file (its own tool, app/tools/import_vendors.py).
"""

import csv
import re
import sys
from collections import defaultdict

TEST = re.compile(r"\btest\b|^vikash testing$|\bsir\b|^naresh bishnoi$|^(mr\. )?mohit kumar$|^2mginc$|^hari dwivedi$|^getmeds healthcare$|no receipt", re.I)
# Sells medicines or medical supplies.
SUPPLIER = re.compile(
    r"pharma|drug|medicament|remedies|parenteral|life ?sciences?|biotech|bioceutical|generics?\b|medicines?\b|"
    r"medical (supplies|supply|distribut|trading|products|equipment)|surgical|laborator(y|ies) (ltd|limited|pvt|inc)|labs? (ltd|limited|pvt)|"
    r"healthcare (ltd|limited|pvt|inc|corp)|\bhealth ?care products|apothec|botica|vaccin",
    re.I,
)
# Medical-sounding, but paid for a service, not products.
NOT_SUPPLIER = re.compile(
    r"hospital|medical cent(er|re)|\bsociety\b|association|college|testing|clinic|doctors|travel|automotive|insurance|philhealth|foundation|"
    r"administration|research|adviser|advisor|compact|network|fashion|leather|movider",
    re.I,
)
# Words a name may or may not end with: the same vendor either way.
SUFFIXES = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "pvt", "private", "php", "llp", "the"}
ABROAD = {"india", "bangladesh", "china", "uzbekistan", "thailand", "turkey", "egypt"}
COUNTRY = {"philipines": "Philippines", "philippines": "Philippines", "china": "China"}


def key(name: str) -> str:
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and ").replace("(formerly", " ("))
    words = [w for w in words if w not in SUFFIXES]
    return "".join(words)


def filled(row: dict) -> int:
    return sum(1 for v in row.values() if v and v.strip())


def phone(value: str) -> str | None:
    v = value.strip().lstrip("'").strip()
    if not v or re.search(r"[eE]\+", v) or not re.search(r"\d{7}", re.sub(r"\D", "", v)):
        return None  # Excel turned it into 9.1957E+11: the digits are gone
    return v[:40]


def tin(value: str) -> tuple[str | None, str | None, bool, str | None]:
    """(TIN 123-456-789, branch 00000, non-VAT marked, the problem if it can't be read)."""
    v = value.strip()
    if not v:
        return None, None, False, None
    non_vat = bool(re.match(r"^\s*NV\b", v, re.I))
    digits = re.sub(r"\D", "", v)
    if len(digits) == 15 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 15 and digits.endswith("0"):
        digits = digits[:-1]
    if len(digits) not in (9, 12, 13, 14):
        return None, None, non_vat, f"TIN not readable: {v}"
    branch = digits[9:].rjust(5, "0")[-5:] if len(digits) > 9 else "00000"
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}", branch, non_vat, None


def address(r: dict) -> tuple[str | None, str | None]:
    country = r["Billing Country"].strip()
    country = COUNTRY.get(country.lower(), country.title() if country.islower() else country) or None
    parts = [r["Billing Address"], r["Billing Street2"], r["Billing City"], r["Billing State"], r["Billing Code"], country or ""]
    text = ", ".join(p for p in (re.sub(r"\s*\n\s*", ", ", x.strip()).strip(", ") for x in parts) if p)
    return (text[:300] or None), country


def kind(r: dict, country: str | None) -> str:
    name = f"{r['Display Name']} {r['Company Name']}"
    if TEST.search(r["Display Name"]) or "test" in f"{r['First Name']} {r['Last Name']}".lower():
        return "test"
    if NOT_SUPPLIER.search(name):
        return "payee"
    if SUPPLIER.search(name) or (country or "").lower() in ABROAD or r["Currency Code"] == "USD":
        return "supplier"
    return "payee"


def main(source: str, target: str) -> None:
    rows = list(csv.DictReader(open(source, encoding="utf-8-sig", newline="")))
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[key(r["Display Name"])].append(r)

    out = []
    for same in groups.values():
        same.sort(key=filled, reverse=True)
        r = dict(same[0])
        for other in same[1:]:  # blanks filled from the duplicates
            for k, v in other.items():
                if not (r.get(k) or "").strip() and (v or "").strip():
                    r[k] = v
        issues = []
        number, branch, nv, problem = tin(r["CF.TIN"])
        if problem:
            issues.append(problem)
        where, country = address(r)
        vat = "non_vat" if nv or r["Tax Name"] == "No Tax" else "vat" if r["Tax Name"] == "Vat" else "vat?"
        if vat == "vat?":
            issues.append("VAT status not given in Zoho: assumed VAT-registered")
        ewt = r["Track TDS"] == "TRUE" or r["Tax Name"] in ("Only EWT",)
        if ewt:
            issues.append("Tax is withheld (EWT): choose its ATC in Finance")
        phones = [p for p in (phone(r["Phone"]), phone(r["Billing Phone"])) if p]
        if (r["Phone"] or r["MobilePhone"]) and not phones and not phone(r["MobilePhone"]):
            issues.append("Phone lost to Excel (shown as 9.1E+11)")
        person = " ".join(x for x in (r["Salutation"], r["First Name"], r["Last Name"]) if x.strip()).strip()
        out.append({
            "zoho_id": r["CF.Custom ID"],
            "kind": kind(r, country),
            "name": r["Display Name"].strip(),
            "company_name": r["Company Name"].strip(),
            "contact_person": person if person and "test" not in person.lower() else "",
            "salutation": r["Salutation"].strip(),
            "first_name": r["First Name"].strip(),
            "last_name": r["Last Name"].strip(),
            "designation": r["Designation"].strip(),
            "email": r["EmailID"].strip().lower(),
            "phone": phones[0] if phones else "",
            "mobile": phone(r["MobilePhone"]) or "",
            "address": where or "",
            "country": country or "",
            "currency": r["Currency Code"] or "PHP",
            "tin": number or "",
            "branch_code": branch or "",
            "vat": vat.rstrip("?"),
            "ewt": "yes" if ewt else "",
            "website": r["Website"].strip(),
            "active": "yes" if r["Status"] == "Active" else "no",
            "merged_zoho_ids": " ".join(x["CF.Custom ID"] for x in same[1:]),
            "issues": "; ".join(issues),
        })

    order = {"supplier": 0, "payee": 1, "test": 2}
    out.sort(key=lambda x: (order[x["kind"]], x["name"].lower()))
    with open(target, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    counts = {k: sum(1 for x in out if x["kind"] == k) for k in order}
    print(f"{len(rows)} rows -> {len(out)} vendors ({len(rows) - len(out)} duplicates merged): {counts}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
