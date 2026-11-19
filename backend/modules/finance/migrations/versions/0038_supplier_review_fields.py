"""Supplier origin, items that differ in VAT, and why a receipt has no withholding (Batch A, approved 2026-11-05).

Adds columns in place; nothing is rebuilt and no existing value changes:
- suppliers: origin (local or foreign) and vat_varies_by_item (no, to start). Origin is filled for every
  existing supplier as the user decided on 2026-11-05: a name with "Ltd" or "Limited" is foreign, every other local.
- petty cash receipt lines: no_withholding_reason and no_withholding_note, empty for every existing receipt.
A bill's lines live inside the bill (JSON), so their reason needs no column.

Revision ID: 0038
Revises: 0037

Ported from the approved legacy0036; already-present legacy values are preserved.
"""
import re

from alembic import op
import sqlalchemy as sa

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

# The same rule as app/payables.py FOREIGN_NAME, kept here so this step never changes with the app.
FOREIGN_NAME = re.compile(r"\b(ltd|limited)\b", re.IGNORECASE)


def upgrade():
    check = sa.inspect(op.get_bind())
    wanted = {'nbfi_suppliers': {'origin', 'vat_varies_by_item'}, 'nbfi_petty_cash_lines': {'no_withholding_reason', 'no_withholding_note'}}
    present = {t: {c['name'] for c in check.get_columns(t)} & names for t, names in wanted.items()}
    if present == wanted:
        return
    if any(present.values()):
        raise RuntimeError('Partial legacy supplier-review schema; no automatic repair.')
    op.add_column('nbfi_suppliers', sa.Column('origin', sa.String(10), nullable=True))
    op.add_column('nbfi_suppliers', sa.Column('vat_varies_by_item', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('nbfi_petty_cash_lines', sa.Column('no_withholding_reason', sa.String(20), nullable=True))
    op.add_column('nbfi_petty_cash_lines', sa.Column('no_withholding_note', sa.String(200), nullable=True))
    suppliers = sa.table('nbfi_suppliers', sa.column('id', sa.String), sa.column('name', sa.String), sa.column('origin', sa.String))
    bind = op.get_bind()
    rows = bind.execute(sa.select(suppliers.c.id, suppliers.c.name)).all()
    foreign = [i for i, name in rows if FOREIGN_NAME.search(name or "")]
    bind.execute(sa.update(suppliers).values(origin='local'))
    if foreign:
        bind.execute(sa.update(suppliers).where(suppliers.c.id.in_(foreign)).values(origin='foreign'))


def downgrade():
    op.drop_column('nbfi_petty_cash_lines', 'no_withholding_note')
    op.drop_column('nbfi_petty_cash_lines', 'no_withholding_reason')
    op.drop_column('nbfi_suppliers', 'vat_varies_by_item')
    op.drop_column('nbfi_suppliers', 'origin')
