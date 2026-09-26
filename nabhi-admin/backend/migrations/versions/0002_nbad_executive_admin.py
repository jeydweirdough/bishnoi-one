"""Executive Admin: compliance records, immigration, corporate documents, properties, tickets, and notifications.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nbad_compliance_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("agency", sa.String(100), nullable=False),
        sa.Column("reference_number", sa.String(80), nullable=False),
        sa.Column("issuance_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewal_window_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("responsible_person", sa.String(120), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nbad_immigration_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("individual_name", sa.String(120), nullable=False),
        sa.Column("designation", sa.String(120), nullable=False),
        sa.Column("nationality", sa.String(60), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_number", sa.String(80), nullable=False),
        sa.Column("issuance_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("renewal_lead_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("sponsoring_entity", sa.String(120), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="valid"),
        sa.Column("assigned_assistant", sa.String(120), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nbad_corporate_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("counterparty", sa.String(140), nullable=False),
        sa.Column("reference_number", sa.String(80), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_renews", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("notice_period_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("custodian", sa.String(120), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("annual_value", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nbad_properties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(140), nullable=False),
        sa.Column("property_type", sa.String(40), nullable=False),
        sa.Column("address", sa.String(250), nullable=False),
        sa.Column("lessor_name", sa.String(140), nullable=False),
        sa.Column("lessor_contact", sa.String(140), nullable=True),
        sa.Column("lease_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notice_deadline_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("monthly_rent", sa.Float(), nullable=True),
        sa.Column("escalation_rate_pct", sa.Float(), nullable=True),
        sa.Column("security_deposit", sa.Float(), nullable=True),
        sa.Column("utilities_info", sa.String(500), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("assigned_manager", sa.String(120), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nbad_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticket_number", sa.String(24), nullable=False, unique=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("requester_name", sa.String(120), nullable=False),
        sa.Column("requester_email", sa.String(254), nullable=True),
        sa.Column("executive_sponsor", sa.String(120), nullable=True),
        sa.Column("assigned_to", sa.String(120), nullable=True),
        sa.Column("sla_due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("resolution_notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "nbad_ticket_updates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("nbad_tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_name", sa.String(120), nullable=False),
        sa.Column("author_email", sa.String(254), nullable=True),
        sa.Column("update_type", sa.String(24), nullable=False, server_default="comment"),
        sa.Column("content", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nbad_ticket_updates_ticket_id", "nbad_ticket_updates", ["ticket_id"])

    op.create_table(
        "nbad_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("days_remaining", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nbad_notifications_entity_id", "nbad_notifications", ["entity_id"])


def downgrade() -> None:
    op.drop_table("nbad_notifications")
    op.drop_table("nbad_ticket_updates")
    op.drop_table("nbad_tickets")
    op.drop_table("nbad_properties")
    op.drop_table("nbad_corporate_documents")
    op.drop_table("nbad_immigration_records")
    op.drop_table("nbad_compliance_records")
