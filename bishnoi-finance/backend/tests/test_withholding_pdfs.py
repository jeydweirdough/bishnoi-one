from datetime import date
from io import BytesIO
from pypdf import PdfReader
import pytest
from app.bir_withholding_pdf import prepare,render

WHO={'registeredName':'TEST ONLY COMPANY','tin':'111222333','branchCode':'00000','rdoCode':'53A','address':'FICTIONAL ADDRESS'}
ROW={'atc':'WC160','nature':'Services','rateBp':200,'baseCentavos':100000,'taxCentavos':2000}


def source(form):
    p={'start':'2026-01-01','end':'2026-01-31' if form=='0619E' else ('2026-03-31' if form=='1601EQ' else '2026-12-31')}
    d={'form':form,'taxpayer':WHO,'period':p,'year':2026,'quarter':1,'rows':[ROW.copy()],'totalCentavos':2000}
    if form=='1604E':d.update(payees=[ROW|{'payee':'TEST ONLY SUPPLIER','tin':'222333444'}],totals={'baseCentavos':100000,'taxCentavos':2000})
    return d


@pytest.mark.parametrize('form,pages',[('0619E',1),('1601EQ',2),('1604E',3)])
def test_official_background_review_output_preserves_supported_amounts(form,pages):
    d=prepare(source(form));pdf=PdfReader(BytesIO(render(d)))
    assert len(pdf.pages)==pages
    text=' '.join(p.extract_text() for p in pdf.pages)
    assert 'NOT FOR FILING'in text and d['readyForFiling'] is False
    assert d['electronicAcceptance']=='not_verified'
    if form=='1604E':assert '20.00'in text and 'TEST ONLY SUPPLIER'in text


def test_third_month_cannot_be_exported_as_monthly_filing_and_quarter_must_match():
    d=source('0619E');d['period']={'start':'2026-03-01','end':'2026-03-31'}
    with pytest.raises(ValueError,match='third month'):prepare(d)
    d=source('1601EQ');d['quarter']=2
    with pytest.raises(ValueError,match='calendar quarter'):prepare(d)


def test_remittances_never_inferred_and_overflow_is_refused():
    d=prepare(source('1601EQ'))
    assert 'dueCentavos' not in d and 'remitted' not in d
    d=source('1601EQ');d['rows']*=7;d['totalCentavos']=14000
    with pytest.raises(ValueError,match='continuation'):prepare(d)
    d=source('0619E');d['rows'][0]['taxCentavos']=20.0
    with pytest.raises(ValueError,match='integer'):prepare(d)


def test_any_withheld_does_not_turn_no_when_positive_and_negative_rows_net_to_zero():
    d=source('1601EQ');d['rows']=[ROW.copy(),ROW|{'atc':'WC158','taxCentavos':-2000,'baseCentavos':-100000}];d['totalCentavos']=0
    assert prepare(d)['anyTaxesWithheld'] is True
