"""Rehearse the exported CSV pack on disposable databases, never the active test site."""
import json
from pathlib import Path
from sqlalchemy import select, func
from app.models import Invoice, InvoicePayment, Bill, PaymentVoucher, ImportedExpense, JournalLine, JournalEntry
from app.ledger import settings as posting_settings
from .test_concurrent_saves import app
from .test_tax_api import ana, client
from .test_payables import supplier, account
from .test_oojeema_sales_and_expense_import import sales_ready, load, preview, run

PACK = Path(__file__).parent / 'fixtures/fictional-import'

def files(*names):
    return [{'name':n,'content':(PACK/n).read_text(encoding='utf-8-sig')} for n in names]

def prepare_matches(client,t,pack):
    load(client,t['cristal'],pack)
    sheet=client.get('/finance/imports/matching',headers=t['cristal']).json()
    for m in sheet['matches']:
        if m['status']=='confirmed':continue
        section=m['section'];body={};who=t['malou']
        if section=='company':body={'company':'2mg'}
        elif section=='money':body={'accountId':account(client,t['admin'],'1010')}
        elif section=='account':body={'accountId':account(client,t['admin'],'6500'),'purchaseType':'services' if m['role']=='expense' else 'other_goods'}
        elif section=='tax':body={'vatKind':'vat'};who=t['rommel']
        r=client.put('/finance/imports/matching/'+m['id'],headers=who,json=body)
        assert r.status_code==200,r.text

def test_exported_fictional_pack_matches_independent_answers(client,ana,app):
    e=json.loads((PACK/'expected-before-import.json').read_text())['expected']
    t=sales_ready(client,ana);t['admin']=ana
    from .test_dashboard import person, VIEW
    from .test_oojeema_sales_and_expense_import import ROLE
    t['cristal']=person(client,ana,'Pack Recorder',VIEW+ROLE+['vouchers.view','imports.propose','imports.run'])
    supplier(client,ana,name='TEST ONLY - Fictional Supplies',withholding=None)
    packs={
      'oojeema-sales':files('01-Sales-Journal.csv','02-Receipt-Journal.csv'),
      'bills':files('03-Bills.csv','04-Vendor-Payments.csv'),
      'supplier-payments':files('03-Bills.csv','04-Vendor-Payments.csv'),
      'expenses':files('05-Expenses.csv'),
    }
    # Real endpoint spellings come from existing import tests.
    from .test_oojeema_sales_and_expense_import import KIND
    packs[KIND]=packs.pop('oojeema-sales')
    for kind,count in [(KIND,5),('bills',2),('supplier-payments',1),('expenses',1)]:
        pack=packs[kind];prepare_matches(client,t,pack)
        p=preview(client,t['cristal'],kind,pack)
        assert p['counts']['ready']==count and p['counts']['held']==0 and p['counts']['skipped']==0,p
        run(client,t['cristal'],kind,pack,p['planKey'])
    with app.state.sessions() as db:
        invs=list(db.scalars(select(Invoice).order_by(Invoice.number)))
        assert len(invs)==3 and [i.paid_centavos for i in invs]==[112000,56000,0]
        assert sum(i.total_centavos-i.paid_centavos for i in invs)==e['receivables']
        bills=list(db.scalars(select(Bill).order_by(Bill.bill_number)))
        assert len(bills)==2 and [b.paid_centavos for b in bills]==[56000,0]
        assert sum(b.payable_centavos-b.paid_centavos for b in bills)==e['payables']
        assert db.scalar(select(func.count()).select_from(InvoicePayment))==2
        assert db.scalar(select(func.count()).select_from(PaymentVoucher))==1
        assert db.scalar(select(func.count()).select_from(ImportedExpense))==1
        s=posting_settings(db)
        balances={aid:db.scalar(select(func.coalesce(func.sum(JournalLine.debit_centavos-JournalLine.credit_centavos),0)).where(JournalLine.account_id==aid)) for aid in [s.bank_account_id,s.receivables_account_id,s.payables_account_id,s.input_tax_account_id,s.output_tax_account_id,s.sales_account_id]}
        assert balances[s.bank_account_id]==e['moneyNetMovement']
        assert balances[s.receivables_account_id]==e['receivables']
        assert balances[s.payables_account_id]==-e['payables']
        assert balances[s.input_tax_account_id]==e['inputVat']
        assert balances[s.output_tax_account_id]==-e['outputVat']
        assert balances[s.sales_account_id]==-e['salesNet']
        expense_id=account(client,ana,'6500')
        expense_balance=db.scalar(select(func.sum(JournalLine.debit_centavos-JournalLine.credit_centavos)).where(JournalLine.account_id==expense_id))
        assert expense_balance==e['expensesTotal']
        assert e['salesNet']-expense_balance==e['profitBeforeOtherCosts']
        debit=db.scalar(select(func.sum(JournalLine.debit_centavos)))
        credit=db.scalar(select(func.sum(JournalLine.credit_centavos)))
        assert debit==credit
        baseline=(len(invs),db.scalar(select(func.count()).select_from(JournalEntry)))
    for kind,pack in packs.items():
        p=preview(client,t['cristal'],kind,pack)
        assert p['counts']['ready']==0 and p['counts']['held']==0,p
    with app.state.sessions() as db:
        assert (db.scalar(select(func.count()).select_from(Invoice)),db.scalar(select(func.count()).select_from(JournalEntry)))==baseline
