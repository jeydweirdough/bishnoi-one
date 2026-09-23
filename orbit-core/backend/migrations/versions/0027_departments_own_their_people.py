"""a department runs its own people, positions and places

Three tiers sit under the company, and until now the tables only really held
two of them. An admin runs one department: its teams, the locations under them,
the positions it names, and everyone in it. A team leader runs one or more of
its teams. An employee sits somewhere exact.

"Somewhere exact" is what was missing. An assignment reached a team and stopped,
so a person at CEBU and a person at DAVAO on the same team were the same record.
Headquarters has been in the schema since 0023; this lets an assignment name one.

And a position is a department's, not the company's. `roles.division_code` is
what makes it so: null is company-wide, as every role was before this, and set
means only that department's admins may name it or grant it.

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Where a person actually sits. Nullable because most teams have no
    # headquarters at all, and those people stop at the team above.
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("headquarters_code", sa.String(40), nullable=True))
        batch.create_check_constraint(
            "headquarters_needs_subdivision",
            "headquarters_code IS NULL OR subdivision_code IS NOT NULL",
        )
        batch.create_foreign_key(
            "assignment_headquarters",
            "headquarters",
            ["org_id", "division_code", "subdivision_code", "headquarters_code"],
            ["org_id", "division_code", "subdivision_code", "code"],
        )

    # Whose position it is. Every role that exists today is the company's, so
    # they all start null and nothing changes for them.
    #
    # Added in place rather than through a batch, and without a foreign key:
    # `roles` is pointed at by `assignments` and `role_permissions`, and a batch
    # rebuilds a table by dropping it, which SQLite refuses while anything still
    # references it. A nullable column it can add outright. The division a
    # position belongs to is checked where the position is named instead, so
    # every database describes the same schema (see app/models.py: Role).
    op.add_column("roles", sa.Column("division_code", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("roles", "division_code")

    with op.batch_alter_table("assignments") as batch:
        batch.drop_constraint("assignment_headquarters", type_="foreignkey")
        batch.drop_constraint("headquarters_needs_subdivision", type_="check")
        batch.drop_column("headquarters_code")
