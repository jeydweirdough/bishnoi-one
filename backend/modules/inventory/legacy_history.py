"""Recognize the old receipt-only0024, before the unified main's different0024."""
from sqlalchemy import inspect, text

def reconcile(connection):
    i=inspect(connection);tables=set(i.get_table_names())
    if 'nbin_alembic_version' not in tables:return
    revision=connection.execute(text('SELECT version_num FROM nbin_alembic_version')).scalar_one_or_none()
    if revision!='0024' or 'nbin_receipt_finance_handoffs' not in tables:return
    fields={c['name'] for c in i.get_columns('nbin_receipt_finance_handoffs')}
    required={'receipt_id','digest','snapshot','version','remaining','bills','sent_by','sent_at'}
    if not required<=fields or any(x['name']=='nbin_audit_log_actor' for x in i.get_indexes('nbin_audit_log')):
        raise RuntimeError('Unrecognized/mixed Inventory receipt history; migration refused.')
    connection.execute(text("UPDATE nbin_alembic_version SET version_num='0023'"))
