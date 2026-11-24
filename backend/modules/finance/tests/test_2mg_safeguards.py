"""Company boundary regressions use fictional records only."""
from datetime import date
import pytest
from fastapi import HTTPException
from sqlalchemy import select, delete
from modules.finance.models import Account, CompanyScopeReview, Bill, JournalEntry
from modules.finance.ledger import post, Leg
from .test_tax_api import app, client, ana
from .test_payables import supplier, bill, account


def mark(app, kind, id, value):
    with app.state.sessions() as db:
        db.merge(CompanyScopeReview(subject_kind=kind,subject_id=id,scope=value,evidence={'source':'fictional test'},reviewed_by='TEST'))
        db.commit()


@pytest.fixture
def approved(app):
    with app.state.sessions() as db:
        for a in db.scalars(select(Account)):
            db.merge(CompanyScopeReview(subject_kind='account',subject_id=a.id,scope='2mg',evidence={'source':'fictional test'},reviewed_by='TEST'))
        db.commit()


def test_books_nobody_reviewed_use_their_accounts(app,client,ana):
    # The company review is 2MG's; a company starting fresh (Getmeds on the one system) uses its chart as it is (2026-11-24).
    with app.state.sessions() as db:
        db.execute(delete(CompanyScopeReview));db.commit()
    assert client.get('/finance/bills/choices',headers=ana).json()['accounts']
    assert client.get('/finance/ledger/accounts',headers=ana).json()['items']


def test_direct_new_bill_refuses_hidden_legacy_account(app,client,ana,approved):
    s=supplier(client,ana);mark(app,'supplier',s['id'],'2mg')
    a=account(client,ana,'6500');mark(app,'account',a,'legacy')
    r=client.post('/finance/bills',headers=ana,json={'supplierId':s['id'],'billNumber':'TEST-SCOPE','billDate':'2026-10-01',
        'lines':[{'accountId':a,'amountCentavos':10000,'vat':'none','withholding':None}]})
    assert r.status_code==422 and '2MG' in r.text
    with app.state.sessions() as db:assert db.scalar(select(Bill).where(Bill.bill_number=='TEST-SCOPE')) is None


def test_supplier_history_is_read_only_and_not_normal_directory(app,client,ana,approved):
    s=supplier(client,ana);mark(app,'supplier',s['id'],'review')
    assert client.get('/finance/suppliers',headers=ana).json()['items']==[]
    old=client.get('/finance/suppliers/review?company_use=all',headers=ana).json()
    assert old['canEdit'] is False
    assert client.get('/finance/suppliers?company_use=history',headers=ana).json()['canEdit'] is False
    row=old['items'][0]
    r=client.post('/finance/suppliers/review',headers=ana,json={'changes':[{'id':s['id'],'version':row['version'],'origin':'foreign','withholding':None}]})
    assert r.status_code==409 and '2MG' in r.text
    assert client.get('/finance/suppliers/'+s['id'],headers=ana).json()['canEdit'] is False


def test_changed_company_scope_blocks_submission_and_keeps_history(app,client,ana,approved):
    s=supplier(client,ana);mark(app,'supplier',s['id'],'2mg')
    b=bill(client,ana,s['id'])
    mark(app,'supplier',s['id'],'review')
    r=client.post('/finance/bills/'+b['id']+'/submit',headers=ana)
    assert r.status_code==409 and '2MG' in r.text
    assert client.get('/finance/bills/'+b['id'],headers=ana).status_code==200


def test_petty_cash_choices_exclude_legacy_accounts(app,client,ana,approved):
    a=account(client,ana,'6500');mark(app,'account',a,'legacy')
    assert a not in {a['id'] for a in client.get('/finance/petty-cash/choices',headers=ana).json()['accounts']}


def test_all_posting_paths_refuse_unreviewed_defaults_but_exact_reversal_survives(app,approved):
    with app.state.sessions() as db:
        debit=db.scalar(select(Account).where(Account.code=='6500'))
        credit=db.scalar(select(Account).where(Account.code=='1000'))
        original=post(db,date(2026,10,1),'TEST original',[Leg(debit,debit=100),Leg(credit,credit=100)],'TEST')
        db.commit();original_id=original.id;debit_id=debit.id;credit_id=credit.id
    mark(app,'account',debit_id,'legacy')
    with app.state.sessions() as db:
        debit=db.get(Account,debit_id);credit=db.get(Account,credit_id)
        with pytest.raises(HTTPException,match='2MG'):
            post(db,date(2026,10,2),'TEST new',[Leg(debit,debit=100),Leg(credit,credit=100)],'TEST')
        db.rollback()
    with app.state.sessions() as db:
        debit=db.get(Account,debit_id);credit=db.get(Account,credit_id);original=db.get(JournalEntry,original_id)
        reverse=post(db,date(2026,10,2),'TEST reverse',[Leg(debit,credit=100),Leg(credit,debit=100)],'TEST',reverses=original)
        db.commit();assert reverse.reverses_id==original_id


def test_reverse_reference_is_not_a_scope_bypass(app,approved):
    with app.state.sessions() as db:
        a=db.scalar(select(Account).where(Account.code=='6500'));c=db.scalar(select(Account).where(Account.code=='1000'))
        e=post(db,date(2026,10,1),'TEST original',[Leg(a,debit=100),Leg(c,credit=100)],'TEST');db.commit()
        with pytest.raises(HTTPException):
            post(db,date(2026,10,2),'TEST fake',[Leg(a,credit=200),Leg(c,debit=200)],'TEST',reverses=e)


def test_journal_waiting_approval_rechecks_company_scope(app,client,ana,approved):
    from .test_tax_api import ben
    from .test_auth import bearer, sign_in
    a=account(client,ana,'6500');c=account(client,ana,'1000')
    author=bearer(sign_in(client,'ben@example.com'))
    r=client.post('/finance/ledger/entries',headers=author,json={'date':'2026-10-01','memo':'TEST approval scope',
        'lines':[{'accountId':a,'debitCentavos':100},{'accountId':c,'creditCentavos':100}]})
    assert r.status_code==201,r.text
    mark(app,'account',a,'legacy')
    refused=client.post('/finance/ledger/entries/'+r.json()['id']+'/approve',headers=ana)
    assert refused.status_code==409 and '2MG' in refused.text
    with app.state.sessions() as db:assert db.get(JournalEntry,r.json()['id']).status=='waiting'


def test_direct_petty_cash_save_refuses_legacy_line(app,client,ana,approved):
    from .test_petty_cash import fund,line
    f=fund(app);a=account(client,ana,'6500');mark(app,'account',a,'legacy')
    r=client.post('/finance/petty-cash',headers=ana,json={'number':'TEST-SCOPE-PC','fundAccountId':f,
        'voucherDate':'2026-10-06','lines':[{'accountId':a,'amountCentavos':10000,'spentOn':'2026-10-05','store':'TEST store','receiptNumber':'TEST-OR','vat':'none','withholding':None,'noWithholdingReason':'not_covered','purchaseType':'other_goods'}]})
    assert r.status_code==422 and '2MG' in r.text


def test_reclassified_bill_cannot_be_approved(app,client,ana,approved):
    from .test_auth import bearer, sign_in
    author=bearer(sign_in(client,'ben@example.com'))
    s=supplier(client,author)
    b=bill(client,author,s['id'])
    assert client.post('/finance/bills/'+b['id']+'/submit',headers=author).status_code==200
    mark(app,'supplier',s['id'],'review')
    r=client.post('/finance/bills/'+b['id']+'/approve',headers=ana)
    assert r.status_code==409 and '2MG' in r.text
    saved=client.get('/finance/bills/'+b['id'],headers=ana).json()
    assert saved['companyHold'] and saved['canApprove'] is False


def test_unknown_consignment_vendor_is_held_without_committing_a_bill(app):
    from modules.finance.consignment_bills import from_settlement
    from modules.finance.models import Supplier
    with app.state.sessions() as db:
        with pytest.raises(HTTPException,match='2MG'):
            from_settlement(db,{'number':'TEST-CS-HOLD','supplier':{'name':'TEST unknown source'},
                'lines':[{'name':'TEST item','sku':'TEST-1','quantity':1,'total':100}]},'2mg')
        db.rollback()
    with app.state.sessions() as db:
        assert db.scalar(select(Bill).where(Bill.bill_number=='TEST-CS-HOLD')) is None
        assert db.scalar(select(Supplier).where(Supplier.name=='TEST unknown source')) is None


def test_finance_takes_its_own_companys_events(app,client,monkeypatch):
    from modules.finance import business_events
    from modules.finance.business_events import InboxEvent
    from .test_platform_roles import note
    from .test_platform_sign_in import PUBLIC
    app.state.settings.platform_public_key=PUBLIC
    called=[]
    monkeypatch.setitem(business_events.HANDLERS,'delivery.done',lambda *args:called.append(True))
    event={'id':'TEST-other-company-event','kind':'delivery.done','source':'inventory','data':{}}
    # Finance keeps one company's books and takes that company's events, whichever company it is (2026-11-24).
    r=client.post('/platform/events',json={'pass':note('event',event=event,slug='')})
    assert r.status_code==404 and called==[]
    r=client.post('/platform/events',json={'pass':note('event',event=event,slug='getmeds')})
    assert r.status_code==204 and called==[True]
    with app.state.sessions() as db:assert db.get(InboxEvent,event['id']) is not None


def test_unverified_account_cannot_be_a_new_parent_or_default(app,client,ana):
    a=account(client,ana,'6500');mark(app,'account',a,'legacy')
    parent=client.post('/finance/ledger/accounts',headers=ana,json={
        'code':'TEST-CHILD','name':'TEST child','type':'expense','parentId':a})
    assert parent.status_code==422 and '2MG' in parent.text
    default=client.put('/finance/ledger/posting',headers=ana,json={'accounts':{'cogs_account_id':a}})
    assert default.status_code==422 and '2MG' in default.text
