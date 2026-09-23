"""two tiers at the top: Admin, and Developer Admin above every company

"System Admin" was Orbit's name for the role that runs one company. The company
calls that tier Admin, so the role is renamed -- the key never changes, so every
assignment, grant and audit line still points at the same thing.

Developer Admin stops being a company role. It was one for a day and that was
wrong: a company's Admin edits the permission matrix, so a role is something
they can give themselves, and a company promoting its own staff to reach every
*other* company would make the wall decoration. It is membership of
`platform_admins` now, set from outside any company (`python -m app.platform`).

What a Developer Admin holds inside a company is unchanged -- `settings:recover`
-- and a company may still grant that locally to someone technical of its own.
Anyone who was given the old role keeps nothing: the role goes, and whoever
should have the tier is granted it on the platform instead.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

OLD_NAME = "System Admin"
NEW_NAME = "Admin"
GONE = "developer_admin"


def upgrade() -> None:
    bind = op.get_bind()

    # Renamed only where it still says what Orbit called it. A company that has
    # already named the role something of its own keeps that name.
    bind.execute(
        sa.text("UPDATE roles SET name = :new WHERE key = 'admin' AND name = :old"),
        {"new": NEW_NAME, "old": OLD_NAME},
    )

    # The role goes, and its assignments with it. Nobody is left holding a role
    # that no longer exists; whoever needs the tier is granted it on the
    # platform, which is not a company's to give.
    bind.execute(sa.text("DELETE FROM assignments WHERE role_key = :key"), {"key": GONE})
    bind.execute(sa.text("DELETE FROM role_permissions WHERE role_key = :key"), {"key": GONE})
    bind.execute(sa.text("DELETE FROM roles WHERE key = :key"), {"key": GONE})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE roles SET name = :old WHERE key = 'admin' AND name = :new"),
        {"new": NEW_NAME, "old": OLD_NAME},
    )
    # The role is not put back: whoever holds the tier now holds it on the
    # platform, and re-creating an empty role would say otherwise.
