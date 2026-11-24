"""Draft BIR .DAT generators (RELIEF SLS/SLP, Alphalist SAWT/QAP) from posted lists.

Text normalization, TIN formatting and 30-char address splitting follow the
BIR Sales DAT rules confirmed with Sir Rommel (bir/sales-dat/engine.ts).
Outputs are labeled as review drafts for verification in the official BIR
RELIEF / Alphalist Validation Module before eSubmission.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

FOLD = {
    "Ø": "O", "ø": "o", "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe",
    "ß": "ss", "Đ": "D", "đ": "d", "Þ": "TH", "þ": "th", "Ł": "L", "ł": "l",
}


def fold_text(value: str | None) -> str:
    raw = "".join(FOLD.get(ch, ch) for ch in str(value or ""))
    return "".join(ch for ch in unicodedata.normalize("NFD", raw) if unicodedata.category(ch) != "Mn")


def clean_text(value: str | None, width: int | None = None) -> str:
    s = re.sub(r"\s{2,}", " ", re.sub(r"[^A-Z0-9 ]", "", fold_text(value).upper())).strip()
    return s[:width].strip() if width else s


def clean_name(value: str | None) -> str:
    txt = fold_text(value).upper().replace("&", " AND ")
    txt = re.sub(r"[.\-]", " ", txt)
    txt = re.sub(r"['\u2019,]", "", txt)
    txt = re.sub(r"[^A-Z0-9 ]", " ", txt)
    return re.sub(r"\s{2,}", " ", txt).strip()


def tin9(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))[:9]


def branch4(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return (digits[-4:] or "0000").zfill(4)


def split_addr(address: str | None) -> tuple[str, str]:
    s = clean_text(address)
    if not s:
        return "", ""
    if len(s) <= 30:
        return s, ""
    cut = s.rfind(" ", 0, 31)
    if cut <= 0:
        cut = 30
    return s[:cut].strip(), clean_text(s[cut:].strip(), 30)


def amt_h(centavos: int | None) -> str:
    return f"{(centavos or 0) / 100:.2f}"


def amt_d(centavos: int | None) -> str:
    c = centavos or 0
    return "0" if c == 0 else f"{c / 100:.2f}"


def qq(value: str) -> str:
    return f'"{value}"'


def _header_names(taxpayer: dict) -> tuple[str, str, str, str, str, str]:
    seller = tin9(taxpayer.get("tin")) or "000000000"
    reg = clean_text(taxpayer.get("registeredName") or taxpayer.get("tradeName") or "TAXPAYER")
    trd = clean_text(taxpayer.get("tradeName") or taxpayer.get("registeredName") or "TAXPAYER")
    a1, a2 = split_addr(taxpayer.get("address"))
    rdo = clean_text(taxpayer.get("rdoCode") or "000")
    return seller, reg, trd, a1, a2, rdo


def build_sls_dat(taxpayer: dict, end: date, data: dict) -> tuple[str, str]:
    seller, reg, trd, a1, a2, rdo = _header_names(taxpayer)
    period_str = end.strftime("%m/%d/%Y")
    fy = str(int(taxpayer.get("fiscalMonthEnd") or 12))
    t = data["totals"]
    lines = [
        ",".join([
            "H", "S", qq(seller), qq(reg), qq(""), qq(""), qq(""), qq(trd),
            qq(a1), qq(a2),
            amt_h(t.get("exemptCentavos")), amt_h(t.get("zeroRatedCentavos")),
            amt_h(t.get("taxableCentavos")), amt_h(t.get("outputTaxCentavos")),
            qq(rdo), period_str, fy,
        ])
    ]
    for r in data["rows"]:
        ra1, ra2 = split_addr(r.get("address"))
        lines.append(",".join([
            "D", "S", qq(tin9(r.get("tin"))), qq(clean_name(r.get("name"))), qq(""), qq(""), qq(""),
            qq(ra1), qq(ra2),
            amt_d(r.get("exemptCentavos")), amt_d(r.get("zeroRatedCentavos")),
            amt_d(r.get("taxableCentavos")), amt_d(r.get("outputTaxCentavos")),
            seller, period_str,
        ]))
    filename = f"{seller}S{end:%m%Y}.DAT"
    return "\r\n".join(lines) + "\r\n", filename


def build_slp_dat(taxpayer: dict, end: date, data: dict) -> tuple[str, str]:
    seller, reg, trd, a1, a2, rdo = _header_names(taxpayer)
    period_str = end.strftime("%m/%d/%Y")
    fy = str(int(taxpayer.get("fiscalMonthEnd") or 12))
    t = data["totals"]
    lines = [
        ",".join([
            "H", "P", qq(seller), qq(reg), qq(""), qq(""), qq(""), qq(trd),
            qq(a1), qq(a2),
            amt_h(t.get("exemptCentavos")), amt_h(t.get("zeroRatedCentavos")),
            amt_h(t.get("servicesCentavos")), amt_h(t.get("capitalGoodsCentavos")),
            amt_h(t.get("otherGoodsCentavos")), amt_h(t.get("inputTaxCentavos")),
            amt_h(0), qq(rdo), period_str, fy,
        ])
    ]
    for r in data["rows"]:
        ra1, ra2 = split_addr(r.get("address"))
        lines.append(",".join([
            "D", "P", qq(tin9(r.get("tin"))), qq(clean_name(r.get("name"))), qq(""), qq(""), qq(""),
            qq(ra1), qq(ra2),
            amt_d(r.get("exemptCentavos")), amt_d(r.get("zeroRatedCentavos")),
            amt_d(r.get("servicesCentavos")), amt_d(r.get("capitalGoodsCentavos")),
            amt_d(r.get("otherGoodsCentavos")), amt_d(r.get("inputTaxCentavos")),
            seller, period_str,
        ]))
    filename = f"{seller}P{end:%m%Y}.DAT"
    return "\r\n".join(lines) + "\r\n", filename


def build_sawt_dat(taxpayer: dict, end: date, data: dict, *, form: str = "1702Q") -> tuple[str, str]:
    if form not in ("1702Q", "2550Q"):
        raise ValueError(f"Unsupported SAWT form: {form}")
    seller, reg, _, _, _, rdo = _header_names(taxpayer)
    br = branch4(taxpayer.get("branchCode"))
    period_mm_yyyy = end.strftime("%m/%Y")
    t = data["totals"]
    lines = [
        ",".join(["HSAWT", f"H{form}", seller, br, qq(reg), qq(""), qq(""), qq(""), period_mm_yyyy, rdo]),
    ]
    for idx, r in enumerate(data["rows"], start=1):
        pt = tin9(r.get("tin"))
        pbr = branch4(None)
        rate_pct = f"{(r.get('rateBp') or 0) / 100:.2f}"
        lines.append(",".join([
            "DSAWT", f"D{form}", str(idx), pt, pbr, qq(clean_name(r.get("payor"))), qq(""), qq(""), qq(""),
            period_mm_yyyy, qq(""), clean_text(r.get("atc") or ""), rate_pct,
            amt_h(r.get("incomePaymentCentavos")), amt_h(r.get("withheldCentavos")),
        ]))
    lines.append(",".join([
        "CSAWT", f"C{form}", seller, br, period_mm_yyyy,
        amt_h(t.get("incomePaymentCentavos")), amt_h(t.get("withheldCentavos")),
    ]))
    filename = f"{seller}{br}{end:%m%Y}{form}.DAT"
    return "\r\n".join(lines) + "\r\n", filename


def build_qap_dat(taxpayer: dict, end: date, data: dict) -> tuple[str, str]:
    seller, reg, _, _, _, rdo = _header_names(taxpayer)
    br = branch4(taxpayer.get("branchCode"))
    period_str = end.strftime("%m/%Y")
    t = data["totals"]
    lines = [
        ",".join(["H1601EQ", seller, br, qq(reg), period_str, rdo]),
    ]
    for idx, r in enumerate(data["rows"], start=1):
        pt = tin9(r.get("tin"))
        pbr = branch4(None)
        rate_pct = f"{(r.get('rateBp') or 0) / 100:.2f}"
        lines.append(",".join([
            "D1601EQ", str(idx), pt, pbr, qq(clean_name(r.get("payee"))), qq(""), qq(""), qq(""),
            period_str, clean_text(r.get("atc") or ""), rate_pct,
            amt_h(r.get("baseCentavos")), amt_h(r.get("taxCentavos")),
        ]))
    lines.append(",".join([
        "C1601EQ", seller, br, period_str,
        amt_h(t.get("baseCentavos")), amt_h(t.get("taxCentavos")),
    ]))
    filename = f"{seller}{br}{end:%m%Y}1601EQ.DAT"
    return "\r\n".join(lines) + "\r\n", filename


def build_list_dat(which: str, taxpayer: dict, end: date, data: dict, *, sawt_form: str = "1702Q") -> tuple[str, str]:
    if which == "sawt":
        return build_sawt_dat(taxpayer, end, data, form=sawt_form)
    builders = {"sls": build_sls_dat, "slp": build_slp_dat, "qap": build_qap_dat}
    if which not in builders:
        raise ValueError(f"Unsupported DAT list: {which}")
    return builders[which](taxpayer, end, data)
