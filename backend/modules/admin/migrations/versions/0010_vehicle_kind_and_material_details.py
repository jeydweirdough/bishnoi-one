"""A vehicle's kind (car or motorcycle, for its icon), worked out for the ones
already there from the plate (Philippine motorcycle plates start with digits)
or the name. A promotional material's planned quantity, specifications, date
needed and budget; and a photo as proof on each production run received and
each distribution given out.

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

COLUMNS = {
    "nbad_vehicles": (("kind", sa.String(12)),),
    "nbad_promo_materials": (("quantity", sa.Integer()), ("specs", sa.String(300)), ("needed_by", sa.Date()), ("budget", sa.Float())),
    "nbad_promo_productions": (("proof_ref", sa.String(32)), ("proof_name", sa.String(200))),
    "nbad_promo_distributions": (("proof_ref", sa.String(32)), ("proof_name", sa.String(200))),
}


def _kind(name: str | None, plate: str | None) -> str:
    # The same rule as app/models.py guess_vehicle_kind, kept here as it was on this day.
    if (plate or "").strip()[:1].isdigit():
        return "motorcycle"
    return "motorcycle" if any(w in (name or "").upper() for w in ("MOTORCYCLE", "MOTORBIKE", "SCOOTER")) else "car"


def upgrade() -> None:
    bind = op.get_bind()
    inspect = sa.inspect(bind)
    for table, columns in COLUMNS.items():
        have = {c["name"] for c in inspect.get_columns(table)}
        for name, kind in columns:
            if name not in have:
                with op.batch_alter_table(table) as batch:
                    batch.add_column(sa.Column(name, kind, nullable=True, server_default="car" if name == "kind" else None))
    for id_, name, plate in bind.execute(sa.text("SELECT id, name, plate FROM nbad_vehicles")).all():
        bind.execute(sa.text("UPDATE nbad_vehicles SET kind = :k WHERE id = :i"), {"k": _kind(name, plate), "i": id_})


def downgrade() -> None:
    for table, columns in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for name, _ in reversed(columns):
                batch.drop_column(name)
