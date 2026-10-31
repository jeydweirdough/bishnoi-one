"""Sign-in security (2026-10-30): what a person needs to get in safely on their own.

- Accounts: `must_change_password` (a password someone else handed over is changed at the first
  sign-in), and two-step sign-in with an authenticator app: `two_step_secret` (sealed), when it was
  turned on, and the one-time recovery codes (hashed).
- nbpl_sign_in_links: one-time links by email: "reset" (forgot password), "invite" (a new person
  sets their own password), "two_step" (a sign-in waiting for its code). Only the token's hash is kept.
- nbpl_sign_in_failures: wrong passwords by email, kept in the database so a restart doesn't forget
  them and every copy of the API counts the same ones.

Added in place; nothing existing changes.

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbpl_accounts")}
    if "must_change_password" not in have:
        op.add_column("nbpl_accounts", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "two_step_secret" not in have:
        op.add_column("nbpl_accounts", sa.Column("two_step_secret", sa.Text(), nullable=True))
    if "two_step_on_at" not in have:
        op.add_column("nbpl_accounts", sa.Column("two_step_on_at", sa.DateTime(timezone=True), nullable=True))
    if "recovery_codes" not in have:
        op.add_column("nbpl_accounts", sa.Column("recovery_codes", sa.JSON(), nullable=True))
    tables = set(sa.inspect(bind).get_table_names())
    if "nbpl_sign_in_links" not in tables:
        op.create_table(
            "nbpl_sign_in_links",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("account_id", sa.String(36), sa.ForeignKey("nbpl_accounts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(12), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("made_by", sa.String(254), nullable=True),
            sa.Column("identity_id", sa.String(36), nullable=True),
            sa.CheckConstraint("kind IN ('reset', 'invite', 'two_step')", name="nbpl_sign_in_link_kind"),
        )
        op.create_index("nbpl_sign_in_links_token", "nbpl_sign_in_links", ["token_hash"], unique=True)
        op.create_index("nbpl_sign_in_links_account", "nbpl_sign_in_links", ["account_id"])
    if "nbpl_sign_in_failures" not in tables:
        op.create_table(
            "nbpl_sign_in_failures",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("address", sa.String(64), nullable=True),
        )
        op.create_index("nbpl_sign_in_failures_email", "nbpl_sign_in_failures", ["email", "at"])


def downgrade() -> None:
    op.drop_table("nbpl_sign_in_failures")
    op.drop_table("nbpl_sign_in_links")
    with op.batch_alter_table("nbpl_accounts") as batch:
        for name in ("recovery_codes", "two_step_on_at", "two_step_secret", "must_change_password"):
            batch.drop_column(name)
