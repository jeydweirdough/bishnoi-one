"""Add received-purchase evidence/links only; no backfill or existing-row changes."""
from alembic import op
import sqlalchemy as sa

revision = '0040'
down_revision = '0039'
branch_labels=None
depends_on=None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    wanted = {'nbfi_purchase_allocations', 'nbfi_purchase_supplier_links', 'nbfi_purchase_preparations', 'nbfi_purchase_intakes'}
    present = set(inspector.get_table_names()) & wanted
    if present == wanted:
        required = {'nbfi_purchase_intakes': {'reason', 'version', 'digest', 'id', 'company', 'snapshot', 'received_at', 'handoff_id', 'source_conflict', 'receipt_id'}, 'nbfi_purchase_supplier_links': {'reviewed_by', 'supplier_id', 'evidence', 'reviewed_at', 'company', 'source_supplier_id'}, 'nbfi_purchase_allocations': {'position', 'source_line_id', 'intake_id', 'id', 'bill_id', 'quantity', 'active'}, 'nbfi_purchase_preparations': {'invoice_key', 'request_id', 'digest', 'bill_id'}}
        for table, fields in required.items():
            if not fields <= {c['name'] for c in inspector.get_columns(table)}:
                raise RuntimeError('Partial legacy table columns; no automatic repair.')
        return
    if present:
        raise RuntimeError('Partial legacy receipt/company-review schema; no automatic repair.')
    op.create_table('nbfi_purchase_intakes',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('company',sa.String(40),nullable=False),
        sa.Column('receipt_id',sa.String(36),nullable=False),sa.Column('handoff_id',sa.String(36),nullable=False,unique=True),
        sa.Column('digest',sa.String(64),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('reason',sa.String(300)),
        sa.Column('source_conflict',sa.Boolean(),nullable=False),
        sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('company','receipt_id',name='purchase_intake_source_once'))
    op.create_table('nbfi_purchase_supplier_links',
        sa.Column('company',sa.String(40),primary_key=True),sa.Column('source_supplier_id',sa.String(36),primary_key=True),
        sa.Column('supplier_id',sa.String(36),sa.ForeignKey('nbfi_suppliers.id'),nullable=False),
        sa.Column('reviewed_by',sa.String(120),nullable=False),sa.Column('evidence',sa.String(300),nullable=False),
        sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('nbfi_purchase_allocations',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('intake_id',sa.String(36),sa.ForeignKey('nbfi_purchase_intakes.id'),nullable=False),
        sa.Column('source_line_id',sa.String(36),nullable=False),sa.Column('quantity',sa.Integer(),nullable=False),
        sa.Column('bill_id',sa.String(36),sa.ForeignKey('nbfi_bills.id'),nullable=False),
        sa.Column('position',sa.Integer(),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),
        sa.UniqueConstraint('bill_id','position',name='purchase_bill_line_once'),sa.CheckConstraint('quantity > 0',name='purchase_allocation_positive'))
    op.create_table('nbfi_purchase_preparations',
        sa.Column('request_id',sa.String(36),primary_key=True),sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('invoice_key',sa.String(64),unique=True),
        sa.Column('bill_id',sa.String(36),sa.ForeignKey('nbfi_bills.id'),nullable=False))


def downgrade():
    op.drop_table('nbfi_purchase_preparations')
    op.drop_table('nbfi_purchase_allocations')
    op.drop_table('nbfi_purchase_supplier_links')
    op.drop_table('nbfi_purchase_intakes')
