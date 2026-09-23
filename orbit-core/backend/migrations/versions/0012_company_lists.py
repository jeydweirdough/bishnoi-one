"""every pick-list a company can change

`order_list_items` becomes `list_items`: the same shape already served the
order pick-lists, and customer kinds, activity kinds and call outcomes are the
same thing — choices that belong to a company, not to Orbit. Those three were
fixed lists in app/schemas.py until now.

The values inserted here are exactly the ones that were in code, with the codes
they had, so every record written before today still matches a choice.

SQLite carries a table's CHECK constraint through a rename, and the old one
only allowed the five order kinds, so the table has to be rebuilt for the new
kinds to be insertable. Nothing holds a foreign key to it, which is what makes
that safe. Each step checks the state it finds first, so this can be run again
over a half-applied attempt.

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

ORDER_KINDS = ("payment_method", "payment_term", "source", "delivery_method", "invoicing_entity")
RECORD_KINDS = ("customer_kind", "activity_kind", "outcome")
ALL_KINDS = (*ORDER_KINDS, *RECORD_KINDS)

# (kind, code, name, icon) — the lists as app/schemas.py held them until now.
SEED: tuple[tuple[str, str, str, str | None], ...] = (
    ("customer_kind", "doctor", "Doctor", None),
    ("customer_kind", "hospital", "Hospital", None),
    ("customer_kind", "clinic", "Clinic", None),
    ("customer_kind", "pharmacy", "Pharmacy", None),
    ("customer_kind", "patient", "Patient", None),
    ("customer_kind", "company", "Company", None),
    ("customer_kind", "distributor", "Distributor", None),
    ("customer_kind", "other", "Other", None),
    ("activity_kind", "call", "Call", "call"),
    ("activity_kind", "visit", "Visit", "visit"),
    ("activity_kind", "message", "Message", "message"),
    ("activity_kind", "note", "Note", "note"),
    ("outcome", "reached", "Reached", None),
    ("outcome", "no_answer", "No answer", None),
    ("outcome", "call_back", "Call back", None),
    ("outcome", "not_interested", "Not interested", None),
)


def check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def shape(kinds: tuple[str, ...], name: str) -> sa.Table:
    """The table as it should be, for SQLite's rebuild to copy into."""
    return sa.Table(
        "list_items",
        sa.MetaData(),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True, nullable=False),
        sa.Column("kind", sa.String(24), primary_key=True, nullable=False),
        sa.Column("code", sa.String(60), primary_key=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("icon", sa.String(40)),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.CheckConstraint(check(kinds), name=name),
    )


def rows_table() -> sa.Table:
    return sa.table(
        "list_items",
        sa.column("org_id", sa.String),
        sa.column("kind", sa.String),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("icon", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "list_items" not in tables:
        op.rename_table("order_list_items", "list_items")
    # A fresh look: the inspector above still remembers the name it had.
    if "icon" not in {c["name"] for c in sa.inspect(bind).get_columns("list_items")}:
        op.add_column("list_items", sa.Column("icon", sa.String(length=40), nullable=True))

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("list_items", copy_from=shape(ALL_KINDS, "list_kind"), recreate="always"):
            pass
    else:
        op.drop_constraint("order_list_kind", "list_items", type_="check")
        op.create_check_constraint("list_kind", "list_items", check(ALL_KINDS))

    table = rows_table()
    done = {(org, kind) for org, kind in bind.execute(sa.text("SELECT DISTINCT org_id, kind FROM list_items"))}
    rows = [
        {"org_id": org_id, "kind": kind, "code": code, "name": name, "icon": icon, "is_active": True, "sort_order": order}
        for org_id, in bind.execute(sa.text("SELECT id FROM organizations"))
        for order, (kind, code, name, icon) in enumerate(SEED)
        if (org_id, kind) not in done
    ]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(sa.text("DELETE FROM list_items WHERE kind IN " + str(RECORD_KINDS)))
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("list_items", copy_from=shape(ORDER_KINDS, "order_list_kind"), recreate="always"):
            pass
        op.drop_column("list_items", "icon")
    else:
        op.drop_constraint("list_kind", "list_items", type_="check")
        op.create_check_constraint("order_list_kind", "list_items", check(ORDER_KINDS))
        op.drop_column("list_items", "icon")
    op.rename_table("list_items", "order_list_items")
