"""Empty protected connection and worker-control tables; no business row changes."""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("nbfi_zoho_connections",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("encrypted", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("nbfi_zoho_runtime",
        sa.Column("connection_id", sa.String(80), primary_key=True),
        sa.Column("organization_id", sa.String(80), primary_key=True),
        sa.Column("owner", sa.String(80)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("quota_day", sa.Date()),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    pass  # Preserve authorisation and operational evidence; restore a verified backup instead.
