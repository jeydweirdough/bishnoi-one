"""Directory imports retain unresolved details without certifying tax defaults."""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nbfi_suppliers", sa.Column("tax_defaults_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("nbfi_suppliers", sa.Column("import_details", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("nbfi_bills", sa.Column("tax_reviewed", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    # Preserve recorded evidence; no table rebuild or destructive downgrade.
    pass
