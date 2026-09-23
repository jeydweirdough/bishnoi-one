"""a job title, kept apart from what it may do

A department names the jobs inside it -- Pharmacist, Procurement Officer, Sales
Representative -- and a person holds one. That is the org chart's word for them.

What they may do is a role, and roles already exist. These two are kept in
separate tables with no link between them on purpose: the same title carries
different authority in two companies, and reading permission off a job title is
how renaming somebody's job quietly becomes a privilege change. Nothing in
app/access.py reads this table.

`positions.division_code` is the department that named it; null is the company's
own. `memberships.position_id` is the one a person holds, and is nullable
because a company may never use positions at all.

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("division_code", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id", "division_code"], ["divisions.org_id", "divisions.code"], name="position_division"
        ),
    )

    # Nullable, and no foreign key: `memberships` is pointed at by `assignments`,
    # and SQLite adds a constraint to an existing table only by rebuilding it,
    # which it will not do while anything references it. The position is checked
    # where it is set, the same way roles.division_code is (see 0027).
    op.add_column("memberships", sa.Column("position_id", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("memberships", "position_id")
    op.drop_table("positions")
