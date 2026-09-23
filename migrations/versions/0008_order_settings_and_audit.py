"""order settings (lists, extra fields, rules) and the audit log

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Each company starts from its template's order lists (code, name); Getmeds's
# (pharma_ph) are the lists its old Orders app had.
TEMPLATES = {'pharma_ph': {'payment_method': [('cash-on-delivery', 'Cash on delivery'),
                                  ('bank-transfer', 'Bank transfer'),
                                  ('gcash', 'GCash'),
                                  ('credit-terms', 'Credit terms'),
                                  ('check', 'Check'),
                                  ('credit-card', 'Credit Card'),
                                  ('pdc', 'PDC')],
               'payment_term': [('due-end-of-next-month', 'Due end of next month'),
                                ('due-end-of-the-month', 'Due end of the month'),
                                ('paid', 'Paid'),
                                ('advanced-payment', 'Advanced Payment'),
                                ('advanced-payment-partial', 'Advanced Payment - Partial'),
                                ('donation-charity', 'Donation/Charity'),
                                ('samples', 'Samples'),
                                ('due-on-receipt', 'Due on Receipt'),
                                ('60-dp-40-upon-del', '60% DP 40% UPON DEL'),
                                ('cash', 'CASH'),
                                ('cod', 'COD'),
                                ('net', 'Net'),
                                ('net-15', 'Net 15'),
                                ('30-days', '30 days'),
                                ('45-day', '45 Day'),
                                ('bpo-wallet', 'BPO WALLET'),
                                ('60-day', '60 Day'),
                                ('dswd-pcso', 'DSWD/PCSO'),
                                ('op', 'OP'),
                                ('90-day', '90 Day'),
                                ('initial-stocking', 'INITIAL STOCKING'),
                                ('120-day', '120 Day'),
                                ('180-day', '180 Day')],
               'source': [('doctor-order', 'Doctor order'),
                          ('patient-order-referred-by-doctor', 'Patient order referred by doctor'),
                          ('patient-order-referred-by-patient', 'Patient order referred by patient'),
                          ('emergency-purchase', 'Emergency purchase'),
                          ('hospital-po', 'Hospital PO'),
                          ('distributor-order', 'Distributor order')],
               'delivery_method': [('own-rider-company-vehicle', 'Own Rider / Company Vehicle'),
                                   ('lbc-express', 'LBC Express'),
                                   ('grab-express', 'Grab Express'),
                                   ('j-t-express', 'J&T Express'),
                                   ('lalamove', 'Lalamove'),
                                   ('customer-pick-up', 'Customer Pick-up'),
                                   ('distributor-delivery', 'Distributor Delivery')],
               'invoicing_entity': [('2mg-incorporated', '2mg Incorporated'),
                                    ('getmeds-philippines-inc', 'Getmeds Philippines Inc.')]},
 'generic_b2b': {'payment_method': [('cash', 'Cash'),
                                    ('bank-transfer', 'Bank transfer'),
                                    ('check', 'Check'),
                                    ('credit-card', 'Credit card')],
                 'payment_term': [('due-on-receipt', 'Due on receipt'),
                                  ('net-15', 'Net 15'),
                                  ('net-30', 'Net 30'),
                                  ('net-60', 'Net 60')],
                 'source': [('phone', 'Phone'),
                            ('email', 'Email'),
                            ('walk-in', 'Walk-in'),
                            ('website', 'Website')],
                 'delivery_method': [('our-own-delivery', 'Our own delivery'),
                                     ('courier', 'Courier'),
                                     ('customer-pick-up', 'Customer pick-up')],
                 'invoicing_entity': []}}


def upgrade() -> None:
    op.create_table('order_list_items',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.CheckConstraint("kind IN ('payment_method', 'payment_term', 'source', 'delivery_method', 'invoicing_entity')", name='order_list_kind'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'kind', 'code')
    )
    op.create_table('order_fields',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('type', sa.String(length=16), nullable=False),
    sa.Column('required', sa.Boolean(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('help', sa.String(length=200), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.CheckConstraint("type IN ('text', 'textarea', 'number', 'date', 'choice')", name='order_field_type'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'key')
    )
    op.create_table('order_settings',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('large_order_centavos', sa.Integer(), nullable=False),
    sa.Column('recycle_days', sa.Integer(), nullable=False),
    sa.CheckConstraint('large_order_centavos >= 0', name='large_order_not_negative'),
    sa.CheckConstraint('recycle_days >= 1 AND recycle_days <= 365', name='recycle_days_range'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id')
    )
    op.create_table('audit_log',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('actor', sa.String(length=254), nullable=False),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('target', sa.String(length=200), nullable=False),
    sa.Column('fields', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_at'), 'audit_log', ['at'], unique=False)
    op.create_index(op.f('ix_audit_log_org_id'), 'audit_log', ['org_id'], unique=False)

    bind = op.get_bind()
    meta = sa.MetaData()
    organizations = sa.Table("organizations", meta, autoload_with=bind)
    items = sa.Table("order_list_items", meta, autoload_with=bind)
    rules = sa.Table("order_settings", meta, autoload_with=bind)
    for org, template in bind.execute(sa.select(organizations.c.id, organizations.c.template)).all():
        lists = TEMPLATES.get(template, TEMPLATES["generic_b2b"])
        rows = [
            {"org_id": org, "kind": kind, "code": code, "name": name, "is_active": True, "sort_order": order}
            for kind, pairs in lists.items()
            for order, (code, name) in enumerate(pairs)
        ]
        if rows:
            bind.execute(items.insert(), rows)
        bind.execute(rules.insert().values(org_id=org, large_order_centavos=10_000_000, recycle_days=30))


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('order_settings')
    op.drop_table('order_fields')
    op.drop_table('order_list_items')
