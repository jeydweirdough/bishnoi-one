"""price book: price types, division rules, products, promos

Also grants the new Inventory module to the starting roles of an existing
database (seeding only adds roles to an empty one): Department Staff may view,
add and edit, Executives may view. Default pricing rules are added by
`python -m app.seed`, which only fills in what's missing.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

INVENTORY_GRANTS = {"department_staff": ("view", "create", "edit"), "executive": ("view",)}


def upgrade() -> None:
    op.create_table('gl_issuers',
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('price_types',
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('entry', sa.String(length=16), nullable=False),
    sa.Column('requires_notes', sa.Boolean(), nullable=False),
    sa.Column('needs_approval', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.CheckConstraint("entry IN ('list', 'entered')", name='price_type_entry'),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('products',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('generic_name', sa.String(length=120), nullable=True),
    sa.Column('strength', sa.String(length=60), nullable=True),
    sa.Column('form', sa.String(length=60), nullable=True),
    sa.Column('unit', sa.String(length=60), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('promos',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('percent_bp', sa.Integer(), nullable=True),
    sa.Column('amount_centavos', sa.Integer(), nullable=True),
    sa.Column('buy_qty', sa.Integer(), nullable=True),
    sa.Column('free_qty', sa.Integer(), nullable=True),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=True),
    sa.Column('all_products', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("kind IN ('percent', 'amount', 'free_goods', 'tiered')", name='promo_kind'),
    sa.CheckConstraint('ends_on IS NULL OR ends_on >= starts_on', name='promo_dates'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('division_pricing',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('uses_price_list', sa.Boolean(), nullable=False),
    sa.Column('allows_guarantee_letters', sa.Boolean(), nullable=False),
    sa.Column('discount_approval_bp', sa.Integer(), nullable=False),
    sa.CheckConstraint('discount_approval_bp >= 0 AND discount_approval_bp <= 10000', name='discount_approval_range'),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.PrimaryKeyConstraint('division_code')
    )
    op.create_table('product_prices',
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('price_type_code', sa.String(length=40), nullable=False),
    sa.Column('amount_centavos', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('amount_centavos >= 0', name='product_price_not_negative'),
    sa.ForeignKeyConstraint(['price_type_code'], ['price_types.code'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('product_id', 'price_type_code')
    )
    op.create_table('promo_divisions',
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['division_code'], ['divisions.code'], ),
    sa.ForeignKeyConstraint(['promo_id'], ['promos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('promo_id', 'division_code')
    )
    op.create_table('promo_products',
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['promo_id'], ['promos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('promo_id', 'product_id')
    )
    op.create_table('promo_tiers',
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('min_qty', sa.Integer(), nullable=False),
    sa.Column('percent_bp', sa.Integer(), nullable=False),
    sa.CheckConstraint('min_qty > 0 AND percent_bp > 0 AND percent_bp <= 10000', name='promo_tier_values'),
    sa.ForeignKeyConstraint(['promo_id'], ['promos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('promo_id', 'min_qty')
    )
    op.create_table('division_price_types',
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('price_type_code', sa.String(length=40), nullable=False),
    sa.Column('rule', sa.String(length=16), nullable=False),
    sa.CheckConstraint("rule IN ('always', 'with_rx')", name='division_price_type_rule'),
    sa.ForeignKeyConstraint(['division_code'], ['division_pricing.division_code'], ),
    sa.ForeignKeyConstraint(['price_type_code'], ['price_types.code'], ),
    sa.PrimaryKeyConstraint('division_code', 'price_type_code')
    )

    connection = op.get_bind()
    roles = sa.table('roles', sa.column('key', sa.String))
    grants = sa.table(
        'role_permissions', sa.column('role_key', sa.String), sa.column('module_key', sa.String), sa.column('action', sa.String)
    )
    existing = set(connection.execute(sa.select(roles.c.key)).scalars())
    already = set(
        connection.execute(sa.select(grants.c.role_key).where(grants.c.module_key == 'inventory')).scalars()
    )
    rows = [
        {'role_key': role, 'module_key': 'inventory', 'action': action}
        for role, actions in INVENTORY_GRANTS.items()
        if role in existing and role not in already
        for action in actions
    ]
    if rows:
        op.bulk_insert(grants, rows)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_key = 'inventory'")
    op.drop_table('division_price_types')
    op.drop_table('promo_tiers')
    op.drop_table('promo_products')
    op.drop_table('promo_divisions')
    op.drop_table('product_prices')
    op.drop_table('division_pricing')
    op.drop_table('promos')
    op.drop_table('products')
    op.drop_table('price_types')
    op.drop_table('gl_issuers')
