"""GraphQL for reading: one request per page, only the fields the page shows.

    POST /graphql   {"query": "...", "variables": {...}}

Each field is answered by the REST route that answers the same question, so
the two can't disagree: the same queries, the same permission, the same
limits. The machinery (calling a route, the limits, the endpoint) is
app/graphql_core.py, the same file in every app.

Why: a page used to make a call per piece (the order, the reference lists, the
stock), and each call checked the session and opened the company again. The
reference lists were the heaviest: every form loaded every product, supplier
and warehouse whether it picked from them or not. Here each list is its own
field, read only when asked for.
"""

from typing import Annotated

import strawberry
from strawberry.scalars import JSON

from app.graphql_core import build, graphql_router, route
from app.routers import adjustments, admin, auth, catalog, insight, orders, purchasing, stock, transfers, unset, warehouses


@strawberry.type
class Location:
    id: str
    code: str
    name: str
    is_default: bool
    is_active: bool


@strawberry.type
class Category:
    id: str
    name: str
    path: str
    parent_id: str | None
    is_active: bool


@strawberry.type
class Brand:
    id: str
    name: str
    is_active: bool


@strawberry.type
class Unit:
    code: str
    name: str
    is_active: bool


@strawberry.type
class Supplier:
    id: str
    code: str
    name: str
    is_active: bool


@strawberry.type
class Warehouse:
    id: str
    code: str
    name: str
    is_active: bool
    locations: list[Location]


@strawberry.type
class Product:
    id: str
    sku: str
    name: str
    unit: str
    track_batches: bool
    track_expiry: bool
    track_serials: bool
    status: str
    cost_price: float
    selling_price: float
    supplier_id: str | None


def _part(info: strawberry.Info, name: str, cls):
    return [build(cls, row) for row in catalog.REFERENCE[name](info.context["db"])]


@strawberry.type
class Reference:
    """The lists forms pick from, each read only when a page asks for it."""

    @strawberry.field
    def categories(self, info: strawberry.Info) -> list[Category]:
        return _part(info, "categories", Category)

    @strawberry.field
    def brands(self, info: strawberry.Info) -> list[Brand]:
        return _part(info, "brands", Brand)

    @strawberry.field
    def units(self, info: strawberry.Info) -> list[Unit]:
        return _part(info, "units", Unit)

    @strawberry.field
    def suppliers(self, info: strawberry.Info) -> list[Supplier]:
        return _part(info, "suppliers", Supplier)

    @strawberry.field
    def warehouses(self, info: strawberry.Info) -> list[Warehouse]:
        return _part(info, "warehouses", Warehouse)

    @strawberry.field
    def products(self, info: strawberry.Info) -> list[Product]:
        return _part(info, "products", Product)


@strawberry.type
class Query:
    # --- the frame every page shares ---

    @strawberry.field
    def me(self, info: strawberry.Info) -> JSON | None:
        return route(auth.me, info)

    @strawberry.field
    def alerts(self, info: strawberry.Info) -> JSON | None:
        return route(insight.list_alerts, info)

    @strawberry.field
    def unset(self, info: strawberry.Info) -> JSON | None:
        return route(unset.unset, info)

    # --- what forms pick from ---

    @strawberry.field
    def reference(self, info: strawberry.Info) -> Reference:
        return Reference()  # signed in is enough, as GET /inventory/reference

    @strawberry.field
    def availability(self, info: strawberry.Info) -> JSON | None:
        return route(stock.available, info)

    # --- catalogue ---

    @strawberry.field
    def products(
        self,
        info: strawberry.Info,
        q: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        supplier: str | None = None,
        status: str | None = None,
        stock: str | None = None,
        parent: str | None = None,
        missing: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> JSON | None:
        return route(catalog.list_products, info, q=q, category=category, brand=brand, supplier=supplier, status_=status, stock=stock, parent=parent, missing=missing, limit=limit, offset=offset)

    @strawberry.field
    def product(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(catalog.read_product, info, product_id=id)

    @strawberry.field
    def categories(self, info: strawberry.Info) -> JSON | None:
        return route(catalog.list_categories, info)

    @strawberry.field
    def brands(self, info: strawberry.Info) -> JSON | None:
        return route(catalog.list_brands, info)

    @strawberry.field
    def units(self, info: strawberry.Info) -> JSON | None:
        return route(catalog.list_units, info)

    # --- stock ---

    @strawberry.field
    def stock(self, info: strawberry.Info, warehouse: str | None = None, q: str | None = None, category: str | None = None, state: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(stock.stock_overview, info, warehouse=warehouse, q=q, category=category, state_=state, limit=limit, offset=offset)

    @strawberry.field
    def movements(
        self,
        info: strawberry.Info,
        product: str | None = None,
        warehouse: str | None = None,
        kind: str | None = None,
        reference: str | None = None,
        q: str | None = None,
        start: Annotated[str | None, strawberry.argument(name="from")] = None,
        end: Annotated[str | None, strawberry.argument(name="to")] = None,
        before: int | None = None,
        limit: int | None = None,
    ) -> JSON | None:
        return route(stock.movements, info, product=product, warehouse=warehouse, kind=kind, reference=reference, q=q, start=start, end=end, before=before, limit=limit)

    @strawberry.field
    def batches(
        self, info: strawberry.Info, q: str | None = None, product: str | None = None, warehouse: str | None = None, expiry: str | None = None, empty: bool | None = None, limit: int | None = None, offset: int | None = None
    ) -> JSON | None:
        return route(stock.batches, info, q=q, product=product, warehouse=warehouse, expiry=expiry, empty=empty, limit=limit, offset=offset)

    @strawberry.field
    def serials(self, info: strawberry.Info, q: str, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(stock.serials, info, q=q, limit=limit, offset=offset)

    @strawberry.field
    def warehouses(self, info: strawberry.Info) -> JSON | None:
        return route(warehouses.list_warehouses, info)

    @strawberry.field
    def warehouse(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(warehouses.read_warehouse, info, warehouse_id=id)

    # --- orders and transfers ---

    @strawberry.field
    def orders(self, info: strawberry.Info, status: str | None = None, kind: str | None = None, warehouse: str | None = None, q: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(orders.list_orders, info, status_=status, kind=kind, warehouse=warehouse, q=q, limit=limit, offset=offset)

    @strawberry.field
    def order(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(orders.read_order, info, order_id=id)

    @strawberry.field
    def reservations(self, info: strawberry.Info, warehouse: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(orders.reservations, info, warehouse=warehouse, limit=limit, offset=offset)

    @strawberry.field
    def transfers(self, info: strawberry.Info, status: str | None = None, warehouse: str | None = None, q: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(transfers.list_transfers, info, status_=status, warehouse=warehouse, q=q, limit=limit, offset=offset)

    @strawberry.field
    def transfer(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(transfers.read_transfer, info, transfer_id=id)

    @strawberry.field
    def transfers_map(self, info: strawberry.Info) -> JSON | None:
        return route(transfers.transfers_map, info)

    @strawberry.field
    def setup(self, info: strawberry.Info) -> JSON | None:
        return route(unset.setup, info)

    # --- purchasing ---

    @strawberry.field
    def suppliers(self, info: strawberry.Info, q: str | None = None, state: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(purchasing.list_suppliers, info, q=q, state=state, limit=limit, offset=offset)

    @strawberry.field
    def supplier(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(purchasing.read_supplier, info, supplier_id=id)

    @strawberry.field(name="purchaseOrders")
    def purchase_orders(self, info: strawberry.Info, status: str | None = None, supplier: str | None = None, q: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(purchasing.list_pos, info, status_=status, supplier=supplier, q=q, limit=limit, offset=offset)

    @strawberry.field(name="purchaseOrder")
    def purchase_order(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(purchasing.read_po, info, po_id=id)

    @strawberry.field
    def backorders(self, info: strawberry.Info, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(purchasing.backorders, info, limit=limit, offset=offset)

    @strawberry.field
    def receipts(self, info: strawberry.Info, supplier: str | None = None, warehouse: str | None = None, q: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(purchasing.list_receipts, info, supplier=supplier, warehouse=warehouse, q=q, limit=limit, offset=offset)

    @strawberry.field
    def receipt(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(purchasing.read_receipt, info, receipt_id=id)

    # --- adjustments and counts ---

    @strawberry.field(name="adjustmentReasons")
    def adjustment_reasons(self, info: strawberry.Info) -> JSON | None:
        return route(adjustments.reasons, info)

    @strawberry.field
    def adjustments(self, info: strawberry.Info, status: str | None = None, warehouse: str | None = None, reason: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(adjustments.list_adjustments, info, status_=status, warehouse=warehouse, reason=reason, limit=limit, offset=offset)

    @strawberry.field
    def adjustment(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(adjustments.read_adjustment, info, adjustment_id=id)

    @strawberry.field
    def counts(self, info: strawberry.Info, status: str | None = None, limit: int | None = None, offset: int | None = None) -> JSON | None:
        return route(adjustments.list_counts, info, status_=status, limit=limit, offset=offset)

    @strawberry.field
    def count(self, info: strawberry.Info, id: str) -> JSON | None:
        return route(adjustments.read_count, info, count_id=id)

    # --- insight ---

    @strawberry.field
    def dashboard(self, info: strawberry.Info) -> JSON | None:
        return route(insight.dashboard, info)

    @strawberry.field
    def reports(self, info: strawberry.Info) -> JSON | None:
        return route(insight.list_reports, info)

    @strawberry.field
    def report(
        self,
        info: strawberry.Info,
        key: str,
        warehouse: str | None = None,
        start: Annotated[str | None, strawberry.argument(name="from")] = None,
        end: Annotated[str | None, strawberry.argument(name="to")] = None,
    ) -> JSON | None:
        return route(insight.read_report, info, key=key, warehouse=warehouse, start=start, end=end)

    # --- administration ---

    @strawberry.field
    def users(self, info: strawberry.Info) -> JSON | None:
        return route(admin.list_users, info)

    @strawberry.field
    def roles(self, info: strawberry.Info) -> JSON | None:
        return route(admin.list_roles, info)

    @strawberry.field
    def audit(self, info: strawberry.Info, before: int | None = None, limit: int | None = None, action: str | None = None, actor: str | None = None) -> JSON | None:
        return route(admin.audit_log, info, before=before, limit=limit, action=action, actor_id=actor)


router = graphql_router(Query)
