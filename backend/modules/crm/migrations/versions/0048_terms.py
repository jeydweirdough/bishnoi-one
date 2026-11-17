"""Each company's own words (app/terms.py): saved with the CRM's settings.

A database that already works like a pharmaceutical company (it has
customers of the type "doctor") keeps today's words: doctors, detailing,
clinics, molecules. Any other starts with the general ones, and the "Doctor"
customer type that migration 0015 gave every database is switched off there
(an admin can switch it back on, or pick the words in Settings → Terms).

Revision ID: 0048
Revises: 0047
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

PHARMA = {"visited": {"one": "Doctor", "many": "Doctors"}, "visited_type": "doctor", "detailing": "Detailing", "site": "Clinic", "generic_name": "Molecule"}


def upgrade() -> None:
    bind = op.get_bind()
    if "terms" not in {c["name"] for c in sa.inspect(bind).get_columns("nbcm_sales_settings")}:
        with op.batch_alter_table("nbcm_sales_settings") as batch:
            batch.add_column(sa.Column("terms", sa.JSON(), nullable=True))
    if bind.execute(sa.text("SELECT 1 FROM nbcm_companies WHERE status = 'doctor' LIMIT 1")).scalar():
        # (No settings row yet: it's made on first use, with the general words.)
        bind.execute(sa.text("UPDATE nbcm_sales_settings SET terms = :t WHERE id = 1"), {"t": json.dumps(PHARMA)})
    else:
        bind.execute(sa.text("UPDATE nbcm_customer_types SET is_active = false WHERE code = 'doctor'"))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        batch.drop_column("terms")
