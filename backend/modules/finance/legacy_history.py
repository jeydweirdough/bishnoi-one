"""Recognize the exact pre-unification Finance branch before replaying main's steps.

Called only within the migration backup/restore boundary (or PostgreSQL transaction).
Existing feature columns/tables are retained by the later additive migrations.
"""
from sqlalchemy import inspect, text

COMPANY={'nbfi_company_review_batches','nbfi_company_review_rows','nbfi_company_scope_reviews'}
INTAKE={'nbfi_purchase_intakes','nbfi_purchase_supplier_links','nbfi_purchase_allocations','nbfi_purchase_preparations'}

def reconcile(connection):
    i=inspect(connection);tables=set(i.get_table_names())
    if 'nbfi_alembic_version' not in tables:return
    revision=connection.execute(text('SELECT version_num FROM nbfi_alembic_version')).scalar_one_or_none()
    if revision not in ('0036','0037','0038'):return
    fields={c['name'] for c in i.get_columns('nbfi_suppliers')}
    if not fields & {'origin','vat_varies_by_item'}:return
    # These four columns and the old FX schema identify the known feature history.
    receipt_fields={c['name'] for c in i.get_columns('nbfi_petty_cash_lines')}
    bill_fields={c['name'] for c in i.get_columns('nbfi_bills')}
    required=({'origin','vat_varies_by_item'}<=fields and {'no_withholding_reason','no_withholding_note'}<=receipt_fields)
    expected_company=COMPANY if revision in ('0037','0038') else set()
    expected_intake=INTAKE if revision=='0038' else set()
    if not required or tables&COMPANY!=expected_company or tables&INTAKE!=expected_intake or 'currency' not in bill_fields:
        raise RuntimeError('Unrecognized/partial legacy Finance history; migration refused before schema changes.')
    if any(x['name']=='nbfi_audit_log_actor' for x in i.get_indexes('nbfi_audit_log')):
        raise RuntimeError('Mixed Finance histories require explicit review; migration refused.')
    connection.execute(text("UPDATE nbfi_alembic_version SET version_num='0035'"))
