"""Directory-first imports need no vendor-by-vendor accounting decisions."""
from app.models import Supplier
from .test_tax_api import app, ana, ben, client  # noqa: F401
from .test_payables import account
from .test_dashboard import VIEW, person


def check(client, who, rows):
    r=client.post('/finance/suppliers/import/check',headers=who,json={'rows':rows})
    assert r.status_code==200,r.text
    return r.json()


def test_directory_import_without_row_reviews_and_repeat_is_idempotent(client,ana):
    rows=[{'name':f'Fictional directory vendor {i}','terms':'30','contactNumber':'09990000000'} for i in range(200)]
    preview=check(client,ana,rows)
    assert preview['counts']['new']==200
    response=client.post('/finance/suppliers/import',headers=ana,json={'rows':rows,'confirmed':True})
    assert response.status_code==201,response.text
    assert response.json()['added']==200
    again=client.post('/finance/suppliers/import',headers=ana,json={'rows':rows,'confirmed':True})
    assert again.json()['added']==0 and again.json()['counts']['here']==200
    saved=client.get('/finance/suppliers',headers=ana).json()['items']
    assert len(saved)==200 and all(not s['taxDefaultsConfirmed'] for s in saved)
    assert all(s['contacts'][0]['phone']=='09990000000' for s in saved)


def test_invalid_tin_and_overflow_are_retained_not_blocked_and_conflicts_are_skipped(client,ana):
    rows=[{'name':'Retained source','tin':'bad-original','notes':'x'*600,'contactNumber':'1'*50,'taxName':'No Tax','terms':'120','termsLabel':'COD'},
          {'name':'Repeated directory name','tin':'12345678900000'}, {'name':'Repeated directory name','tin':'12345678900000'},
          {'name':'Conflicting identity','tin':'22233344400000'}, {'name':'Conflicting identity','tin':'33344455500000'}, {'name':''}]
    preview=check(client,ana,rows)
    assert preview['counts']=={'new':2,'here':0,'duplicate':1,'conflict':2,'problem':1}
    data=preview['rows'][0]
    assert data['supplier']['tin'] is None and data['supplier']['notes'] is None
    assert data['importDetails']['unresolved']['tinCandidates']==['bad-original']
    assert data['importDetails']['unresolved']['additionalNumbers'][0]['phone']=='1'*50
    response=client.post('/finance/suppliers/import',headers=ana,json={'rows':rows,'confirmed':True})
    assert response.status_code==201 and response.json()['added']==2
    saved=next(s for s in client.get('/finance/suppliers',headers=ana).json()['items'] if s['name']=='Retained source')
    assert saved['importDetails']['hints']['tax_name']=='No Tax' and not saved['taxDefaultsConfirmed']


def test_unknown_bill_defaults_require_explicit_document_choices_and_cannot_grant_master_edit(client,ana):
    imported=client.post('/finance/suppliers/import',headers=ana,json={'rows':[{'name':'First use example'}],'confirmed':True})
    assert imported.status_code==201
    vendor=client.get('/finance/suppliers',headers=ana).json()['items'][0]
    maker=person(client,ana,'Creates bills only',VIEW+['suppliers.view','bills.view','bills.create'])
    line={'accountId':account(client,ana,'6500'),'amountCentavos':10000,'vat':'none','withholding':None}
    body={'supplierId':vendor['id'],'billNumber':'TEST-FIRST-USE','billDate':'2026-10-01','lines':[line]}
    response=client.post('/finance/bills',headers=maker,json=body); assert response.status_code==201,response.text
    bill=response.json(); assert not bill['taxReviewed']
    assert client.post(f"/finance/bills/{bill['id']}/submit",headers=maker).status_code==409
    # A boolean alone does not certify silently defaulted line VAT/withholding.
    omitted=body|{'taxReviewed':True,'lines':[{'accountId':line['accountId'],'amountCentavos':10000}]}
    response=client.put(f"/finance/bills/{bill['id']}",headers=maker,json=omitted)
    assert response.status_code==200 and not response.json()['taxReviewed']
    attempts=body|{'taxReviewed':True,'saveSupplierDefaults':True,'supplierVatRegistered':False,'supplierWithholding':None}
    assert client.put(f"/finance/bills/{bill['id']}",headers=maker,json=attempts).status_code==403
    response=client.put(f"/finance/bills/{bill['id']}",headers=maker,json=body|{'taxReviewed':True})
    assert response.status_code==200 and response.json()['taxReviewed']
    assert not response.json()['supplier']['taxDefaultsConfirmed']
    # Editing without a fresh document review clears the flag.
    response=client.put(f"/finance/bills/{bill['id']}",headers=maker,json=body)
    assert not response.json()['taxReviewed']
    response=client.put(f"/finance/bills/{bill['id']}",headers=ana,json=attempts)
    assert response.status_code==200 and response.json()['supplier']['taxDefaultsConfirmed']
    assert response.json()['supplier']['vatRegistered'] is False
    assert client.post(f"/finance/bills/{bill['id']}/submit",headers=maker).status_code==200
