"""Customers and activities: companies, the contacts in them, and the calls,
meetings, emails, notes and tasks about either. Each has an owner and the
owner's team, which a role's scope reads.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def owned() -> list[sa.Column]:
    return [
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def index_owned(table: str) -> None:
    op.create_index(f"ix_{table}_owner_id", table, ["owner_id"])
    op.create_index(f"ix_{table}_team_id", table, ["team_id"])


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("industry", sa.String(80), nullable=True),
        sa.Column("website", sa.String(200), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("city", sa.String(80), nullable=True),
        sa.Column("country", sa.String(80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *owned(),
        sa.CheckConstraint("status IN ('prospect', 'customer', 'partner', 'inactive')", name="company_status"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    index_owned("companies")

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=True),
        sa.Column("job_title", sa.String(120), nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("mobile", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *owned(),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    index_owned("contacts")

    op.create_table(
        "activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(8), nullable=True),
        *owned(),
        sa.CheckConstraint("kind IN ('call', 'meeting', 'email', 'note', 'task')", name="activity_kind"),
    )
    for column in ("kind", "company_id", "contact_id", "at", "done_at"):
        op.create_index(f"ix_activities_{column}", "activities", [column])
    index_owned("activities")


def downgrade() -> None:
    op.drop_table("activities")
    op.drop_table("contacts")
    op.drop_table("companies")
