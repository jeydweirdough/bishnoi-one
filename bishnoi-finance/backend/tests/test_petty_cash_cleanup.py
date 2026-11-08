"""Petty cash accounting history survives administrator cleanup and still voids normally."""
from datetime import date
import pytest
from sqlalchemy import select, text
from app.models import Account, JournalEntry, LedgerSettings
from app.ledger import Leg, post
from .test_petty_cash import MAKER, CHECKER, attach_all, fund, voucher
from .test_dashboard import person
from .test_concurrent_saves import app  # noqa: F401
from .test_tax_api import ana, client  # noqa: F401


def posted(app,client,ana):
    maker=person(client,ana,'Synthetic Cleanup Maker',MAKER)
    checker=person(client,ana,'Synthetic Cleanup Checker',CHECKER+['petty_cash.void'])
    v=attach_all(client,maker,voucher(client,maker,fund(app),number='SYN-PC-CLEANUP'))
    assert client.post(f"/finance/petty-cash/{v['id']}/submit",headers=maker).status_code==200
    response=client.post(f"/finance/petty-cash/{v['id']}/check",headers=checker)
    assert response.status_code==200,response.text
    return response.json(),maker,checker


def money_rows(app):
    names=('nbfi_journal_entries','nbfi_journal_lines','nbfi_petty_cash_vouchers','nbfi_petty_cash_lines','nbfi_petty_cash_events','nbfi_recycle_bin')
    with app.state.sessions() as db:
        return {n:sorted(repr(tuple(r)) for r in db.execute(text(f'SELECT * FROM "{n}"'))) for n in names}


@pytest.mark.parametrize('confirm',[False,True])
def test_posted_petty_cash_entry_cannot_be_cleaned_up(app,client,ana,confirm):
    v,_,_=posted(app,client,ana)
    before=money_rows(app)
    response=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[v['entryId']],'confirmPosted':confirm},headers=ana)
    assert response.status_code==409,response.text
    assert 'petty cash' in response.text.lower()
    assert money_rows(app)==before


def test_void_still_works_and_both_original_and_reversal_stay_protected(app,client,ana):
    v,_,checker=posted(app,client,ana)
    response=client.post(f"/finance/petty-cash/{v['id']}/void",json={'reason':'Synthetic duplicate'},headers=checker)
    assert response.status_code==200,response.text
    assert response.json()['status']=='void'
    with app.state.sessions() as db:
        reversal=db.get(JournalEntry,v['entryId']).reversed_by_id
        assert reversal
    before=money_rows(app)
    for identity in (v['entryId'],reversal):
        response=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[identity],'confirmPosted':True},headers=ana)
        assert response.status_code==409,response.text
        assert 'petty cash' in response.text.lower()
        assert money_rows(app)==before


def test_mixed_batch_rolls_back_and_ordinary_entry_can_still_restore(app,client,ana):
    v,_,_=posted(app,client,ana)
    with app.state.sessions() as db:
        cash=db.scalar(select(Account).where(Account.code=='1000'))
        expense=db.scalar(select(Account).where(Account.code=='6500'))
        entry=post(db,date(2026,10,6),'Synthetic ordinary entry',[Leg(cash,debit=100),Leg(expense,credit=100)],'Synthetic',source='manual')
        ordinary=entry.id
        db.commit()
    before=money_rows(app)
    response=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[ordinary,v['entryId']],'confirmPosted':True},headers=ana)
    assert response.status_code==409,response.text
    assert money_rows(app)==before
    done=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[ordinary],'confirmPosted':True},headers=ana)
    assert done.status_code==200,done.text
    identity=done.json()['binIds'][0]
    assert client.post(f'/data-cleanup/bin/{identity}/restore',headers=ana).status_code==200
    assert money_rows(app)==before


def test_a_link_is_protected_even_if_legacy_source_is_not_petty_cash(app,client,ana):
    v,_,_=posted(app,client,ana)
    with app.state.sessions() as db:
        db.get(JournalEntry,v['entryId']).source='manual'
        db.commit()
    before=money_rows(app)
    response=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[v['entryId']],'confirmPosted':True},headers=ana)
    assert response.status_code==409,response.text
    assert 'petty cash' in response.text.lower()
    assert money_rows(app)==before


def test_closed_period_guard_and_administrator_permission_remain(app,client,ana):
    v,maker,_=posted(app,client,ana)
    forbidden=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[v['entryId']],'confirmPosted':True},headers=maker)
    assert forbidden.status_code==403
    with app.state.sessions() as db:
        db.query(LedgerSettings).one().locked_until=date(2026,10,6)
        db.commit()
    before=money_rows(app)
    response=client.post('/data-cleanup/kinds/journal-entries/delete',json={'ids':[v['entryId']],'confirmPosted':True},headers=ana)
    assert response.status_code==409
    assert money_rows(app)==before


def test_document_cleanup_cannot_take_a_petty_cash_entry_indirectly(app,client,ana):
    from .test_invoices import issued,ready
    from app.models import Invoice
    v,_,_=posted(app,client,ana)
    ready(client,ana)
    invoice=issued(client,ana)
    # Synthetic inconsistent legacy link: cleanup must refuse, not detach the
    # petty cash voucher while removing a different document's linked entry.
    with app.state.sessions() as db:
        db.get(Invoice,invoice['id']).entry_id=v['entryId']
        db.commit()
    before=money_rows(app)
    response=client.post('/data-cleanup/kinds/invoices/delete',json={'ids':[invoice['id']],'confirmPosted':True},headers=ana)
    assert response.status_code==409,response.text
    assert 'petty cash' in response.text.lower()
    assert money_rows(app)==before
    assert client.get(f"/finance/invoices/{invoice['id']}",headers=ana).status_code==200
