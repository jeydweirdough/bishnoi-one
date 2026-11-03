"""2307 certificate on the official BIR January 2018 v3 background.

Uses quarter/payee/ATC aggregation from the reports, never reclassifies a receipt
or manufactures remittances, addresses, signatures or electronic acceptance.
"""
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
from decimal import Decimal
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth

TEMPLATES = Path(__file__).parent / 'templates/bir'
TIN_X = (213.4,226.6,239.7,264.9,278.1,291.3,316.5,329.7,342.9)
BRANCH_X = (368.7,383.6,398.7,414.4,428.7)
FROM_X = (157.9,171.5,185.1,197.9,210.6,224.0,237.5,250.5)
TO_X = tuple(x+247.6 for x in FROM_X)
HEIGHT = 936

def _integer(v):
    if type(v) is not int:
        raise ValueError('Certificate amounts must be integer centavos.')
    return v

def prepare(report: dict) -> dict:
    c = deepcopy(report['certificate'])
    start,end = [date.fromisoformat(report['period'][k]) for k in ('start','end')]
    if start>end:
        raise ValueError('Invalid certificate period.')
    if len(c['rows'])>10:
        raise ValueError('More than 10 ATC rows need a reviewed continuation schedule; no rows were dropped.')
    base,tax = 0,0
    for row in c['rows']:
        if len(row['months'])!=3 or sum(_integer(x) for x in row['months'])!=_integer(row['baseCentavos']):
            raise ValueError('Monthly certificate bases do not equal the total.')
        base+=row['baseCentavos'];tax+=_integer(row['taxCentavos'])
        if not re.fullmatch(r'[A-Z]{2}\d{3}',row['atc'] or ''):
            raise ValueError('Each withholding row needs a supported ATC.')
    if (base,tax)!=(_integer(c['totals']['baseCentavos']),_integer(c['totals']['taxCentavos'])):
        raise ValueError('Certificate rows disagree with totals.')
    missing=[]
    who=deepcopy(report['taxpayer']);payee=c['payee']
    for label,party in [('Payor',who),('Payee',payee)]:
        source_digits=re.sub(r'\D','',party.get('tin') or '')
        if len(source_digits)==14:
            embedded=source_digits[9:]
            if party.get('branchCode') and party['branchCode']!=embedded:
                raise ValueError(f'{label} TIN branch disagrees with its separate branch field.')
            party['tin']=source_digits[:9];party['branchCode']=embedded
        for field in ('tin','address','branchCode'):
            if not party.get(field):missing.append(f'{label}: {field}')
        if not (party.get('registeredName') or party.get('name')):missing.append(f'{label}: registered name')
        digits=re.sub(r'\D','',party.get('tin') or '')
        if digits and len(digits)!=9:raise ValueError(f'{label} TIN must contain nine main digits; branch is separate.')
        branch=party.get('branchCode')
        if branch and not re.fullmatch(r'\d{5}',branch):raise ValueError(f'{label} branch must contain five digits.')
    return {'form':'2307','version':'January 2018 (ENCS), v3','period':report['period'],
            'taxpayer':who,'certificate':c,'missing':missing,'draftOnly':True,
            'readyForFiling':False,'electronicAcceptance':'not_verified',
            'notes':['No signature or payment evidence is generated. Missing identity fields remain blank.',
                     'An official-template PDF is not an electronically filed or accepted return.']}

def _fit(c,text,x,baseline,width,size=9):
    text=str(text or '').upper()
    while size>=6 and stringWidth(text,'Helvetica',size)>width:size-=.25
    if size<6:raise ValueError('Text does not fit the certificate; it was not truncated.')
    c.setFont('Helvetica',size);c.drawString(x,HEIGHT-baseline,text)

def _nature(c,text,x,baseline,width):
    text=str(text or '').upper()
    if stringWidth(text,'Helvetica',7)<=width:
        _fit(c,text,x,baseline,width,7);return
    lines=[];line=''
    for word in text.split():
        trial=(line+' '+word).strip()
        if stringWidth(trial,'Helvetica',6)>width:
            if not line:raise ValueError('Nature of payment contains a word wider than its field.')
            lines.append(line);line=word
        else:line=trial
    if line:lines.append(line)
    if len(lines)>2:raise ValueError('Nature of payment needs a reviewed continuation; no text was truncated.')
    for i,line in enumerate(lines):_fit(c,line,x,baseline-4.3+i*6.3,width,6)

def _boxes(c,text,centres,baseline):
    if len(text)>len(centres):raise ValueError('Certificate value exceeds its printed boxes.')
    c.setFont('Courier-Bold',9)
    for x,ch in zip(centres,text):c.drawCentredString(x,HEIGHT-baseline,ch)

def render(draft: dict) -> bytes:
    if draft.get('form')!='2307' or not draft.get('draftOnly') or draft.get('readyForFiling'):
        raise ValueError('This endpoint produces review certificates only.')
    raw=(TEMPLATES/'2307-2018-01.pdf').read_bytes()
    provenance=json.loads((TEMPLATES/'2307-2018-01.source.json').read_text())
    if hashlib.sha256(raw).hexdigest()!=provenance['sha256']:raise ValueError('Official 2307 template checksum changed.')
    reader=PdfReader(BytesIO(raw));page=reader.pages[0]
    if list(page.mediabox)!=[0,0,612,936]:raise ValueError('Unexpected certificate page geometry.')
    buf=BytesIO();c=canvas.Canvas(buf,pagesize=(612,936),invariant=1)
    for key,centres in [('start',FROM_X),('end',TO_X)]:
        d=date.fromisoformat(draft['period'][key]);_boxes(c,d.strftime('%m%d%Y'),centres,118)
    for party,tin_y,name_y,address_y in [(draft['certificate']['payee'],150,175,204),(draft['taxpayer'],265,290,319)]:
        _boxes(c,re.sub(r'\D','',party.get('tin') or ''),TIN_X,tin_y)
        _boxes(c,party.get('branchCode') or '',BRANCH_X,tin_y)
        _fit(c,party.get('registeredName') or party.get('name'),37,name_y,552)
        _fit(c,party.get('address'),37,address_y,495,8)
    cert=draft['certificate']
    for index,row in enumerate(cert['rows']):
        baseline=375.3+index*13.68
        _nature(c,row['nature'],21,baseline,153)
        _fit(c,row['atc'],181,baseline,34,8)
        c.setFont('Helvetica',8)
        for right,value in zip((289,363.4,435.5,507.5,592),[*row['months'],row['baseCentavos'],row['taxCentavos']]):
            amount=f'{Decimal(_integer(value))/100:,.2f}'
            if stringWidth(amount,'Helvetica',8)>63:raise ValueError('Certificate amount exceeds its column.')
            c.drawRightString(right,HEIGHT-baseline,amount)
    c.setFont('Helvetica-Bold',8)
    totals=[sum(r['months'][i] for r in cert['rows']) for i in range(3)]+[cert['totals']['baseCentavos'],cert['totals']['taxCentavos']]
    for right,value in zip((289,363.4,435.5,507.5,592),totals):
        amount=f'{Decimal(_integer(value))/100:,.2f}'
        if stringWidth(amount,'Helvetica-Bold',8)>63:raise ValueError('Certificate total exceeds its column.')
        c.drawRightString(right,HEIGHT-512,amount)
    c.setFillColor(HexColor('#9B2525'));c.setFont('Helvetica-Bold',8)
    c.drawCentredString(306,40,'DRAFT / REVIEW ONLY - NOT FOR FILING - NO SIGNATURE')
    if draft['missing']:
        _fit(c,'MISSING: '+', '.join(draft['missing']),20,910,574,7)
    c.save();page.merge_page(PdfReader(BytesIO(buf.getvalue())).pages[0])
    writer=PdfWriter();writer.add_page(page)
    # Keep the government's ATC reference page unchanged, rather than replacing it
    # with a copied Oojeema barcode or custom table.
    for p in reader.pages[1:]:writer.add_page(p)
    writer.add_metadata({'/Title':'2307 review certificate - not for filing'})
    out=BytesIO();writer.write(out);return out.getvalue()
