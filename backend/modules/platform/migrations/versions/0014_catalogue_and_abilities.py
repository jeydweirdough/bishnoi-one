"""The app catalogue's switches and job roles' abilities (feature plan step 6, 2026-10-28).

- nbpl_company_switches: a company's choices in the app catalogue ("app:purchasing", "inventory.batches"),
  on or off; anything not chosen is as the catalogue says (app/abilities.py).
- nbpl_access_role_abilities: the abilities a role has, each with its limit where it takes one; the
  role's permissions in each app follow from them. A role made before keeps its permissions as they
  are until abilities are given to it.
- nbpl_access_roles.job_role: the ready-made job role it was copied from, if any.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "nbpl_company_switches" not in tables:
        op.create_table(
            "nbpl_company_switches",
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("key", sa.String(80), primary_key=True),
            sa.Column("is_on", sa.Boolean(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_by", sa.String(254), nullable=False),
        )
    if "nbpl_access_role_abilities" not in tables:
        op.create_table(
            "nbpl_access_role_abilities",
            sa.Column("role_id", sa.String(36), sa.ForeignKey("nbpl_access_roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("ability", sa.String(60), primary_key=True),
            sa.Column("limit_value", sa.BigInteger()),
        )
    if "job_role" not in {c["name"] for c in sa.inspect(bind).get_columns("nbpl_access_roles")}:
        op.add_column("nbpl_access_roles", sa.Column("job_role", sa.String(40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_access_roles") as batch:
        batch.drop_column("job_role")
    op.drop_table("nbpl_access_role_abilities")
    op.drop_table("nbpl_company_switches")
