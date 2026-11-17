"""Saved views (benchmark E2): a list's filters, search and sort kept by name,
one person's own or shared (nbcm_saved_views).

Revision ID: 0074
Revises: 0073
"""

from alembic import op
import sqlalchemy as sa

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_saved_views" in sa.inspect(op.get_bind()).get_table_names():
        return  # made fresh from the models
    op.create_table(
        "nbcm_saved_views",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("list", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("query", sa.String(1000), nullable=False, server_default=""),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "list", "name", name="saved_view_name_once"),
        sa.CheckConstraint("list IN ('companies', 'contacts', 'deals', 'quotes', 'activities')", name="saved_view_list"),
    )


def downgrade() -> None:
    op.drop_table("nbcm_saved_views")
