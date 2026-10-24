"""Bank reconciliation (decided 2026-10-24, from Oojeema): a bank statement
matched against the books, and each journal line marked once the bank shows it.
bank.*: Finance Staff reconcile; the Auditor sees them.

Added in place, never by rebuilding a table (see 0017); safe to run twice.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

STAFF_ID = "00000000-0000-4000-8000-00000000f002"
AUDITOR_ID = "00000000-0000-4000-8000-00000000f003"
GRANTS = {STAFF_ID: ["bank.view", "bank.reconcile"], AUDITOR_ID: ["bank.view"]}


def upgrade() -> None:
    db = op.get_bind()
    inspector = sa.inspect(db)
    postgres = db.dialect.name == "postgresql"
    if "nbfi_bank_reconciliations" not in set(inspector.get_table_names()):
        op.create_table(
            "nbfi_bank_reconciliations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False, index=True),
            sa.Column("statement_date", sa.Date(), nullable=False),
            sa.Column("statement_balance_centavos", sa.Integer(), nullable=False),
            sa.Column("opening_balance_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(6), nullable=False, server_default="open", index=True),
            sa.Column("cleared", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_by", sa.String(120), nullable=True),
            sa.CheckConstraint("status IN ('open', 'done')", name="reconciliation_status"),
        )
    if "reconciliation_id" not in {c["name"] for c in inspector.get_columns("nbfi_journal_lines")}:
        op.add_column("nbfi_journal_lines", sa.Column("reconciliation_id", sa.String(36), nullable=True))
        if postgres:
            op.create_foreign_key(
                "nbfi_journal_lines_reconciliation_id_fkey", "nbfi_journal_lines", "nbfi_bank_reconciliations", ["reconciliation_id"], ["id"], ondelete="SET NULL"
            )
    if "ix_nbfi_journal_lines_reconciliation_id" not in {i["name"] for i in inspector.get_indexes("nbfi_journal_lines")}:
        op.create_index("ix_nbfi_journal_lines_reconciliation_id", "nbfi_journal_lines", ["reconciliation_id"])
    for role, permissions in GRANTS.items():
        if db.execute(sa.text("SELECT id FROM nbfi_roles WHERE id = :r"), {"r": role}).scalar() is None:
            continue
        for p in permissions:
            if db.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = :p"), {"r": role, "p": p}).scalar() is None:
                db.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, :p)"), {"r": role, "p": p})


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission LIKE 'bank.%'"))
    op.drop_index("ix_nbfi_journal_lines_reconciliation_id", table_name="nbfi_journal_lines")
    with op.batch_alter_table("nbfi_journal_lines") as batch:
        batch.drop_column("reconciliation_id")
    op.drop_table("nbfi_bank_reconciliations")
