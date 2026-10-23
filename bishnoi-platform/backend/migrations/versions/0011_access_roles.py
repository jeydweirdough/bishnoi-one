"""Access in one place: a company's roles, each holding any module's permissions
with a scope per module, and each person's one role there (decided 2026-10-23).

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nbpl_access_roles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("company_id", "name", name="nbpl_access_role_name"),
    )
    op.create_table(
        "nbpl_access_role_permissions",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("nbpl_access_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("app_key", sa.String(40), primary_key=True),
        sa.Column("permission", sa.String(64), primary_key=True),
    )
    op.create_table(
        "nbpl_access_role_scopes",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("nbpl_access_roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("app_key", sa.String(40), primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False),
    )
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.add_column(sa.Column("access_role_id", sa.String(36), nullable=True))
        batch.create_foreign_key("nbpl_identity_access_role", "nbpl_access_roles", ["access_role_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_nbpl_identities_access_role_id", ["access_role_id"])


def downgrade() -> None:
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_index("ix_nbpl_identities_access_role_id")
        batch.drop_constraint("nbpl_identity_access_role", type_="foreignkey")
        batch.drop_column("access_role_id")
    op.drop_table("nbpl_access_role_scopes")
    op.drop_table("nbpl_access_role_permissions")
    op.drop_table("nbpl_access_roles")
