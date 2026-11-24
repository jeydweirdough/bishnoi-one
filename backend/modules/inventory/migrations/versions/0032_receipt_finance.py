"""Persist explicit receipt-to-Finance handoffs; no stock/receipt/data backfill."""
from alembic import op
import sqlalchemy as sa

revision = '0032'
down_revision = '0031'
branch_labels=None
depends_on=None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    wanted = {'nbin_receipt_finance_handoffs'}
    present = set(inspector.get_table_names()) & wanted
    if present == wanted:
        required = {'nbin_receipt_finance_handoffs': {'reason', 'version', 'bills', 'digest', 'supplier_id', 'sent_at', 'state', 'remaining', 'id', 'snapshot', 'order_id', 'sent_by', 'receipt_id'}}
        for table, fields in required.items():
            if not fields <= {c['name'] for c in inspector.get_columns(table)}:
                raise RuntimeError('Partial legacy table columns; no automatic repair.')
        return
    if present:
        raise RuntimeError('Partial legacy receipt/company-review schema; no automatic repair.')
    op.create_table('nbin_receipt_finance_handoffs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('receipt_id',sa.String(36),sa.ForeignKey('nbin_receipts.id'),nullable=False,unique=True),
        sa.Column('supplier_id',sa.String(36),sa.ForeignKey('nbin_suppliers.id'),nullable=False),
        sa.Column('order_id',sa.String(36),sa.ForeignKey('nbin_purchase_orders.id'),nullable=False),
        sa.Column('digest',sa.String(64),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.Column('sent_by',sa.String(120),nullable=False),sa.Column('sent_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('state',sa.String(40),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('reason',sa.String(300)),sa.Column('remaining',sa.Integer(),nullable=False),sa.Column('bills',sa.JSON(),nullable=False))


def downgrade():
    op.drop_table('nbin_receipt_finance_handoffs')
