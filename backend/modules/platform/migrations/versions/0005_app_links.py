"""The platform as the apps' switchboard: where each application's API is,
the key it connects to the platform with, and the links between applications
(the CRM uses Inventory...), each with the key one gives the other.

An application keeps only the platform's address and public key, and its own
connect key; everything else it asks the platform for (app/links.py).

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_applications")}
    with op.batch_alter_table("nbpl_applications") as batch:
        if "api_url" not in have:
            batch.add_column(sa.Column("api_url", sa.String(500), nullable=True))
        if "connect_key_hash" not in have:
            batch.add_column(sa.Column("connect_key_hash", sa.String(64), nullable=True))
            batch.add_column(sa.Column("connect_key_hint", sa.String(12), nullable=True))
            batch.add_column(sa.Column("connect_key_made_at", sa.DateTime(timezone=True), nullable=True))
            batch.add_column(sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True))
    # An application's API is where its health address is, without /health.
    apps = sa.table("nbpl_applications", sa.column("id", sa.String), sa.column("health_url", sa.String), sa.column("api_url", sa.String))
    bind = op.get_bind()
    for row in bind.execute(sa.select(apps.c.id, apps.c.health_url).where(apps.c.api_url.is_(None), apps.c.health_url.like("%/health"))):
        bind.execute(apps.update().where(apps.c.id == row.id).values(api_url=row.health_url.removesuffix("/health")))
    op.create_table(
        "nbpl_app_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("from_app_id", sa.String(36), sa.ForeignKey("nbpl_applications.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("to_app_id", sa.String(36), sa.ForeignKey("nbpl_applications.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("is_on", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("made_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("from_app_id", "to_app_id", name="nbpl_app_link_once"),
    )


def downgrade() -> None:
    op.drop_table("nbpl_app_links")
    with op.batch_alter_table("nbpl_applications") as batch:
        for name in ("connected_at", "connect_key_made_at", "connect_key_hint", "connect_key_hash", "api_url"):
            batch.drop_column(name)
