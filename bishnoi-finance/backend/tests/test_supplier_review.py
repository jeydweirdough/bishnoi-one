"""Supplier table saves use fictional records; no real supplier data."""
from app.models import Supplier, AuditEntry
from sqlalchemy import select, func
from .test_tax_api import app, client, ana, ben  # noqa: F401
from .test_payables import supplier, bill
from .test_dashboard import person


def rows(client, who, **params):
    response = client.get('/finance/suppliers/review', headers=who, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def change(row, **patch):
    return {'id': row['id'], 'version': row['version']} | patch


def save(client, who, changes):
    return client.post('/finance/suppliers/review', headers=who, json={'changes': changes})


def test_review_reaches_suppliers_after_500_and_filters_without_private_fields(app, client, ana):
    with app.state.sessions() as db:
        db.add_all([Supplier(name=f'TEST Review {i:04}', origin='local' if i else None,
                             withholding=None, created_by='TEST') for i in range(507)])
        db.add(Supplier(name='TEST Export Limited', origin='foreign', created_by='TEST'))
        db.commit()
    last = rows(client, ana, page=6, page_size=100)
    assert last['total'] == 508 and len(last['items']) == 8
    assert rows(client, ana, origin='foreign')['total'] == 1
    assert rows(client, ana, origin='unset')['total'] == 1
    assert rows(client, ana, q='Review 0506', no_code=True)['total'] == 1
    assert 'bankAccountNumber' not in last['items'][0]
    assert rows(client, ana, page=999, page_size=100)['page'] == 6


def test_batch_changes_only_requested_fields_and_preserves_bills(app, client, ana):
    a = supplier(client, ana, name='TEST Local Branch Limited', origin='local', withholding='WC158', taxDefaultsConfirmed=True)
    b = supplier(client, ana, name='TEST Broker', tin=None, withholding=None)
    existing = bill(client, ana, a['id'])
    before = {s['id']: s for s in rows(client, ana)['items']}
    result = save(client, ana, [change(before[a['id']], withholding='WC140'), change(before[b['id']], origin='foreign')])
    assert result.status_code == 200, result.text
    assert result.json()['changed'] == 2
    after = {s['id']: s for s in rows(client, ana)['items']}
    assert after[a['id']]['origin'] == 'local' and after[a['id']]['withholding'] == 'WC140'
    assert after[a['id']]['taxDefaultsConfirmed'] is False
    assert after[b['id']]['origin'] == 'foreign' and after[b['id']]['withholding'] is None
    assert client.get(f"/finance/bills/{existing['id']}", headers=ana).json()['lines'] == existing['lines']
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(AuditEntry).where(AuditEntry.action == 'supplier.updated')) == 2


def test_conflict_and_stale_row_refuse_whole_batch(client, ana):
    a = supplier(client, ana, name='TEST First', withholding='WC158')
    b = supplier(client, ana, name='TEST Second', tin=None, withholding='WC158')
    before = {s['id']: s for s in rows(client, ana)['items']}
    refused = save(client, ana, [change(before[a['id']], withholding='WC140'), change(before[b['id']], origin='foreign')])
    assert refused.status_code == 422 and 'Nothing was saved' in refused.text
    assert {s['id']: s for s in rows(client, ana)['items']} == before
    assert save(client, ana, [change(before[b['id']], origin='foreign', withholding=None)]).status_code == 200
    stale = save(client, ana, [change(before[a['id']], withholding=None), change(before[b['id']], origin='local')])
    assert stale.status_code == 409
    assert {s['id']: s for s in rows(client, ana)['items']}[a['id']] == before[a['id']]


def test_unknown_code_duplicate_and_view_only_refused(client, ana):
    supplier(client, ana, name='TEST Rights', withholding=None)
    row = rows(client, ana)['items'][0]
    assert save(client, ana, [change(row, withholding='WC640')]).status_code == 422
    assert save(client, ana, [change(row, origin='foreign')]*2).status_code == 422
    viewer = person(client, ana, 'reviewer', ['suppliers.view'])
    assert rows(client, viewer)['canEdit'] is False
    assert save(client, viewer, [change(row, origin='foreign')]).status_code == 403


def test_repeated_success_cannot_overwrite_newer_values(client, ana):
    supplier(client, ana, name='TEST Retry', withholding=None)
    row = rows(client, ana)['items'][0]
    payload = [change(row, withholding='WC140')]
    assert save(client, ana, payload).status_code == 200
    assert save(client, ana, payload).status_code == 409
