"""A partial receipt becomes one independently checked bill, one payment and report evidence."""
from datetime import date
from .test_tax_api import app,client,ana
from .test_vouchers import team,prepare,step
from .test_purchase_intake import intake,linked,request
from .test_ledger import balances
from modules.finance import bir_reports

def test_partial_receipt_bill_payment_and_reports_agree(app,client,ana,team):
    item,supplier=linked(app,client,ana,intake(app,client,ana))
    body=request(client,team['aubrey'],item,supplier,50)
    body['bill']['amountsIncludeVat']=False
    line=body['bill']['lines'][0]
    line.update(vat='vat',withholding='WC158',purchaseType='other_goods')
    line.pop('noWithholdingReason',None)
    prepared=client.post('/finance/purchase-intakes/prepare',headers=team['aubrey'],json=body)
    assert prepared.status_code==201,prepared.text
    bill=prepared.json()
    for actor,action in [('aubrey','submit'),('malou','approve'),('rommel','check')]:
        response=client.post(f"/finance/bills/{bill['id']}/{action}",headers=team[actor])
        assert response.status_code==200,response.text
    recorded=response.json()
    assert recorded['status']=='recorded'
    with app.state.sessions() as db:
        totals=bir_reports.purchase_journal(db,date(2026,11,1),date(2026,11,30))['totals']
    assert totals['vatableCentavos']==5000
    assert totals['inputTaxCentavos']==600
    assert totals['ewtCentavos']==50
    assert totals['payableCentavos']==5550
    voucher=prepare(client,team['cristal'],supplier,[{'billId':bill['id'],'amountCentavos':5550}])
    step(client,team['cristal'],voucher,'submit')
    step(client,team['cristal'],voucher,'release',{'paidOn':'2026-11-11','bankReference':'FICTIONAL-ROUNDTRIP'})
    books=balances(client,ana)
    assert books.get('2000',0)==0
    assert books['6500']==5000 and books['1300']==600 and books['2300']==50
    assert books['1010']==-5550
    aged=client.get('/finance/payables/aging',params={'asOf':'2026-11-11'},headers=ana)
    assert aged.status_code==200 and aged.json()['totals']['owedCentavos']==0
    remaining=client.get('/finance/purchase-intakes/'+item['id'],headers=ana).json()
    assert remaining['remaining']==10
    for key in ['bills-by-supplier','vouchers-released','trial-balance','general-ledger']:
        report=client.get('/finance/reports/'+key,params={'from':'2026-11-01','to':'2026-11-11'},headers=ana)
        assert report.status_code==200 and report.json()['rows'],(key,report.text)
