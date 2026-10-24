"""A supplier's tax registration, for Finance's bills and the BIR's purchase
lists (decided 2026-10-24, BIR features from Oojeema): its TIN, whether it's
VAT-registered, and the ATC usually withheld from what it's paid (WC158 for
goods, WC160 for services, ...). Suppliers stay here, one list; Finance reads them.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbin_suppliers") as batch:
        batch.add_column(sa.Column("tin", sa.String(20), nullable=True))
        batch.add_column(sa.Column("vat_status", sa.String(8), nullable=False, server_default="vat"))
        batch.add_column(sa.Column("default_atc", sa.String(8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbin_suppliers") as batch:
        batch.drop_column("default_atc")
        batch.drop_column("vat_status")
        batch.drop_column("tin")
