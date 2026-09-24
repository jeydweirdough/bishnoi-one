"""Inventory's tables, the roles it starts with, and its units of measure.

A database from before migrations had plain `users` and `sessions` tables
(made by create_all). Their accounts move into nbin_users, admins as
Administrators and the rest as Warehouse, and the old tables go. Their
sessions don't move: everyone signs in again once.

Revision ID: 0001
Revises:
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.permissions import ADMINISTRATOR, STARTING_ROLES, WAREHOUSE


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('nbin_audit_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('actor', sa.String(length=254), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('target_type', sa.String(length=32), nullable=True),
    sa.Column('target_id', sa.String(length=36), nullable=True),
    sa.Column('target', sa.String(length=200), nullable=False),
    sa.Column('fields', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_audit_log_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_audit_log_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_audit_log_at'), ['at'], unique=False)

    op.create_table('nbin_brands',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('nbin_categories',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('parent_id', sa.String(length=36), nullable=True),
    sa.Column('description', sa.String(length=300), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['nbin_categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_categories_parent_id'), ['parent_id'], unique=False)

    op.create_table('nbin_roles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=True),
    sa.Column('is_system', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('nbin_sequences',
    sa.Column('key', sa.String(length=16), nullable=False),
    sa.Column('last', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('nbin_suppliers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('contact_person', sa.String(length=120), nullable=True),
    sa.Column('email', sa.String(length=254), nullable=True),
    sa.Column('phone', sa.String(length=40), nullable=True),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('contacts', sa.JSON(), nullable=False),
    sa.Column('payment_terms', sa.String(length=80), nullable=True),
    sa.Column('lead_time_days', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    with op.batch_alter_table('nbin_suppliers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_suppliers_name'), ['name'], unique=False)

    op.create_table('nbin_units',
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('code')
    )
    op.create_table('nbin_warehouses',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('nbin_locations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('warehouse_id', 'code', name='location_code')
    )
    with op.batch_alter_table('nbin_locations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_locations_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_products',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('sku', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category_id', sa.String(length=36), nullable=True),
    sa.Column('brand_id', sa.String(length=36), nullable=True),
    sa.Column('product_type', sa.String(length=16), nullable=False),
    sa.Column('unit_code', sa.String(length=16), nullable=False),
    sa.Column('barcode', sa.String(length=64), nullable=True),
    sa.Column('supplier_id', sa.String(length=36), nullable=True),
    sa.Column('cost_price', sa.Integer(), nullable=False),
    sa.Column('selling_price', sa.Integer(), nullable=False),
    sa.Column('tax_rate_bp', sa.Integer(), nullable=False),
    sa.Column('tax_inclusive', sa.Boolean(), nullable=False),
    sa.Column('min_stock', sa.Integer(), nullable=False),
    sa.Column('max_stock', sa.Integer(), nullable=True),
    sa.Column('reorder_point', sa.Integer(), nullable=False),
    sa.Column('reorder_qty', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('track_batches', sa.Boolean(), nullable=False),
    sa.Column('track_expiry', sa.Boolean(), nullable=False),
    sa.Column('track_serials', sa.Boolean(), nullable=False),
    sa.Column('attributes', sa.JSON(), nullable=False),
    sa.Column('parent_id', sa.String(length=36), nullable=True),
    sa.Column('variant_label', sa.String(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("product_type IN ('stock', 'consumable', 'asset', 'service')", name='product_type'),
    sa.CheckConstraint("status IN ('active', 'inactive', 'discontinued')", name='product_status'),
    sa.ForeignKeyConstraint(['brand_id'], ['nbin_brands.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['category_id'], ['nbin_categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['parent_id'], ['nbin_products.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['supplier_id'], ['nbin_suppliers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['unit_code'], ['nbin_units.code'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sku')
    )
    with op.batch_alter_table('nbin_products', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_products_barcode'), ['barcode'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_products_brand_id'), ['brand_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_products_category_id'), ['category_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_products_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_products_parent_id'), ['parent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_products_supplier_id'), ['supplier_id'], unique=False)

    op.create_table('nbin_role_permissions',
    sa.Column('role_id', sa.String(length=36), nullable=False),
    sa.Column('permission', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['nbin_roles.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission')
    )
    op.create_table('nbin_users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role_id', sa.String(length=36), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['nbin_roles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    with op.batch_alter_table('nbin_users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_users_role_id'), ['role_id'], unique=False)

    op.create_table('nbin_batches',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('batch_no', sa.String(length=60), nullable=False),
    sa.Column('manufactured_on', sa.Date(), nullable=True),
    sa.Column('expires_on', sa.Date(), nullable=True),
    sa.Column('supplier_id', sa.String(length=36), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supplier_id'], ['nbin_suppliers.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'batch_no', name='batch_no')
    )
    with op.batch_alter_table('nbin_batches', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_batches_expires_on'), ['expires_on'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_batches_product_id'), ['product_id'], unique=False)

    op.create_table('nbin_counts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('category_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('submitted_by_id', sa.String(length=36), nullable=True),
    sa.Column('approved_by_id', sa.String(length=36), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['category_id'], ['nbin_categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['submitted_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_counts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_counts_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_counts_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_orders',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('recipient', sa.String(length=160), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('needed_on', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('confirmed_by_id', sa.String(length=36), nullable=True),
    sa.Column('issued_by_id', sa.String(length=36), nullable=True),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['confirmed_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['issued_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_orders_issued_at'), ['issued_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_orders_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_orders_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_product_images',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('content_type', sa.String(length=40), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_product_images', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_product_images_product_id'), ['product_id'], unique=False)

    op.create_table('nbin_purchase_orders',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('supplier_id', sa.String(length=36), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('ordered_on', sa.Date(), nullable=True),
    sa.Column('expected_on', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('ordered_by_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['ordered_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['supplier_id'], ['nbin_suppliers.id'], ),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_purchase_orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_purchase_orders_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_purchase_orders_supplier_id'), ['supplier_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_purchase_orders_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['nbin_users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    with op.batch_alter_table('nbin_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('nbin_supplier_products',
    sa.Column('supplier_id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('supplier_sku', sa.String(length=40), nullable=True),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('lead_time_days', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supplier_id'], ['nbin_suppliers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('supplier_id', 'product_id')
    )
    op.create_table('nbin_transfers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('from_warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('to_warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('requested_by_id', sa.String(length=36), nullable=True),
    sa.Column('approved_by_id', sa.String(length=36), nullable=True),
    sa.Column('dispatched_by_id', sa.String(length=36), nullable=True),
    sa.Column('received_by_id', sa.String(length=36), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('from_warehouse_id <> to_warehouse_id', name='transfer_places'),
    sa.ForeignKeyConstraint(['approved_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['dispatched_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['from_warehouse_id'], ['nbin_warehouses.id'], ),
    sa.ForeignKeyConstraint(['received_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['requested_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['to_warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_transfers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_transfers_from_warehouse_id'), ['from_warehouse_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_transfers_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_transfers_to_warehouse_id'), ['to_warehouse_id'], unique=False)

    op.create_table('nbin_adjustments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('reason', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('count_id', sa.String(length=36), nullable=True),
    sa.Column('created_by_id', sa.String(length=36), nullable=True),
    sa.Column('decided_by_id', sa.String(length=36), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['count_id'], ['nbin_counts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['decided_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_adjustments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_adjustments_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_adjustments_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_count_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('count_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('location_id', sa.String(length=36), nullable=False),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('expected', sa.Integer(), nullable=False),
    sa.Column('counted', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['count_id'], ['nbin_counts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_count_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_count_lines_count_id'), ['count_id'], unique=False)

    op.create_table('nbin_movements',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('location_id', sa.String(length=36), nullable=True),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('on_hand_change', sa.Integer(), nullable=False),
    sa.Column('on_hand_after', sa.Integer(), nullable=True),
    sa.Column('unit_cost', sa.Integer(), nullable=False),
    sa.Column('reference_type', sa.String(length=20), nullable=True),
    sa.Column('reference_id', sa.String(length=36), nullable=True),
    sa.Column('reference', sa.String(length=40), nullable=True),
    sa.Column('note', sa.String(length=300), nullable=True),
    sa.Column('serials', sa.JSON(), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('user_name', sa.String(length=120), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_movements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_movements_at'), ['at'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_movements_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_movements_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_movements_reference_id'), ['reference_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_movements_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_order_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('order_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Integer(), nullable=False),
    sa.Column('picks', sa.JSON(), nullable=False),
    sa.Column('serials', sa.JSON(), nullable=False),
    sa.CheckConstraint('quantity > 0', name='order_line_quantity'),
    sa.ForeignKeyConstraint(['order_id'], ['nbin_orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_order_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_order_lines_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_order_lines_product_id'), ['product_id'], unique=False)

    op.create_table('nbin_purchase_order_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('order_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('received', sa.Integer(), nullable=False),
    sa.Column('unit_cost', sa.Integer(), nullable=False),
    sa.CheckConstraint('quantity > 0', name='po_line_quantity'),
    sa.ForeignKeyConstraint(['order_id'], ['nbin_purchase_orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_purchase_order_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_purchase_order_lines_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_purchase_order_lines_product_id'), ['product_id'], unique=False)

    op.create_table('nbin_receipts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('number', sa.String(length=20), nullable=False),
    sa.Column('order_id', sa.String(length=36), nullable=True),
    sa.Column('supplier_id', sa.String(length=36), nullable=True),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('location_id', sa.String(length=36), nullable=False),
    sa.Column('delivery_ref', sa.String(length=60), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_by_id', sa.String(length=36), nullable=True),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['nbin_purchase_orders.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['received_by_id'], ['nbin_users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['supplier_id'], ['nbin_suppliers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('number')
    )
    with op.batch_alter_table('nbin_receipts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_receipts_order_id'), ['order_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_receipts_received_at'), ['received_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_receipts_supplier_id'), ['supplier_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_receipts_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_serials',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('serial_no', sa.String(length=80), nullable=False),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('location_id', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'serial_no', name='serial_no')
    )
    with op.batch_alter_table('nbin_serials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_serials_location_id'), ['location_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_serials_product_id'), ['product_id'], unique=False)

    op.create_table('nbin_stock',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('warehouse_id', sa.String(length=36), nullable=False),
    sa.Column('location_id', sa.String(length=36), nullable=False),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('on_hand', sa.Integer(), nullable=False),
    sa.Column('damaged', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('damaged >= 0 AND damaged <= on_hand', name='stock_damaged'),
    sa.CheckConstraint('on_hand >= 0', name='stock_on_hand'),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['warehouse_id'], ['nbin_warehouses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('product_id', 'location_id', 'batch_id', name='stock_balance')
    )
    with op.batch_alter_table('nbin_stock', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_stock_batch_id'), ['batch_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_stock_location_id'), ['location_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_stock_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_stock_warehouse_id'), ['warehouse_id'], unique=False)

    op.create_table('nbin_transfer_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('transfer_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('picks', sa.JSON(), nullable=False),
    sa.Column('serials', sa.JSON(), nullable=False),
    sa.CheckConstraint('quantity > 0', name='transfer_line_quantity'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.ForeignKeyConstraint(['transfer_id'], ['nbin_transfers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_transfer_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_transfer_lines_product_id'), ['product_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_nbin_transfer_lines_transfer_id'), ['transfer_id'], unique=False)

    op.create_table('nbin_adjustment_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('adjustment_id', sa.String(length=36), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('location_id', sa.String(length=36), nullable=False),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('serials', sa.JSON(), nullable=False),
    sa.CheckConstraint('quantity <> 0', name='adjustment_line_quantity'),
    sa.ForeignKeyConstraint(['adjustment_id'], ['nbin_adjustments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['location_id'], ['nbin_locations.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_adjustment_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_adjustment_lines_adjustment_id'), ['adjustment_id'], unique=False)

    op.create_table('nbin_receipt_lines',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('receipt_id', sa.String(length=36), nullable=False),
    sa.Column('order_line_id', sa.String(length=36), nullable=True),
    sa.Column('product_id', sa.String(length=36), nullable=False),
    sa.Column('batch_id', sa.String(length=36), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_cost', sa.Integer(), nullable=False),
    sa.Column('serials', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['batch_id'], ['nbin_batches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['order_line_id'], ['nbin_purchase_order_lines.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['product_id'], ['nbin_products.id'], ),
    sa.ForeignKeyConstraint(['receipt_id'], ['nbin_receipts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('nbin_receipt_lines', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_nbin_receipt_lines_receipt_id'), ['receipt_id'], unique=False)


    _starting_data()


UNITS = (("pc", "Piece"), ("box", "Box"), ("pack", "Pack"), ("bottle", "Bottle"), ("vial", "Vial"), ("ampule", "Ampule"),
         ("tablet", "Tablet"), ("capsule", "Capsule"), ("sachet", "Sachet"), ("set", "Set"), ("pair", "Pair"), ("roll", "Roll"),
         ("kg", "Kilogram"), ("g", "Gram"), ("l", "Litre"), ("ml", "Millilitre"))


def _starting_data() -> None:
    bind = op.get_bind()
    now = datetime.now(UTC)
    roles = sa.table("nbin_roles", sa.column("id"), sa.column("name"), sa.column("description"), sa.column("is_system"), sa.column("created_at"))
    grants = sa.table("nbin_role_permissions", sa.column("role_id"), sa.column("permission"))
    ids: dict[str, str] = {}
    for name, description, permissions in STARTING_ROLES:
        ids[name] = str(uuid.uuid4())
        system = name == ADMINISTRATOR
        op.bulk_insert(roles, [{"id": ids[name], "name": name, "description": description, "is_system": system, "created_at": now}])
        if not system:  # the system role holds everything without being told
            op.bulk_insert(grants, [{"role_id": ids[name], "permission": p} for p in sorted(permissions)])
    units = sa.table("nbin_units", sa.column("code"), sa.column("name"), sa.column("is_active"))
    op.bulk_insert(units, [{"code": c, "name": n, "is_active": True} for c, n in UNITS])

    if "users" in sa.inspect(bind).get_table_names():
        old = bind.execute(sa.text("SELECT id, email, full_name, password_hash, role, is_active, created_at, password_changed_at FROM users")).mappings().all()
        users = sa.table("nbin_users", *(sa.column(c) for c in ("id", "email", "full_name", "password_hash", "role_id", "is_active", "created_at", "password_changed_at")))
        op.bulk_insert(users, [
            {**{k: u[k] for k in ("id", "email", "full_name", "password_hash", "is_active")},
             "role_id": ids[ADMINISTRATOR if u["role"] == "admin" else WAREHOUSE],
             "created_at": _moment(u["created_at"]) or now, "password_changed_at": _moment(u["password_changed_at"]) or now}
            for u in old
        ])
        op.drop_table("sessions")
        op.drop_table("users")


def _moment(value):
    """SQLite hands back what it stored, which may be text."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def downgrade() -> None:
    with op.batch_alter_table('nbin_receipt_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_receipt_lines_receipt_id'))

    op.drop_table('nbin_receipt_lines')
    with op.batch_alter_table('nbin_adjustment_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_adjustment_lines_adjustment_id'))

    op.drop_table('nbin_adjustment_lines')
    with op.batch_alter_table('nbin_transfer_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_transfer_lines_transfer_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_transfer_lines_product_id'))

    op.drop_table('nbin_transfer_lines')
    with op.batch_alter_table('nbin_stock', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_stock_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_stock_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_stock_location_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_stock_batch_id'))

    op.drop_table('nbin_stock')
    with op.batch_alter_table('nbin_serials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_serials_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_serials_location_id'))

    op.drop_table('nbin_serials')
    with op.batch_alter_table('nbin_receipts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_receipts_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_receipts_supplier_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_receipts_received_at'))
        batch_op.drop_index(batch_op.f('ix_nbin_receipts_order_id'))

    op.drop_table('nbin_receipts')
    with op.batch_alter_table('nbin_purchase_order_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_purchase_order_lines_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_purchase_order_lines_order_id'))

    op.drop_table('nbin_purchase_order_lines')
    with op.batch_alter_table('nbin_order_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_order_lines_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_order_lines_order_id'))

    op.drop_table('nbin_order_lines')
    with op.batch_alter_table('nbin_movements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_movements_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_movements_reference_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_movements_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_movements_kind'))
        batch_op.drop_index(batch_op.f('ix_nbin_movements_at'))

    op.drop_table('nbin_movements')
    with op.batch_alter_table('nbin_count_lines', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_count_lines_count_id'))

    op.drop_table('nbin_count_lines')
    with op.batch_alter_table('nbin_adjustments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_adjustments_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_adjustments_status'))

    op.drop_table('nbin_adjustments')
    with op.batch_alter_table('nbin_transfers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_transfers_to_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_transfers_status'))
        batch_op.drop_index(batch_op.f('ix_nbin_transfers_from_warehouse_id'))

    op.drop_table('nbin_transfers')
    op.drop_table('nbin_supplier_products')
    with op.batch_alter_table('nbin_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_sessions_user_id'))

    op.drop_table('nbin_sessions')
    with op.batch_alter_table('nbin_purchase_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_purchase_orders_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_purchase_orders_supplier_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_purchase_orders_status'))

    op.drop_table('nbin_purchase_orders')
    with op.batch_alter_table('nbin_product_images', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_product_images_product_id'))

    op.drop_table('nbin_product_images')
    with op.batch_alter_table('nbin_orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_orders_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_orders_status'))
        batch_op.drop_index(batch_op.f('ix_nbin_orders_issued_at'))

    op.drop_table('nbin_orders')
    with op.batch_alter_table('nbin_counts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_counts_warehouse_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_counts_status'))

    op.drop_table('nbin_counts')
    with op.batch_alter_table('nbin_batches', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_batches_product_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_batches_expires_on'))

    op.drop_table('nbin_batches')
    with op.batch_alter_table('nbin_users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_users_role_id'))

    op.drop_table('nbin_users')
    op.drop_table('nbin_role_permissions')
    with op.batch_alter_table('nbin_products', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_products_supplier_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_products_parent_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_products_name'))
        batch_op.drop_index(batch_op.f('ix_nbin_products_category_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_products_brand_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_products_barcode'))

    op.drop_table('nbin_products')
    with op.batch_alter_table('nbin_locations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_locations_warehouse_id'))

    op.drop_table('nbin_locations')
    op.drop_table('nbin_warehouses')
    op.drop_table('nbin_units')
    with op.batch_alter_table('nbin_suppliers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_suppliers_name'))

    op.drop_table('nbin_suppliers')
    op.drop_table('nbin_sequences')
    op.drop_table('nbin_roles')
    with op.batch_alter_table('nbin_categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_categories_parent_id'))

    op.drop_table('nbin_categories')
    op.drop_table('nbin_brands')
    with op.batch_alter_table('nbin_audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_nbin_audit_log_at'))
        batch_op.drop_index(batch_op.f('ix_nbin_audit_log_actor_id'))
        batch_op.drop_index(batch_op.f('ix_nbin_audit_log_action'))

    op.drop_table('nbin_audit_log')
