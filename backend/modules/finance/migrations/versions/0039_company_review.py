"""Add company review evidence; no existing supplier/account/financial changes."""
from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    wanted = {'nbfi_company_review_batches', 'nbfi_company_scope_reviews', 'nbfi_company_review_rows'}
    present = set(inspector.get_table_names()) & wanted
    if present == wanted:
        required = {'nbfi_company_review_batches': {'source_hash', 'created_by', 'created_at', 'id', 'source_name', 'company'}, 'nbfi_company_review_rows': {'source_line', 'supplier_id', 'data', 'status', 'id', 'batch_id'}, 'nbfi_company_scope_reviews': {'subject_kind', 'reviewed_by', 'evidence', 'subject_id', 'reviewed_at', 'scope'}}
        for table, fields in required.items():
            if not fields <= {c['name'] for c in inspector.get_columns(table)}:
                raise RuntimeError('Partial legacy table columns; no automatic repair.')
        return
    if present:
        raise RuntimeError('Partial legacy receipt/company-review schema; no automatic repair.')
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
