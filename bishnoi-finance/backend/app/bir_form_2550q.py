"""Review-only mapping for BIR 2550Q April 2024. No writes or inferred credits."""
from datetime import date

VERSION = "April 2024 (ENCS)"
TEMPLATE_NAME = "2550q-2024-04.pdf"
TEMPLATE_URL = "https://bir-cdn.bir.gov.ph/BIR/pdf/2550Q%20%20April%202024%20ENCS_Final.pdf"


def build_draft(report: dict, *, domestic_purchases_confirmed: bool = False) -> dict:
    if report.get("form") != "2550Q" or report.get("taxpayer", {}).get("regime") != "vat":
        raise ValueError("This draft supports a VAT-registered taxpayer's 2550Q only.")
    start, end = (date.fromisoformat(report["period"][k]) for k in ("start", "end"))
    year, q = report["year"], report["quarter"]
    fiscal = report["taxpayer"].get("fiscalMonthEnd", 12)
    if type(year) is not int or type(q) is not int or type(fiscal) is not int or q not in (1, 2, 3, 4) or fiscal not in range(1, 13):
        raise ValueError("Invalid return year, quarter or fiscal year end.")
    # A request cannot label one period as another quarter.
    from app.bir_reports import quarter
    expected = quarter(year, q, fiscal)
    if (start, end) != (expected.start, expected.end):
        raise ValueError("The report period does not match the selected quarter.")
    lines = {}
    for r in report["lines"]:
        if r["key"] in lines:
            raise ValueError("Duplicate report field: " + r["key"])
        if "amountCentavos" in r:
            if type(r["amountCentavos"]) is not int:
                raise ValueError("Amounts must be integer centavos, not rounded floats.")
            lines[r["key"]] = r["amountCentavos"]
    fields = {}
    def unresolved(key, label, why):
        fields[key] = {"label": label, "valueCentavos": None, "status": "needs_review", "source": why}
    def mapped(key, label, value, source):
        fields[key] = {"label": label, "valueCentavos": value, "status": "calculated", "source": source}
    def amount(key):
        if key not in lines:
            raise ValueError("Missing source total: " + key)
        return lines[key]
    mapped("31A", "VATable sales", amount("taxable"), "VAT report: taxable")
    mapped("31B", "Output VAT", amount("output"), "VAT report: output")
    mapped("32A", "Zero-rated sales", amount("zero_rated"), "VAT report: zero_rated")
    mapped("33A", "Exempt sales", amount("exempt"), "VAT report: exempt")
    total_sales = sum(fields[k]["valueCentavos"] for k in ("31A", "32A", "33A"))
    if total_sales != amount("total_sales"):
        raise ValueError("VAT report sales detail does not equal its total.")
    mapped("34A", "Total sales", total_sales, "31A + 32A + 33A")
    mapped("34B", "Total output VAT", amount("output"), "31B")
    for key, label in {
        "35B": "Output VAT on uncollected receivables", "36B": "VAT on recoveries previously deducted",
        "37B": "Adjusted output VAT", "38B": "Prior-quarter input VAT", "39B": "Deferred capital-goods input VAT",
        "40B": "Transitional input VAT", "41B": "Presumptive input VAT", "42B": "Other input VAT credits",
        "43B": "Total brought-forward input VAT", "44A": "Domestic VATable purchases", "44B": "Domestic input VAT",
        "45A": "Non-resident services", "45B": "VAT on non-resident services", "46A": "Importations", "46B": "Import VAT",
        "47A": "Other purchases", "47B": "Other current input VAT", "48A": "Domestic purchases with no input VAT",
        "49A": "VAT-exempt importations", "50A": "Current purchases", "50B": "Current input VAT", "51B": "Available input VAT",
        "52B": "Capital-goods input VAT deferred", "53B": "VAT attributable to exempt sales", "54B": "VAT refund/TCC claimed",
        "55B": "Input VAT on unpaid payables", "56B": "Other input VAT deductions", "57B": "Total input VAT deductions",
        "58B": "VAT on settled payables previously deducted", "59B": "Adjusted deductions", "60B": "Allowable input VAT",
        "61B": "Net VAT payable / excess input tax", "15": "Net VAT from item 61", "16": "Creditable VAT withheld",
        "17": "Advance VAT payments", "18": "VAT paid on previous return", "19": "Other credits/payments",
        "20": "Total credits/payments", "21": "Tax still payable / excess credits", "22": "Surcharge", "23": "Interest",
        "24": "Compromise", "25": "Total penalties", "26": "Total payable / excess credits",
        "27": "Cash/bank debit advice", "28": "Check payment", "29": "Tax debit memo", "30": "Other payment",
    }.items():
        unresolved(key, label, "Requires reviewed source evidence or depends on unresolved fields; blank is not zero.")
    if domestic_purchases_confirmed:
        if amount("importation_purchases") or amount("importation_input"):
            raise ValueError("Cannot classify recorded importations as domestic purchases.")
        source = "VAT report + explicit confirmation that all current purchases are domestic; no non-resident services/imports/other categories"
        for key, value in {"44A": amount("purchases"), "44B": amount("input"), "48A": amount("purchases_other"),
                           "45A": 0, "45B": 0, "46A": 0, "46B": 0, "47A": 0, "47B": 0, "49A": 0}.items():
            mapped(key, fields[key]["label"], value, source)
        mapped("50A", fields["50A"]["label"], amount("purchases") + amount("purchases_other"), "44A + 45A + 46A + 47A + 48A + 49A")
        mapped("50B", fields["50B"]["label"], amount("input"), "44B + 45B + 46B + 47B")
    return {"form": "2550Q", "version": VERSION, "draftOnly": True, "readyForFiling": False,
            "taxpayer": report["taxpayer"], "period": report["period"], "year": year, "quarter": q,
            "fields": fields, "domesticPurchasesConfirmed": domestic_purchases_confirmed,
            "warnings": ["DRAFT / REVIEW ONLY - not a filed return or approved tax computation.",
                         "Blank fields are unresolved, not confirmed zero. No signatures or payment proof are generated.",
                         "Unpaid invoices/bills alone do not establish entitlement to the 2024 VAT adjustments.",
                         "Existing VAT-report coverage and reversal limitations still require source-to-ledger review.",
                         "The filing channel, template version and treatment of credits/adjustments must be confirmed with Sir Mel."],
            "sourceNotes": {"inputVatCentavos": amount("input"), "vatablePurchasesCentavos": amount("purchases"),
                            "otherPurchasesCentavos": amount("purchases_other")}}
