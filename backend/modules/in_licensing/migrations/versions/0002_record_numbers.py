"""Each of this app's main records gets a number of its own, from 40000001
up, for paging and lookups (where no >= 40000001), beside its id, which stays
the key every link uses. Existing records are numbered in the order they were
made. On Postgres each table counts with a sequence; SQLite (this computer,
the tests) has none, so the app gives the next (app/numbering.py).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

FIRST = 40000001
TABLES = ('nbil_users',)


def upgrade() -> None:
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    inspect = sa.inspect(bind)
    for table in TABLES:
        columns = {c["name"] for c in inspect.get_columns(table)}
        if "no" not in columns:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("no", sa.Integer(), nullable=True))
        # The ones made so far, in the order they were made.
        order = "created_at, id" if "created_at" in columns else "id"
        ids = [row[0] for row in bind.execute(sa.text(f"select id from {table} where no is null order by {order}"))]
        start = (bind.execute(sa.text(f"select max(no) from {table}")).scalar() or FIRST - 1) + 1
        for n, record_id in enumerate(ids):
            bind.execute(sa.text(f"update {table} set no = :no where id = :id"), {"no": start + n, "id": record_id})
        if postgres:
            seq = f"{table}_no_seq"
            last = bind.execute(sa.text(f"select max(no) from {table}")).scalar()
            bind.execute(sa.text(f"create sequence if not exists {seq} start with {FIRST}"))
            if last:
                bind.execute(sa.text(f"select setval('{seq}', {last})"))
            bind.execute(sa.text(f"alter table {table} alter column no set default nextval('{seq}')"))
            bind.execute(sa.text(f"alter sequence {seq} owned by {table}.no"))
        if f"{table}_no" not in {i["name"] for i in inspect.get_indexes(table)}:
            op.create_index(f"{table}_no", table, ["no"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        op.drop_index(f"{table}_no", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("no")
        if bind.dialect.name == "postgresql":
            bind.execute(sa.text(f"drop sequence if exists {table}_no_seq"))
