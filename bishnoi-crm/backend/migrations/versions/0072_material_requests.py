"""Promotional materials Admin asks to give to a team: the team's manager
approves or rejects each request here (nbcm_material_requests).

Revision ID: 0072
Revises: 0071
"""

from alembic import op
import sqlalchemy as sa

revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_material_requests" in sa.inspect(op.get_bind()).get_table_names():
        return  # made fresh from the models
    op.create_table(
        "nbcm_material_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("material", sa.JSON(), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("recipient_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(500), nullable=True),
        sa.Column("requested_by", sa.String(140), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="waiting", index=True),
        sa.Column("admin_state", sa.String(12), nullable=False, server_default="requested"),
        sa.Column("distributed_on", sa.Date(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('waiting', 'approved', 'rejected')", name="material_request_status"),
        sa.CheckConstraint("admin_state IN ('requested', 'distributed', 'cancelled')", name="material_request_admin_state"),
        sa.UniqueConstraint("source", "source_id", name="uq_nbcm_material_requests_source"),
    )


def downgrade() -> None:
    op.drop_table("nbcm_material_requests")
