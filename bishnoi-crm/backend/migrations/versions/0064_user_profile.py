"""A person's own profile: their name in parts, gender, contact number and birthday.

They edit these on their profile (PUT /auth/profile). The name in parts makes
full_name, which everything else still reads; until someone edits theirs, the
parts are read off full_name (the last word the last name, the rest the first).

Revision ID: 0064
Revises: 0063
"""

from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

COLUMNS = (
    ("first_name", sa.String(60)),
    ("middle_initial", sa.String(4)),
    ("last_name", sa.String(60)),
    ("suffix", sa.String(10)),
    ("gender", sa.String(8)),
    ("phone", sa.String(20)),
    ("birthday", sa.Date()),
)


def upgrade() -> None:
    with op.batch_alter_table("nbcm_users") as batch:
        for name, kind in COLUMNS:
            batch.add_column(sa.Column(name, kind, nullable=True))
    users = sa.table("nbcm_users", sa.column("id", sa.String), sa.column("full_name", sa.String), sa.column("first_name", sa.String), sa.column("last_name", sa.String))
    connection = op.get_bind()
    for id_, full in connection.execute(sa.select(users.c.id, users.c.full_name)).all():
        words = (full or "").split()
        first, last = (" ".join(words[:-1]), words[-1]) if len(words) > 1 else ((words[0] if words else ""), "")
        connection.execute(users.update().where(users.c.id == id_).values(first_name=first[:60] or None, last_name=last[:60] or None))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_users") as batch:
        for name, _ in reversed(COLUMNS):
            batch.drop_column(name)
