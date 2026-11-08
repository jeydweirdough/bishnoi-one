from .test_tax_api import app,client,ana,ben


def test_new_draft_routes_use_existing_bir_permission_and_pdf_content(client,ana):
    for form in ['0619e','1601eq','1604e']:
        path=f'/finance/bir/withholding/{form}/draft.pdf?year=2026&month=1&quarter=1'
        assert client.get(path).status_code==401
        r=client.get(path,headers=ana)
        assert r.status_code==200,r.text
        assert r.headers['content-type']=='application/pdf' and r.content.startswith(b'%PDF-')
        assert r.headers['cache-control']=='no-store'
    assert client.get('/finance/bir/withholding/0619e/draft.pdf?year=2026&month=3',headers=ana).status_code==422
    assert client.get('/finance/bir/withholding/0619e/draft.pdf?year=0&month=1',headers=ana).status_code==422
    assert client.get('/finance/bir/withholding/2307/draft.pdf?year=2026&quarter=1&supplierId=missing',headers=ana).status_code==404


def test_existing_no_bir_access_is_preserved(client,ana):
    from .test_dashboard import person
    no_bir=person(client,ana,'No BIR PDF access',['dashboard.view'])
    for form in ['2307','0619e','1601eq','1604e']:
        assert client.get(f'/finance/bir/withholding/{form}/draft.pdf?year=2026&month=1&quarter=1&supplierId=none',headers=no_bir).status_code==403


def test_pdf_preparation_is_not_reported_as_validation_or_filing(client,ana):
    for form in ['2550Q','2307','0619E','1601EQ','1604E']:
        r=client.get('/finance/bir/filing-guidance?form='+form,headers=ana)
        assert r.status_code==200
        d=r.json();assert d['readyForFiling'] is False and d['electronicValidationStatus']=='not_verified'
        assert d['filingEvidenceStatus']=='not_recorded_in_finance' and d['directElectronicFileGenerated'] is False
        if form=='2307':assert d['kind']=='certificate'
