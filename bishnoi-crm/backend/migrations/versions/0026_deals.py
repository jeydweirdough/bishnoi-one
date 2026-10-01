"""Deals (benchmarks decision D2): business expected from a customer, with a
stage, a value, a close date and a forecast category.

- nbcm_deal_stages: the steps, an administrator's to keep; starts with four
  open ones and the two closed ones (won, lost).
- nbcm_deals: each deal.
- nbcm_quotes.deal_id: the deal a quote was made for.
- nbcm_sales_settings.deal_lists: lead sources and lost reasons.
- deals.* for Team Lead (all four) and Salesperson (view, create, edit), where
  they don't hold them already (0002 and 0008 gave them, unused till now).

Each step only if it isn't done yet, like 0015.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

# Written out here (not imported) so later changes to app/permissions.py never
# rewrite what this did.
GRANTS = {
    "Team Lead": {"deals.view", "deals.create", "deals.edit", "deals.delete"},
    "Salesperson": {"deals.view", "deals.create", "deals.edit"},
}
STAGES = (
    # code, name, outcome, probability, forecast category
    ("qualify", "Qualify", "open", 10, "pipeline"),
    ("needs", "Needs analysis", "open", 25, "pipeline"),
    ("proposal", "Proposal", "open", 50, "best_case"),
    ("negotiation", "Negotiation", "open", 75, "commit"),
    ("won", "Won", "won", 100, "closed"),
    ("lost", "Lost", "lost", 0, "omitted"),
)


def upgrade() -> None:
    db = op.get_bind()
    inspector = sa.inspect(db)
    tables = set(inspector.get_table_names())
    now = sa.DateTime(timezone=True)
    if "nbcm_deal_stages" not in tables:
        stages = op.create_table(
            "nbcm_deal_stages",
            sa.Column("code", sa.String(40), primary_key=True),
            sa.Column("name", sa.String(60), nullable=False, unique=True),
            sa.Column("outcome", sa.String(8), nullable=False),
            sa.Column("probability", sa.Integer(), nullable=False),
            sa.Column("forecast_category", sa.String(12), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.CheckConstraint("outcome IN ('open', 'won', 'lost')", name="deal_stage_outcome"),
            sa.CheckConstraint("forecast_category IN ('pipeline', 'best_case', 'commit', 'closed', 'omitted')", name="deal_stage_forecast"),
            sa.CheckConstraint("probability >= 0 AND probability <= 100", name="deal_stage_probability"),
        )
        op.bulk_insert(stages, [
            {"code": c, "name": n, "outcome": o, "probability": p, "forecast_category": f, "sort_order": i, "is_active": True}
            for i, (c, n, o, p, f) in enumerate(STAGES)
        ])
    if "nbcm_deals" not in tables:
        op.create_table(
            "nbcm_deals",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbcm_companies.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("contact_id", sa.String(36), sa.ForeignKey("nbcm_contacts.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("stage_code", sa.String(40), sa.ForeignKey("nbcm_deal_stages.code"), nullable=False, index=True),
            sa.Column("probability", sa.Integer(), nullable=False),
            sa.Column("forecast_category", sa.String(12), nullable=False, index=True),
            sa.Column("value_centavos", sa.Integer(), nullable=False),
            sa.Column("expected_close_on", sa.String(10), nullable=False, index=True),
            sa.Column("lead_source", sa.String(60), nullable=True),
            sa.Column("price_type", sa.String(40), nullable=True),
            sa.Column("lines", sa.JSON(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("closed_at", now, nullable=True, index=True),
            sa.Column("lost_reason", sa.String(80), nullable=True),
            sa.Column("competitor", sa.String(120), nullable=True),
            sa.Column("won_quote_id", sa.String(36), nullable=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbcm_users.id"), nullable=False, index=True),
            sa.Column("team_id", sa.String(36), sa.ForeignKey("nbcm_teams.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", now, nullable=False),
            sa.Column("updated_at", now, nullable=False),
            sa.CheckConstraint("forecast_category IN ('pipeline', 'best_case', 'commit', 'closed', 'omitted')", name="deal_forecast"),
            sa.CheckConstraint("probability >= 0 AND probability <= 100", name="deal_probability"),
        )
    quote_columns = {c["name"] for c in inspector.get_columns("nbcm_quotes")}
    if "deal_id" not in quote_columns:
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("deal_id", sa.String(36), nullable=True))
            batch.create_foreign_key("fk_nbcm_quotes_deal_id", "nbcm_deals", ["deal_id"], ["id"], ondelete="SET NULL")
            batch.create_index("ix_nbcm_quotes_deal_id", ["deal_id"])
    settings_columns = {c["name"] for c in inspector.get_columns("nbcm_sales_settings")}
    if "deal_lists" not in settings_columns:
        op.add_column("nbcm_sales_settings", sa.Column("deal_lists", sa.JSON(), nullable=True))

    role = lambda name: db.execute(sa.text("SELECT id FROM nbcm_roles WHERE name = :n AND is_system = false"), {"n": name}).scalar()  # noqa: E731
    for name, permissions in GRANTS.items():
        role_id = role(name)
        if not role_id:
            continue
        have = set(db.execute(sa.text("SELECT permission FROM nbcm_role_permissions WHERE role_id = :id"), {"id": role_id}).scalars())
        for p in sorted(permissions - have):
            db.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, :p)"), {"id": role_id, "p": p})


def downgrade() -> None:
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        batch.drop_column("deal_lists")
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_index("ix_nbcm_quotes_deal_id")
        batch.drop_constraint("fk_nbcm_quotes_deal_id", type_="foreignkey")
        batch.drop_column("deal_id")
    op.drop_table("nbcm_deals")
    op.drop_table("nbcm_deal_stages")
