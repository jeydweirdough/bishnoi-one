"""Saved import matches, import runs and imported records (approved 2026-10-29).

Three new tables, empty when made; no existing table or row changes. A Zoho record
is created in Finance at most once (the partial unique index on created records).
"""
from alembic import op
import sqlalchemy as sa
revision='0030'
down_revision='0029'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('nbfi_import_matches',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('source',sa.String(20),nullable=False),sa.Column('section',sa.String(20),nullable=False),
        sa.Column('role',sa.String(20),nullable=False),sa.Column('source_code',sa.String(80),nullable=False),
        sa.Column('source_label',sa.String(200),nullable=False),
        sa.Column('records',sa.Integer(),nullable=False),sa.Column('amount_centavos',sa.BigInteger(),nullable=False),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('nbfi_accounts.id',ondelete='SET NULL')),
        sa.Column('purchase_type',sa.String(20)),sa.Column('vat_kind',sa.String(10)),sa.Column('company',sa.String(10)),
        sa.Column('status',sa.String(12),nullable=False),sa.Column('note',sa.String(300)),
        sa.Column('proposed_by',sa.String(120)),sa.Column('proposed_by_id',sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL')),
        sa.Column('proposed_at',sa.DateTime(timezone=True)),
        sa.Column('confirmed_by',sa.String(120)),sa.Column('confirmed_by_id',sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL')),
        sa.Column('confirmed_at',sa.DateTime(timezone=True)),
        sa.Column('seen_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('source','section','role','source_code','source_label',name='import_match_once'),
        sa.CheckConstraint("status IN ('open', 'proposed', 'confirmed')",name='import_match_status'))
    op.create_table('nbfi_import_runs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('kind',sa.String(20),nullable=False),sa.Column('files',sa.JSON(),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('counts',sa.JSON(),nullable=False),
        sa.Column('created_by',sa.String(120),nullable=False),
        sa.Column('created_by_id',sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('nbfi_import_records',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('run_id',sa.String(36),sa.ForeignKey('nbfi_import_runs.id'),nullable=False),
        sa.Column('source',sa.String(20),nullable=False),sa.Column('kind',sa.String(20),nullable=False),
        sa.Column('source_id',sa.String(120),nullable=False),sa.Column('number',sa.String(60),nullable=False),
        sa.Column('outcome',sa.String(12),nullable=False),sa.Column('reasons',sa.JSON(),nullable=False),
        sa.Column('bill_id',sa.String(36),sa.ForeignKey('nbfi_bills.id')),
        sa.Column('voucher_id',sa.String(36),sa.ForeignKey('nbfi_payment_vouchers.id')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("outcome IN ('created', 'held', 'skipped')",name='import_record_outcome'))
    op.create_index('ix_nbfi_import_records_run_id','nbfi_import_records',['run_id'])
    op.create_index('ix_nbfi_import_records_source_id','nbfi_import_records',['source','kind','source_id'])
    op.create_index('import_created_once','nbfi_import_records',['source','kind','source_id'],unique=True,
        sqlite_where=sa.text("outcome = 'created'"),postgresql_where=sa.text("outcome = 'created'"))


def downgrade():
    pass  # Keep import evidence; restore a verified backup instead.
