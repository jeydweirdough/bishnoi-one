"""What needs someone's attention: the rules (per division) and prompts put aside.

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = sa.inspect(op.get_bind()).get_table_names()
    if "nbcm_attention_rules" not in have:
        op.create_table(
            "nbcm_attention_rules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="CASCADE"), nullable=True, unique=True),
            sa.Column("quiet_days", sa.Integer, nullable=False, server_default="45"),
            sa.Column("notice_days", sa.Integer, nullable=False, server_default="7"),
            sa.Column("clidp_days", sa.Integer, nullable=False, server_default="30"),
            sa.Column("stuck_days", sa.Integer, nullable=False, server_default="2"),
        )
    if "nbcm_attention_dismissals" not in have:
        op.create_table(
            "nbcm_attention_dismissals",
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("key", sa.String(120), primary_key=True),
            sa.Column("until", sa.String(10), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("nbcm_attention_dismissals")
    op.drop_table("nbcm_attention_rules")
