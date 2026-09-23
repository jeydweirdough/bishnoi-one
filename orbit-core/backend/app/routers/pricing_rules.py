"""Settings -> Pricing rules: which price types each division may quote with,
whether it takes guarantee letters, and how big a manual discount can be before
Finance must approve. Also the price types themselves and the guarantee-letter
issuers. Admins only.

Price types and issuers are switched off, never deleted: old quotes name them.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.deps import DB, CurrentUser, require_settings
from app.errors import conflict, invalid
from app.models import Division, DivisionPriceType, DivisionPricing, GuaranteeLetterIssuer, PriceType, PricingSettings
from app.price_book import DEFAULT_DISCOUNT_APPROVAL_BP, bundles_start_as_one_line, price_type_out, quoting_divisions
from app.schemas import NameIn, NamePatch, PriceTypeIn, PriceTypePatch, PricingRulesIn, PricingSettingsIn
from app.scope import is_code, slugify
from app.tenancy import org_get


router = APIRouter(prefix="/admin/pricing", tags=["settings"], dependencies=[Depends(require_settings)])


def rules_out(db: Session) -> dict:
    db.expire_all()
    types = db.scalars(select(PriceType).order_by(PriceType.sort_order, PriceType.name))
    issuers = db.scalars(select(GuaranteeLetterIssuer).order_by(GuaranteeLetterIssuer.sort_order, GuaranteeLetterIssuer.name))
    # This company's own sales divisions, so one added in Settings -> Teams
    # can be given its price types the day it exists.
    divisions = db.scalars(select(Division).where(Division.code.in_(quoting_divisions(db))).order_by(Division.sort_order))
    rows = {
        r.division_code: r
        for r in db.scalars(select(DivisionPricing).options(selectinload(DivisionPricing.price_types)))
    }
    out = []
    for d in divisions:
        row = rows.get(d.code)
        out.append(
            {
                "code": d.code,
                "name": d.name,
                "usesPriceList": row.uses_price_list if row else True,
                "allowsGuaranteeLetters": row.allows_guarantee_letters if row else False,
                "discountApprovalBp": row.discount_approval_bp if row else DEFAULT_DISCOUNT_APPROVAL_BP,
                "priceTypes": {p.price_type_code: p.rule for p in row.price_types} if row else {},
            }
        )
    return {
        "priceTypes": [price_type_out(t) for t in types],
        "issuers": [{"code": i.code, "name": i.name, "isActive": i.is_active} for i in issuers],
        "divisions": out,
        # Company-wide selling defaults, as against a division's rules above.
        "bundlesAsOneLine": bundles_start_as_one_line(db),
    }


@router.get("")
def pricing_rules(db: DB) -> dict:
    return rules_out(db)


@router.put("/divisions")
def replace_division_rules(body: PricingRulesIn, db: DB, me: CurrentUser) -> dict:
    known_types = set(db.scalars(select(PriceType.code)))
    for code, rules in body.divisions.items():
        if code not in quoting_divisions(db) or org_get(db, Division, code) is None:
            raise invalid(f"{code} isn't a division that quotes.")
        unknown = set(rules.price_types) - known_types
        if unknown:
            raise invalid(f"Unknown price type: {', '.join(sorted(unknown))}")
        with_rx = [c for c, rule in rules.price_types.items() if rule == "with_rx"]
        if with_rx and len(with_rx) == len(rules.price_types):
            name = org_get(db, Division, code).name
            raise invalid(f"{name} needs at least one price for quotes without an Rx.")

    for code, rules in body.divisions.items():
        row = db.scalar(
            select(DivisionPricing).where(DivisionPricing.division_code == code).options(selectinload(DivisionPricing.price_types))
        )
        if row is None:
            row = DivisionPricing(division_code=code)
            db.add(row)
        row.uses_price_list = rules.uses_price_list
        row.allows_guarantee_letters = rules.allows_guarantee_letters
        row.discount_approval_bp = rules.discount_approval_bp
        row.price_types = [DivisionPriceType(price_type_code=t, rule=r) for t, r in sorted(rules.price_types.items())]
        db.flush()
    db.commit()
    audit(db, me, "pricing.rules_changed", ", ".join(sorted(body.divisions)))
    return rules_out(db)


def new_code(name: str) -> str:
    code = slugify(name)[:40].strip("-")
    if not is_code(code):
        raise invalid("Give it a name with letters or numbers.")
    return code


@router.post("/price-types", status_code=status.HTTP_201_CREATED)
def add_price_type(body: PriceTypeIn, db: DB, me: CurrentUser) -> dict:
    code = new_code(body.name)
    if org_get(db, PriceType, code) or db.scalar(select(PriceType).where(func.lower(PriceType.name) == body.name.casefold())):
        raise conflict("There's already a price type with that name.")
    last = db.scalar(select(func.max(PriceType.sort_order))) or 0
    db.add(
        PriceType(
            code=code,
            name=body.name,
            entry=body.entry,
            requires_notes=body.requires_notes,
            needs_approval=body.needs_approval,
            sort_order=last + 1,
        )
    )
    db.commit()
    audit(db, me, "price_type.added", code)
    return rules_out(db)


@router.patch("/price-types/{code}")
def update_price_type(code: str, body: PriceTypePatch, db: DB, me: CurrentUser) -> dict:
    price_type = org_get(db, PriceType, code)
    if price_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such price type.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(price_type, key, value)
    db.commit()
    audit(db, me, "price_type.updated", code, body.model_fields_set)
    return rules_out(db)


@router.post("/issuers", status_code=status.HTTP_201_CREATED)
def add_issuer(body: NameIn, db: DB, me: CurrentUser) -> dict:
    code = new_code(body.name)
    if org_get(db, GuaranteeLetterIssuer, code):
        raise conflict("That issuer is already on the list.")
    last = db.scalar(select(func.max(GuaranteeLetterIssuer.sort_order))) or 0
    db.add(GuaranteeLetterIssuer(code=code, name=body.name, sort_order=last + 1))
    db.commit()
    audit(db, me, "issuer.added", code)
    return rules_out(db)


@router.patch("/issuers/{code}")
def update_issuer(code: str, body: NamePatch, db: DB, me: CurrentUser) -> dict:
    issuer = org_get(db, GuaranteeLetterIssuer, code)
    if issuer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such issuer.")
    if body.name is not None:
        issuer.name = body.name
    if body.is_active is not None:
        issuer.is_active = body.is_active
    db.commit()
    audit(db, me, "issuer.updated", code, body.model_fields_set)
    return rules_out(db)


@router.put("/defaults")
def replace_defaults(body: PricingSettingsIn, db: DB, me: CurrentUser) -> dict:
    """The company's selling defaults. Only what a new row starts as: changing
    this never touches a bundle that already exists."""
    row = org_get(db, PricingSettings)
    if row is None:
        row = PricingSettings()
        db.add(row)
    row.bundles_as_one_line = body.bundles_as_one_line
    db.commit()
    audit(db, me, "pricing.defaults_changed", "bundlesAsOneLine")
    return rules_out(db)
