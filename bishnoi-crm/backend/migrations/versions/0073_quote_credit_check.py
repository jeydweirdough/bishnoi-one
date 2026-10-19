"""A quote's credit check (B2B, decided 2026-10-19): the customer's credit
status as Finance's invoices showed it when the quote was made, and Finance's
confirmation of it (nbcm_quotes.credit_check). Confirming it is a permission of
its own (orders.credit), given to the Finance role.

Revision ID: 0073
Revises: 0072
"""

from alembic import op
import sqlalchemy as sa

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("nbcm_quotes")}
    if "credit_check" not in columns:
        with op.batch_alter_table("nbcm_quotes") as batch:
            batch.add_column(sa.Column("credit_check", sa.JSON(), nullable=True))
    finance = bind.execute(sa.text("SELECT id FROM nbcm_roles WHERE lower(name) = 'finance' AND is_system = false")).scalar()
    if finance is not None:
        held = bind.execute(sa.text("SELECT 1 FROM nbcm_role_permissions WHERE role_id = :id AND permission = 'orders.credit'"), {"id": finance}).first()
        if held is None:
            bind.execute(sa.text("INSERT INTO nbcm_role_permissions (role_id, permission) VALUES (:id, 'orders.credit')"), {"id": finance})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM nbcm_role_permissions WHERE permission = 'orders.credit'"))
    with op.batch_alter_table("nbcm_quotes") as batch:
        batch.drop_column("credit_check")
