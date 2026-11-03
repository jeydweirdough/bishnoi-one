"""Imported Q1 expenses, and what each imported record became (approved 2026-10-31, Plans/Plan - Q1 imports per area).

Adds three new empty tables: imported expenses, their lines, and the links from an imported record to the invoice,
payment or expense it became. Nothing existing changes.

Revision ID: 0035
Revises: 0034
"""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    user = lambda name: sa.Column(name, sa.String(36), sa.ForeignKey('nbfi_users.id', ondelete='SET NULL'))  # noqa: E731
    money = lambda name: sa.Column(name, sa.BigInteger(), nullable=False)  # noqa: E731
    op.create_table('nbfi_imported_expenses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source', sa.String(20), nullable=False), sa.Column('source_id', sa.String(120), nullable=False),
        sa.Column('number', sa.String(60), nullable=False), sa.Column('reference', sa.String(80)), sa.Column('voucher', sa.String(80)),
        sa.Column('department', sa.String(120)), sa.Column('person_in_charge', sa.String(120)),
        sa.Column('status', sa.String(10), nullable=False), sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('vendor', sa.String(200), nullable=False), sa.Column('vendor_tin', sa.String(20)),
        sa.Column('paid_from_id', sa.String(36), sa.ForeignKey('nbfi_accounts.id'), nullable=False),
        sa.Column('amounts_include_vat', sa.Boolean(), nullable=False),
        money('net_centavos'), money('vat_centavos'), money('withheld_centavos'), money('total_centavos'), money('paid_out_centavos'),
        sa.Column('entry_id', sa.String(36), sa.ForeignKey('nbfi_journal_entries.id', ondelete='SET NULL')),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('nbfi_import_runs.id', ondelete='SET NULL')),
        sa.Column('source_file', sa.String(200), nullable=False), sa.Column('imported_by', sa.String(120), nullable=False), user('imported_by_id'),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('voided_by', sa.String(120)), sa.Column('voided_at', sa.DateTime(timezone=True)), sa.Column('void_reason', sa.String(300)),
        sa.CheckConstraint("status IN ('posted', 'void')", name='imported_expense_status'),
        sa.UniqueConstraint('source', 'source_id', name='imported_expense_once'))
    op.create_index('ix_nbfi_imported_expenses_status', 'nbfi_imported_expenses', ['status'])
    op.create_index('ix_nbfi_imported_expenses_expense_date', 'nbfi_imported_expenses', ['expense_date'])
    op.create_index('ix_nbfi_imported_expenses_paid_from_id', 'nbfi_imported_expenses', ['paid_from_id'])
    op.create_table('nbfi_imported_expense_lines',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('expense_id', sa.String(36), sa.ForeignKey('nbfi_imported_expenses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('nbfi_accounts.id'), nullable=False),
        sa.Column('source_account', sa.String(200), nullable=False), sa.Column('source_tax', sa.String(100), nullable=False),
        sa.Column('description', sa.String(200)), sa.Column('purchase_type', sa.String(20), nullable=False),
        sa.Column('vat', sa.String(10), nullable=False), sa.Column('withholding', sa.String(10)),
        money('amount_centavos'), money('net_centavos'), money('vat_centavos'), money('withheld_centavos'),
        sa.CheckConstraint("purchase_type IN ('services', 'capital_goods', 'other_goods', 'importation')", name='imported_expense_purchase_type'),
        sa.CheckConstraint("vat IN ('vat', 'zero', 'exempt', 'none')", name='imported_expense_vat'))
    op.create_index('ix_nbfi_imported_expense_lines_expense_id', 'nbfi_imported_expense_lines', ['expense_id'])
    op.create_table('nbfi_import_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('record_id', sa.String(36), sa.ForeignKey('nbfi_import_records.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('nbfi_invoices.id', ondelete='SET NULL')),
        sa.Column('payment_id', sa.String(36), sa.ForeignKey('nbfi_invoice_payments.id', ondelete='SET NULL')),
        sa.Column('expense_id', sa.String(36), sa.ForeignKey('nbfi_imported_expenses.id', ondelete='SET NULL')))
    op.create_index('ix_nbfi_import_links_record_id', 'nbfi_import_links', ['record_id'])
    op.create_index('ix_nbfi_import_links_invoice_id', 'nbfi_import_links', ['invoice_id'])
    op.create_index('ix_nbfi_import_links_payment_id', 'nbfi_import_links', ['payment_id'])
    op.create_index('ix_nbfi_import_links_expense_id', 'nbfi_import_links', ['expense_id'])


def downgrade():
    op.drop_table('nbfi_import_links')
    op.drop_table('nbfi_imported_expense_lines')
    op.drop_table('nbfi_imported_expenses')
