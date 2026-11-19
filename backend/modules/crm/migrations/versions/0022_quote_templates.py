"""Quotation templates: forms designed in the CRM or uploaded as Excel, per
guarantee-letter issuer, with a logo and an e-signature, and the control
numbers quotes get on them.

Each step only if it isn't done yet, like 0015.

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    now = sa.DateTime(timezone=True)
    if "nbcm_quote_templates" not in tables:
        op.create_table(
            "nbcm_quote_templates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("kind", sa.String(8), nullable=False),
            sa.Column("payer", sa.String(40), nullable=True),
            sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("control_prefix", sa.String(20), nullable=True),
            sa.Column("control_next", sa.Integer(), nullable=False),
            sa.Column("control_digits", sa.Integer(), nullable=False),
            sa.Column("design", sa.JSON(), nullable=False),
            sa.Column("logo_ref", sa.String(32), nullable=True),
            sa.Column("signature_ref", sa.String(32), nullable=True),
            sa.Column("excel_ref", sa.String(32), nullable=True),
            sa.Column("excel_name", sa.String(200), nullable=True),
            sa.Column("excel_sheet", sa.String(120), nullable=True),
            sa.Column("excel_map", sa.JSON(), nullable=True),
            sa.Column("created_at", now, nullable=False),
            sa.Column("updated_at", now, nullable=False),
            sa.CheckConstraint("kind IN ('form', 'excel')", name="quote_template_kind"),
        )
    if "nbcm_quote_controls" not in tables:
        op.create_table(
            "nbcm_quote_controls",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("template_id", sa.String(36), sa.ForeignKey("nbcm_quote_templates.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("quote_id", sa.String(36), sa.ForeignKey("nbcm_quotes.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("number", sa.String(60), nullable=False),
            sa.Column("created_at", now, nullable=False),
            sa.UniqueConstraint("template_id", "quote_id", name="quote_control_once"),
        )


def downgrade() -> None:
    op.drop_table("nbcm_quote_controls")
    op.drop_table("nbcm_quote_templates")
