from datetime import date,timedelta
import pytest
from sqlalchemy import select
from app.models import Bill,User,PaymentVoucher,JournalLine
from .test_tax_api import app,ana,client,REGISTRATION
from .test_banking import account,cash_in_bank
from .test_invoices import TODAY


def test_rdo_accepts_letters_roundtrips_and_rejects_bad_codes(client,ana):
    r=client.put('/tax/profile',json={**REGISTRATION,'rdoCode':'53a'},headers=ana)
    assert r.status_code==200,r.text
    assert r.json()['profile']['rdoCode']=='53A'
    assert client.get('/finance/bir/returns/vat',headers=ana).json()['taxpayer']['rdoCode']=='53A'
    from pypdf import PdfReader
    from io import BytesIO
    pdf=client.get('/finance/bir/returns/vat/draft.pdf',headers=ana)
    assert pdf.status_code==200,pdf.text if pdf.status_code!=200 else ''
    # The official form has one character per cell; extraction separates cells.
    assert '\n5\n3\nA\n' in PdfReader(BytesIO(pdf.content)).pages[0].extract_text()
    for value in ['ABC','5-A','1234','5','1!2',123]:
        assert client.put('/tax/profile',json={**REGISTRATION,'rdoCode':value},headers=ana).status_code==422
    r=client.put('/tax/profile',json={**REGISTRATION,'rdoCode':'053'},headers=ana)
    assert r.status_code==200 and r.json()['profile']['rdoCode']=='053'


@pytest.mark.parametrize('kind',['expense','income'])
@pytest.mark.parametrize('paid_rate,side',[(55.5,'credit_centavos'),(56.5,'debit_centavos')])
def test_one_combined_fx_account_handles_gains_and_losses(app,client,ana,kind,paid_rate,side):
    combined=account(client,ana,'TEST-FX','Synthetic combined Forex Gain/Loss',kind)
    r=client.put('/finance/ledger/posting',json={'accounts':{'fx_gain_account_id':combined,'fx_loss_account_id':combined}},headers=ana)
    assert r.status_code==200,r.text
    items={i['key']:i for i in r.json()['items']}
    assert items['fx_gain_account_id']['account']['id']==combined==items['fx_loss_account_id']['account']['id']
    assert items['fx_gain_account_id']['types']==['income','expense']
    assert client.put('/finance/ledger/posting',json={'accounts':{'receivables_account_id':combined}},headers=ana).status_code==422
    earlier=(date.fromisoformat(TODAY)-timedelta(days=1)).isoformat()
    for on,rate in [(earlier,56),(TODAY,paid_rate)]:
        assert client.put('/finance/exchange-rates',json={'currency':'USD','on':on,'rate':rate},headers=ana).status_code==200
    supplier=client.post('/finance/suppliers',json={'name':'Synthetic FX supplier','vatRegistered':False},headers=ana).json()
    expense=next(a['id'] for a in client.get('/finance/ledger/accounts',headers=ana).json()['items'] if a['code']=='6900')
    r=client.post('/finance/bills',json={'supplierId':supplier['id'],'billNumber':'TEST-FX-BILL','billDate':earlier,'currency':'USD','amountsIncludeVat':True,'lines':[{'accountId':expense,'description':'Fictional cost','amountCentavos':100000,'vat':'none'}]},headers=ana)
    assert r.status_code==201,r.text
    b=r.json()
    from app.routers.payables import clear
    with app.state.sessions() as db:
        clear(db,db.scalar(select(User)),db.get(Bill,b['id']));db.commit()
    r=client.post('/finance/vouchers',json={'supplierId':supplier['id'],'method':'bank','paidFromId':cash_in_bank(client,ana),'lines':[{'billId':b['id'],'amountCentavos':5600000}]},headers=ana)
    assert r.status_code==201,r.text
    voucher_id=r.json()['id']
    with app.state.sessions() as db:
        db.get(PaymentVoucher,voucher_id).status='to_release';db.commit()
    r=client.post(f'/finance/vouchers/{voucher_id}/release',json={'paidOn':TODAY,'bankReference':'TEST-FX-REF'},headers=ana)
    assert r.status_code==200,r.text
    with app.state.sessions() as db:
        v=db.get(PaymentVoucher,voucher_id)
        lines=list(db.scalars(select(JournalLine).where(JournalLine.entry_id==v.entry_id)))
        assert sum(x.debit_centavos for x in lines)==sum(x.credit_centavos for x in lines)
        line=next(x for x in lines if x.account_id==combined)
        assert getattr(line,side)==50000
