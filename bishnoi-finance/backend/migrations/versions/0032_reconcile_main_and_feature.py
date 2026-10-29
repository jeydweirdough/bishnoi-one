"""Join main's and the feature branch's 0027-0029 additively (approved 2026-10-29).

Both lines issued 0027, 0028 and 0029 for different changes on the same day:
- main: invoices from deliveries; banks, payments and equity; management reports;
- feature (now in migrations/compat): the encrypted Zoho connection; the Zoho delivery queue;
  the reconciliation of the earlier 0023-0026 clash.
Main's files stay canonical (unchanged) in this chain, followed by the feature's 0030-0031.
A database records only a number, so one that came along either line is at the same
revision as one that came along the other but lacks the other's schema. 0032 supplies
whichever schema each database lacks. Every step adds only what is missing; nothing is
stamped, rebuilt, renumbered or replayed, and no recorded value changes.
"""
from pathlib import Path
import runpy
import sqlalchemy as sa
from alembic import op

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None
ROOT = Path(__file__).resolve().parent.parent


def run(relative):
    runpy.run_path(str(ROOT / relative))['upgrade']()


def missing(tables: set[str], needed: set[str], what: str) -> bool:
    """True when none of a step's tables exist (run it); False when all do. Part of them means a
    damaged database: stop, so it's restored from its verified backup rather than half-repaired."""
    have = needed & tables
    if have and have != needed:
        raise RuntimeError(f'Incomplete {what} schema: restore the verified backup before upgrading.')
    return not have


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    # The feature line, for a database that came along main's 0027-0029.
    if missing(tables, {'nbfi_zoho_connections', 'nbfi_zoho_runtime'}, 'Zoho connection'):
        run('compat/feature_0027_zoho_persistent_connection.py')
    if missing(tables, {'nbfi_zoho_deliveries', 'nbfi_zoho_links', 'nbfi_zoho_delivery_events'}, 'Zoho delivery'):
        run('compat/feature_0028_zoho_delivery_queue.py')
    run('compat/feature_0029_reconcile_finance_histories.py')  # adds only what's missing
    # Main's line, for a database that came along the feature's 0027-0029 (each adds only what's missing).
    for step in ('0027_invoices_from_deliveries', '0028_banks_payments_equity', '0029_management_reports'):
        run(f'versions/{step}.py')


def downgrade():
    raise RuntimeError('This joins applied histories. Restore the verified database backup to roll back safely.')
