"""which part of the form a field sits in

The old Orders app groups its order form into four parts — Order Details,
Billing & Payment, Logistics & Delivery, Additional Information — and puts each
extra field in one of them. Orbit's fields had a label, a type and an order but
nothing that said where on the form they belong, so a rebuilt order form would
have put every one of them in a single heap.

The sections are a company's own list, like every other pick-list, rather than
four words in the code: a company that calls it "Delivery" can say so.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

ORDER_KINDS = ("payment_method", "payment_term", "source", "delivery_method", "invoicing_entity", "field_section")
RECORD_KINDS = ("customer_kind", "activity_kind", "outcome")
ALL_KINDS = (*ORDER_KINDS, *RECORD_KINDS)

# name -> code, in the order a form shows them. Per template, because a company
# that doesn't sell medicine words its form differently.
SECTIONS = {
    "pharma_ph": ["Order Details", "Billing & Payment", "Logistics & Delivery", "Additional Information"],
    "generic_b2b": ["Details", "Payment", "Delivery", "Anything else"],
}


def check(kinds: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{k}'" for k in kinds) + ")"


def shape(kinds: tuple[str, ...], name: str) -> sa.Table:
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


def slug(name: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in name]
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:60]


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("custom_fields", sa.Column("section", sa.String(length=60), nullable=True))

    # `field_section` is a new kind, and the CHECK names every kind it allows.
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("list_items", copy_from=shape(ALL_KINDS, "list_kind"), recreate="always"):
            pass
    else:
        op.drop_constraint("list_kind", "list_items", type_="check")
        op.create_check_constraint("list_kind", "list_items", check(ALL_KINDS))

    rows = []
    have = {org for org, in bind.execute(sa.text("SELECT DISTINCT org_id FROM list_items WHERE kind = 'field_section'"))}
    for org_id, template in bind.execute(sa.text("SELECT id, template FROM organizations")):
        if org_id in have:
            continue
        for order, name in enumerate(SECTIONS.get(template, SECTIONS["generic_b2b"])):
            rows.append(
                {"org_id": org_id, "kind": "field_section", "code": slug(name), "name": name,
                 "icon": None, "is_active": True, "sort_order": order}
            )
    if rows:
        op.bulk_insert(
            sa.table(
                "list_items",
                sa.column("org_id", sa.String), sa.column("kind", sa.String), sa.column("code", sa.String),
                sa.column("name", sa.String), sa.column("icon", sa.String), sa.column("is_active", sa.Boolean),
                sa.column("sort_order", sa.Integer),
            ),
            rows,
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(sa.text("DELETE FROM list_items WHERE kind = 'field_section'"))
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("list_items", copy_from=shape((*ORDER_KINDS[:-1], *RECORD_KINDS), "list_kind"), recreate="always"):
            pass
    else:
        op.drop_constraint("list_kind", "list_items", type_="check")
        op.create_check_constraint("list_kind", "list_items", check((*ORDER_KINDS[:-1], *RECORD_KINDS)))
    op.drop_column("custom_fields", "section")
