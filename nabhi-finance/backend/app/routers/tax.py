"""Tax: the company's registration, the dated rates, and working out a sale.

Anyone signed in to Finance can see the setup and work out a sale; only its
admins change the registration or a rate. The other Nabhi apps ask for the
same answer through /integration/tax (app/routers/integration.py), so a
quote, a pharmacy sale and an invoice are taxed by one set of rules.
"""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import select

from app.config import Settings
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import TaxProfile, TaxRate
from app.tax import rates as rate_book
from app.tax.engine import LineIn, SaleIn, TaxError, compute
from app.tax.packs import PACKS, pack_for

router = APIRouter(prefix="/tax", tags=["tax"])


class Api(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _blank_is_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in data.items()}
        return data


def field_error(field: str, message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", *field.split(".")], "msg": message}])


def today(settings: Settings) -> date:
    return datetime.now(ZoneInfo(settings.org_timezone)).date()


def iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return (moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment).isoformat()


# --- the TIN -------------------------------------------------------------------------------

TIN_DIGITS = re.compile(r"\d{9}(\d{3}|\d{5})?")


def split_tin(value: str) -> tuple[str, str | None]:
    """'123-456-789-00000' -> ('123-456-789', '00000'). A TIN is 9 digits; a
    branch code, 3 or 5 more."""
    digits = re.sub(r"[\s-]", "", value)
    if not TIN_DIGITS.fullmatch(digits):
        raise ValueError("Enter the TIN as 9 digits, with the branch code after it if you have one: 123-456-789-00000.")
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}", digits[9:] or None


# --- setup ---------------------------------------------------------------------------------


def profile_complete(p: TaxProfile | None) -> bool:
    """Registered enough to issue a tax invoice: the name, the TIN and the address."""
    return bool(p and p.registered_name and p.tin and p.registered_address)


def profile_out(p: TaxProfile) -> dict:
    pack = pack_for(p.country)
    return {
        "country": p.country,
        "countryName": pack.name,
        "regime": p.regime,
        "regimeName": pack.regimes[p.regime],
        "registeredName": p.registered_name,
        "tradeName": p.trade_name,
        "tin": p.tin,
        "branchCode": p.branch_code,
        "registeredAddress": p.registered_address,
        "pricesIncludeTax": p.prices_include_tax,
        "complete": profile_complete(p),
        "updatedAt": iso(p.updated_at),
    }


def rate_out(r: TaxRate) -> dict:
    return {
        "id": r.id,
        "rateBp": r.rate_bp,
        "validFrom": r.valid_from.isoformat(),
        "validTo": r.valid_to.isoformat() if r.valid_to else None,
        "source": r.source,
        "basis": r.basis,
    }


def setup_out(db: DB, settings: Settings, can_edit: bool) -> dict:
    profile = db.get(TaxProfile, 1)
    pack = pack_for(profile.country)
    on = today(settings)
    rows = db.scalars(select(TaxRate).where(TaxRate.country == pack.country).order_by(TaxRate.valid_from.desc())).all()
    lookup = rate_book.lookup(db, pack.country)
    return {
        "profile": profile_out(profile),
        "countries": [{"code": c, "name": p.name} for c, p in PACKS.items()],
        "pack": {
            "country": pack.country,
            "name": pack.name,
            "document": pack.invoice["document"],
            "regimes": [{"key": k, "name": v} for k, v in pack.regimes.items()],
            "categories": [{"key": k, "name": v} for k, v in pack.categories.items()],
            "treatments": [{"key": k, "name": v["name"], "needsId": v["needs_id"]} for k, v in pack.treatments.items()],
            "codes": [
                {
                    "code": c.code,
                    "name": c.name,
                    "bucket": c.bucket,
                    "rated": c.rated,
                    "rateTodayBp": lookup(c.code, on) if c.rated else None,
                    "rates": [rate_out(r) for r in rows if r.code == c.code],
                }
                for c in pack.codes.values()
            ],
        },
        "today": on.isoformat(),
        "canEdit": can_edit,
    }


@router.get("/setup")
def read_setup(user: CurrentUser, db: DB, settings: SettingsDep) -> dict:
    return setup_out(db, settings, user.role == "admin")


class ProfileIn(Api):
    country: str = Field("PH", min_length=2, max_length=2)
    regime: str = Field(max_length=12)
    registered_name: str | None = Field(None, max_length=200)
    trade_name: str | None = Field(None, max_length=200)
    tin: str | None = Field(None, max_length=20)
    branch_code: str | None = Field(None, max_length=5)
    registered_address: str | None = Field(None, max_length=300)
    prices_include_tax: bool = True

    @field_validator("branch_code")
    @classmethod
    def _branch(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{3}|\d{5}", value):
            raise ValueError("A branch code is 3 or 5 digits: 00000 for the head office.")
        return value


@router.put("/profile")
def update_profile(admin: AdminUser, db: DB, settings: SettingsDep, body: ProfileIn) -> dict:
    if body.country not in PACKS:
        raise field_error("country", "There's no tax pack for that country yet.")
    if body.regime not in pack_for(body.country).regimes:
        raise field_error("regime", "Pick how the company is registered.")
    profile = db.get(TaxProfile, 1)
    tin, branch = None, body.branch_code
    if body.tin:
        try:
            tin, in_tin = split_tin(body.tin)
        except ValueError as problem:
            raise field_error("tin", str(problem)) from None
        branch = branch or in_tin
    profile.country, profile.regime = body.country, body.regime
    profile.registered_name, profile.trade_name = body.registered_name, body.trade_name
    profile.tin, profile.branch_code = tin, branch or "00000"
    profile.registered_address, profile.prices_include_tax = body.registered_address, body.prices_include_tax
    profile.updated_by_id = admin.id
    db.commit()
    return setup_out(db, settings, True)


class RateIn(Api):
    code: str = Field(max_length=20)
    rate_bp: int = Field(ge=0, le=10_000)
    valid_from: date
    basis: str = Field(min_length=3, max_length=200)


@router.post("/rates", status_code=status.HTTP_201_CREATED)
def add_rate(admin: AdminUser, db: DB, settings: SettingsDep, body: RateIn) -> dict:
    """A change in a rate, from a day on: the law's, entered ahead of an update."""
    profile = db.get(TaxProfile, 1)
    pack = pack_for(profile.country)
    code = pack.codes.get(body.code)
    if code is None or not code.rated:
        raise field_error("code", "Pick a tax code that has a rate.")
    if db.scalar(select(TaxRate.id).where(TaxRate.country == pack.country, TaxRate.code == body.code, TaxRate.valid_from == body.valid_from)):
        raise field_error("validFrom", "A rate already starts on that day. Pick another day.")
    rate_book.change(db, pack.country, body.code, body.rate_bp, body.valid_from, body.basis, admin.id)
    db.commit()
    return setup_out(db, settings, True)


# --- working out a sale ----------------------------------------------------------------------


class LineBody(Api):
    ref: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=200)
    quantity: int = Field(ge=1, le=1_000_000)
    unit_price_centavos: int = Field(ge=0, le=10_000_000_000)
    discount_centavos: int = Field(0, ge=0)
    category: str = Field("standard", max_length=20)
    # Whether a senior citizen's or PWD's 20% applies to it (medicines, for one).
    relief_eligible: bool = False


class BuyerBody(Api):
    name: str | None = Field(None, max_length=200)
    tin: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=300)
    # A senior citizen's OSCA ID or a PWD's ID number.
    id_number: str | None = Field(None, max_length=40)


class SaleBody(Api):
    treatment: str = Field("regular", max_length=20)
    on: date | None = None
    # Leave out to use the company's setting.
    prices_include_tax: bool | None = None
    buyer: BuyerBody | None = None
    lines: list[LineBody] = Field(min_length=1, max_length=500)


def work_out(db, settings: Settings, body: SaleBody) -> dict:
    """The sale as its invoice shows it. Shared by /tax/compute and /integration/tax/compute."""
    profile = db.get(TaxProfile, 1)
    pack = pack_for(profile.country)
    treatment = pack.treatments.get(body.treatment)
    if treatment is None:
        raise field_error("treatment", "Pick who is buying.")
    for n, line in enumerate(body.lines):
        if line.category not in pack.categories:
            raise field_error(f"lines.{n}.category", "Pick the product's VAT category.")
    buyer = body.buyer or BuyerBody()
    if treatment["needs_id"] and not buyer.id_number:
        raise field_error("buyer.idNumber", f"A {treatment['name'].split(' (')[0].lower()}'s ID number goes on the invoice.")
    if buyer.tin:
        try:
            split_tin(buyer.tin)
        except ValueError as problem:
            raise field_error("buyer.tin", str(problem)) from None
    on = body.on or today(settings)
    inclusive = profile.prices_include_tax if body.prices_include_tax is None else body.prices_include_tax
    sale = SaleIn(
        profile.regime, body.treatment, inclusive, on,
        [LineIn(l.quantity, l.unit_price_centavos, l.category, l.discount_centavos, l.relief_eligible, l.ref, l.description) for l in body.lines],
    )
    try:
        result = compute(pack, rate_book.lookup(db, pack.country), sale)
    except TaxError as problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(problem)) from None

    warnings = []
    if not (profile.registered_name and profile.tin and profile.registered_address):
        warnings.append("The company's registered name, TIN and address aren't all filled in, and every invoice needs them.")
    summary = pack.invoice["summary"]["vat" if profile.regime == "vat" else "non_vat"]
    seller_code = pack.codes.get(result.seller_tax_code) if result.seller_tax_code else None
    return {
        "document": pack.invoice["document"],
        "country": pack.country,
        "on": on.isoformat(),
        "pricesIncludeTax": inclusive,
        "seller": {
            "registeredName": profile.registered_name,
            "tradeName": profile.trade_name,
            "tin": f"{profile.tin}-{profile.branch_code}" if profile.tin else None,
            "address": profile.registered_address,
            "regime": profile.regime,
            "regimeName": pack.regimes[profile.regime],
        },
        "buyer": {"name": buyer.name, "tin": buyer.tin, "address": buyer.address, "idNumber": buyer.id_number},
        "treatment": {"key": body.treatment, "name": treatment["name"]},
        "lines": [
            {
                "ref": l.ref, "description": l.description, "code": l.code, "codeName": l.code_name, "bucket": l.bucket,
                "rateBp": l.rate_bp, "priceCentavos": l.price, "baseCentavos": l.base, "reliefCentavos": l.relief,
                "taxableCentavos": l.taxable, "taxCentavos": l.tax, "totalCentavos": l.total,
            }
            for l in result.lines
        ],
        "summary": [{"key": key, "label": label, "amountCentavos": getattr(result, key)} for key, label in summary],
        "relief": {"label": result.relief_label, "amountCentavos": result.relief} if result.relief else None,
        "totalDueCentavos": result.total_due,
        "sellerTax": {
            "code": seller_code.code, "name": seller_code.name, "rateBp": result.seller_tax_rate_bp, "amountCentavos": result.seller_tax,
        } if seller_code else None,
        "notice": pack.invoice["non_vat_notice"] if profile.regime == "non_vat" else None,
        "warnings": warnings,
    }


@router.post("/compute")
def compute_sale(_: CurrentUser, db: DB, settings: SettingsDep, body: SaleBody) -> dict:
    return work_out(db, settings, body)
