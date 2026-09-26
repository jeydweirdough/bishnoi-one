"""Fund requests: money asked for ahead of spending it, approved by the Team
Lead here and released by Nabhi Finance.

- nbcm_fund_purposes: what money is asked for, and whether it's liquidated.
- nbcm_fund_requests: each request, its decision, and Finance's copy.
- funds.view / funds.create for Salesperson and Field agent, and
  funds.approve too for Team Lead.

Each step only if it isn't done yet, like 0015.

Revision ID: 0020
Revises: 0019
"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# Written out here (not imported) so later changes to app/permissions.py never
# rewrite what this did.
GRANTS = {
    "Team Lead": {"funds.view", "funds.create", "funds.approve"},
    "Salesperson": {"funds.view", "funds.create"},
    "Field agent": {"funds.view", "funds.create"},
}
PURPOSES = (
    ("Partnership dinner / client meal", "Meals with doctors, clinics and partners.", True),
    ("Transportation & travel", "Fares, fuel and tolls for field work.", True),
    ("Event or sponsorship", "A booth, a talk, a clinic event.", True),
    ("Allowance", "A fixed amount, not accounted for receipt by receipt.", False),
)


def upgrade() -> None:
    db = op.get_bind()
    tables = set(sa.inspect(db).get_table_names())
    now = sa.DateTime(timezone=True)
    if "nbcm_fund_purposes" not in tables:
        purposes = op.create_table(
            "nbcm_fund_purposes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("liquidate", sa.Boolean(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
        )
        op.bulk_insert(purposes, [
            {"id": str(uuid.uuid4()), "name": n, "description": d, "liquidate": liq, "is_active": True, "sort_order": i}
            for i, (n, d, liq) in enumerate(PURPOSES)
        ])
    if "nbcm_fund_requests" not in tables:
        op.create_table(
            "nbcm_fund_requests",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(24), nullable=False, unique=True),
            sa.Column("purpose_id", sa.String(36), sa.ForeignKey("nbcm_fund_purposes.id", ondelete="SET NULL"), nullable=True),
            sa.Column("purpose_name", sa.String(80), nullable=False),
            sa.Column("liquidate", sa.Boolean(), nullable=False),
            sa.Column("amount_centavos", sa.Integer(), nullable=False),
            sa.Column("needed_on", sa.String(10), nullable=True),
            sa.Column("details", sa.Text(), nullable=False),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, index=True),
            sa.Column("approved_centavos", sa.Integer(), nullable=True),
            sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("decided_at", now, nullable=True),
            sa.Column("decision_note", sa.String(500), nullable=True),
            sa.Column("finance", sa.JSON(), nullable=True),
            sa.Column("finance_synced_at", now, nullable=True),
            sa.Column("finance_error", sa.String(300), nullable=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id"), nullable=False, index=True),
            sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", now, nullable=False),
            sa.Column("updated_at", now, nullable=False),
            sa.CheckConstraint(
                "status IN ('pending', 'declined', 'cancelled', 'approved', 'to_release', 'to_liquidate', 'to_check', 'to_return', 'to_reimburse', 'closed')",
                name="fund_request_status",
            ),
        )

    role = lambda name: db.execute(sa.text("SELECT id FROM nbcm_roles WHERE name = :n AND is_system = false"), {"n": name}).scalar()  # noqa: E731
    for name, permissions in GRANTS.items():
        role_id = role(name)
        if not role_id:
            continue
        have = set(db.execute(sa.text("SELECT permission FROM nbcm_role_permissions WHERE role_id = :id"), {"id": role_id}).scalars())
        for p in sorted(permissions - have):
            db.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, :p)"), {"id": role_id, "p": p})


def downgrade() -> None:
    op.execute("DELETE FROM nbcm_role_permissions WHERE permission LIKE 'funds.%'")
    op.drop_table("nbcm_fund_requests")
    op.drop_table("nbcm_fund_purposes")
