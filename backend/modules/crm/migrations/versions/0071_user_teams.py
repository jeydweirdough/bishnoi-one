"""A person in several teams: the other teams they're in, beside their main one
(users.team_id). Their reach covers all of them.

Revision ID: 0071
Revises: 0070
"""

from alembic import op
import sqlalchemy as sa

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_user_teams" in sa.inspect(op.get_bind()).get_table_names():
        return  # made fresh from the models
    op.create_table(
        "nbcm_user_teams",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="CASCADE"), primary_key=True, index=True),
    )


def downgrade() -> None:
    op.drop_table("nbcm_user_teams")
