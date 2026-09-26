"""RBAC, roles, permissions, and audit log.

Revision ID: 0003
Revises: 0002
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.permissions import (
    ADMINISTRATOR,
    ROLE_ADMIN_ID,
    ROLE_EXEC_ASST_ID,
    STARTING_ROLES,
)

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create nbad_roles if not exists
    if "nbad_roles" not in existing_tables:
        op.create_table(
            "nbad_roles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False, unique=True),
            sa.Column("description", sa.String(300), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    # 2. Create nbad_role_permissions if not exists
    if "nbad_role_permissions" not in existing_tables:
        op.create_table(
            "nbad_role_permissions",
            sa.Column("role_id", sa.String(36), sa.ForeignKey("nbad_roles.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("permission", sa.String(64), primary_key=True),
        )

    # 3. Create nbad_audit_log if not exists
    if "nbad_audit_log" not in existing_tables:
        op.create_table(
            "nbad_audit_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("actor_id", sa.String(36), nullable=True),
            sa.Column("actor", sa.String(254), nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("target_type", sa.String(32), nullable=True),
            sa.Column("target_id", sa.String(36), nullable=True),
            sa.Column("target", sa.String(200), nullable=False, server_default=""),
            sa.Column("fields", sa.JSON(), nullable=False),
        )
        op.create_index("ix_nbad_audit_log_at", "nbad_audit_log", ["at"])
        op.create_index("ix_nbad_audit_log_actor_id", "nbad_audit_log", ["actor_id"])
        op.create_index("ix_nbad_audit_log_action", "nbad_audit_log", ["action"])

    # 4. Seed starting roles
    roles_table = sa.table(
        "nbad_roles",
        sa.column("id"),
        sa.column("name"),
        sa.column("description"),
        sa.column("is_system"),
        sa.column("created_at"),
    )
    grants_table = sa.table("nbad_role_permissions", sa.column("role_id"), sa.column("permission"))

    now = datetime.now(UTC)
    existing_role_ids = set(bind.execute(sa.text("SELECT id FROM nbad_roles")).scalars().all())

    for role_id, name, description, permissions in STARTING_ROLES:
        if role_id not in existing_role_ids:
            is_sys = name == ADMINISTRATOR
            op.bulk_insert(
                roles_table,
                [{"id": role_id, "name": name, "description": description, "is_system": is_sys, "created_at": now}],
            )
            if not is_sys:
                op.bulk_insert(
                    grants_table,
                    [{"role_id": role_id, "permission": p} for p in sorted(permissions)],
                )

    # 5. Migrate nbad_users table to reference role_id
    user_columns = {col["name"] for col in inspector.get_columns("nbad_users")}
    if "role_id" not in user_columns:
        # Recreate table cleanly so SQLite check constraints on dropped columns don't fail
        op.create_table(
            "nbad_users_new",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(254), nullable=False, unique=True),
            sa.Column("full_name", sa.String(120), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("role_id", sa.String(36), sa.ForeignKey("nbad_roles.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_nbad_users_role_id", "nbad_users_new", ["role_id"])

        old_rows = bind.execute(sa.text("SELECT * FROM nbad_users")).mappings().all()
        if old_rows:
            new_users = sa.table(
                "nbad_users_new",
                *(sa.column(c) for c in ("id", "email", "full_name", "password_hash", "role_id", "is_active", "created_at", "password_changed_at"))
            )
            op.bulk_insert(
                new_users,
                [
                    {
                        "id": r["id"],
                        "email": r["email"],
                        "full_name": r["full_name"],
                        "password_hash": r["password_hash"],
                        "role_id": ROLE_ADMIN_ID if r.get("role") == "admin" else ROLE_EXEC_ASST_ID,
                        "is_active": r["is_active"],
                        "created_at": r["created_at"],
                        "password_changed_at": r["password_changed_at"],
                    }
                    for r in old_rows
                ],
            )

        # Drop sessions first or drop nbad_users with foreign keys off
        if bind.dialect.name == "sqlite":
            bind.execute(sa.text("PRAGMA foreign_keys = OFF"))
        op.drop_table("nbad_users")
        op.rename_table("nbad_users_new", "nbad_users")
        if bind.dialect.name == "sqlite":
            bind.execute(sa.text("PRAGMA foreign_keys = ON"))




def downgrade() -> None:
    with op.batch_alter_table("nbad_users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(16), nullable=True))
        batch_op.drop_constraint("fk_nbad_users_role_id", type_="foreignkey")
        batch_op.drop_index("ix_nbad_users_role_id")
        batch_op.drop_column("role_id")

    op.drop_table("nbad_audit_log")
    op.drop_table("nbad_role_permissions")
    op.drop_table("nbad_roles")
