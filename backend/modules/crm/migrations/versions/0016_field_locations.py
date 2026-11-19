"""Field locations: where visits were logged, clinics' pins, and agents' trails.

- nbcm_companies: latitude, longitude, pinned_at, pinned_by_id (a clinic's pin).
- nbcm_visits: latitude, longitude, accuracy_m, distance_m (where the phone
  was when the visit was logged, and how far from the clinic's pin).
- nbcm_trail_batches: an agent's points, packed, one row per upload.
- nbcm_route_days: each person's day on the road, summed up.

Like 0015, each step only if it isn't done yet, for a database whose recorded
revision fell behind its tables.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    present = set(inspector.get_table_names())
    columns = lambda table: {c["name"] for c in inspector.get_columns(table)}  # noqa: E731
    now = sa.DateTime(timezone=True)

    have = columns("nbcm_companies")
    with op.batch_alter_table("nbcm_companies") as batch:
        for name, kind in (("latitude", sa.Float()), ("longitude", sa.Float()), ("pinned_at", now)):
            if name not in have:
                batch.add_column(sa.Column(name, kind))
        if "pinned_by_id" not in have:
            batch.add_column(sa.Column("pinned_by_id", sa.String(36)))
            batch.create_foreign_key("fk_company_pinned_by", "nbcm_users", ["pinned_by_id"], ["id"], ondelete="SET NULL")

    have = columns("nbcm_visits")
    with op.batch_alter_table("nbcm_visits") as batch:
        for name, kind in (("latitude", sa.Float()), ("longitude", sa.Float()), ("accuracy_m", sa.Integer()), ("distance_m", sa.Integer())):
            if name not in have:
                batch.add_column(sa.Column(name, kind))

    if "nbcm_trail_batches" not in present:
        op.create_table(
            "nbcm_trail_batches",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("day", sa.String(10), nullable=False, index=True),
            sa.Column("started_at", now, nullable=False, index=True),
            sa.Column("ended_at", now, nullable=False),
            sa.Column("count", sa.Integer(), nullable=False),
            sa.Column("points", sa.Text(), nullable=False),
            sa.Column("min_lat", sa.Float(), nullable=False),
            sa.Column("max_lat", sa.Float(), nullable=False),
            sa.Column("min_lng", sa.Float(), nullable=False),
            sa.Column("max_lng", sa.Float(), nullable=False),
            sa.Column("created_at", now, nullable=False),
        )
    if "nbcm_route_days" not in present:
        op.create_table(
            "nbcm_route_days",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("day", sa.String(10), nullable=False, index=True),
            sa.Column("distance_m", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("first_at", now, nullable=False),
            sa.Column("last_at", now, nullable=False),
            sa.Column("last_lat", sa.Float(), nullable=False),
            sa.Column("last_lng", sa.Float(), nullable=False),
            sa.UniqueConstraint("user_id", "day", name="route_day_once"),
        )


def downgrade() -> None:
    op.drop_table("nbcm_route_days")
    op.drop_table("nbcm_trail_batches")
    with op.batch_alter_table("nbcm_visits") as batch:
        for name in ("distance_m", "accuracy_m", "longitude", "latitude"):
            batch.drop_column(name)
    with op.batch_alter_table("nbcm_companies") as batch:
        batch.drop_constraint("fk_company_pinned_by", type_="foreignkey")
        for name in ("pinned_by_id", "pinned_at", "longitude", "latitude"):
            batch.drop_column(name)
