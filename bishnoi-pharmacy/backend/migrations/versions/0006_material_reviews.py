"""Promotional material reviews: designs Admin sends for the pharmacist's
approval before they're produced (nbph_material_reviews, the file kept with
each). The Pharmacist may review them; the Pharmacy Assistant sees them. A role
an administrator has changed keeps its changes; only what's new is added.
(Administrator holds everything already.)

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

GRANTS = {"Pharmacist": ("materials.view", "materials.review"), "Pharmacy Assistant": ("materials.view",)}


def upgrade() -> None:
    bind = op.get_bind()
    if "nbph_material_reviews" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbph_material_reviews",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("source_id", sa.String(64), nullable=False),
            sa.Column("reference", sa.String(40), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("product", sa.String(160), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("file_name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("file_data", sa.LargeBinary(), nullable=False),
            sa.Column("sent_by", sa.String(120), nullable=False),
            sa.Column("status", sa.String(10), nullable=False, server_default="waiting", index=True),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("reviewed_by_id", sa.String(36), sa.ForeignKey("nbph_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('waiting', 'approved', 'returned', 'rejected')", name="material_review_status"),
            sa.UniqueConstraint("source", "source_id", name="uq_nbph_material_reviews_source"),
        )

    grants = sa.table("nbph_role_permissions", sa.column("role_id"), sa.column("permission"))
    for name, permissions in GRANTS.items():
        role_id = bind.execute(sa.text("SELECT id FROM nbph_roles WHERE name = :n"), {"n": name}).scalar()
        if role_id is None:
            continue
        held = set(bind.execute(sa.text("SELECT permission FROM nbph_role_permissions WHERE role_id = :r"), {"r": role_id}).scalars().all())
        new = [p for p in permissions if p not in held]
        if new:
            op.bulk_insert(grants, [{"role_id": role_id, "permission": p} for p in new])


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM nbph_role_permissions WHERE permission LIKE 'materials.%'"))
    op.drop_table("nbph_material_reviews")
