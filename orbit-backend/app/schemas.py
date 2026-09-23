"""Request bodies. JSON is camelCase on the wire; Python stays snake_case."""

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.security import MAX_PASSWORD_BYTES, MIN_PASSWORD


class Api(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _blank_is_none(cls, data: Any) -> Any:
        # Forms send "" for an empty optional field; treat it as not given.
        if isinstance(data, dict):
            return {k: (None if isinstance(v, str) and not v.strip() else v) for k, v in data.items()}
        return data


def _check_password(value: str | None) -> str | None:
    if value is None:
        return value
    if len(value) < MIN_PASSWORD:
        raise ValueError(f"Use at least {MIN_PASSWORD} characters.")
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Use at most {MAX_PASSWORD_BYTES} bytes.")
    return value


def _check_email(value: str) -> str:
    # Shape only. Deliverability isn't ours to judge, and demo accounts use .test.
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s.]+", value):
        raise ValueError("Enter an email address like name@company.com.")
    return value.lower()


Email = Annotated[str, AfterValidator(_check_email)]


def phone_digits(phone: str | None) -> str | None:
    return re.sub(r"\D", "", phone) if phone else None


# --- sign-in -----------------------------------------------------------------


class LoginIn(Api):
    email: Email
    password: str = Field(min_length=1, max_length=200)


class NewCompanyIn(Api):
    """A company joining the platform, and the first person who will run it.

    Only a Developer Admin sends this (app/routers/platform_api.py). Everything
    with a default is something the company's own Admin changes afterwards in
    Settings; they are here so a new company opens to a working system."""

    name: str = Field(min_length=2, max_length=120)
    # Its address inside Orbit. Made from the name when not given, and never
    # changed afterwards: other things point at it.
    slug: str | None = Field(None, max_length=40)
    brand_name: str | None = Field(None, max_length=80)
    template: str = Field("generic_b2b", max_length=40)
    currency: str = Field("PHP", min_length=3, max_length=3)
    minor_units: int = Field(2, ge=0, le=4)
    locale: str = Field("en-PH", max_length=16)
    timezone: str = Field("Asia/Manila", max_length=64)
    order_prefix: str | None = Field(None, max_length=8)

    admin_email: Email
    admin_name: str = Field(min_length=2, max_length=120)
    admin_password: str

    _password = field_validator("admin_password")(_check_password)

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class SwitchOrgIn(Api):
    org_id: str = Field(min_length=1, max_length=36)


class ViewAsIn(Api):
    """Whose eyes to look through, and in which company. Developer Admins only."""

    org_id: str = Field(min_length=1, max_length=36)
    user_id: str = Field(min_length=1, max_length=36)


# --- sales workspace -----------------------------------------------------------

# A company picks its own customer kinds, activity kinds and call outcomes in
# Settings -> Lists (app/lists.py), so these carry a code, not one of a fixed
# set. The routers check the code against that company's list; only the shape
# is enforced here.
Choice = Annotated[str, Field(min_length=1, max_length=60)]
CustomerKind = Choice
ActivityKind = Choice
Outcome = Choice
# Not a pick-list: retention, dashboards and reminders all read this, and a
# fourth value would change what they mean.
CustomerStatus = Literal["lead", "active", "inactive"]

CUSTOMER_REQUIRED = ("team", "name", "kind", "status")

# What a company's own field holds: text, a number, or a date as 2026-03-31.
# Which keys are allowed and what each one means is that company's to say, so
# only the shape is enforced here; app/fields.py checks the values themselves.
FieldValue = str | int | float | None
Details = dict[str, FieldValue]


class CustomerFields(Api):
    team: str | None = Field(None, max_length=40)
    headquarters: str | None = Field(None, max_length=40)
    name: str | None = Field(None, min_length=2, max_length=120)
    kind: CustomerKind | None = None
    specialty: str | None = Field(None, max_length=80)
    phone: str | None = Field(None, max_length=40)
    email: Email | None = None
    address: str | None = Field(None, max_length=240)
    city: str | None = Field(None, max_length=80)
    status: CustomerStatus | None = None
    notes: str | None = Field(None, max_length=2000)
    # This company's own customer fields (Settings -> Fields).
    details: Details | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.fullmatch(r"[0-9+()\-\s.]+", value) or len(phone_digits(value) or "") < 7:
            raise ValueError("Enter a phone number with at least 7 digits.")
        return value


class CustomerIn(CustomerFields):
    # A customer belongs to one division's team. The sales workspace spans every
    # division a person sells in, so which one is asked on the form rather than
    # taken from the address (and filled in silently for anyone with only one).
    division: str = Field(max_length=32)
    team: str = Field(max_length=40)
    name: str = Field(min_length=2, max_length=120)
    kind: CustomerKind
    status: CustomerStatus = "lead"
    # Set after the person has seen the possible duplicates and wants to save anyway.
    allow_duplicate: bool = False


class CustomerPatch(CustomerFields):
    rev: str | None = None

    @model_validator(mode="after")
    def _required_stay_set(self) -> "CustomerPatch":
        for name in CUSTOMER_REQUIRED:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be empty")
        return self


class FollowUpIn(Api):
    title: str = Field(min_length=2, max_length=160)
    due_on: date
    assignee_id: str | None = None


class ActivityIn(Api):
    kind: ActivityKind
    outcome: Outcome | None = None
    summary: str = Field(min_length=2, max_length=2000)
    occurred_at: datetime | None = None
    follow_up: FollowUpIn | None = None


class FollowUpPatch(Api):
    status: Literal["open", "done"] | None = None
    title: str | None = Field(None, min_length=2, max_length=160)
    due_on: date | None = None
    assignee_id: str | None = None


# --- quotes (money in centavos, percentages in basis points: 1250 = 12.5%) --------

# A ceiling on any single amount, in whole minor units: ten billion of them,
# which is a thousand million pesos. It exists to catch a typo, not to price anything.
MAX_CENTAVOS = 100_000_000_000
Centavos = Annotated[int, Field(ge=0, le=MAX_CENTAVOS)]


class ManualDiscountIn(Api):
    kind: Literal["percent", "amount"]
    # Basis points for "percent", centavos off the line for "amount".
    value: int = Field(gt=0, le=MAX_CENTAVOS)

    @model_validator(mode="after")
    def _percent_at_most_100(self) -> "ManualDiscountIn":
        if self.kind == "percent" and self.value > 10_000:
            raise ValueError("A discount can't be more than 100%.")
        return self


class QuoteLineIn(Api):
    # A line is either a product or a bundle. A bundle line carries `bundleId`
    # and leaves `productId` empty; `quantity` is then how many sets.
    product_id: str = Field("", max_length=36)
    bundle_id: str | None = Field(None, max_length=36)
    quantity: int = Field(ge=1, le=100_000)
    # Only for price types the rep types in (Special Price); list prices come from Inventory.
    unit_price_centavos: int | None = Field(None, gt=0, le=MAX_CENTAVOS)
    promo_id: str | None = Field(None, max_length=36)
    discount: ManualDiscountIn | None = None

    @model_validator(mode="after")
    def _one_or_the_other(self) -> "QuoteLineIn":
        if bool(self.product_id) == bool(self.bundle_id):
            raise ValueError("A line is either a product or a bundle.")
        if self.bundle_id and (self.promo_id or self.discount or self.unit_price_centavos):
            # The set price is the price: see app/bundles.py.
            raise ValueError("A bundle's price is the price — no promo or discount on top.")
        return self


class GuaranteeLetterIn(Api):
    number: str = Field(min_length=2, max_length=60)
    issued_on: date
    amount_centavos: int = Field(gt=0, le=MAX_CENTAVOS)


class QuoteIn(Api):
    price_type: str = Field(max_length=40)
    rx: bool = False
    # "self", or the code of a guarantee-letter issuer (dswd, pcso...).
    payer: str = Field("self", max_length=40)
    notes: str | None = Field(None, max_length=2000)
    lines: list[QuoteLineIn] = Field(min_length=1, max_length=50)
    letter: GuaranteeLetterIn | None = None


# --- finance ---------------------------------------------------------------------


class DecisionIn(Api):
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _reason_for_rejecting(self) -> "DecisionIn":
        if self.decision == "reject" and not self.note:
            raise ValueError("Say why, so the rep knows what to fix.")
        return self


class PaymentIn(Api):
    paid_on: date
    amount_centavos: int = Field(gt=0, le=MAX_CENTAVOS)
    reference: str | None = Field(None, max_length=80)


# --- settings --------------------------------------------------------------------


class AssignmentIn(Api):
    role_key: str
    module_key: str
    division_code: str | None = None
    subdivision_code: str | None = None


class UserIn(Api):
    email: Email
    full_name: str = Field(min_length=2, max_length=120)
    password: str
    assignments: list[AssignmentIn] = []

    _password = field_validator("password")(_check_password)


class UserPatch(Api):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    is_active: bool | None = None
    password: str | None = None
    # The job title they hold. "" clears it; it never affects what they may do.
    position_id: str | None = None

    _password = field_validator("password")(_check_password)


class PositionIn(Api):
    title: str = Field(min_length=2, max_length=80)
    # The department that names it. Null is the company's own.
    division_code: str | None = None


class PositionPatch(Api):
    title: str | None = Field(None, min_length=2, max_length=80)
    is_active: bool | None = None


class RoleIn(Api):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field("", max_length=300)


class RolePatch(Api):
    name: str | None = Field(None, min_length=2, max_length=80)
    description: str | None = Field(None, max_length=300)


class MatrixIn(Api):
    # role key -> module key -> actions
    permissions: dict[str, dict[str, list[str]]]


class NameIn(Api):
    name: str = Field(min_length=2, max_length=80)


class NamePatch(Api):
    name: str | None = Field(None, min_length=2, max_length=80)
    is_active: bool | None = None


# A department an Admin adds in Settings -> Teams. `icon` is a name from
# the frontend's own registry; None leaves it with the default.
class CompanyPatch(Api):
    """What an Admin may change about their own company. Its slug and id
    are not among them: other things point at those."""

    name: str | None = Field(None, min_length=2, max_length=120)
    brand_name: str | None = Field(None, min_length=1, max_length=80)
    currency: str | None = Field(None, min_length=3, max_length=3)
    # 2 for a peso, 0 for a yen. Amounts are whole minor units everywhere.
    minor_units: int | None = Field(None, ge=0, le=4)
    locale: str | None = Field(None, min_length=2, max_length=16)
    timezone: str | None = Field(None, min_length=3, max_length=64)
    # Not the order prefix: order numbering belongs together, in Settings ->
    # Orders, and one setting with two screens is one too many.


class DepartmentIn(NameIn):
    icon: str | None = Field(None, max_length=40)
    # A sales division gets the sales workspace and the rules it needs to quote;
    # a department holds teams and people without screens of its own.
    kind: Literal["sales", "department"] = "department"


class DepartmentPatch(NamePatch):
    icon: str | None = Field(None, max_length=40)


# --- pricing rules (Settings) -------------------------------------------------------

PriceEntry = Literal["list", "entered"]
PriceRule = Literal["always", "with_rx"]


class DivisionPricingIn(Api):
    uses_price_list: bool
    allows_guarantee_letters: bool
    discount_approval_bp: int = Field(ge=0, le=10_000)
    # price type code -> rule. A price type left out is off for the division.
    price_types: dict[str, PriceRule]


class PricingRulesIn(Api):
    # division code -> its rules. Divisions left out are unchanged.
    divisions: dict[str, DivisionPricingIn]


class PriceTypeIn(Api):
    name: str = Field(min_length=2, max_length=80)
    entry: PriceEntry = "list"
    requires_notes: bool = False
    needs_approval: bool = False


class PriceTypePatch(Api):
    name: str | None = Field(None, min_length=2, max_length=80)
    entry: PriceEntry | None = None
    requires_notes: bool | None = None
    needs_approval: bool | None = None
    is_active: bool | None = None


# --- retention rules (Settings) ------------------------------------------------------


class RetentionRuleIn(Api):
    at_risk_days: int = Field(ge=1, le=365)
    lost_days: int = Field(ge=2, le=730)

    @model_validator(mode="after")
    def _lost_after_at_risk(self) -> "RetentionRuleIn":
        if self.lost_days <= self.at_risk_days:
            raise ValueError("A customer is lost only after being at risk: make “lost after” the bigger number.")
        return self


class RetentionRulesIn(Api):
    # division code -> its thresholds. Divisions left out are unchanged.
    divisions: dict[str, RetentionRuleIn]


class GoalTargetsIn(Api):
    # division code -> goal key -> target, in the goal's unit (see app/goals.py).
    # Divisions and goals left out are unchanged.
    targets: dict[str, dict[str, int]]


# --- inventory ---------------------------------------------------------------------

PRODUCT_REQUIRED = ("code", "name", "unit")


class ProductFields(Api):
    code: str | None = Field(None, min_length=2, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    name: str | None = Field(None, min_length=2, max_length=120)
    # This company's own product fields (Settings -> Fields).
    details: Details | None = None
    # The pharma three, which are now ordinary fields under these same keys.
    # They stay until the web app sends them in `details` (see inventory.py).
    generic_name: str | None = Field(None, max_length=120)
    strength: str | None = Field(None, max_length=60)
    form: str | None = Field(None, max_length=60)
    unit: str | None = Field(None, min_length=1, max_length=60)


class ProductIn(ProductFields):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    name: str = Field(min_length=2, max_length=120)
    unit: str = Field(min_length=1, max_length=60)
    # list price type code -> centavos
    prices: dict[str, Centavos] = {}


class ProductPatch(ProductFields):
    is_active: bool | None = None

    @model_validator(mode="after")
    def _required_stay_set(self) -> "ProductPatch":
        for name in PRODUCT_REQUIRED:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be empty")
        return self


class PricesIn(Api):
    # list price type code -> centavos, or null to remove that price
    prices: dict[str, Centavos | None]


PromoKind = Literal["percent", "amount", "free_goods", "tiered"]


class PromoTierIn(Api):
    min_qty: int = Field(ge=1, le=100_000)
    percent_bp: int = Field(ge=1, le=10_000)


class PromoIn(Api):
    name: str = Field(min_length=2, max_length=120)
    kind: PromoKind
    percent_bp: int | None = Field(None, ge=1, le=10_000)
    amount_centavos: int | None = Field(None, ge=1, le=MAX_CENTAVOS)
    buy_qty: int | None = Field(None, ge=1, le=100_000)
    free_qty: int | None = Field(None, ge=1, le=100_000)
    tiers: list[PromoTierIn] = Field([], max_length=10)
    starts_on: date
    ends_on: date | None = None
    # None: every product. Otherwise only these.
    product_ids: list[str] | None = Field(None, max_length=500)
    division_codes: list[str] = Field(min_length=1, max_length=20)


class PromoPatch(Api):
    is_active: bool


class BundleItemIn(Api):
    product_id: str = Field(max_length=36)
    qty: int = Field(ge=1, le=10_000)


class BundleIn(Api):
    """A set of products at one price. `as_one_line` decides only what the
    customer reads — the total is the same either way (app/bundles.py)."""

    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
    name: str = Field(min_length=2, max_length=120)
    price_centavos: int = Field(ge=1, le=MAX_CENTAVOS)
    as_one_line: bool = True
    items: list[BundleItemIn] = Field(max_length=50)
    starts_on: date
    ends_on: date | None = None
    division_codes: list[str] = Field(max_length=20)

    @field_validator("items")
    @classmethod
    def _has_products(cls, items: list[BundleItemIn]) -> list[BundleItemIn]:
        if not items:
            raise ValueError("Put at least one product in the set.")
        return items

    @field_validator("division_codes")
    @classmethod
    def _has_divisions(cls, codes: list[str]) -> list[str]:
        if not codes:
            raise ValueError("Pick at least one division that may sell it.")
        return codes


class BundlePatch(Api):
    is_active: bool


class AppLinkIn(Api):
    """One application this company reaches from Orbit. `code` is left out for a
    new one — it is made from the name — and carried for one that exists."""

    code: str | None = Field(None, max_length=32)
    name: str = Field(min_length=2, max_length=80)
    # Empty is allowed and means "not set up yet": the link isn't offered until
    # somebody says where it is, which is better than a link that goes nowhere.
    # None because Api turns a blank form field into one; both mean "not set".
    url: str | None = Field("", max_length=300)
    description: str | None = Field("", max_length=200)
    icon: str | None = Field(None, max_length=40)
    is_active: bool = True
    # Read the list, change a line, send it back is the natural way to use this,
    # so the two the API decides for itself are taken and ignored rather than
    # refused. Whether an app is built in, and whether it is ready to be opened,
    # are never the caller's to say.
    is_built_in: bool | None = None
    is_ready: bool | None = None

    @field_validator("url", "description")
    @classmethod
    def _never_none(cls, value: str | None) -> str:
        return value or ""

    @field_validator("url")
    @classmethod
    def _a_real_address(cls, url: str) -> str:
        if not url:
            return ""
        if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", url):
            raise ValueError("Give the full address, starting with http:// or https://.")
        return url.rstrip("/")


class AppLinksIn(Api):
    apps: list[AppLinkIn] = Field(max_length=30)


class PricingSettingsIn(Api):
    bundles_as_one_line: bool


# --- bulk actions (app/routers/bulk.py) ----------------------------------------------

MAX_BULK = 500
BulkIds = Annotated[list[Annotated[str, Field(min_length=1, max_length=64)]], Field(min_length=1, max_length=MAX_BULK)]


class CustomersStatusBulk(Api):
    action: Literal["status"]
    ids: BulkIds
    status: CustomerStatus


class CustomersOwnerBulk(Api):
    action: Literal["owner"]
    ids: BulkIds
    owner_id: str = Field(max_length=64)


class CustomersFollowUpBulk(Api):
    """One follow-up for each customer: a win-back round, a promo round of calls."""

    action: Literal["follow_up"]
    ids: BulkIds
    follow_up: FollowUpIn
    # Give each to the customer's owner (a lead's win-back round); unowned ones go to the assignee.
    to_owner: bool = False


class CustomersDeleteBulk(Api):
    action: Literal["delete"]
    ids: BulkIds


CustomersBulkIn = Annotated[
    CustomersStatusBulk | CustomersOwnerBulk | CustomersFollowUpBulk | CustomersDeleteBulk,
    Field(discriminator="action"),
]


class FollowUpsBulkIn(Api):
    action: Literal["done", "open", "due", "assign"]
    ids: BulkIds
    due_on: date | None = None
    assignee_id: str | None = Field(None, max_length=64)

    @model_validator(mode="after")
    def _what_to_change(self) -> "FollowUpsBulkIn":
        if self.action == "due" and self.due_on is None:
            raise ValueError("Pick the new due date.")
        if self.action == "assign" and not self.assignee_id:
            raise ValueError("Pick who to give them to.")
        return self


class DecisionsBulkIn(DecisionIn):
    ids: BulkIds


class ProductsBulkIn(Api):
    action: Literal["activate", "deactivate", "reprice"]
    ids: BulkIds
    # reprice: change each price by this much, in basis points (+500 is 5% up,
    # -1000 is 10% down); only the named price type, or every list price.
    change_bp: int | None = Field(None, ge=-9_000, le=10_000)
    price_type: str | None = Field(None, max_length=40)

    @model_validator(mode="after")
    def _how_much(self) -> "ProductsBulkIn":
        if self.action == "reprice" and not self.change_bp:
            raise ValueError("Say how much to change the prices by.")
        return self


# --- order settings (Settings -> Orders) ------------------------------------------------

OrderFieldType = Literal["text", "textarea", "number", "date", "choice"]


class OrderListItemIn(Api):
    # Absent for a new item; its code is made from the name.
    code: str | None = Field(None, max_length=60)
    name: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class OrderListIn(Api):
    items: list[OrderListItemIn] = Field(max_length=100)


class ListItemIn(OrderListItemIn):
    # Only some lists show an icon; the rest ignore it.
    icon: str | None = Field(None, max_length=40)


class ListIn(Api):
    items: list[ListItemIn] = Field(max_length=100)


class TeamPriceIn(Api):
    product_id: str = Field(max_length=36)
    price_type_code: str = Field(max_length=40)
    # None hands this price back to the company's.
    amount_centavos: int | None = Field(None, ge=0, le=MAX_CENTAVOS)


class TeamPricesIn(Api):
    items: list[TeamPriceIn] = Field(max_length=500)


class TeamPriceTypesIn(Api):
    codes: list[str] = Field(default_factory=list, max_length=40)


class OrderFieldIn(Api):
    key: str | None = Field(None, max_length=40)
    label: str = Field(min_length=2, max_length=80)
    type: OrderFieldType = "text"
    required: bool = False
    options: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field([], max_length=30)
    help: str = Field("", max_length=200)
    # The code of a `field_section` list item; None puts it in the last section.
    section: str | None = Field(None, max_length=60)
    is_active: bool = True

    @field_validator("help", mode="before")
    @classmethod
    def _no_hint(cls, value: str | None) -> str:
        # A field with no hint comes back from the screen as "", which the base
        # class reads as "not given"; here that means no hint, not no value.
        return value or ""


class OrderFieldsIn(Api):
    fields: list[OrderFieldIn] = Field(max_length=30)


class OrderRulesIn(Api):
    large_order_centavos: Centavos
    recycle_days: int = Field(ge=1, le=365)
    order_prefix: str = Field(min_length=1, max_length=8, pattern=r"^[A-Z0-9]+$")


# --- the Orders app (orders_api.py) ----------------------------------------------------


class OrdersCustomerIn(CustomerIn):
    """A customer added while raising an order. Nothing extra: the division is
    on CustomerIn itself, because a customer always belongs to one."""
