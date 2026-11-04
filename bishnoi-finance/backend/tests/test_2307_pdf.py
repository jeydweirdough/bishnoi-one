from copy import deepcopy
from io import BytesIO
import pytest
from pypdf import PdfReader
from app.bir_form_2307 import prepare,render


def report():
    return {'period':{'start':'2026-01-01','end':'2026-03-31'},'taxpayer':{'registeredName':'TEST ONLY COMPANY','tin':'111222333','branchCode':'00000','address':'FICTIONAL ADDRESS'},'certificate':{'payee':{'name':'TEST ONLY SUPPLIER','tin':'222333444','branchCode':'00000','address':'FICTIONAL SUPPLIER ADDRESS'},'rows':[{'atc':'WC160','nature':'Services, from a company (top withholding agent)','rateBp':200,'months':[100000,0,50000],'baseCentavos':150000,'taxCentavos':3000}],'totals':{'baseCentavos':150000,'taxCentavos':3000}}}


def test_quarterly_certificate_preserves_months_and_totals_and_barcode_background():
    r=report();d=prepare(r);assert d['certificate']['rows'][0]['months']==[100000,0,50000]
    assert d['readyForFiling'] is False and d['electronicAcceptance']=='not_verified'
    raw=render(d);p=PdfReader(BytesIO(raw));assert len(p.pages)==2
    t=p.pages[0].extract_text();assert '1,500.00'in t and '30.00'in t and 'WC160'in t
    assert 'NOT FOR FILING'in t and not p.get_fields()


def test_missing_store_identity_stays_missing_not_invented():
    r=report();r['certificate']['payee']['address']=None;r['certificate']['payee']['branchCode']=None
    d=prepare(r);assert 'Payee: address'in d['missing'] and 'Payee: branchCode'in d['missing']
    assert d['certificate']['payee']['address'] is None


def test_bad_months_totals_and_overflow_are_refused_without_silent_truncation():
    r=report();r['certificate']['rows'][0]['months']=[1,2,3]
    with pytest.raises(ValueError,match='Monthly'):prepare(r)
    r=report();r['certificate']['rows']*=11
    with pytest.raises(ValueError,match='continuation'):prepare(r)
    r=report();r['certificate']['rows'][0]['taxCentavos']=30.00
    with pytest.raises(ValueError,match='integer'):prepare(r)


def test_full_source_tin_retains_its_embedded_branch_and_rejects_conflicts():
    r=report();r['certificate']['payee']['tin']='222-333-444-00000'
    d=prepare(r);assert d['certificate']['payee']['tin']=='222333444'
    assert d['certificate']['payee']['branchCode']=='00000'
    r['certificate']['payee']['branchCode']='00001'
    with pytest.raises(ValueError,match='disagrees'):prepare(r)
