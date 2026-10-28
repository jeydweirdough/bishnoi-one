"""The app catalogue, abilities and ready-made job roles (feature plan step 6, decisions 10, 20–25).

Bishnoi One defines all three here; companies choose from them.

- CATALOGUE: what a company turns on and sees (CRM, Field sales, Purchasing…), each running inside
  a service (an Application: crm, inventory, finance…), with the feature switches inside it. A
  company's choices are kept in nbpl_company_switches ("app:purchasing", "inventory.batches");
  anything not chosen yet is as the catalogue says (switches(), below). Off: its menus, fields and
  reports are hidden. Switches still marked `later` aren't built yet and can't be turned on.
- ABILITIES: one business task in plain words ("Approve discounts"), bundling the technical
  permissions it needs in each app (each app still declares and enforces those). Some take a limit
  (a discount percentage, an amount): kept on the role and sent with it, for approval workflows to
  check. Workflows check abilities, never role names (decision 25).
- JOB_ROLES: ready-made sets of abilities for a job, with whose records each sees in each app. A
  company copies one, then switches abilities on or off (decisions 22, 23).
"""

from dataclasses import dataclass, field

# ---- The catalogue --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Switch:
    key: str  # "<catalogue app>.<feature>"
    label: str
    hint: str = ""
    on: bool = True  # before the company chooses
    later: bool = False  # not built yet: shown, can't be turned on


@dataclass(frozen=True)
class CatalogueApp:
    key: str
    name: str
    job: str
    service: str  # the Application that runs it
    switches: tuple[Switch, ...] = ()
    later: bool = False  # not built yet


CATALOGUE: tuple[CatalogueApp, ...] = (
    CatalogueApp("crm", "CRM", "Win customers and keep them", "crm", (
        Switch("crm.deals", "Deals and forecast"),
        Switch("crm.quotes", "Quotes and approvals"),
        Switch("crm.prices", "Price rules and promos"),
        Switch("crm.lead_inbox", "Lead inbox", "Facebook, Messenger, WhatsApp, Viber and website leads in one inbox."),
        Switch("crm.retention", "Retention", "Customers at risk and lost, by department."),
        Switch("crm.kpis", "KPIs and scorecards"),
    )),
    CatalogueApp("field_sales", "Field sales", "Reps' visits to doctors and clinics", "crm", (
        Switch("field_sales.call_plans", "Call plans, tiers and zones"),
        Switch("field_sales.patient_assistance", "Patient assistance"),
        Switch("field_sales.collections", "Collections"),
        Switch("field_sales.samples", "Samples", later=True),
    )),
    CatalogueApp("sales", "Sales", "Confirmed orders, delivered and invoiced", "inventory", (
        Switch("sales.backorders", "Backorders", later=True),
        Switch("sales.returns", "Returns", later=True),
        Switch("sales.order_on_demand", "Order-on-demand", later=True),
        Switch("sales.dropship", "Dropshipping", later=True),
        Switch("sales.credit_check", "Credit check", later=True),
        Switch("sales.rx_check", "Rx check", later=True),
    ), later=True),
    CatalogueApp("purchasing", "Purchasing", "Buying from vendors", "inventory", (
        Switch("purchasing.approvals", "Purchase approvals"),
        Switch("purchasing.auto_draft", "Automatic draft purchase orders", later=True),
        Switch("purchasing.price_lists", "Vendor price lists", later=True),
        Switch("purchasing.consignment", "Consignment", later=True),
    )),
    CatalogueApp("inventory", "Inventory", "Stock and its traceability", "inventory", (
        Switch("inventory.batches", "Batches and expiry"),
        Switch("inventory.serials", "Serial numbers"),
        Switch("inventory.cpr", "CPR", "The FDA's certificate of product registration on each product."),
        Switch("inventory.warehouses", "Several warehouses"),
        Switch("inventory.counts", "Stock counts"),
        Switch("inventory.locations", "Locations in a warehouse", later=True),
        Switch("inventory.units", "Units and packaging", later=True),
    )),
    CatalogueApp("warehouse", "Warehouse", "Moving goods in and out", "inventory", (
        Switch("warehouse.routes", "Multi-step routes", later=True),
        Switch("warehouse.packages", "Packages", later=True),
        Switch("warehouse.waves", "Wave picking", later=True),
        Switch("warehouse.barcodes", "Barcode scanning", later=True),
        Switch("warehouse.quality", "Quality checks", later=True),
    ), later=True),
    CatalogueApp("shipping", "Shipping", "Getting orders to customers", "inventory", (
        Switch("shipping.couriers", "Couriers (LBC, J&T, Lalamove)", later=True),
        Switch("shipping.tracking", "Tracking numbers", later=True),
        Switch("shipping.proof", "Proof of delivery", later=True),
    ), later=True),
    CatalogueApp("invoicing", "Invoicing", "Bill customers, collect payments", "finance", (
        Switch("invoicing.payments", "Record payments"),
        Switch("invoicing.auto", "Automatic invoices", later=True),
        Switch("invoicing.channels", "Payment channels (GCash, Maya)", later=True),
        Switch("invoicing.statements", "Customer statements", later=True),
    )),
    CatalogueApp("accounting", "Accounting", "The books and the BIR", "finance", (
        Switch("accounting.bills", "Bills and vouchers"),
        Switch("accounting.funds", "Expenses and advances"),
        Switch("accounting.bank", "Bank reconciliation"),
        Switch("accounting.bir", "BIR files"),
        Switch("accounting.budgets", "Budgets", later=True),
        Switch("accounting.fixed_assets", "Fixed assets", later=True),
    )),
    CatalogueApp("pharmacy", "Pharmacy", "Prescriptions and counter dispensing", "pharmacy", (
        Switch("pharmacy.controlled", "Controlled drugs register"),
        Switch("pharmacy.patients", "Patient records"),
    )),
    CatalogueApp("office", "Office", "The office and its compliance", "admin", (
        Switch("office.permits", "Permits"),
        Switch("office.fleet", "Fleet and travel"),
        Switch("office.devices", "Devices"),
        Switch("office.requests", "Office requests"),
    )),
)

APPS = {a.key: a for a in CATALOGUE}
SWITCHES = {s.key: (a, s) for a in CATALOGUE for s in a.switches}


def app_switch(key: str) -> str:
    return f"app:{key}"


def effective(chosen: dict[str, bool], services: set[str]) -> dict[str, bool]:
    """Every catalogue app and feature, on or off for a company: what it chose, else the catalogue's
    default. A catalogue app is on only when the company has its service and it isn't switched off;
    a feature only when its app is on. Nothing not built yet is on."""
    out: dict[str, bool] = {}
    for a in CATALOGUE:
        on = not a.later and a.service in services and chosen.get(app_switch(a.key), True)
        out[app_switch(a.key)] = on
        for s in a.switches:
            out[s.key] = on and not s.later and chosen.get(s.key, s.on)
    return out


# ---- Abilities ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ability:
    key: str
    label: str
    group: str
    # By app: the technical permissions it needs there.
    grants: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # Takes a limit: what it means ("Largest discount, %"), else None.
    limit: str | None = None


def _crud(area: str, *actions: str) -> tuple[str, ...]:
    return tuple(f"{area}.{a}" for a in actions)


ABILITIES: tuple[Ability, ...] = (
    # CRM and Sales
    Ability("customers.work", "Work with customers and leads", "CRM and Sales", {
        "crm": ("dashboard.view", *_crud("customers", "view", "create", "edit"), *_crud("activities", "view", "create", "edit", "delete"),
                *_crud("visits", "view", "create", "edit", "delete"), *_crud("deals", "view", "create", "edit"), "goals.view", "products.view"),
    }),
    Ability("leads.inbox", "Work the lead inbox", "CRM and Sales", {"crm": ("customers.inbox",)}),
    Ability("quotes.make", "Make quotes and sales orders", "CRM and Sales", {
        "crm": (*_crud("quotes", "view", "create", "edit"), *_crud("orders", "view", "create", "edit")),
        "inventory": ("orders.view", "orders.create", "stock.view", "products.view"),
    }),
    Ability("discounts.give", "Give discounts, up to a limit", "CRM and Sales", {"crm": ("quotes.view",)}, limit="Largest discount, %"),
    Ability("discounts.approve", "Approve discounts, up to a limit", "CRM and Sales", {"crm": ("quotes.approve",)}, limit="Largest discount, %"),
    Ability("orders.credit", "Approve orders on credit", "CRM and Sales", {"crm": ("orders.approve", "orders.credit")}),
    Ability("records.remove", "Remove customers, deals and quotes", "CRM and Sales", {
        "crm": ("customers.delete", "deals.delete", "quotes.delete", "orders.delete"),
    }),
    Ability("prices.manage", "Manage price lists and promos", "CRM and Sales", {
        "crm": ("products.view", "products.create", "products.edit", "products.prices", "products.approve"),
        "finance": ("prices.view", "prices.approve"),
    }),
    Ability("targets.set", "Set sales targets", "CRM and Sales", {"crm": ("goals.view", "goals.manage", "goals.import")}),
    Ability("lists.manage", "Manage checklists and terms", "CRM and Sales", {"crm": ("admin.types", "admin.settings")}),
    Ability("margins.see", "See costs and margins", "CRM and Sales", {"finance": ("dashboard.view", "invoices.view", "prices.view")}),
    # Operations
    Ability("stock.see", "See stock and products", "Operations", {"inventory": ("dashboard.view", "stock.view", "products.view", "warehouses.view")}),
    Ability("stock.receive", "Receive stock", "Operations", {"inventory": ("receiving.view", "receiving.receive", "purchasing.view")}),
    Ability("stock.deliver", "Send out deliveries", "Operations", {
        "inventory": ("orders.view", "orders.edit", "orders.issue", "transfers.view", "transfers.dispatch", "transfers.receive"),
    }),
    Ability("stock.move", "Move and adjust stock", "Operations", {"inventory": ("transfers.view", "transfers.create", "adjustments.view", "adjustments.create")}),
    Ability("stock.count", "Count stock", "Operations", {"inventory": ("counts.view", "counts.create")}),
    Ability("stock.approve", "Approve stock adjustments, counts and transfers", "Operations", {
        "inventory": ("adjustments.view", "adjustments.approve", "counts.view", "counts.approve", "transfers.view", "transfers.approve", "orders.approve"),
    }),
    Ability("products.manage", "Manage the product list and CPR", "Operations", {
        "inventory": ("products.view", "products.create", "products.edit", "products.delete", "warehouses.view", "warehouses.manage"),
        "crm": ("products.view", "products.create", "products.edit", "products.delete"),
    }),
    Ability("purchasing.order", "Order from vendors", "Operations", {"inventory": ("purchasing.view", "purchasing.create", "purchasing.edit", "suppliers.view")}),
    Ability("purchasing.approve", "Approve purchase orders, up to a limit", "Operations", {"inventory": ("purchasing.view", "purchasing.approve")}, limit="Largest order, ₱"),
    Ability("vendors.manage", "Manage vendors", "Operations", {
        "inventory": ("suppliers.view", "suppliers.create", "suppliers.edit", "suppliers.delete"),
        "finance": ("suppliers.view", "suppliers.add", "suppliers.edit", "suppliers.deactivate"),
    }),
    # Books
    Ability("invoices.make", "Make invoices", "Books", {"finance": ("dashboard.view", "invoices.view", "invoices.create", "invoices.issue", "calendar.use")}),
    Ability("payments.record", "Record payments", "Books", {"finance": ("invoices.view", "invoices.collect", "bank.view")}),
    Ability("bills.enter", "Enter bills and expenses", "Books", {
        "finance": ("bills.view", "bills.create", "funds.view", "vouchers.view", "vouchers.prepare", "categories.view", "suppliers.view", "calendar.use"),
    }),
    Ability("bills.approve", "Approve bills and expenses, up to a limit", "Books", {
        "finance": ("bills.view", "bills.approve", "bills.first", "bills.check", "funds.view", "funds.check", "journal.view", "journal.approve", "journal.first"),
    }, limit="Largest bill, ₱"),
    Ability("payments.release", "Release payments", "Books", {
        "finance": ("vouchers.view", "vouchers.release", "vouchers.void", "funds.view", "funds.release", "funds.settle", "funds.cancel", "bills.void"),
    }),
    Ability("month.close", "Close the month", "Books", {
        "finance": ("journal.view", "journal.post", "journal.reverse", "accounts.view", "accounts.manage", "bank.view", "bank.reconcile",
                    "categories.view", "categories.manage", "invoices.view", "invoices.void", "invoices.setup"),
    }),
    Ability("bir.prepare", "Prepare BIR filings", "Books", {"finance": ("bir.view", "bir.prepare", "tax.view", "tax.manage")}),
    # Company
    Ability("org.manage", "Manage the organisation", "Company", {"crm": ("admin.teams", "department.manage")}),
    Ability("reports.management", "See management reports", "Company", {
        "crm": ("dashboard.view", "reports.view"),
        "inventory": ("dashboard.view", "reports.view"),
        "finance": ("dashboard.view", "accounts.view", "journal.view", "invoices.view"),
    }),
    Ability("reports.export", "Export reports", "Company", {"crm": ("reports.view", "reports.export"), "inventory": ("reports.view", "reports.export")}),
    Ability("activity.see", "See each app's activity log", "Company", {"crm": ("admin.audit",), "inventory": ("admin.audit",), "finance": ("admin.audit",)}),
)

ABILITY = {a.key: a for a in ABILITIES}
GROUPS = tuple(dict.fromkeys(a.group for a in ABILITIES))


def permissions_for(abilities: list[str], apps: set[str]) -> dict[str, list[str]]:
    """The technical permissions a set of abilities needs, by app (only the apps given)."""
    out: dict[str, set[str]] = {}
    for key in abilities:
        for app, perms in ABILITY[key].grants.items():
            if app in apps:
                out.setdefault(app, set()).update(perms)
    return {app: sorted(perms) for app, perms in out.items()}


# ---- Ready-made job roles -------------------------------------------------------------------------


@dataclass(frozen=True)
class JobRole:
    key: str
    name: str
    sees: str  # whose records, in words
    abilities: tuple[str, ...]
    # By app: whose records it reaches there (the app's own scopes; the CRM's own/team/managed/all).
    scopes: dict[str, str] = field(default_factory=dict)
    limits: dict[str, int] = field(default_factory=dict)
    admin: bool = False


_REP = ("customers.work", "quotes.make", "discounts.give", "stock.see")
_LEAD = (*_REP, "leads.inbox", "discounts.approve")
_DIVISION = (*_LEAD, "orders.credit", "prices.manage", "margins.see", "targets.set", "records.remove", "reports.management")
_WAREHOUSE = ("stock.see", "stock.receive", "stock.deliver", "stock.move", "stock.count")
_FINANCE = ("invoices.make", "payments.record", "bills.enter")

JOB_ROLES: tuple[JobRole, ...] = (
    JobRole("sales_rep", "Sales rep", "Their own", _REP, {"crm": "own"}, {"discounts.give": 5}),
    JobRole("team_lead", "Team lead", "Their team", _LEAD, {"crm": "team"}, {"discounts.give": 10, "discounts.approve": 10}),
    JobRole("division_head", "Division head", "Their division", _DIVISION, {"crm": "managed"}, {"discounts.give": 15, "discounts.approve": 20}),
    JobRole("warehouse_staff", "Warehouse staff", "Their warehouse", _WAREHOUSE),
    JobRole("warehouse_head", "Warehouse head", "Their warehouses", (*_WAREHOUSE, "stock.approve", "products.manage", "reports.management")),
    JobRole("purchasing_officer", "Purchasing officer", "Whole company", ("stock.see", "purchasing.order", "vendors.manage")),
    JobRole("finance_officer", "Finance officer", "Whole company", _FINANCE),
    JobRole("finance_head", "Finance head", "Whole company",
            (*_FINANCE, "bills.approve", "payments.release", "month.close", "bir.prepare", "margins.see", "reports.management", "reports.export", "activity.see"),
            limits={"bills.approve": 500_000}),
    JobRole("business_manager", "Business manager", "Whole company",
            ("customers.work", "stock.see", "discounts.approve", "orders.credit", "purchasing.approve", "bills.approve", "margins.see",
             "reports.management", "reports.export", "activity.see"),
            {"crm": "all"}, {"discounts.approve": 100, "purchasing.approve": 100_000_000, "bills.approve": 100_000_000}),
    JobRole("company_admin", "Company administrator", "Whole company", (), admin=True),
)

JOB = {j.key: j for j in JOB_ROLES}
