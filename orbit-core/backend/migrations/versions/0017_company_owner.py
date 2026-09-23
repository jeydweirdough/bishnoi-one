"""whoever owns the company

A System Admin runs a company day to day: its people, roles, teams and lists.
Deciding what the company *is* — its name, how its money reads, its data coming
in and going out — belongs to whoever set it up. That person is its owner, and
until now there was nowhere to say so.

Every company that already exists gets one: the longest-standing person in it
who can manage settings, which is the person who has been running it.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()))

    bind = op.get_bind()
    # Whoever can manage settings, earliest first: their assignment names a role
    # that holds the "manage" action on the settings row, however the company has
    # since renamed that role.
    admins = bind.execute(
        sa.text(
            """
            SELECT m.org_id, m.user_id, m.created_at
            FROM memberships m
            JOIN assignments a ON a.org_id = m.org_id AND a.user_id = m.user_id AND a.division_code IS NULL
            JOIN role_permissions p ON p.org_id = m.org_id AND p.role_key = a.role_key
            WHERE m.status = 'active' AND p.module_key = 'settings' AND p.action = 'manage'
            ORDER BY m.created_at
            """
        )
    ).fetchall()

    first: dict[str, str] = {}
    for org_id, user_id, _ in admins:
        first.setdefault(org_id, user_id)

    # A company with nobody like that still gets an owner: its oldest member,
    # rather than being left with no one who can change it.
    for org_id, user_id in bind.execute(
        sa.text("SELECT org_id, user_id FROM memberships WHERE status = 'active' ORDER BY created_at")
    ):
        first.setdefault(org_id, user_id)

    for org_id, user_id in first.items():
        bind.execute(
            sa.text("UPDATE memberships SET is_owner = 1 WHERE org_id = :org AND user_id = :user"),
            {"org": org_id, "user": user_id},
        )


def downgrade() -> None:
    op.drop_column("memberships", "is_owner")
