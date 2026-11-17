"""Funds: money released to people in other apps (the CRM's fund requests),
how it was spent, and what Finance sorts spending into.

- nbfi_expense_categories: what money is spent on; reimbursable or not.
- nbfi_fund_requests, nbfi_fund_expenses, nbfi_fund_events: each request,
  its receipts, and its record.
- nbfi_stored_files: the receipts' files.

Each step only if it isn't done yet.

Revision ID: 0003
Revises: 0002
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# What field spending is usually sorted into. Finance changes them under
# Funds -> Categories; "Personal" is there so spending that isn't the
# company's still has somewhere to go.
CATEGORIES = (
    ("Meals & representation", True, "Meals with customers and partners."),
    ("Transportation", True, "Fares, taxis, ride-hailing."),
    ("Fuel, parking & tolls", True, None),
    ("Lodging", True, None),
    ("Supplies & materials", True, "Samples, printing, small supplies."),
    ("Personal", False, "Personal expenses: not charged to the company."),
)


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    now = sa.DateTime(timezone=True)
    if "nbfi_expense_categories" not in tables:
        categories = op.create_table(
            "nbfi_expense_categories",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("reimbursable", sa.Boolean(), nullable=False),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
        )
        op.bulk_insert(categories, [
            {"id": str(uuid.uuid4()), "name": n, "reimbursable": r, "description": d, "is_active": True, "sort_order": i}
            for i, (n, r, d) in enumerate(CATEGORIES)
        ])
    if "nbfi_fund_requests" not in tables:
        op.create_table(
            "nbfi_fund_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source_app", sa.String(20), nullable=False),
            sa.Column("source_id", sa.String(36), nullable=False),
            sa.Column("number", sa.String(30), nullable=False, index=True),
            sa.Column("requester_name", sa.String(120), nullable=False),
            sa.Column("requester_email", sa.String(254), nullable=False, index=True),
            sa.Column("team_name", sa.String(80), nullable=True),
            sa.Column("purpose", sa.String(80), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("customer_name", sa.String(200), nullable=True),
            sa.Column("needed_on", sa.Date(), nullable=True),
            sa.Column("liquidate", sa.Boolean(), nullable=False),
            sa.Column("requested_centavos", sa.Integer(), nullable=False),
            sa.Column("approved_centavos", sa.Integer(), nullable=False),
            sa.Column("approved_by_name", sa.String(120), nullable=False),
            sa.Column("approved_at", now, nullable=False),
            sa.Column("approval_note", sa.String(500), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, index=True),
            sa.Column("released_centavos", sa.Integer(), nullable=True),
            sa.Column("release_method", sa.String(20), nullable=True),
            sa.Column("release_reference", sa.String(80), nullable=True),
            sa.Column("released_at", now, nullable=True),
            sa.Column("released_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("liquidate_by", sa.Date(), nullable=True),
            sa.Column("liquidated_at", now, nullable=True),
            sa.Column("checked_at", now, nullable=True),
            sa.Column("checked_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("sent_back_note", sa.String(500), nullable=True),
            sa.Column("covered_centavos", sa.Integer(), nullable=True),
            sa.Column("return_due_centavos", sa.Integer(), nullable=False),
            sa.Column("returned_centavos", sa.Integer(), nullable=False),
            sa.Column("reimburse_due_centavos", sa.Integer(), nullable=False),
            sa.Column("reimbursed_centavos", sa.Integer(), nullable=False),
            sa.Column("closed_at", now, nullable=True),
            sa.Column("cancel_reason", sa.String(500), nullable=True),
            sa.Column("created_at", now, nullable=False),
            sa.Column("updated_at", now, nullable=False),
            sa.CheckConstraint(
                "status IN ('to_release', 'to_liquidate', 'to_check', 'to_return', 'to_reimburse', 'closed', 'cancelled')", name="fund_status"
            ),
            sa.UniqueConstraint("source_app", "source_id", name="fund_from_source_once"),
        )
    if "nbfi_fund_expenses" not in tables:
        op.create_table(
            "nbfi_fund_expenses",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("request_id", sa.String(36), sa.ForeignKey("nbfi_fund_requests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("spent_on", sa.Date(), nullable=False),
            sa.Column("description", sa.String(200), nullable=False),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("nbfi_expense_categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount_centavos", sa.Integer(), nullable=False),
            sa.Column("receipt_ref", sa.String(32), nullable=True),
            sa.Column("receipt_name", sa.String(160), nullable=True),
            sa.Column("no_receipt_reason", sa.String(300), nullable=True),
            sa.Column("accepted", sa.Boolean(), nullable=True),
            sa.Column("refused_reason", sa.String(300), nullable=True),
            sa.Column("created_at", now, nullable=False),
        )
    if "nbfi_fund_events" not in tables:
        op.create_table(
            "nbfi_fund_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("request_id", sa.String(36), sa.ForeignKey("nbfi_fund_requests.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("at", now, nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("who", sa.String(120), nullable=False),
            sa.Column("text", sa.String(500), nullable=False),
            sa.Column("amount_centavos", sa.Integer(), nullable=True),
        )
    if "nbfi_stored_files" not in tables:
        op.create_table(
            "nbfi_stored_files",
            sa.Column("ref", sa.String(32), primary_key=True),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("created_at", now, nullable=False),
        )


def downgrade() -> None:
    for table in ("nbfi_stored_files", "nbfi_fund_events", "nbfi_fund_expenses", "nbfi_fund_requests", "nbfi_expense_categories"):
        op.drop_table(table)
