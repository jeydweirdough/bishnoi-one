"""KPI management: KPIs an administrator defines, monthly targets for people and
teams, and results entered by hand for KPIs the CRM can't count.

The field goals (doctors visited, doctors updated, amount collected, collection
visits) and the revenue targets become the first five KPIs, with their targets
copied over; their own tables go.

Revision ID: 0031
Revises: 0030
"""

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

# (code, name, measure, unit, who: "field" or "sellers", what it counts)
BUILT_IN = [
    ("revenue_won", "Revenue won", "deals_won_value", "money", "sellers", "The value of the deals they won in the month."),
    ("doctors_visited", "Doctors visited", "doctors_visited", "count", "field", "Different doctors visited in the month."),
    ("doctors_updated", "Doctors updated", "customers_updated", "count", "field", "Different doctors whose details they updated."),
    ("amount_collected", "Amount collected", "collections_amount", "money", "field", "Payments collected on visits."),
    ("collection_visits", "Collection visits", "collection_visits", "count", "field", "Visits where a payment was collected."),
]
FIELD_COLUMNS = {"doctors_visited": "doctors_visited", "doctors_updated": "doctors_updated", "amount_collected": "amount_centavos", "collection_visits": "collection_visits"}


def upgrade() -> None:
    bind = op.get_bind()
    have = set(sa.inspect(bind).get_table_names())
    now = datetime.now(UTC)
    if "nbcm_kpis" not in have:
        op.create_table(
            "nbcm_kpis",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(40), unique=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(300)),
            sa.Column("measure", sa.String(40), nullable=False),
            sa.Column("filters", sa.JSON(), nullable=False),
            sa.Column("unit", sa.String(10), nullable=False),
            sa.Column("better", sa.String(6), nullable=False),
            sa.Column("roles", sa.JSON(), nullable=False),
            sa.Column("green_at", sa.Integer(), nullable=False),
            sa.Column("amber_at", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_table(
            "nbcm_kpi_targets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kpi_id", sa.String(36), sa.ForeignKey("nbcm_kpis.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("month", sa.String(7), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), index=True),
            sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="CASCADE"), index=True),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("kpi_id", "month", "user_id", name="kpi_target_person_once"),
            sa.UniqueConstraint("kpi_id", "month", "team_id", name="kpi_target_team_once"),
            sa.CheckConstraint("(user_id IS NULL) <> (team_id IS NULL)", name="kpi_target_whose"),
        )
        op.create_table(
            "nbcm_kpi_entries",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("kpi_id", sa.String(36), sa.ForeignKey("nbcm_kpis.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("month", sa.String(7), nullable=False, index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("note", sa.String(200)),
            sa.Column("entered_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("kpi_id", "month", "user_id", name="kpi_entry_once"),
        )

    kpis = sa.table(
        "nbcm_kpis", sa.column("id"), sa.column("code"), sa.column("name"), sa.column("description"), sa.column("measure"),
        sa.column("filters", sa.JSON), sa.column("unit"), sa.column("better"), sa.column("roles", sa.JSON), sa.column("green_at"),
        sa.column("amber_at"), sa.column("is_active"), sa.column("sort_order"), sa.column("created_at"),
    )
    targets = sa.table("nbcm_kpi_targets", sa.column("id"), sa.column("kpi_id"), sa.column("month"), sa.column("user_id"), sa.column("team_id"), sa.column("value"), sa.column("updated_at"))

    # Who the built-in KPIs apply to: the Field agent role; the roles that sell.
    field_roles = [r for (r,) in bind.execute(sa.text("SELECT id FROM nbcm_roles WHERE name = 'Field agent'"))]
    seller_roles = [
        r for (r,) in bind.execute(sa.text(
            "SELECT DISTINCT role_id FROM nbcm_role_permissions WHERE permission IN ('deals.create', 'quotes.create')"
            " AND role_id NOT IN (SELECT id FROM nbcm_roles WHERE is_system)"
        ))
    ]
    ids = {}
    for n, (code, name, measure, unit, who, about) in enumerate(BUILT_IN):
        found = bind.execute(sa.select(kpis.c.id).where(kpis.c.code == code)).first()
        if found:
            ids[code] = found.id
            continue
        ids[code] = str(uuid.uuid4())
        bind.execute(kpis.insert().values(
            id=ids[code], code=code, name=name, description=about, measure=measure, filters={}, unit=unit, better="higher",
            roles=field_roles if who == "field" else seller_roles, green_at=100, amber_at=80, is_active=True, sort_order=n, created_at=now,
        ))

    # The targets already set, moved over.
    if "nbcm_field_goals" in have:
        for row in bind.execute(sa.text("SELECT user_id, month, doctors_visited, doctors_updated, amount_centavos, collection_visits FROM nbcm_field_goals")).mappings():
            for code, column in FIELD_COLUMNS.items():
                if row[column]:
                    bind.execute(targets.insert().values(id=str(uuid.uuid4()), kpi_id=ids[code], month=row["month"], user_id=row["user_id"], team_id=None, value=row[column], updated_at=now))
        op.drop_table("nbcm_field_goals")
    if "nbcm_revenue_targets" in have:
        for row in bind.execute(sa.text("SELECT user_id, month, amount_centavos FROM nbcm_revenue_targets")).mappings():
            bind.execute(targets.insert().values(id=str(uuid.uuid4()), kpi_id=ids["revenue_won"], month=row["month"], user_id=row["user_id"], team_id=None, value=row["amount_centavos"], updated_at=now))
        op.drop_table("nbcm_revenue_targets")


def downgrade() -> None:
    op.create_table(
        "nbcm_revenue_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("month", sa.String(7), nullable=False, index=True),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month", name="revenue_target_once"),
    )
    op.create_table(
        "nbcm_field_goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("month", sa.String(7), nullable=False, index=True),
        sa.Column("doctors_visited", sa.Integer(), nullable=False),
        sa.Column("doctors_updated", sa.Integer(), nullable=False),
        sa.Column("amount_centavos", sa.Integer(), nullable=False),
        sa.Column("collection_visits", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month", name="field_goal_once"),
    )
    op.drop_table("nbcm_kpi_entries")
    op.drop_table("nbcm_kpi_targets")
    op.drop_table("nbcm_kpis")
