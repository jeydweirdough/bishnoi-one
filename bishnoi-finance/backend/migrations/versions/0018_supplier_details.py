"""Suppliers like Zoho's vendors, and finer permissions for suppliers and bills.

- nbfi_suppliers: company name, the primary contact (salutation, first and last name),
  mobile, the supplier's own payables account, and other contact persons (a list).
- nbfi_supplier_files: the supplier's papers (BIR 2303, accreditation); the files
  themselves go in nbfi_stored_files.
- Permissions: suppliers.manage becomes suppliers.add, .edit and .deactivate (Switch
  off) on every role that had it; every role that could record bills (which included
  making them) also gets bills.create (Make drafts). Nobody loses anything.

Columns are added in place, never by rebuilding a table (on SQLite a rebuild empties
what points at it: found 2026-10-23, see 0017). Decided 2026-10-23 (Plans/Plan -
Suppliers like Zoho's vendors). Main's latest migration was 0012 when this was
written (checked right before).

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

COLUMNS = (
    ("company_name", sa.String(200)),
    ("salutation", sa.String(10)),
    ("first_name", sa.String(80)),
    ("last_name", sa.String(80)),
    ("mobile", sa.String(40)),
    ("payables_account_id", sa.String(36)),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    have = {c["name"] for c in inspector.get_columns("nbfi_suppliers")}
    for name, kind in COLUMNS:
        if name not in have:
            op.add_column("nbfi_suppliers", sa.Column(name, kind, nullable=True))
    if "contacts" not in have:
        op.add_column("nbfi_suppliers", sa.Column("contacts", sa.JSON(), nullable=False, server_default="[]"))
    if "payables_account_id" not in have and bind.dialect.name == "postgresql":
        op.create_foreign_key("nbfi_suppliers_payables_account_id_fkey", "nbfi_suppliers", "nbfi_accounts", ["payables_account_id"], ["id"], ondelete="SET NULL")

    if "nbfi_supplier_files" not in set(inspector.get_table_names()):
        op.create_table(
            "nbfi_supplier_files",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbfi_suppliers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ref", sa.String(32), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("uploaded_by", sa.String(120), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_nbfi_supplier_files_supplier_id", "nbfi_supplier_files", ["supplier_id"])

    def grant(old: str, new: tuple[str, ...]) -> None:
        roles = [r[0] for r in bind.execute(sa.text("SELECT role_id FROM nbfi_role_permissions WHERE permission = :p"), {"p": old})]
        for role in roles:
            for p in new:
                if bind.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                    bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})

    grant("suppliers.manage", ("suppliers.add", "suppliers.edit", "suppliers.deactivate"))
    bind.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission = 'suppliers.manage'"))
    grant("bills.record", ("bills.create",))


def downgrade() -> None:
    bind = op.get_bind()
    roles = [r[0] for r in bind.execute(sa.text("SELECT DISTINCT role_id FROM nbfi_role_permissions WHERE permission IN ('suppliers.add', 'suppliers.edit')"))]
    for role in roles:
        bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, 'suppliers.manage')"), {"r": role})
    bind.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission IN ('suppliers.add', 'suppliers.edit', 'suppliers.deactivate', 'bills.create')"))
    op.drop_table("nbfi_supplier_files")
    if bind.dialect.name == "postgresql":
        op.drop_constraint("nbfi_suppliers_payables_account_id_fkey", "nbfi_suppliers", type_="foreignkey")
    for name, _ in COLUMNS:
        op.drop_column("nbfi_suppliers", name)
    op.drop_column("nbfi_suppliers", "contacts")
