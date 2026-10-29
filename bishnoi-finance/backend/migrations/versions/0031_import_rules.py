"""Import matching by supplier or by line (approved 2026-10-29).

Sir Mel: one Zoho account can stand for several of Finance's, and purchase types vary within one.
Adds one column to the import matches (a label can "depend on the record"), filled with false for
every existing match, and one new empty table for supplier rules and line choices. No other change.
"""
from alembic import op
import sqlalchemy as sa
revision='0031'
down_revision='0030'
branch_labels=None
depends_on=None


def upgrade():
    # Added in place (never a table rebuild); every existing match keeps one account per label.
    op.add_column('nbfi_import_matches',sa.Column('per_record',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_table('nbfi_import_rules',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('match_id',sa.String(36),sa.ForeignKey('nbfi_import_matches.id',ondelete='CASCADE'),nullable=False),
        sa.Column('scope',sa.String(10),nullable=False),
        sa.Column('supplier',sa.String(200),nullable=False),sa.Column('supplier_key',sa.String(200),nullable=False),
        sa.Column('bill_source_id',sa.String(120)),sa.Column('bill_number',sa.String(60)),
        sa.Column('line_position',sa.Integer()),sa.Column('line_amount_centavos',sa.BigInteger()),
        sa.Column('account_id',sa.String(36),sa.ForeignKey('nbfi_accounts.id',ondelete='SET NULL')),
        sa.Column('purchase_type',sa.String(20)),sa.Column('vat_kind',sa.String(10)),
        sa.Column('status',sa.String(12),nullable=False),sa.Column('note',sa.String(300)),
        sa.Column('proposed_by',sa.String(120),nullable=False),
        sa.Column('proposed_by_id',sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL')),
        sa.Column('proposed_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('confirmed_by',sa.String(120)),
        sa.Column('confirmed_by_id',sa.String(36),sa.ForeignKey('nbfi_users.id',ondelete='SET NULL')),
        sa.Column('confirmed_at',sa.DateTime(timezone=True)),
        sa.CheckConstraint("scope IN ('supplier', 'line')",name='import_rule_scope'),
        sa.CheckConstraint("status IN ('proposed', 'confirmed')",name='import_rule_status'))
    op.create_index('ix_nbfi_import_rules_match_id','nbfi_import_rules',['match_id'])
    op.create_index('import_rule_supplier_once','nbfi_import_rules',['match_id','supplier_key'],unique=True,
        sqlite_where=sa.text("scope = 'supplier'"),postgresql_where=sa.text("scope = 'supplier'"))
    op.create_index('import_rule_line_once','nbfi_import_rules',['match_id','bill_source_id','line_position'],unique=True,
        sqlite_where=sa.text("scope = 'line'"),postgresql_where=sa.text("scope = 'line'"))


def downgrade():
    pass  # Keep matching decisions; restore a verified backup instead.
