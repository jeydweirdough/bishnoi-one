"""Reconcile the two issued 0033 histories without changing existing records.

Main's 0033 is canonical; the feature's original petty cash step is kept in compat.
Validate both features before any persistent DDL. A partially applied or malformed
schema requires investigation/restoration, never a guessed repair.
"""
from pathlib import Path
import re
import runpy

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None
ROOT = Path(__file__).resolve().parent.parent
FEATURES = (
    ('petty cash', 'compat/feature_0033_petty_cash.py',
     {'nbfi_petty_cash_vouchers', 'nbfi_petty_cash_lines', 'nbfi_petty_cash_events'}),
    ('recycle bin', 'versions/0033_recycle_bin.py', {'nbfi_recycle_bin'}),
)


def _run(relative, operations=None):
    upgrade = runpy.run_path(str(ROOT / relative))['upgrade']
    if operations is not None:
        upgrade.__globals__['op'] = operations
    upgrade()


def _sql(value):
    # PostgreSQL reflection adds casts/parentheses to an equivalent predicate.
    value = re.sub(r'::(?:text|character varying)(?:\[\])?', '', str(value).lower())
    value = re.sub(r'=\s*any\s*\(\s*array\s*\[', ' in (', value)
    return re.sub(r'[\s()\[\]"`]', '', value)


def _columns(inspector, table):
    return {c['name']: (c['type']._type_affinity.__name__, getattr(c['type'], 'length', None), c['nullable'])
            for c in inspector.get_columns(table)}


def _fks(inspector, table):
    return {(tuple(f['constrained_columns']), f['referred_table'], tuple(f['referred_columns']),
             (f.get('options', {}).get('ondelete') or 'NO ACTION').upper())
            for f in inspector.get_foreign_keys(table)}


def _indexes(inspector, table):
    return {(i['name'], tuple(i['column_names']), bool(i['unique']),
             _sql(i.get('dialect_options', {}).get(inspector.bind.dialect.name + '_where', '')))
            for i in inspector.get_indexes(table)}


def _checks(inspector, table):
    # These original migrations use only named column IN (literal...) checks.
    # PostgreSQL reflects IN as = ANY(ARRAY[...]); preserve the column and every value.
    result = set()
    for check in inspector.get_check_constraints(table):
        result.add((check['name'], _sql(check['sqltext'])))
    return result


def _validate(actual, expected, tables, what):
    for table in sorted(tables):
        checks = {
            'columns': (_columns(actual, table), _columns(expected, table)),
            'primary key': (actual.get_pk_constraint(table)['constrained_columns'], expected.get_pk_constraint(table)['constrained_columns']),
            'foreign keys': (_fks(actual, table), _fks(expected, table)),
            'indexes': (_indexes(actual, table), _indexes(expected, table)),
            'checks': (_checks(actual, table), _checks(expected, table)),
        }
        for part, (have, need) in checks.items():
            if have != need:
                raise RuntimeError(f'Incomplete or incompatible {what} schema: {table} {part} differ. '
                                   'Investigate or restore the verified backup before upgrading.')


def upgrade():
    actual = sa.inspect(op.get_bind())
    present = set(actual.get_table_names())
    pending = []
    # Build the expectation from the unchanged original migrations in a private
    # in-memory database; this never connects to app settings or business data.
    expected_engine = sa.create_engine('sqlite:///:memory:')
    try:
        with expected_engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            for _, relative, _ in FEATURES:
                _run(relative, operations)
            expected = sa.inspect(connection)
            for what, relative, tables in FEATURES:
                have = present & tables
                if have and have != tables:
                    raise RuntimeError(f'Incomplete {what} schema: investigate or restore the verified backup before upgrading.')
                if have:
                    _validate(actual, expected, tables, what)
                else:
                    pending.append(relative)
    finally:
        expected_engine.dispose()
    for relative in pending:
        _run(relative)


def downgrade():
    raise RuntimeError('This joins issued migration histories. Restore the verified backup to roll back safely.')
