"""Approved first batch: import capacity, approved books, and final period checks. Synthetic only."""
from datetime import date,timedelta
from sqlalchemy import func,select
import pytest
from app import bir_reports as bir
from app.models import Bill,Invoice,JournalEntry,JournalLine,LedgerSettings,PaymentVoucher,VoucherLine,ZohoDelivery,BankReconciliation
from app.routers.banking import period_moves
from .test_concurrent_saves import app  # noqa: F401
from .test_tax_api import ana,ben,client  # noqa: F401
from .test_ledger import accounts
from .test_zoho_import import matched,pack,bill_row,payment_row,preview,run,matches,propose


def setup_payment(client,ana,amounts,total):
    first=payment_row('synthetic-payment','b1','SYN-PAY',amount=amounts[0])
    first.update({'Amount':total,'PIPayment ID':'allocation-0'})
    rows=[{**first,'Bill Amount':amount,'PIPayment ID':f'allocation-{i}'} for i,amount in enumerate(amounts)]
    files=pack(bills=[bill_row('b1','SYN-BILL')],payments=rows)
    team,files=matched(client,ana,files)
    p=preview(client,team['cristal'],'bills',files)
    run(client,team['cristal'],'bills',files,p['planKey'])
    return team,files


def financial_counts(app):
    with app.state.sessions() as db:
        return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Bill,PaymentVoucher,JournalEntry,ZohoDelivery))


def test_one_payment_cannot_overpay_the_same_bill_twice(app,client,ana):
    team,files=setup_payment(client,ana,['40.00','40.00'],'80.00')
    before=financial_counts(app)
    p=preview(client,team['cristal'],'supplier-payments',files)
    assert p['counts']['ready']==0 and p['counts']['held']==1,p
    assert 'left to pay' in ' '.join(p['rows'][0]['reasons'])
    run(client,team['cristal'],'supplier-payments',files,p['planKey'])
    assert financial_counts(app)==before
    with app.state.sessions() as db:assert db.scalar(select(Bill).where(Bill.zoho_ref=='b1')).paid_centavos==0


def test_valid_split_allocation_is_preserved_and_imported_once(app,client,ana):
    team,files=setup_payment(client,ana,['20.00','20.00'],'40.00')
    p=preview(client,team['cristal'],'supplier-payments',files)
    assert p['counts']['ready']==1,p
    run(client,team['cristal'],'supplier-payments',files,p['planKey'])
    with app.state.sessions() as db:
        bill=db.scalar(select(Bill).where(Bill.zoho_ref=='b1'))
        assert bill.paid_centavos==4000
        v=db.scalar(select(PaymentVoucher).where(PaymentVoucher.zoho_ref=='synthetic-payment'))
        assert len(v.lines)==2 and [line.amount_centavos for line in v.lines]==[2000,2000]
        assert sum(line.debit_centavos for line in db.get(JournalEntry,v.entry_id).lines)==4000
        assert db.scalar(select(func.count()).select_from(ZohoDelivery))==0
    before=financial_counts(app)
    again=preview(client,team['cristal'],'supplier-payments',files)
    assert again['counts']['imported']==1
    run(client,team['cristal'],'supplier-payments',files,again['planKey'])
    assert financial_counts(app)==before


@pytest.mark.parametrize('each,ready,held',[('40.00',0,2),('28.00',2,0)])
def test_all_payments_in_pack_fit_together_or_conflicting_records_are_held(app,client,ana,each,ready,held):
    files=pack(bills=[bill_row('b1','SYN-BILL')],payments=[payment_row('p1','b1','SYN-P1',amount=each),payment_row('p2','b1','SYN-P2',amount=each)])
    team,files=matched(client,ana,files)
    run(client,team['cristal'],'bills',files,preview(client,team['cristal'],'bills',files)['planKey'])
    p=preview(client,team['cristal'],'supplier-payments',files)
    assert (p['counts']['ready'],p['counts']['held'])==(ready,held),p
    run(client,team['cristal'],'supplier-payments',files,p['planKey'])
    with app.state.sessions() as db:
        bill=db.scalar(select(Bill).where(Bill.zoho_ref=='b1'))
        assert bill.paid_centavos==(5600 if ready else 0)


def test_reserved_money_and_changed_source_refuse_stale_preview(app,client,ana):
    team,files=setup_payment(client,ana,['40.00'],'40.00')
    p=preview(client,team['cristal'],'supplier-payments',files)
    # Same payment identity, different valid amount: the old key cannot authorise it.
    changed=pack(bills=[bill_row('b1','SYN-BILL')],payments=[payment_row('synthetic-payment','b1','SYN-PAY',amount='30.00')])
    before=financial_counts(app)
    run(client,team['cristal'],'supplier-payments',changed,p['planKey'],expect=409)
    assert financial_counts(app)==before
    with app.state.sessions() as db:
        b=db.scalar(select(Bill).where(Bill.zoho_ref=='b1'));supplier_id=b.supplier_id;bill_id=b.id
    reserve=client.post('/finance/vouchers',json={'supplierId':supplier_id,'method':'bank','paidFromId':accounts(client,ana)['1010']['id'],'lines':[{'billId':bill_id,'amountCentavos':2000}]},headers=ana)
    assert reserve.status_code==201,reserve.text
    before=financial_counts(app)
    run(client,team['cristal'],'supplier-payments',files,p['planKey'],expect=409)
    assert financial_counts(app)==before
    assert preview(client,team['cristal'],'supplier-payments',files)['counts']['held']==1


def entry(client,ben,on=None,amount=10000):
    a=accounts(client,ben)
    made=client.post('/finance/ledger/entries',json={'date':(on or date.today()).isoformat(),'memo':'Synthetic batch approval cost','lines':[
        {'accountId':a['6500']['id'],'debitCentavos':amount},
        {'accountId':a['1010']['id'],'creditCentavos':amount}]},headers=ben)
    assert made.status_code==201,made.text
    return made.json(),a


def report_amounts(app,client,ana,start,end):
    with app.state.sessions() as db:
        return {
            'journal':bir.general_journal(db,start,end)['totals']['debitCentavos'],
            'cash':bir.cash_disbursements(db,start,end)['totals']['amountCentavos'],
            'expense':bir.income_statement(db,start,end)['totals']['expensesCentavos'],
            'balanceMoves':sum(d for d,c in bir.balances(db,start=start,end=end).values()),
            'ledgerRows':sum(len(a['rows']) for a in bir.general_ledger(db,start,end)['accounts']),
            'equityMoves':sum(d for d,c in period_moves(db,start,end).values()),
            'bank':next(a['bookBalanceCentavos'] for a in client.get('/finance/bank/accounts',headers=ana).json()['accounts'] if a['code']=='1010'),
        }


def test_reports_exclude_waiting_and_rejected_but_include_approved(app,client,ana,ben):
    e,_=entry(client,ben);today=date.today()
    amounts=report_amounts(app,client,ana,today,today)
    assert set(amounts.values())=={0},amounts
    assert client.post(f"/finance/ledger/entries/{e['id']}/reject",json={'reason':'Synthetic rejection'},headers=ana).status_code==200
    assert set(report_amounts(app,client,ana,today,today).values())=={0}
    approved,_=entry(client,ben)
    assert client.post(f"/finance/ledger/entries/{approved['id']}/approve",headers=ana).status_code==200
    amounts=report_amounts(app,client,ana,today,today)
    assert amounts=={'journal':10000,'cash':10000,'expense':10000,'balanceMoves':10000,'ledgerRows':2,'equityMoves':10000,'bank':-10000},amounts


def test_bank_matching_cannot_select_unapproved_lines(app,client,ana,ben):
    e,a=entry(client,ben)
    r=client.post('/finance/bank/reconciliations',json={'accountId':a['1010']['id'],'statementDate':date.today().isoformat(),'statementBalanceCentavos':-10000},headers=ana)
    assert r.status_code==201,r.text
    path=f"/finance/bank/reconciliations/{r.json()['id']}"
    assert client.get(path,headers=ana).json()['lines']==[]
    assert client.post(path+'/finish',headers=ana).status_code==409
    assert client.post(f"/finance/ledger/entries/{e['id']}/approve",headers=ana).status_code==200
    lines=client.get(path,headers=ana).json()['lines'];assert len(lines)==1
    assert client.put(path+'/cleared',json={'lineIds':[lines[0]['id']]},headers=ana).status_code==200
    assert client.post(path+'/finish',headers=ana).json()['status']=='done'


def test_closed_period_refuses_late_approval_and_allows_rejection(app,client,ana,ben):
    on=date.today()-timedelta(days=40);e,_=entry(client,ben,on)
    assert client.put('/finance/period-lock',json={'lockedUntil':on.isoformat()},headers=ana).status_code==200
    result=client.post(f"/finance/ledger/entries/{e['id']}/approve",headers=ana)
    assert result.status_code==409 and 'closed' in result.text,result.text
    with app.state.sessions() as db:
        assert db.get(JournalEntry,e['id']).status=='waiting'
        assert db.get(JournalEntry,e['id']).decided_at is None
    assert client.post(f"/finance/ledger/entries/{e['id']}/reject",json={'reason':'Synthetic rejected closed item'},headers=ana).status_code==200


def test_bulk_approval_skips_closed_entries_and_keeps_open_ones(app,client,ana,ben):
    on=date.today()-timedelta(days=40)
    closed,_=entry(client,ben,on);opened,_=entry(client,ben)
    assert client.put('/finance/period-lock',json={'lockedUntil':on.isoformat()},headers=ana).status_code==200
    result=client.post('/finance/ledger/entries/approve',json={'ids':[closed['id'],opened['id']]},headers=ana)
    assert result.status_code==200,result.text
    assert result.json()['approved']==[opened['number']]
    assert len(result.json()['skipped'])==1 and 'closed' in result.json()['skipped'][0]['reason']
    with app.state.sessions() as db:
        assert db.get(JournalEntry,closed['id']).status=='waiting'
        assert db.get(JournalEntry,opened['id']).status=='approved'


def test_source_bill_changes_and_bank_choice_changes_need_new_preview(app,client,ana):
    original=pack(bills=[bill_row('b1','SYN-BILL')])
    team,files=matched(client,ana,original)
    p=preview(client,team['cristal'],'bills',files)
    changed=pack(bills=[bill_row('b1','SYN-BILL',total='112.00',tax='12.00',item='100.00')])
    before=financial_counts(app)
    run(client,team['cristal'],'bills',changed,p['planKey'],expect=409)
    assert financial_counts(app)==before
    run(client,team['cristal'],'bills',files,p['planKey'])
    p=preview(client,team['cristal'],'supplier-payments',files)
    money=matches(client,team['malou'])[('money','Synthetic Bank')]
    propose(client,team['malou'],money,accountId=accounts(client,ana)['1000']['id'])
    before=financial_counts(app)
    run(client,team['cristal'],'supplier-payments',files,p['planKey'],expect=409)
    assert financial_counts(app)==before


def test_group_total_is_checked_again_under_bill_lock(app,client,ana,monkeypatch):
    from app import zoho_import as zi
    team,files=setup_payment(client,ana,['20.00','20.00'],'40.00')
    p=preview(client,team['cristal'],'supplier-payments',files)
    real=zi.locked
    def changed_before_locked_read(db,model,ids):
        rows=real(db,model,ids)
        if model is Bill:
            # Simulate a newer paid amount read under lock after the preview.
            # Each allocation still fits individually, but their sum no longer does.
            rows[0].paid_centavos=2000
            db.flush()
        return rows
    monkeypatch.setattr(zi,'locked',changed_before_locked_read)
    before=financial_counts(app)
    run(client,team['cristal'],'supplier-payments',files,p['planKey'],expect=409)
    assert financial_counts(app)==before
    with app.state.sessions() as db:assert db.scalar(select(Bill).where(Bill.zoho_ref=='b1')).paid_centavos==0


def test_waiting_opening_and_rejected_reversal_never_change_approved_books(app,client,ana,ben):
    old,_=entry(client,ben,date.today()-timedelta(days=10))
    with app.state.sessions() as db:
        assert bir.general_ledger(db,date.today(),date.today())['accounts']==[]
    assert client.post(f"/finance/ledger/entries/{old['id']}/approve",headers=ana).status_code==200
    with app.state.sessions() as db:
        ledger=bir.general_ledger(db,date.today(),date.today())
        assert next(a for a in ledger['accounts'] if a['code']=='1010')['openingCentavos']==-10000
    reversed_=client.post(f"/finance/ledger/entries/{old['id']}/reverse",json={},headers=ben)
    assert reversed_.status_code==201,reversed_.text
    with app.state.sessions() as db:assert sum(c for d,c in bir.balances(db,end=date.today()).values())==10000
    assert client.post(f"/finance/ledger/entries/{reversed_.json()['id']}/reject",json={'reason':'Synthetic rejected reversal'},headers=ana).status_code==200
    with app.state.sessions() as db:assert sum(c for d,c in bir.balances(db,end=date.today()).values())==10000
    new=client.post(f"/finance/ledger/entries/{old['id']}/reverse",json={},headers=ben)
    assert new.status_code==201,new.text
    assert client.post(f"/finance/ledger/entries/{new.json()['id']}/approve",headers=ana).status_code==200
    with app.state.sessions() as db:
        assert all(d==c for d,c in bir.balances(db,end=date.today()).values())


def test_old_unapproved_cleared_ids_cannot_be_finished_silently(app,client,ana,ben):
    e,a=entry(client,ben)
    r=client.post('/finance/bank/reconciliations',json={'accountId':a['1010']['id'],'statementDate':date.today().isoformat(),'statementBalanceCentavos':0},headers=ana)
    with app.state.sessions() as db:
        line=db.scalar(select(JournalLine).where(JournalLine.entry_id==e['id'],JournalLine.account_id==a['1010']['id']))
        rec=db.get(BankReconciliation,r.json()['id']);rec.cleared=[line.id];db.commit()
    refused=client.post(f"/finance/bank/reconciliations/{r.json()['id']}/finish",headers=ana)
    assert refused.status_code==409 and 'approved books' in refused.text
    with app.state.sessions() as db:assert db.get(BankReconciliation,r.json()['id']).status=='open'


def test_reopening_is_explicit_and_keeps_the_original_entry_date(app,client,ana,ben):
    on=date.today()-timedelta(days=40);e,_=entry(client,ben,on)
    assert client.put('/finance/period-lock',json={'lockedUntil':on.isoformat()},headers=ana).status_code==200
    assert client.post(f"/finance/ledger/entries/{e['id']}/approve",headers=ana).status_code==409
    assert client.put('/finance/period-lock',json={'lockedUntil':None},headers=ana).status_code==200
    assert client.post(f"/finance/ledger/entries/{e['id']}/approve",headers=ana).status_code==200
    with app.state.sessions() as db:assert db.get(JournalEntry,e['id']).entry_date==on


@pytest.mark.parametrize('closing_first',[True,False])
def test_period_close_and_approval_have_a_consistent_order(app,client,ana,ben,monkeypatch,closing_first):
    from app.routers import banking,ledger as journal
    from .test_concurrent_saves import race
    on=date.today()-timedelta(days=40);e,_=entry(client,ben,on)
    close=lambda:client.put('/finance/period-lock',json={'lockedUntil':on.isoformat()},headers=ana)
    approve=lambda:client.post(f"/finance/ledger/entries/{e['id']}/approve",headers=ana)
    if closing_first:
        first,second=race(monkeypatch,banking,'audit',close,approve)
        assert (first.status_code,second.status_code)==(200,409),(first.text,second.text)
    else:
        first,second=race(monkeypatch,journal,'require_open_period',approve,close)
        assert (first.status_code,second.status_code)==(200,200),(first.text,second.text)
    with app.state.sessions() as db:
        assert db.get(JournalEntry,e['id']).status==('waiting' if closing_first else 'approved')
        assert db.get(LedgerSettings,1).locked_until==on
