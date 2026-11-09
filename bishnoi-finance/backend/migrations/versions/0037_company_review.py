"""Add company review evidence; no existing supplier/account/financial changes."""
from alembic import op
import sqlalchemy as sa

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('nbfi_company_review_batches',
        sa.Column('id', sa.String(36), primary_key=True), sa.Column('source_name', sa.String(200), nullable=False),
        sa.Column('source_hash', sa.String(64), unique=True, nullable=False), sa.Column('company', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('created_by', sa.String(120), nullable=False))
    op.create_table('nbfi_company_review_rows',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('batch_id', sa.String(36), sa.ForeignKey('nbfi_company_review_batches.id'), nullable=False),
        sa.Column('source_line', sa.Integer(), nullable=False), sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(40), nullable=False), sa.Column('supplier_id', sa.String(36), sa.ForeignKey('nbfi_suppliers.id')),
        sa.UniqueConstraint('batch_id', 'source_line', name='company_review_source_row'))
    op.create_table('nbfi_company_scope_reviews',
        sa.Column('subject_kind', sa.String(20), primary_key=True), sa.Column('subject_id', sa.String(36), primary_key=True),
        sa.Column('scope', sa.String(20), nullable=False), sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('reviewed_by', sa.String(120), nullable=False), sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('nbfi_company_scope_reviews')
    op.drop_table('nbfi_company_review_rows')
    op.drop_table('nbfi_company_review_batches')
