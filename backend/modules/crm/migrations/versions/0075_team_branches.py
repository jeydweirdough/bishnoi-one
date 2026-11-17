"""Branches of a division (decided 2026-10-19, from the 2026 org chart): a team
can be part of another (nbcm_teams.parent_id), one level deep.

Revision ID: 0075
Revises: 0074
"""

from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_teams")}
    if "parent_id" not in columns:
        with op.batch_alter_table("nbcm_teams") as batch:
            batch.add_column(sa.Column("parent_id", sa.String(36), nullable=True))
            batch.create_foreign_key("fk_nbcm_teams_parent", "nbcm_teams", ["parent_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_nbcm_teams_parent_id", ["parent_id"])


def downgrade() -> None:
    with op.batch_alter_table("nbcm_teams") as batch:
        batch.drop_index("ix_nbcm_teams_parent_id")
        batch.drop_constraint("fk_nbcm_teams_parent", type_="foreignkey")
        batch.drop_column("parent_id")
