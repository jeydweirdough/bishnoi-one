"""Add new tables for Credit Notes, Vendor Credits, Advances/Deposits, Recurring Templates, and Document Scans.

Purely additive migration: alters zero existing tables or columns so it merges cleanly across branches.
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "nbfi_credit_notes" not in tables:
        op.create_table(
            "nbfi_credit_notes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
            sa.Column("number", sa.String(30), nullable=True, unique=True),
            sa.Column("invoice_id", sa.String(36), sa.ForeignKey("nbfi_invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("customer_id", sa.String(36), nullable=True),
            sa.Column("customer_name", sa.String(200), nullable=False),
            sa.Column("customer_tin", sa.String(20), nullable=True),
            sa.Column("customer_address", sa.String(300), nullable=True),
            sa.Column("treatment", sa.String(20), nullable=False, server_default="regular"),
            sa.Column("buyer_id_number", sa.String(40), nullable=True),
            sa.Column("credit_date", sa.Date(), nullable=False),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("prices_include_tax", sa.Boolean(), nullable=True),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("computed", sa.JSON(), nullable=True),
            sa.Column("total_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("tax_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("applied_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("issued_by", sa.String(120), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_by", sa.String(120), nullable=True),
            sa.Column("void_reason", sa.String(300), nullable=True),
            sa.CheckConstraint("status IN ('draft', 'issued', 'void')", name="credit_note_status"),
        )
        op.create_index("ix_nbfi_credit_notes_status", "nbfi_credit_notes", ["status"])
        op.create_index("ix_nbfi_credit_notes_invoice_id", "nbfi_credit_notes", ["invoice_id"])
        op.create_index("ix_nbfi_credit_notes_customer_id", "nbfi_credit_notes", ["customer_id"])

    if "nbfi_credit_allocations" not in tables:
        op.create_table(
            "nbfi_credit_allocations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("credit_note_id", sa.String(36), sa.ForeignKey("nbfi_credit_notes.id", ondelete="CASCADE"), nullable=False),
            sa.Column("invoice_id", sa.String(36), sa.ForeignKey("nbfi_invoices.id", ondelete="CASCADE"), nullable=False),
            sa.Column("applied_on", sa.Date(), nullable=False),
            sa.Column("amount_centavos", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.String(120), nullable=True),
        )
        op.create_index("ix_nbfi_credit_allocations_credit_note_id", "nbfi_credit_allocations", ["credit_note_id"])
        op.create_index("ix_nbfi_credit_allocations_invoice_id", "nbfi_credit_allocations", ["invoice_id"])

    if "nbfi_vendor_credits" not in tables:
        op.create_table(
            "nbfi_vendor_credits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
            sa.Column("number", sa.String(30), nullable=True, unique=True),
            sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id", ondelete="SET NULL"), nullable=True),
            sa.Column("supplier_id", sa.String(36), sa.ForeignKey("nbfi_suppliers.id"), nullable=False),
            sa.Column("credit_date", sa.Date(), nullable=False),
            sa.Column("reference", sa.String(60), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("amounts_include_vat", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("net_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("vat_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("withheld_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("total_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("credit_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("applied_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("payables_account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("recorded_by", sa.String(120), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_by", sa.String(120), nullable=True),
            sa.Column("void_reason", sa.String(300), nullable=True),
            sa.CheckConstraint("status IN ('draft', 'recorded', 'void')", name="vendor_credit_status"),
        )
        op.create_index("ix_nbfi_vendor_credits_status", "nbfi_vendor_credits", ["status"])
        op.create_index("ix_nbfi_vendor_credits_bill_id", "nbfi_vendor_credits", ["bill_id"])
        op.create_index("ix_nbfi_vendor_credits_supplier_id", "nbfi_vendor_credits", ["supplier_id"])

    if "nbfi_vendor_credit_allocations" not in tables:
        op.create_table(
            "nbfi_vendor_credit_allocations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("vendor_credit_id", sa.String(36), sa.ForeignKey("nbfi_vendor_credits.id", ondelete="CASCADE"), nullable=False),
            sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("applied_on", sa.Date(), nullable=False),
            sa.Column("amount_centavos", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.String(120), nullable=True),
        )
        op.create_index("ix_nbfi_vendor_credit_allocations_vc_id", "nbfi_vendor_credit_allocations", ["vendor_credit_id"])
        op.create_index("ix_nbfi_vendor_credit_allocations_bill_id", "nbfi_vendor_credit_allocations", ["bill_id"])

    if "nbfi_advances" not in tables:
        op.create_table(
            "nbfi_advances",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("status", sa.String(10), nullable=False, server_default="posted"),
            sa.Column("number", sa.String(30), nullable=False, unique=True),
            sa.Column("party_id", sa.String(36), nullable=True),
            sa.Column("party_name", sa.String(200), nullable=False),
            sa.Column("advance_date", sa.Date(), nullable=False),
            sa.Column("method", sa.String(12), nullable=False, server_default="bank"),
            sa.Column("bank_account_id", sa.String(36), sa.ForeignKey("nbfi_bank_accounts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("advance_account_id", sa.String(36), sa.ForeignKey("nbfi_accounts.id"), nullable=False),
            sa.Column("reference", sa.String(80), nullable=True),
            sa.Column("notes", sa.String(500), nullable=True),
            sa.Column("amount_centavos", sa.BigInteger(), nullable=False),
            sa.Column("applied_centavos", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_by", sa.String(120), nullable=True),
            sa.Column("void_reason", sa.String(300), nullable=True),
            sa.CheckConstraint("kind IN ('supplier', 'customer')", name="advance_kind"),
            sa.CheckConstraint("status IN ('posted', 'void')", name="advance_status"),
        )
        op.create_index("ix_nbfi_advances_kind", "nbfi_advances", ["kind"])
        op.create_index("ix_nbfi_advances_status", "nbfi_advances", ["status"])
        op.create_index("ix_nbfi_advances_party_id", "nbfi_advances", ["party_id"])

    if "nbfi_advance_applications" not in tables:
        op.create_table(
            "nbfi_advance_applications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("advance_id", sa.String(36), sa.ForeignKey("nbfi_advances.id", ondelete="CASCADE"), nullable=False),
            sa.Column("target_kind", sa.String(10), nullable=False),
            sa.Column("target_id", sa.String(36), nullable=False),
            sa.Column("applied_on", sa.Date(), nullable=False),
            sa.Column("amount_centavos", sa.BigInteger(), nullable=False),
            sa.Column("entry_id", sa.String(36), sa.ForeignKey("nbfi_journal_entries.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.String(120), nullable=True),
            sa.CheckConstraint("target_kind IN ('bill', 'invoice')", name="advance_app_target"),
        )
        op.create_index("ix_nbfi_advance_applications_advance_id", "nbfi_advance_applications", ["advance_id"])
        op.create_index("ix_nbfi_advance_applications_target_id", "nbfi_advance_applications", ["target_id"])

    if "nbfi_recurring_templates" not in tables:
        op.create_table(
            "nbfi_recurring_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("frequency", sa.String(12), nullable=False, server_default="monthly"),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("next_run_date", sa.Date(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.CheckConstraint("kind IN ('bill', 'invoice')", name="recurring_kind"),
            sa.CheckConstraint("frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')", name="recurring_frequency"),
        )
        op.create_index("ix_nbfi_recurring_templates_kind", "nbfi_recurring_templates", ["kind"])
        op.create_index("ix_nbfi_recurring_templates_next_run_date", "nbfi_recurring_templates", ["next_run_date"])

    if "nbfi_document_scans" not in tables:
        op.create_table(
            "nbfi_document_scans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("file_ref", sa.String(32), nullable=False),
            sa.Column("file_name", sa.String(200), nullable=False),
            sa.Column("file_type", sa.String(100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(12), nullable=False, server_default="ready"),
            sa.Column("raw_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("parsed", sa.JSON(), nullable=False),
            sa.Column("linked_bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.CheckConstraint("status IN ('ready', 'linked', 'archived')", name="document_scan_status"),
        )
        op.create_index("ix_nbfi_document_scans_status", "nbfi_document_scans", ["status"])


def downgrade():
    for tbl in (
        "nbfi_document_scans",
        "nbfi_recurring_templates",
        "nbfi_advance_applications",
        "nbfi_advances",
        "nbfi_vendor_credit_allocations",
        "nbfi_vendor_credits",
        "nbfi_credit_allocations",
        "nbfi_credit_notes",
    ):
        op.drop_table(tbl)
