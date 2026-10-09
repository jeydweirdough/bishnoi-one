"""Outside services (Zoho Books, the email providers) are connected here, per
company, instead of on each application's server; and each application is
given a key for its own secrets with its links, instead of keeping one in its
settings (CONNECTIONS_KEY).

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspect = sa.inspect(op.get_bind())
    if "data_key" not in {c["name"] for c in inspect.get_columns("nbpl_applications")}:
        with op.batch_alter_table("nbpl_applications") as batch:
            batch.add_column(sa.Column("data_key", sa.Text(), nullable=True))
    if "nbpl_service_connections" in inspect.get_table_names():
        return
    op.create_table(
        "nbpl_service_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("service", sa.String(40), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("secrets", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_ok", sa.Boolean(), nullable=True),
        sa.Column("check_message", sa.String(300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_id", sa.String(36), sa.ForeignKey("nbpl_users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("company_id", "service", name="nbpl_service_connection_once"),
    )


def downgrade() -> None:
    op.drop_table("nbpl_service_connections")
    with op.batch_alter_table("nbpl_applications") as batch:
        batch.drop_column("data_key")
