"""The lead inbox (decided 2026-10-19): people who reached the company on its
own channels (Facebook lead forms, Messenger, WhatsApp, Viber, Tawk.to, the
website's forms), waiting to be added to the customers (nbcm_inbox_leads).
Handling it is a permission of its own (customers.inbox), given to the roles
that reach more than their own records and can add customers.

Revision ID: 0076
Revises: 0075
"""

from alembic import op
import sqlalchemy as sa

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "nbcm_inbox_leads" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbcm_inbox_leads",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("channel", sa.String(12), nullable=False),
            sa.Column("sender", sa.String(120), nullable=True),
            sa.Column("status", sa.String(10), nullable=False, server_default="new"),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("business", sa.String(160), nullable=True),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("email", sa.String(254), nullable=True),
            sa.Column("city", sa.String(80), nullable=True),
            sa.Column("messages", sa.JSON(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("handled_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("channel IN ('facebook', 'messenger', 'whatsapp', 'viber', 'tawkto', 'form')", name="inbox_channel"),
            sa.CheckConstraint("status IN ('new', 'added', 'dismissed')", name="inbox_status"),
        )
        for col in ("channel", "sender", "status", "received_at", "last_at", "company_id"):
            op.create_index(f"ix_nbcm_inbox_leads_{col}", "nbcm_inbox_leads", [col])
    roles = bind.execute(sa.text(
        "SELECT r.id FROM nbcm_roles r JOIN nbcm_role_permissions p ON p.role_id = r.id "
        "WHERE p.permission = 'customers.create' AND r.is_system = false AND r.scope <> 'own'"
    )).scalars().all()
    for role in roles:
        held = bind.execute(sa.text("SELECT 1 FROM nbcm_role_permissions WHERE role_id = :id AND permission = 'customers.inbox'"), {"id": role}).first()
        if held is None:
            bind.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, 'customers.inbox')"), {"id": role})


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM nbcm_role_permissions WHERE permission = 'customers.inbox'"))
    op.drop_table("nbcm_inbox_leads")
