"""companies: organizations, memberships, and org_id on every company table

Everything that existed before goes into the first company, Getmeds
(FIRST_ORG_ID below), and every person gets a membership in it. A person
switched off before is switched off in Getmeds (their membership), not
everywhere.

Natural keys (a division's code, a role's key...) become unique per company,
so each company table is rebuilt with org_id leading its key: its rows are
copied out, the table is dropped and made again, and the rows go back in with
the company filled in. Works the same on SQLite and Postgres.

Revision ID: 0005
Revises: 0004
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

FIRST_ORG_ID = "00000000-0000-4000-8000-000000000001"

# Parents before children; dropped in the reverse order.
REBUILT = (
    "divisions",
    "subdivisions",
    "headquarters",
    "roles",
    "role_permissions",
    "assignments",
    "price_types",
    "division_pricing",
    "division_price_types",
    "gl_issuers",
    "products",
    "product_prices",
    "promos",
    "promo_products",
    "promo_divisions",
    "promo_tiers",
    "retention_rules",
    "goal_targets",
)


def create_organizations() -> None:
    op.create_table('organizations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('slug', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('template', sa.String(length=40), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('minor_units', sa.Integer(), nullable=False),
    sa.Column('locale', sa.String(length=16), nullable=False),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('brand_name', sa.String(length=80), nullable=False),
    sa.Column('order_prefix', sa.String(length=8), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active', 'suspended')", name='organization_status'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )

def create_platform_admins() -> None:
    op.create_table('platform_admins',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )

def create_memberships() -> None:
    op.create_table('memberships',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('manager_id', sa.String(length=36), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("status IN ('active', 'suspended')", name='membership_status'),
    sa.ForeignKeyConstraint(['org_id', 'manager_id'], ['memberships.org_id', 'memberships.user_id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('org_id', 'user_id')
    )
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)

def create_divisions() -> None:
    op.create_table('divisions',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'code')
    )

def create_subdivisions() -> None:
    op.create_table('subdivisions',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code', 'code')
    )

def create_headquarters() -> None:
    op.create_table('headquarters',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('subdivision_code', sa.String(length=40), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['org_id', 'division_code', 'subdivision_code'], ['subdivisions.org_id', 'subdivisions.division_code', 'subdivisions.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code', 'subdivision_code', 'code')
    )

def create_roles() -> None:
    op.create_table('roles',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('key', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'key')
    )

def create_role_permissions() -> None:
    op.create_table('role_permissions',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('role_key', sa.String(length=40), nullable=False),
    sa.Column('module_key', sa.String(length=32), nullable=False),
    sa.Column('action', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['org_id', 'role_key'], ['roles.org_id', 'roles.key'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'role_key', 'module_key', 'action')
    )

def create_assignments() -> None:
    op.create_table('assignments',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('role_key', sa.String(length=40), nullable=False),
    sa.Column('module_key', sa.String(length=32), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=True),
    sa.Column('subdivision_code', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('subdivision_code IS NULL OR division_code IS NOT NULL', name='subdivision_needs_division'),
    sa.ForeignKeyConstraint(['org_id', 'division_code', 'subdivision_code'], ['subdivisions.org_id', 'subdivisions.division_code', 'subdivisions.code'], ),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id', 'role_key'], ['roles.org_id', 'roles.key'], ),
    sa.ForeignKeyConstraint(['org_id', 'user_id'], ['memberships.org_id', 'memberships.user_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['profiles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assignments_org_id'), 'assignments', ['org_id'], unique=False)
    op.create_index(op.f('ix_assignments_user_id'), 'assignments', ['user_id'], unique=False)

def create_price_types() -> None:
    op.create_table('price_types',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('entry', sa.String(length=16), nullable=False),
    sa.Column('requires_notes', sa.Boolean(), nullable=False),
    sa.Column('needs_approval', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.CheckConstraint("entry IN ('list', 'entered')", name='price_type_entry'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'code')
    )

def create_division_pricing() -> None:
    op.create_table('division_pricing',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('uses_price_list', sa.Boolean(), nullable=False),
    sa.Column('allows_guarantee_letters', sa.Boolean(), nullable=False),
    sa.Column('discount_approval_bp', sa.Integer(), nullable=False),
    sa.CheckConstraint('discount_approval_bp >= 0 AND discount_approval_bp <= 10000', name='discount_approval_range'),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code')
    )

def create_division_price_types() -> None:
    op.create_table('division_price_types',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('price_type_code', sa.String(length=40), nullable=False),
    sa.Column('rule', sa.String(length=16), nullable=False),
    sa.CheckConstraint("rule IN ('always', 'with_rx')", name='division_price_type_rule'),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['division_pricing.org_id', 'division_pricing.division_code'], ),
    sa.ForeignKeyConstraint(['org_id', 'price_type_code'], ['price_types.org_id', 'price_types.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code', 'price_type_code')
    )

def create_gl_issuers() -> None:
    op.create_table('gl_issuers',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'code')
    )

def create_products() -> None:
    op.create_table('products',
    sa.Column('org_id', sa.String(length=36), nullable=False),
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
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'code', name='product_code_per_company'),
    sa.UniqueConstraint('org_id', 'id', name='product_in_company')
    )
    op.create_index(op.f('ix_products_org_id'), 'products', ['org_id'], unique=False)

def create_product_prices() -> None:
    op.create_table('product_prices',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('price_type_code', sa.String(length=40), nullable=False),
    sa.Column('amount_centavos', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('amount_centavos >= 0', name='product_price_not_negative'),
    sa.ForeignKeyConstraint(['org_id', 'price_type_code'], ['price_types.org_id', 'price_types.code'], ),
    sa.ForeignKeyConstraint(['org_id', 'product_id'], ['products.org_id', 'products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('product_id', 'price_type_code')
    )
    op.create_index(op.f('ix_product_prices_org_id'), 'product_prices', ['org_id'], unique=False)

def create_promos() -> None:
    op.create_table('promos',
    sa.Column('org_id', sa.String(length=36), nullable=False),
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
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('org_id', 'id', name='promo_in_company')
    )
    op.create_index(op.f('ix_promos_org_id'), 'promos', ['org_id'], unique=False)

def create_promo_products() -> None:
    op.create_table('promo_products',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.ForeignKeyConstraint(['org_id', 'product_id'], ['products.org_id', 'products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id', 'promo_id'], ['promos.org_id', 'promos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('promo_id', 'product_id')
    )
    op.create_index(op.f('ix_promo_products_org_id'), 'promo_products', ['org_id'], unique=False)

def create_promo_divisions() -> None:
    op.create_table('promo_divisions',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id', 'promo_id'], ['promos.org_id', 'promos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('promo_id', 'division_code')
    )
    op.create_index(op.f('ix_promo_divisions_org_id'), 'promo_divisions', ['org_id'], unique=False)

def create_promo_tiers() -> None:
    op.create_table('promo_tiers',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('promo_id', sa.String(length=36), nullable=False),
    sa.Column('min_qty', sa.Integer(), nullable=False),
    sa.Column('percent_bp', sa.Integer(), nullable=False),
    sa.CheckConstraint('min_qty > 0 AND percent_bp > 0 AND percent_bp <= 10000', name='promo_tier_values'),
    sa.ForeignKeyConstraint(['org_id', 'promo_id'], ['promos.org_id', 'promos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('promo_id', 'min_qty')
    )
    op.create_index(op.f('ix_promo_tiers_org_id'), 'promo_tiers', ['org_id'], unique=False)

def create_retention_rules() -> None:
    op.create_table('retention_rules',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('at_risk_days', sa.Integer(), nullable=False),
    sa.Column('lost_days', sa.Integer(), nullable=False),
    sa.CheckConstraint('at_risk_days >= 1 AND lost_days > at_risk_days AND lost_days <= 730', name='retention_days'),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code')
    )

def create_goal_targets() -> None:
    op.create_table('goal_targets',
    sa.Column('org_id', sa.String(length=36), nullable=False),
    sa.Column('division_code', sa.String(length=32), nullable=False),
    sa.Column('goal', sa.String(length=40), nullable=False),
    sa.Column('target', sa.Integer(), nullable=False),
    sa.CheckConstraint('target >= 0', name='goal_target_not_negative'),
    sa.ForeignKeyConstraint(['org_id', 'division_code'], ['divisions.org_id', 'divisions.code'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('org_id', 'division_code', 'goal')
    )


def copy_rows(bind, name: str) -> list[dict]:
    table = sa.Table(name, sa.MetaData(), autoload_with=bind)
    return [dict(row) for row in bind.execute(sa.select(table)).mappings()]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)

    create_organizations()
    create_platform_admins()
    create_memberships()
    op.bulk_insert(
        sa.Table("organizations", sa.MetaData(), autoload_with=bind),
        [
            {
                "id": FIRST_ORG_ID,
                "slug": "getmeds",
                "name": "Getmeds",
                "status": "active",
                "template": "pharma_ph",
                "currency": "PHP",
                "minor_units": 2,
                "locale": "en-PH",
                "timezone": "Asia/Manila",
                "brand_name": "Getmeds",
                "order_prefix": "GM",
                "created_at": now,
            }
        ],
    )

    # Everyone joins Getmeds; being switched off moves from the person to the membership.
    profiles = sa.Table("profiles", sa.MetaData(), autoload_with=bind)
    people = bind.execute(sa.select(profiles.c.id, profiles.c.is_active, profiles.c.created_at)).all()
    if people:
        op.bulk_insert(
            sa.Table("memberships", sa.MetaData(), autoload_with=bind),
            [
                {
                    "org_id": FIRST_ORG_ID,
                    "user_id": pid,
                    "status": "active" if active else "suspended",
                    "created_at": created or now,
                }
                for pid, active, created in people
            ],
        )
    bind.execute(profiles.update().values(is_active=True))

    saved = {name: copy_rows(bind, name) for name in REBUILT}
    for name in reversed(REBUILT):
        op.drop_table(name)
    for name in REBUILT:
        globals()[f"create_{name}"]()
        rows = saved[name]
        if rows:
            table = sa.Table(name, sa.MetaData(), autoload_with=bind)
            bind.execute(table.insert(), [{**row, "org_id": FIRST_ORG_ID} for row in rows])


def downgrade() -> None:
    raise NotImplementedError("Companies can't be undone: restore the backup taken before upgrading.")
