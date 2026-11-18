"""Approval slips (2026-11-18, Step 4C): nbpl_approvals (one request with a number, AR-000001 per company, and a
record number from 40000001), nbpl_approval_steps (its steps, in order) and nbpl_approval_attachments (records it
links to, files added to it). Added in place; no rows change.

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

FIRST = 40000001


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    postgres = bind.dialect.name == "postgresql"
    if "nbpl_approvals" not in tables:
        op.create_table(
            "nbpl_approvals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("no", sa.Integer()),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("number", sa.String(20), nullable=False),
            sa.Column("app", sa.String(40), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("record_id", sa.String(36), nullable=False),
            sa.Column("record_number", sa.String(60)),
            sa.Column("record_url", sa.String(300)),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("summary", sa.JSON()),
            sa.Column("requested_by_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="SET NULL")),
            sa.Column("requested_by_name", sa.String(120), nullable=False),
            sa.Column("requested_by_email", sa.String(254)),
            sa.Column("status", sa.String(12), nullable=False),
            sa.Column("replaces_id", sa.String(36)),
            sa.Column("note", sa.String(500)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("status IN ('pending', 'approved', 'returned', 'cancelled')", name="nbpl_approval_status"),
            sa.UniqueConstraint("company_id", "number", name="nbpl_approval_number_once"),
        )
        op.create_index("ix_nbpl_approvals_company_id", "nbpl_approvals", ["company_id"])
        op.create_index("ix_nbpl_approvals_requested_by_id", "nbpl_approvals", ["requested_by_id"])
        op.create_index("ix_nbpl_approvals_status", "nbpl_approvals", ["status"])
        op.create_index("nbpl_approvals_record", "nbpl_approvals", ["company_id", "app", "kind", "record_id"])
        op.create_index("nbpl_approvals_no", "nbpl_approvals", ["no"], unique=True)
        if postgres:
            bind.execute(sa.text(f"create sequence if not exists nbpl_approvals_no_seq start with {FIRST}"))
            bind.execute(sa.text("alter table nbpl_approvals alter column no set default nextval('nbpl_approvals_no_seq')"))
            bind.execute(sa.text("alter sequence nbpl_approvals_no_seq owned by nbpl_approvals.no"))
    if "nbpl_approval_steps" not in tables:
        op.create_table(
            "nbpl_approval_steps",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("approval_id", sa.String(36), sa.ForeignKey("nbpl_approvals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(80), nullable=False),
            sa.Column("approver_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="SET NULL")),
            sa.Column("approver_name", sa.String(120)),
            sa.Column("app_key", sa.String(40)),
            sa.Column("permission", sa.String(64)),
            sa.Column("status", sa.String(10), nullable=False),
            sa.Column("note", sa.String(500)),
            sa.Column("acted_by_id", sa.String(36)),
            sa.Column("acted_by_name", sa.String(120)),
            sa.Column("acted_as", sa.String(16)),
            sa.Column("acted_at", sa.DateTime(timezone=True)),
            sa.Column("signature_id", sa.String(36)),
            sa.CheckConstraint("status IN ('waiting', 'signed', 'returned', 'skipped')", name="nbpl_approval_step_status"),
            sa.UniqueConstraint("approval_id", "position", name="nbpl_approval_step_once"),
        )
        op.create_index("ix_nbpl_approval_steps_approval_id", "nbpl_approval_steps", ["approval_id"])
        op.create_index("ix_nbpl_approval_steps_approver_id", "nbpl_approval_steps", ["approver_id"])
    if "nbpl_approval_attachments" not in tables:
        op.create_table(
            "nbpl_approval_attachments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("approval_id", sa.String(36), sa.ForeignKey("nbpl_approvals.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(8), nullable=False),
            sa.Column("label", sa.String(120), nullable=False),
            sa.Column("app", sa.String(40)),
            sa.Column("record_kind", sa.String(40)),
            sa.Column("record_id", sa.String(36)),
            sa.Column("record_number", sa.String(60)),
            sa.Column("url", sa.String(300)),
            sa.Column("file_name", sa.String(200)),
            sa.Column("content_type", sa.String(100)),
            sa.Column("data", sa.LargeBinary()),
            sa.Column("size", sa.Integer()),
            sa.Column("added_by", sa.String(254), nullable=False),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_nbpl_approval_attachments_approval_id", "nbpl_approval_attachments", ["approval_id"])


def downgrade() -> None:
    op.drop_table("nbpl_approval_attachments")
    op.drop_table("nbpl_approval_steps")
    op.drop_table("nbpl_approvals")
