"""Supplier-import source and review data. No persistence or tax inference."""
import re
from typing import Literal

from pydantic import Field
from app.payables import WITHHOLDING
from app.routers.tax import Api, split_tin


class TinSource(Api):
    heading: str = Field(max_length=100)
    value: str = Field(max_length=200)


class Review(Api):
    tin: str | None = Field(None, max_length=200)
    tin_confirmed: bool = False
    missing_tin_accepted: bool = False
    vat_registered: bool | None = None
    withholding: str | None = Field(None, max_length=10)
    tax_confirmed: bool = False
    terms_days: int | None = Field(None, ge=0, le=365)
    terms_confirmed: bool = False
    address_choice: Literal["billing", "shipping", "missing"] | None = None
    payables_account_id: str | None = None
    account_confirmed: bool = False
    branch_confirmed: bool = False
    notes: str | None = Field(None, max_length=2000)


class SupplierRowIn(Api):
    record: int | None = Field(None, ge=1)
    name: str | None = Field(None, max_length=1000)
    company_name: str | None = Field(None, max_length=1000)
    salutation: str | None = Field(None, max_length=1000)
    first_name: str | None = Field(None, max_length=1000)
    last_name: str | None = Field(None, max_length=1000)
    email: str | None = Field(None, max_length=1000)
    phone: str | None = Field(None, max_length=1000)
    mobile: str | None = Field(None, max_length=1000)
    contact_number: str | None = Field(None, max_length=1000)
    billing_phone: str | None = Field(None, max_length=1000)
    billing_attention: str | None = Field(None, max_length=1000)
    designation: str | None = Field(None, max_length=1000)
    website: str | None = Field(None, max_length=1000)
    tin: str | None = Field(None, max_length=200)
    tin_sources: list[TinSource] = Field(default_factory=list, max_length=30)
    company_id: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=2000)
    shipping_address: str | None = Field(None, max_length=2000)
    terms: str | None = Field(None, max_length=100)
    terms_label: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=4000)
    status: str | None = Field(None, max_length=100)
    currency: str | None = Field(None, max_length=100)
    tax_name: str | None = Field(None, max_length=100)
    tax_percentage: str | None = Field(None, max_length=100)
    tax_type: str | None = Field(None, max_length=100)
    taxable: str | None = Field(None, max_length=100)
    track_tds: str | None = Field(None, max_length=100)
    accounts_payable: str | None = Field(None, max_length=300)
    review: Review = Field(default_factory=Review)


class SupplierImportCheckIn(Api):
    mode: Literal["directory", "review"] = "directory"
    rows: list[SupplierRowIn] = Field(min_length=1, max_length=3000)


class SupplierImportIn(SupplierImportCheckIn):
    confirmed: bool = False


def terms_days(text: str | None) -> int:
    if not text:
        return 30
    digits = re.search(r"\d+", text)
    return int(digits.group()) if digits else 0 if "receipt" in text.lower() else 30


def clean_supplier_row(r: SupplierRowIn) -> tuple[dict, list[str], list[str], list[str]]:
    notes, errors, reviews = [], [], []
    decision = r.review
    tin = branch = None
    candidates = [s.value for s in r.tin_sources] or ([r.tin] if r.tin else [])
    normal = {re.sub(r"[\s-]", "", value) for value in candidates}
    if len(normal) > 1 and not decision.tin_confirmed:
        reviews.append("Conflicting TIN columns: choose and confirm the correct TIN.")
    given = decision.tin if decision.tin_confirmed else next(iter(candidates), None)
    if not given and not candidates and not decision.tin_confirmed:
        given = r.company_id
    if given:
        try:
            tin, branch = split_tin(given)
            branch = branch or "00000"
        except ValueError:
            if candidates or decision.tin_confirmed:
                errors.append("Invalid TIN: correct it or exclude this row; digits are never guessed.")
            else:
                notes.append(f"Company ID in Zoho: {given} (not a TIN).")
    if decision.tin_confirmed and not decision.tin and candidates:
        errors.append("A supplied TIN cannot be silently removed. Correct it or exclude this row.")
    if not tin and not decision.missing_tin_accepted:
        reviews.append("Missing TIN: acknowledge incomplete BIR details before importing.")
    if decision.vat_registered is None or not decision.tax_confirmed:
        reviews.append("Confirm VAT registration and usual withholding; exported tax settings are hints only.")
    if decision.withholding and decision.withholding not in WITHHOLDING:
        errors.append("Choose a valid BIR withholding code.")
    days = decision.terms_days if decision.terms_days is not None else terms_days(r.terms)
    label = (r.terms_label or "").lower()
    label_days = re.search(r"\d+", label)
    contradiction = (label_days and int(label_days.group()) != days) or (any(x in label for x in ("cod", "receipt", "paid", "advance")) and days != 0)
    if (contradiction or not r.terms) and not decision.terms_confirmed:
        reviews.append("Confirm payment days against the source terms label.")
    address = r.address
    if decision.address_choice == "shipping":
        address = r.shipping_address
    elif decision.address_choice == "missing":
        address = None
    elif not address and r.shipping_address:
        reviews.append("Shipping-only address: choose shipping or leave the address missing.")
    contacts = []
    numbers = {v for v in (r.phone, r.mobile) if v}
    for number, origin in ((r.contact_number, "Zoho custom contact number"), (r.billing_phone, "Zoho billing phone")):
        if number and number not in numbers:
            contacts.append({"phone": number, "designation": origin})
            numbers.add(number)
    remarks = [r.notes]
    for heading, value in (("Zoho terms", r.terms_label), ("Billing attention", r.billing_attention), ("Website", r.website), ("Designation", r.designation)):
        if value:
            remarks.append(f"{heading}: {value}")
    if r.currency and r.currency.upper() not in ("PHP", "₱"):
        notes.append(f"Billed in {r.currency.upper()} in Zoho: Finance keeps pesos only for now.")
    if r.status and r.status.lower() not in ("active", "inactive", "disabled"):
        reviews.append("Unrecognised source status: confirm Active or Inactive in the source fields.")
    active = (r.status or "").lower() not in ("inactive", "disabled")
    if not active:
        notes.append("Inactive in Zoho: imported switched off.")
    remarks.extend(notes)
    result = {
        "name": r.name or r.company_name or "", "companyName": r.company_name,
        "salutation": r.salutation, "firstName": r.first_name, "lastName": r.last_name,
        "email": r.email, "phone": r.phone, "mobile": r.mobile,
        "tin": tin, "branchCode": branch, "address": address, "termsDays": days,
        "contacts": contacts, "notes": decision.notes if decision.notes is not None else "\n".join(v for v in remarks if v) or None,
        "vatRegistered": decision.vat_registered, "withholding": decision.withholding,
        "payablesAccountId": decision.payables_account_id, "isActive": active,
    }
    return result, notes, errors, reviews
