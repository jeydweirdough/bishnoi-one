"""Review draft on disposable databases; no official or active test data."""
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
import csv,json
import pytest
from pypdf import PdfReader
from sqlalchemy import select,func
from app.bir_form_2550q import build_draft
from app.bir_pdf import render_draft
from app.models import TaxProfile, JournalEntry, Invoice, ImportMatch
from app.ledger import settings as posting_settings
from .test_concurrent_saves import app
from .test_tax_api import ana,client
from .test_fictional_import_pack import PACK, test_exported_fictional_pack_matches_independent_answers as rehearse_pack


def source(client,ana,app):
    rehearse_pack(client,ana,app)
    with app.state.sessions() as db:
        who=db.get(TaxProfile,1)
        who.registered_name='TEST ONLY - FICTIONAL COMPANY'
        who.registered_address='FICTIONAL TEST ADDRESS - NOT FOR FILING'
        who.tin='111-222-333';who.branch_code='00000';who.rdo_code='000'
        db.commit()
    result=client.get('/finance/bir/returns/vat?year=2026&quarter=1',headers=ana)
    assert result.status_code==200,result.text
    return result.json()


def test_form_maps_actual_imports_without_inventing_missing_tax_data(client,ana,app,tmp_path):
    report=source(client,ana,app)
    draft=build_draft(report)
    assert draft['fields']['31A']['valueCentavos']==300000
    assert draft['fields']['31B']['valueCentavos']==36000
    assert draft['sourceNotes']['inputVatCentavos']==25200
    assert draft['fields']['44A']['valueCentavos'] is None
    for key in ('35B','38B','53B','55B','58B','61B','15','26'):
        assert draft['fields'][key]['valueCentavos'] is None
    assert draft['readyForFiling'] is False
    confirmed=build_draft(report,domestic_purchases_confirmed=True)
    pack=PACK
    independent=json.loads((pack/'expected-before-import.json').read_text(encoding='utf-8'))['expected']
    targets={'31A':independent['salesNet'],'31B':independent['outputVat'],'32A':0,'33A':0,
             '34A':independent['salesNet'],'34B':independent['outputVat'],
             '44A':independent['billNet']+independent['expenseNet'],'44B':independent['inputVat'],
             '50A':independent['billNet']+independent['expenseNet'],'50B':independent['inputVat']}
    for key,value in targets.items():assert confirmed['fields'][key]['valueCentavos']==value
    assert confirmed['fields']['44A']['valueCentavos']==210000
    assert confirmed['fields']['44B']['valueCentavos']==25200
    assert confirmed['fields']['50A']['valueCentavos']==210000
    assert confirmed['fields']['50B']['valueCentavos']==25200
    document=render_draft(confirmed)
    pdf=PdfReader(BytesIO(document))
    assert len(pdf.pages)==3
    assert not pdf.get_fields()
    assert all(not any(a.get_object().get('/Subtype')=='/Widget' for a in page.get('/Annots',[])) for page in pdf.pages)
    text='\n'.join(p.extract_text() for p in pdf.pages)
    assert 'NOT FOR FILING' in text and '2,100.00' in text and '252.00' in text
    assert 'Unresolved fields remain blank' in text
    # Fictional demonstrator only. The output is not obtained from the active database.
    output=tmp_path/'pdf'
    output.mkdir(parents=True,exist_ok=True)
    (output/'2550Q-fictional-review-draft.pdf').write_bytes(document)
    (output/'2550Q-fictional-review-data.json').write_text(json.dumps(confirmed,indent=2),encoding='utf-8')
    with (output/'2550Q-field-map.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['Field','Meaning','PDF PHP (blank means unresolved)','Independent expected PHP (test scenario only)','Sir Mel finding','Status','Source / review requirement'])
        for key,value in confirmed['fields'].items():
            amount=value['valueCentavos']
            expected=targets.get(key)
            w.writerow([key,value['label'],f'{amount/100:.2f}' if amount is not None else '',f'{expected/100:.2f}' if expected is not None else '', '',value['status'],value['source']])


def test_draft_download_does_not_change_closed_books_or_approve_records(client,ana,app):
    source(client,ana,app)
    def saved():
        with app.state.sessions() as db:
            return (posting_settings(db).locked_until,
                db.scalar(select(func.count()).select_from(JournalEntry)),
                [(i.id,i.status,i.paid_centavos) for i in db.scalars(select(Invoice).order_by(Invoice.id))],
                [(m.id,m.status,m.account_id) for m in db.scalars(select(ImportMatch).order_by(ImportMatch.id))])
    with app.state.sessions() as db:
        posting_settings(db).locked_until=date(2026,3,31);db.commit()
    before=saved()
    r=client.get('/finance/bir/returns/vat/draft.pdf?year=2026&quarter=1',headers=ana)
    assert r.status_code==200,r.text
    assert r.headers['content-type']=='application/pdf' and r.headers['cache-control']=='no-store'
    assert len(PdfReader(BytesIO(r.content)).pages)==3
    assert before==saved()
    assert client.get('/finance/bir/returns/vat/draft.pdf?year=2026&quarter=1').status_code in (401,403)


def test_form_refuses_wrong_period_inconsistent_totals_and_float_amounts(client,ana,app):
    report=source(client,ana,app)
    cases=[]
    wrong=deepcopy(report);wrong['quarter']=2;cases.append(wrong)
    wrong=deepcopy(report);wrong['form']='2551Q';cases.append(wrong)
    wrong=deepcopy(report);wrong['lines'][0]['amountCentavos']=0.1;cases.append(wrong)
    wrong=deepcopy(report)
    next(x for x in wrong['lines'] if x['key']=='total_sales')['amountCentavos']+=1;cases.append(wrong)
    for wrong in cases:
        with pytest.raises(ValueError):build_draft(wrong)
    wrong=deepcopy(report)
    next(x for x in wrong['lines'] if x['key']=='importation_purchases')['amountCentavos']=100
    with pytest.raises(ValueError):build_draft(wrong,domestic_purchases_confirmed=True)
    credit=deepcopy(report)
    for line in credit['lines']:
        if line['key'] in ('taxable','total_sales'):line['amountCentavos']=-300000
        if line['key']=='output':line['amountCentavos']=-36000
    negative=build_draft(credit)
    assert negative['fields']['31B']['valueCentavos']==-36000
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_draft(negative))).pages)
    assert '-3,000.00' in text and '-360.00' in text  # never turn a credit into a positive amount
    assert negative['fields']['26']['valueCentavos'] is None
    huge=build_draft(report);huge['fields']['31A']['valueCentavos']=10**16
    with pytest.raises(ValueError):render_draft(huge)
    wrong=deepcopy(report);wrong['lines'].append(deepcopy(wrong['lines'][0]))
    with pytest.raises(ValueError):build_draft(wrong)
    draft=build_draft(report);draft['taxpayer']['registeredName']='VERY LONG NAME '*40
    with pytest.raises(ValueError):render_draft(draft)
