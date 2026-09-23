"""the pharma product columns become a company's own fields

Generic name, Strength and Form were columns on every product, in every
company, whatever that company sells. They are ordinary product fields now
(app/fields.py), so each product's three values move into `products.details`
under the keys `generic_name`, `strength` and `form`, and a company that had
any of them gets the matching rows in `custom_fields` so its screens keep
asking for them.

A company whose products never had those values gets no fields: it writes its
own in Settings -> Fields.

Nothing is dropped. The three columns stay, kept in step with `details`, until
the web app reads the fields instead; only then do they go.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

# key -> label, in the order the form asked for them.
PHARMA_FIELDS: tuple[tuple[str, str], ...] = (
    ("generic_name", "Generic name"),
    ("strength", "Strength"),
    ("form", "Form"),
)


def products_table() -> sa.Table:
    """Only the columns this migration reads and writes. `details` is typed, so
    SQLAlchemy reads and writes the JSON for whichever database this runs on."""
    return sa.Table(
        "products",
        sa.MetaData(),
        sa.Column("org_id", sa.String(36), primary_key=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generic_name", sa.String(120)),
        sa.Column("strength", sa.String(60)),
        sa.Column("form", sa.String(60)),
        sa.Column("details", sa.JSON),
    )


def fields_table() -> sa.Table:
    return sa.Table(
        "custom_fields",
        sa.MetaData(),
        sa.Column("org_id", sa.String(36), primary_key=True),
        sa.Column("subject", sa.String(16), primary_key=True),
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("label", sa.String(80)),
        sa.Column("type", sa.String(16)),
        sa.Column("required", sa.Boolean),
        sa.Column("options", sa.JSON),
        sa.Column("help", sa.String(200)),
        sa.Column("is_active", sa.Boolean),
        sa.Column("sort_order", sa.Integer),
    )


def upgrade() -> None:
    bind = op.get_bind()
    products, fields = products_table(), fields_table()

    # Which companies turn out to use which of the three; only those get fields.
    used: dict[str, set[str]] = {}
    for row in bind.execute(sa.select(products)):
        values = {key: getattr(row, key) for key, _ in PHARMA_FIELDS if getattr(row, key)}
        if not values:
            continue
        used.setdefault(row.org_id, set()).update(values)
        # `details` is empty everywhere today, but merging rather than replacing
        # means nothing is lost if this runs after something has written to it.
        bind.execute(
            products.update()
            .where(products.c.org_id == row.org_id, products.c.id == row.id)
            .values(details={**(row.details or {}), **values})
        )

    have = {
        (row.org_id, row.key)
        for row in bind.execute(sa.select(fields.c.org_id, fields.c.key).where(fields.c.subject == "product"))
    }
    rows = [
        {"org_id": org_id, "subject": "product", "key": key, "label": label, "type": "text", "required": False,
         "options": [], "help": "", "is_active": True, "sort_order": order}
        for org_id, keys in sorted(used.items())
        for order, (key, label) in enumerate(PHARMA_FIELDS)
        if key in keys and (org_id, key) not in have
    ]
    if rows:
        op.bulk_insert(fields, rows)


def downgrade() -> None:
    bind = op.get_bind()
    products, fields = products_table(), fields_table()
    keys = [key for key, _ in PHARMA_FIELDS]

    # The columns were never emptied, so taking the three keys back out of
    # `details` loses nothing.
    for row in bind.execute(sa.select(products).where(products.c.details.is_not(None))):
        kept = {k: v for k, v in (row.details or {}).items() if k not in keys}
        if kept != (row.details or {}):
            bind.execute(
                products.update().where(products.c.org_id == row.org_id, products.c.id == row.id).values(details=kept)
            )
    bind.execute(fields.delete().where(fields.c.subject == "product", fields.c.key.in_(keys)))
