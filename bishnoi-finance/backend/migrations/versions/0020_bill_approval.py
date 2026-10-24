"""Supplier bills are approved before they're paid (Aubrey's flow).

- nbfi_bills: where a bill stands in its approval (stage: to approve, to check, returned; a
  draft being made has none), who submitted, approved and checked it and when. A bill's status
  keeps its values (draft, recorded, void): it's recorded, posted, when it clears.
- nbfi_bill_events: what happened to each bill (submitted, approved, returned with the reason,
  checked, cleared, voided).
- Ticks: "Record" for bills goes (a bill is now posted when it clears), and whoever had it keeps
  "Make drafts". The payment voucher's check, approve and told-first ticks go: the checks are
  on the bill now. Approve and check for bills are ticked on the Roles screen.
- Payment vouchers waiting to be checked or approved move to "to release", and their
  notifications are marked done.

Added in place, never by rebuilding a table (see 0017). Decided 2026-10-23 (Plans/Plan - Bill
approval flow). Main's latest migration was 0012 when this was written (checked right before).

Revision ID: 0020
Revises: 0019
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

GONE = ("bills.record", "vouchers.check", "vouchers.approve", "vouchers.first")
USERS = ("submitted_by_id", "approved_by_id", "checked_by_id")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    postgres = bind.dialect.name == "postgresql"

    have = {c["name"] for c in inspector.get_columns("nbfi_bills")}
    columns = (
        ("stage", sa.String(12)), ("submitted_by_id", sa.String(36)),
        ("approved_by", sa.String(120)), ("approved_by_id", sa.String(36)), ("approved_at", sa.DateTime(timezone=True)),
        ("checked_by", sa.String(120)), ("checked_by_id", sa.String(36)), ("checked_at", sa.DateTime(timezone=True)),
    )
    for name, kind in columns:
        if name not in have:
            op.add_column("nbfi_bills", sa.Column(name, kind, nullable=True))
            if postgres and name in USERS:
                op.create_foreign_key(f"nbfi_bills_{name}_fkey", "nbfi_bills", "nbfi_users", [name], ["id"], ondelete="SET NULL")
    if "ix_nbfi_bills_stage" not in {i["name"] for i in inspector.get_indexes("nbfi_bills")}:
        op.create_index("ix_nbfi_bills_stage", "nbfi_bills", ["stage"])

    if "nbfi_bill_events" not in tables:
        op.create_table(
            "nbfi_bill_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("bill_id", sa.String(36), sa.ForeignKey("nbfi_bills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("who", sa.String(120), nullable=False),
            sa.Column("who_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("text", sa.String(300), nullable=True),
        )
        op.create_index("ix_nbfi_bill_events_bill_id", "nbfi_bill_events", ["bill_id"])

    # Whoever could record bills keeps making drafts; then the retired ticks go.
    for (role,) in bind.execute(sa.text("SELECT role_id FROM nbfi_role_permissions WHERE permission = 'bills.record'")).all():
        if bind.execute(sa.text("SELECT 1 FROM nbfi_role_permissions WHERE role_id = :r AND permission = 'bills.create'"), {"r": role}).scalar() is None:
            bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, 'bills.create')"), {"r": role})
    for p in GONE:
        bind.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission = :p"), {"p": p})

    # Vouchers part-way through the old checks: ready to release (the bills carry the checks now).
    now = datetime.now(UTC)
    if "nbfi_payment_vouchers" in tables:
        bind.execute(sa.text("UPDATE nbfi_payment_vouchers SET status = 'to_release', updated_at = :t WHERE status IN ('to_check', 'to_approve')"), {"t": now})
    bind.execute(
        sa.text("UPDATE nbfi_notifications SET read_at = :t WHERE kind IN ('voucher.to_check', 'voucher.to_approve') AND read_at IS NULL"), {"t": now}
    )


def downgrade() -> None:
    bind = op.get_bind()
    for (role,) in bind.execute(sa.text("SELECT role_id FROM nbfi_role_permissions WHERE permission = 'bills.create'")).all():
        bind.execute(sa.text("INSERT INTO nbfi_role_permissions (role_id, permission) VALUES (:r, 'bills.record')"), {"r": role})
    for p in ("bills.approve", "bills.first", "bills.check"):
        bind.execute(sa.text("DELETE FROM nbfi_role_permissions WHERE permission = :p"), {"p": p})
    op.drop_table("nbfi_bill_events")
    op.drop_index("ix_nbfi_bills_stage", "nbfi_bills")
    postgres = bind.dialect.name == "postgresql"
    for name in ("checked_at", "checked_by_id", "checked_by", "approved_at", "approved_by_id", "approved_by", "submitted_by_id", "stage"):
        if postgres and name in USERS:
            op.drop_constraint(f"nbfi_bills_{name}_fkey", "nbfi_bills", type_="foreignkey")
        op.drop_column("nbfi_bills", name)
