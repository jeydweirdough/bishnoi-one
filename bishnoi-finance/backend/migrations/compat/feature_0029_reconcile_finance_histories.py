"""Complete both issued Finance histories additively, without changing recorded versions.

Main's 0023-0026 are canonical. The feature branch independently issued these IDs
for different changes. 0029 supplies whichever schema each database lacks. It
never stamps versions, rebuilds tables, replays postings or replaces recorded values.
"""
from pathlib import Path
import runpy
import sqlalchemy as sa
from alembic import op

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None
ROOT = Path(__file__).resolve().parent.parent


def run(relative):
    runpy.run_path(str(ROOT / relative))['upgrade']()


def upgrade():
    db = op.get_bind()
    tables = set(sa.inspect(db).get_table_names())
    for table, columns in {
        'nbfi_suppliers': [
            sa.Column('tax_defaults_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('import_details', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        ],
        'nbfi_bills': [sa.Column('tax_reviewed', sa.Boolean(), nullable=False, server_default=sa.false())],
    }.items():
        have = {c['name'] for c in sa.inspect(db).get_columns(table)}
        for column in columns:
            if column.name not in have:
                op.add_column(table, column)
    if 'nbfi_sales_orders' not in tables:
        run('compat/feature_0025_sales_orders.py')
    cache = {'nbfi_zoho_source_documents', 'nbfi_zoho_source_runs'}
    if cache & tables and not cache <= tables:
        raise RuntimeError('Incomplete Zoho cache schema: restore/repair the verified backup before upgrading.')
    if not cache & tables:
        run('compat/feature_0026_zoho_source_cache.py')
    run('compat/feature_0023_bill_purchase_types.py')
    for helper in ('0023_account_term', '0024_cost_of_goods_sold', '0025_invoice_division', '0026_business_events'):
        run(f'versions/{helper}.py')


def downgrade():
    raise RuntimeError('This joins applied histories. Restore the verified database backup to roll back safely.')
