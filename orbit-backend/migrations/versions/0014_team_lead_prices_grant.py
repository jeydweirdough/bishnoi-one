"""team leads may set their team's prices

The "prices" action is new, so no role has it yet. The roles that exist to run
a team get it, in the modules they already work: a Team Lead for their own
teams, a Division Head for their division's. Any company that has since renamed
or rewritten those roles is left alone — its admins decide.

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

LEADS = ("team_lead", "division_head")


def upgrade() -> None:
    bind = op.get_bind()
    # Wherever one of those roles can already edit, it can now price too.
    rows = bind.execute(
        sa.text(
            "SELECT DISTINCT org_id, role_key, module_key FROM role_permissions "
            "WHERE role_key IN :leads AND action = 'edit'"
        ).bindparams(sa.bindparam("leads", expanding=True)),
        {"leads": list(LEADS)},
    ).fetchall()
    have = {
        (org, role, module)
        for org, role, module in bind.execute(
            sa.text("SELECT org_id, role_key, module_key FROM role_permissions WHERE action = 'prices'")
        )
    }
    new = [
        {"org_id": org, "role_key": role, "module_key": module, "action": "prices"}
        for org, role, module in rows
        if (org, role, module) not in have
    ]
    if new:
        op.bulk_insert(
            sa.table(
                "role_permissions",
                sa.column("org_id", sa.String),
                sa.column("role_key", sa.String),
                sa.column("module_key", sa.String),
                sa.column("action", sa.String),
            ),
            new,
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM role_permissions WHERE action = 'prices'"))
