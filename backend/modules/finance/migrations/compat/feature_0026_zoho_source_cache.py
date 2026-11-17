"""Read-only Zoho source cache and sync coverage. Existing financial tables unchanged."""
from alembic import op
import sqlalchemy as sa
revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('nbfi_zoho_source_documents',
        sa.Column('organization_id', sa.String(80), primary_key=True),
        sa.Column('kind', sa.String(20), primary_key=True),
        sa.Column('source_id', sa.String(80), primary_key=True),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('nbfi_zoho_source_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(80), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_start', sa.Date(), nullable=False),
        sa.Column('window_end', sa.Date(), nullable=False),
        sa.Column('coverage', sa.JSON(), nullable=False))
    op.create_index('ix_nbfi_zoho_source_runs_organization_id', 'nbfi_zoho_source_runs', ['organization_id'])


def downgrade():
    pass  # Preserve source evidence; do not rebuild or drop financial tables.
