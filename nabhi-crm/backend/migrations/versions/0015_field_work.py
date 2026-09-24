"""Field work: field agents visit doctors and collect what they owe.

- nbcm_balances: what a doctor owed on a date, uploaded from accounting.
- nbcm_visits: a visit to a doctor and what came of it (a payment collected,
  with its receipt; a promise; nobody in; details updated).
- nbcm_field_goals: each person's goals for a month.
- The customer type Doctor, and the role Field agent (their own doctors, their
  visits). A Team Lead gets the team's visits and the tracker.

Revision ID: 0015
Revises: 0014
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

# Written out here (not imported) so later changes to app/permissions.py never
# rewrite what this did.
FIELD_AGENT = {
    "customers.view", "customers.edit",
    "visits.view", "visits.create", "visits.edit",
    "activities.view", "activities.create", "activities.edit",
    "dashboard.view",
}
TEAM_LEAD_ADDS = {"visits.view", "visits.create", "visits.edit", "visits.delete", "goals.view"}


def upgrade() -> None:
    now = sa.DateTime(timezone=True)
    op.create_table(
        "nbcm_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("as_of", sa.String(10), nullable=False, index=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(200)),
        sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL")),
        sa.Column("created_at", now, nullable=False),
    )
    op.create_table(
        "nbcm_visits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("visited_at", now, nullable=False, index=True),
        sa.Column("outcome", sa.String(10), nullable=False, index=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("receipt_no", sa.String(40)),
        sa.Column("notes", sa.Text()),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id"), nullable=False, index=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="SET NULL"), index=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL")),
        sa.Column("created_at", now, nullable=False),
        sa.Column("updated_at", now, nullable=False),
        sa.CheckConstraint("outcome IN ('collected', 'promised', 'not_in', 'updated', 'other')", name="visit_outcome"),
        sa.CheckConstraint("amount_centavos >= 0", name="visit_amount"),
    )
    op.create_table(
        "nbcm_field_goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("month", sa.String(7), nullable=False, index=True),
        sa.Column("doctors_visited", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("doctors_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_centavos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collection_visits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", now, nullable=False),
        sa.UniqueConstraint("user_id", "month", name="field_goal_once"),
    )

    db = op.get_bind()
    stamp = datetime.now(UTC)
    # Doctor: a customer type like any other, unless an admin already made one.
    taken = db.execute(sa.text("SELECT count(*) FROM nbcm_customer_types WHERE code = 'doctor' OR lower(name) = 'doctor'")).scalar()
    if not taken:
        last = db.execute(sa.text("SELECT coalesce(max(sort_order), -1) FROM nbcm_customer_types")).scalar()
        db.execute(
            sa.text("INSERT INTO nbcm_customer_types (code, name, color, sort_order, is_active) VALUES ('doctor', 'Doctor', 'blue', :n, true)"),
            {"n": last + 1},
        )

    role = lambda name: db.execute(sa.text("SELECT id FROM nbcm_roles WHERE name = :n AND is_system = false"), {"n": name}).scalar()  # noqa: E731
    grant = lambda role_id, permissions: [  # noqa: E731
        db.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, :p)"), {"id": role_id, "p": p})
        for p in sorted(permissions - set(db.execute(sa.text("SELECT permission FROM nbcm_role_permissions WHERE role_id = :id"), {"id": role_id}).scalars()))
    ]
    if not role("Field agent"):
        agent = str(uuid.uuid4())
        db.execute(
            sa.text("INSERT INTO nbcm_roles (id, name, description, scope, is_system, created_at) VALUES (:id, 'Field agent', :d, 'own', false, :at)"),
            {"id": agent, "d": "Visits their own doctors and collects what they owe; sees their own goals.", "at": stamp},
        )
        grant(agent, FIELD_AGENT)
    lead = role("Team Lead")
    if lead:
        grant(lead, TEAM_LEAD_ADDS)


def downgrade() -> None:
    op.drop_table("nbcm_field_goals")
    op.drop_table("nbcm_visits")
    op.drop_table("nbcm_balances")
