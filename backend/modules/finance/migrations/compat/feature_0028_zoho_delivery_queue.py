"""Durable approved-record deliveries and explicit mappings; never replay old work."""
from alembic import op
import sqlalchemy as sa
revision='0028'
down_revision='0027'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('nbfi_zoho_deliveries',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('environment',sa.String(20),nullable=False),sa.Column('kind',sa.String(30),nullable=False),
        sa.Column('local_id',sa.String(36),nullable=False),sa.Column('organization_id',sa.String(80),nullable=False),
        sa.Column('reference',sa.String(80),nullable=False,unique=True),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('next_attempt',sa.DateTime(timezone=True),nullable=False),
        sa.Column('owner',sa.String(80)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('remote_id',sa.String(80)),sa.Column('error_code',sa.String(80)),
        sa.Column('created_by',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('environment','kind','local_id',name='zoho_deliver_once'))
    op.create_index('ix_nbfi_zoho_deliveries_local_id','nbfi_zoho_deliveries',['local_id'])
    op.create_index('ix_nbfi_zoho_deliveries_status','nbfi_zoho_deliveries',['status'])
    op.create_table('nbfi_zoho_links',sa.Column('organization_id',sa.String(80),primary_key=True),
        sa.Column('kind',sa.String(30),primary_key=True),sa.Column('local_id',sa.String(80),primary_key=True),
        sa.Column('remote_id',sa.String(80)),sa.Column('details',sa.JSON(),nullable=False),
        sa.Column('confirmed',sa.Boolean(),nullable=False),sa.Column('confirmed_by',sa.String(120),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_table('nbfi_zoho_delivery_events',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('delivery_id',sa.String(36),sa.ForeignKey('nbfi_zoho_deliveries.id'),nullable=False),
        sa.Column('kind',sa.String(40),nullable=False),sa.Column('actor',sa.String(120),nullable=False),
        sa.Column('code',sa.String(80)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_nbfi_zoho_delivery_events_delivery_id','nbfi_zoho_delivery_events',['delivery_id'])


def downgrade():
    pass  # Keep delivery evidence; restore a verified backup instead.
