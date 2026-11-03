"""Administrator-reviewed access policy imports and version history."""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("nbpl_access_policy_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("preview", sa.JSON(), nullable=False))
    op.create_index("ix_nbpl_access_policy_imports_company_id", "nbpl_access_policy_imports", ["company_id"])
    op.create_index("ix_nbpl_access_policy_imports_applied_at", "nbpl_access_policy_imports", ["applied_at"])


def downgrade():
    op.drop_table("nbpl_access_policy_imports")
