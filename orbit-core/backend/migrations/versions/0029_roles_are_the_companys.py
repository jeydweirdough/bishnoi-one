"""a role is the company's; a position is the department's

0027 gave `roles` a `division_code`, for a role a department would own. 0028
then built `positions`, and that is where a department's own naming belongs: a
title it invents, held by its people, granting nothing.

What is left for a role is what a role was always for -- what somebody may do --
and that is the company's, scoped by the assignment rather than by the role
itself. "Team Leader in B2B" is a role plus a scope, never a role called
"B2B Team Leader". So the column has no reader and no writer, and a field in
the authorization schema that nothing consults is worse than no field: it reads
like a rule somebody forgot to enforce.

Dropped rather than left. Nothing in app/ or tests/ referenced it, and no row
ever carried a value -- it was added nullable in 0027 and never written.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite has dropped columns natively since 3.35, and `roles` carries no
    # constraint mentioning this one (0027 deliberately added none), so it goes
    # without the rebuild that `assignments` and `role_permissions` would block.
    op.drop_column("roles", "division_code")


def downgrade() -> None:
    # Comes back as it was: nullable, no foreign key, no data.
    op.add_column("roles", sa.Column("division_code", sa.String(32), nullable=True))
