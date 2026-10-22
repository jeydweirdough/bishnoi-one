"""E-signatures, and which steps were signed.

- nbfi_signatures: each person's signature (a PNG, black on transparent),
  drawn or uploaded on their account page. Replaced or removed ones are kept,
  so documents signed with them still show them.
- nbfi_signed_steps: a step on a document (a journal entry prepared or
  approved; a liquidation reviewed or settled): who, when, with which
  signature, and a fingerprint (SHA-256) of the document at that moment.

Nothing existing changes. Decided 2026-10-22 (Plans/Plan - E-signatures).
Main's latest migration was 0012 when this was written (checked right before).

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbfi_signatures" not in tables:
        op.create_table(
            "nbfi_signatures",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("image", sa.LargeBinary(), nullable=False),
            sa.Column("method", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.String(120), nullable=True),
        )
        op.create_index("ix_nbfi_signatures_user_id", "nbfi_signatures", ["user_id"])
    if "nbfi_signed_steps" not in tables:
        op.create_table(
            "nbfi_signed_steps",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("record_type", sa.String(20), nullable=False),
            sa.Column("record_id", sa.String(36), nullable=False),
            sa.Column("step", sa.String(20), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signature_id", sa.String(36), sa.ForeignKey("nbfi_signatures.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signer_name", sa.String(120), nullable=False),
            sa.Column("signer_role", sa.String(80), nullable=False),
            sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fingerprint", sa.String(64), nullable=False),
        )
        op.create_index("nbfi_signed_steps_record", "nbfi_signed_steps", ["record_type", "record_id"])


def downgrade() -> None:
    op.drop_table("nbfi_signed_steps")
    op.drop_table("nbfi_signatures")
