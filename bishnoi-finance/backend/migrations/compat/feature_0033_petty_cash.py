"""Petty cash vouchers with their receipts (approved 2026-10-30, Plans/Plan - Petty cash and receipts).

Adds three new empty tables: petty cash vouchers, their receipt lines (each with its photo or PDF, kept
in nbfi_stored_files like bill files), and their history. Nothing existing changes.
"""
from alembic import op
import sqlalchemy as sa
revision='0033'
down_revision='0032'
branch_labels=None
depends_on=None


def upgrade():
    user=lambda name:sa.Column(name,sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL'))  # noqa: E731
    op.create_table('nbfi_petty_cash_vouchers',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('number',sa.String(60),nullable=False),sa.Column('number_key',sa.String(60),nullable=False),
        sa.Column('status',sa.String(10),nullable=False),
        sa.Column('fund_account_id',sa.String(36),sa.ForeignKey('nbfi_accounts.id'),nullable=False),
        sa.Column('voucher_date',sa.Date(),nullable=False),
        sa.Column('person_in_charge',sa.String(120)),sa.Column('department',sa.String(120)),sa.Column('notes',sa.String(500)),
        sa.Column('amounts_include_vat',sa.Boolean(),nullable=False),
        sa.Column('net_centavos',sa.BigInteger(),nullable=False),sa.Column('vat_centavos',sa.BigInteger(),nullable=False),
        sa.Column('withheld_centavos',sa.BigInteger(),nullable=False),sa.Column('total_centavos',sa.BigInteger(),nullable=False),
        sa.Column('paid_out_centavos',sa.BigInteger(),nullable=False),
        sa.Column('entry_id',sa.String(36),sa.ForeignKey('nbfi_journal_entries.id',ondelete='SET NULL')),
        sa.Column('created_by',sa.String(120),nullable=False),user('created_by_id'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        user('submitted_by_id'),sa.Column('submitted_at',sa.DateTime(timezone=True)),
        sa.Column('checked_by',sa.String(120)),user('checked_by_id'),sa.Column('checked_at',sa.DateTime(timezone=True)),
        sa.Column('voided_by',sa.String(120)),sa.Column('voided_at',sa.DateTime(timezone=True)),sa.Column('void_reason',sa.String(300)),
        sa.CheckConstraint("status IN ('draft', 'to_check', 'returned', 'posted', 'void')",name='petty_cash_status'))
    op.create_index('ix_nbfi_petty_cash_vouchers_status','nbfi_petty_cash_vouchers',['status'])
    op.create_index('ix_nbfi_petty_cash_vouchers_fund_account_id','nbfi_petty_cash_vouchers',['fund_account_id'])
    op.create_index('petty_cash_number_once','nbfi_petty_cash_vouchers',['number_key'],unique=True,
        sqlite_where=sa.text("status <> 'void'"),postgresql_where=sa.text("status <> 'void'"))
    op.create_table('nbfi_petty_cash_lines',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('voucher_id',sa.String(36),sa.ForeignKey('nbfi_petty_cash_vouchers.id',ondelete='CASCADE'),nullable=False),
        sa.Column('position',sa.Integer(),nullable=False),sa.Column('spent_on',sa.Date(),nullable=False),
        sa.Column('store',sa.String(200),nullable=False),sa.Column('store_tin',sa.String(20)),
        sa.Column('receipt_number',sa.String(60),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('nbfi_accounts.id'),nullable=False),
        sa.Column('description',sa.String(200)),
        sa.Column('purchase_type',sa.String(20),nullable=False),sa.Column('vat',sa.String(10),nullable=False),
        sa.Column('withholding',sa.String(10)),
        sa.Column('amount_centavos',sa.BigInteger(),nullable=False),sa.Column('net_centavos',sa.BigInteger(),nullable=False),
        sa.Column('vat_centavos',sa.BigInteger(),nullable=False),sa.Column('withheld_centavos',sa.BigInteger(),nullable=False),
        sa.Column('file_ref',sa.String(32)),sa.Column('file_name',sa.String(200)),sa.Column('file_type',sa.String(100)),
        sa.Column('file_size',sa.Integer()),sa.Column('file_by',sa.String(120)),sa.Column('file_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint("purchase_type IN ('services', 'capital_goods', 'other_goods', 'importation')",name='petty_cash_purchase_type'),
        sa.CheckConstraint("vat IN ('vat', 'zero', 'exempt', 'none')",name='petty_cash_vat'))
    op.create_index('ix_nbfi_petty_cash_lines_voucher_id','nbfi_petty_cash_lines',['voucher_id'])
    op.create_table('nbfi_petty_cash_events',
        sa.Column('id',sa.Integer(),primary_key=True,autoincrement=True),
        sa.Column('voucher_id',sa.String(36),sa.ForeignKey('nbfi_petty_cash_vouchers.id',ondelete='CASCADE'),nullable=False),
        sa.Column('at',sa.DateTime(timezone=True),nullable=False),sa.Column('kind',sa.String(20),nullable=False),
        sa.Column('who',sa.String(120),nullable=False),user('who_id'),sa.Column('text',sa.String(300)))
    op.create_index('ix_nbfi_petty_cash_events_voucher_id','nbfi_petty_cash_events',['voucher_id'])


def downgrade():
    pass  # Keep vouchers and their receipts; restore a verified backup instead.
