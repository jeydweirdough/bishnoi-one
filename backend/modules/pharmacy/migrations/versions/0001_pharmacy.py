"""Nabhi Pharmacy: accounts, roles and the activity log; medicines, suppliers,
batches and stock; patients; prescriptions, their checks, dispensing; sales
and returns. Every table is nbph_ (NaBhi PHarmacy).

A database from Orbit Pharmacy (its plain `users` and `sessions`, made before
migrations) has its accounts carried over: its admins become Administrators,
everyone else a Pharmacy Assistant. Their old sessions end.

The starting roles are written out here, not imported, so changing the
defaults in app/permissions.py later never rewrites what this did.

Revision ID: 0001
Revises:
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ADMIN_ONLY = {"admin": "users roles audit"}
EVERYTHING_ELSE = {
    "dashboard": "view", "prescriptions": "view create edit verify", "dispensing": "view create",
    "patients": "view create edit delete", "sales": "view create refund", "medicines": "view create edit delete",
    "batches": "view manage", "stock": "view receive adjust", "suppliers": "view create edit delete", "reports": "view",
}
# name, description, is_system, {area: actions}
ROLES = (
    ("Administrator", "Everything, including users, roles and the activity log.", True, {**EVERYTHING_ELSE, **ADMIN_ONLY}),
    ("Pharmacist", "Checks and verifies prescriptions, dispenses, and runs the stock. No administration.", False, EVERYTHING_ELSE),
    ("Pharmacy Assistant", "Takes prescriptions in, keeps patient records, sells over the counter and receives stock. "
     "Doesn't verify or dispense.", False, {
        "dashboard": "view", "prescriptions": "view create edit", "dispensing": "view", "patients": "view create edit",
        "sales": "view create", "medicines": "view", "batches": "view", "stock": "view receive", "suppliers": "view",
    }),
)


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _when(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _user_fk(name: str) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey("nbph_users.id", ondelete="SET NULL"), nullable=True)


def upgrade() -> None:
    now = datetime.now(UTC)
    bind = op.get_bind()
    legacy = {"users", "sessions"} <= set(sa.inspect(bind).get_table_names())

    # --- accounts and administration ---
    roles = op.create_table(
        "nbph_roles", _id(),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        _when("created_at"),
    )
    grants = op.create_table(
        "nbph_role_permissions",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("nbph_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission", sa.String(64), primary_key=True),
    )
    users = op.create_table(
        "nbph_users", _id(),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("nbph_roles.id"), nullable=False, index=True),
        sa.Column("license_no", sa.String(40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _when("created_at"), _when("password_changed_at"),
    )
    op.create_table(
        "nbph_sessions", _id(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbph_users.id", ondelete="CASCADE"), nullable=False, index=True),
        _when("created_at"), _when("expires_at"), _when("revoked_at", True),
    )
    op.create_table(
        "nbph_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _when("at"),
        sa.Column("actor_id", sa.String(36), nullable=True, index=True),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(36), nullable=True),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
    )
    op.create_index("ix_nbph_audit_log_at", "nbph_audit_log", ["at"])
    op.create_table(
        "nbph_counters",
        sa.Column("kind", sa.String(8), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("value", sa.Integer(), nullable=False),
    )

    # --- medicines ---
    op.create_table(
        "nbph_categories", _id(),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _when("created_at"),
    )
    op.create_table(
        "nbph_brands", _id(),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("manufacturer", sa.String(160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _when("created_at"),
    )
    op.create_table(
        "nbph_medicines", _id(),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("generic_name", sa.String(160), nullable=False, index=True),
        sa.Column("brand_id", sa.String(36), sa.ForeignKey("nbph_brands.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("nbph_categories.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("strength", sa.String(40), nullable=True),
        sa.Column("dosage_form", sa.String(40), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("rx_class", sa.String(12), nullable=False),
        sa.Column("price_centavos", sa.Integer(), nullable=False),
        sa.Column("reorder_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _when("created_at"), _when("updated_at"),
        sa.CheckConstraint("rx_class IN ('otc', 'rx', 'dangerous')", name="medicine_rx_class"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'discontinued')", name="medicine_status"),
    )

    # --- suppliers, batches, stock ---
    op.create_table(
        "nbph_suppliers", _id(),
        sa.Column("name", sa.String(160), nullable=False, unique=True),
        sa.Column("contact_person", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        _when("created_at"), _when("updated_at"),
    )
    op.create_table(
        "nbph_receivings", _id(),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbph_suppliers.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("reference", sa.String(80), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _user_fk("received_by_id"),
        _when("created_at"),
    )
    op.create_index("ix_nbph_receivings_created_at", "nbph_receivings", ["created_at"])
    op.create_table(
        "nbph_batches", _id(),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("nbph_medicines.id"), nullable=False, index=True),
        sa.Column("lot_no", sa.String(60), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbph_suppliers.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("receiving_id", sa.String(36), sa.ForeignKey("nbph_receivings.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("manufactured_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=False, index=True),
        sa.Column("cost_centavos", sa.Integer(), nullable=False),
        sa.Column("qty_received", sa.Integer(), nullable=False),
        sa.Column("qty_on_hand", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("status_reason", sa.String(300), nullable=True),
        _when("status_changed_at", True),
        _when("created_at"),
        sa.UniqueConstraint("medicine_id", "lot_no", name="batch_lot"),
        sa.CheckConstraint("status IN ('available', 'quarantined', 'recalled')", name="batch_status"),
        sa.CheckConstraint("qty_on_hand >= 0", name="batch_not_negative"),
    )
    op.create_table(
        "nbph_stock_movements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _when("at"),
        sa.Column("kind", sa.String(12), nullable=False, index=True),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("nbph_medicines.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("nbph_batches.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("reference", sa.String(20), nullable=True),
        _user_fk("by_id"),
    )
    op.create_index("ix_nbph_stock_movements_at", "nbph_stock_movements", ["at"])

    # --- patients ---
    op.create_table(
        "nbph_patients", _id(),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False, index=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(10), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("allergies", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _when("created_at"), _when("updated_at"),
        sa.CheckConstraint("kind IN ('patient', 'customer')", name="patient_kind"),
    )

    # --- prescriptions and dispensing ---
    op.create_table(
        "nbph_prescriptions", _id(),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("nbph_patients.id"), nullable=False, index=True),
        sa.Column("prescriber_name", sa.String(120), nullable=False),
        sa.Column("prescriber_license", sa.String(40), nullable=True),
        sa.Column("prescriber_clinic", sa.String(160), nullable=True),
        sa.Column("prescribed_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, index=True),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        _user_fk("checked_by_id"),
        _when("checked_at", True),
        _user_fk("received_by_id"),
        _when("received_at"), _when("updated_at"),
        sa.CheckConstraint(
            "status IN ('received', 'pending', 'verified', 'needs_clarification', 'rejected')", name="prescription_status"
        ),
    )
    op.create_index("ix_nbph_prescriptions_received_at", "nbph_prescriptions", ["received_at"])
    op.create_table(
        "nbph_prescription_items", _id(),
        sa.Column("prescription_id", sa.String(36), sa.ForeignKey("nbph_prescriptions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("written_as", sa.String(200), nullable=False),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("nbph_medicines.id"), nullable=True, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("directions", sa.String(300), nullable=True),
        sa.Column("qty_dispensed", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="item_quantity"),
    )
    op.create_table(
        "nbph_sales", _id(),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("source", sa.String(12), nullable=False, index=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("nbph_patients.id", ondelete="SET NULL"), nullable=True, index=True),
        _user_fk("sold_by_id"),
        _when("sold_at"),
        sa.Column("subtotal_centavos", sa.Integer(), nullable=False),
        sa.Column("discount_centavos", sa.Integer(), nullable=False),
        sa.Column("total_centavos", sa.Integer(), nullable=False),
        sa.Column("payment_method", sa.String(12), nullable=False),
        sa.Column("refunded_centavos", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_nbph_sales_sold_at", "nbph_sales", ["sold_at"])
    op.create_table(
        "nbph_dispensings", _id(),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("prescription_id", sa.String(36), sa.ForeignKey("nbph_prescriptions.id"), nullable=False, index=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("nbph_patients.id"), nullable=False, index=True),
        _user_fk("dispensed_by_id"),
        _when("dispensed_at"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("nbph_sales.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_nbph_dispensings_dispensed_at", "nbph_dispensings", ["dispensed_at"])
    op.create_table(
        "nbph_dispensing_lines", _id(),
        sa.Column("dispensing_id", sa.String(36), sa.ForeignKey("nbph_dispensings.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("nbph_prescription_items.id"), nullable=False, index=True),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("nbph_medicines.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("nbph_batches.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="dispensing_quantity"),
    )

    # --- sale lines and returns ---
    op.create_table(
        "nbph_sale_lines", _id(),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("nbph_sales.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("medicine_id", sa.String(36), sa.ForeignKey("nbph_medicines.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("nbph_batches.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_centavos", sa.Integer(), nullable=False),
        sa.Column("line_total_centavos", sa.Integer(), nullable=False),
        sa.Column("qty_returned", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="sale_quantity"),
    )
    op.create_table(
        "nbph_returns", _id(),
        sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("nbph_sales.id"), nullable=False, index=True),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("restocked", sa.Boolean(), nullable=False),
        sa.Column("refund_centavos", sa.Integer(), nullable=False),
        sa.Column("refund_method", sa.String(12), nullable=True),
        _user_fk("by_id"),
        _when("at"),
        sa.Column("lines", sa.JSON(), nullable=False),
    )
    op.create_index("ix_nbph_returns_at", "nbph_returns", ["at"])

    # --- the starting roles ---
    ids = {name: str(uuid.uuid4()) for name, *_ in ROLES}
    op.bulk_insert(roles, [
        {"id": ids[name], "name": name, "description": desc, "is_system": system, "created_at": now}
        for name, desc, system, _ in ROLES
    ])
    op.bulk_insert(grants, [
        {"role_id": ids[name], "permission": f"{area}.{action}"}
        for name, _, _, areas in ROLES
        for area, actions in areas.items()
        for action in actions.split()
    ])

    # --- Orbit Pharmacy's accounts, carried over ---
    if legacy:
        old = bind.execute(sa.text("SELECT id, email, full_name, password_hash, role, is_active, created_at, password_changed_at FROM users")).mappings()
        rows = [
            {**{k: row[k] for k in ("id", "email", "full_name", "password_hash", "is_active")},
             "role_id": ids["Administrator" if row["role"] == "admin" else "Pharmacy Assistant"],
             "license_no": None,
             "created_at": _moment(row["created_at"], now),
             "password_changed_at": _moment(row["password_changed_at"], now)}
            for row in old
        ]
        if rows:
            op.bulk_insert(users, rows)
        op.drop_table("sessions")
        op.drop_table("users")


def _moment(value, fallback: datetime) -> datetime:
    """SQLite hands a stored moment back as text."""
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return fallback


def downgrade() -> None:
    for name in (
        "nbph_returns", "nbph_sale_lines", "nbph_dispensing_lines", "nbph_dispensings", "nbph_sales",
        "nbph_prescription_items", "nbph_prescriptions", "nbph_patients", "nbph_stock_movements", "nbph_batches",
        "nbph_receivings", "nbph_suppliers", "nbph_medicines", "nbph_brands", "nbph_categories", "nbph_counters",
        "nbph_audit_log", "nbph_sessions", "nbph_users", "nbph_role_permissions", "nbph_roles",
    ):
        op.drop_table(name)
