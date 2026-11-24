"""Official-background withholding review PDFs, with no assumed remittances.

Rendering is distinct from electronic validation, filing and payment. Saved
filing evidence is a separate workflow; these GETs cannot alter the books.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from modules.finance.bir_form_2307 import _integer
from modules.finance import bir_reports as bir

TEMPLATES=Path(__file__).parent/'templates/bir'
FILES={'0619E':'0619e-2018-01','1601EQ':'1601eq-2019-01','1604E':'1604e-2018-01'}

def prepare(report:dict)->dict:
    d=deepcopy(report);form=d['form']
    if form not in FILES:raise ValueError('Unsupported withholding form.')
    start,end=[date.fromisoformat(d['period'][k]) for k in ('start','end')]
    if start>end:raise ValueError('Invalid withholding period.')
    if form=='0619E':
        if start.day!=1 or end!=bir.month_end(start.year,start.month):raise ValueError('Monthly withholding needs one complete calendar month.')
        if start.month%3==0:raise ValueError('The third month belongs to the quarterly 1601EQ, not a monthly 0619E filing.')
    elif form=='1601EQ':
        p=bir.quarter(d['year'],d['quarter'],12)
        if (start,end)!=(p.start,p.end):raise ValueError('Expanded withholding must use the selected calendar quarter.')
    elif (start,end)!=(date(d['year'],1,1),date(d['year'],12,31)):
        raise ValueError('Verify the annual withholding calendar-year source period.')
    rows=d['payees'] if form=='1604E' else d['rows']
    total=0
    for row in rows:
        _integer(row['baseCentavos']);_integer(row['rateBp']);total+=_integer(row['taxCentavos'])
        if not re.fullmatch(r'[A-Z]{2}\d{3}',row['atc'] or ''):raise ValueError('Missing or invalid withholding ATC.')
    expected=d['totals']['taxCentavos'] if form=='1604E' else d['totalCentavos']
    if total!=_integer(expected):raise ValueError('Withholding rows disagree with the total.')
    d.update(draftOnly=True,readyForFiling=False,electronicAcceptance='not_verified',anyTaxesWithheld=any(r['taxCentavos']!=0 for r in rows))
    d['missing']=['Amended-return declaration','Confirmed agent category and required registration fields',
                  'Actual remittance/payment evidence','Final review and authorised signature']
    if form=='1604E':d['missing']+=['Confirmed top-withholding-agent status','Complete-year source coverage','Validated electronic alphalist']
    return d

def _fit(c,text,x,top,width,size=9):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text=str(text or '').upper()
    while size>=6 and stringWidth(text,'Helvetica',size)>width:size-=.25
    if size<6:raise ValueError('Text exceeds official form field; it was not clipped.')
    c.setFont('Helvetica',size);c.drawString(x,c._pagesize[1]-top,text)

def _boxes(c,text,centres,top):
    if len(text)>len(centres):raise ValueError('Value exceeds printed boxes.')
    c.setFont('Courier-Bold',9)
    for x,t in zip(centres,text):c.drawCentredString(x,c._pagesize[1]-top,t)

def _money(c,value,top,*,base=False,monthly=False):
    if value is None:return
    value=_integer(value);whole,cents=divmod(abs(value),100)
    digits=('-' if value<0 else '')+str(whole)
    limit=11 if monthly else (12 if base else 11)
    if len(digits)>limit:raise ValueError('Amount exceeds printed money cells.')
    last,cent=(268.5,297.7) if base else ((543.6,571.9) if monthly else (542.2,571.7))
    c.setFont('Courier-Bold',9);h=c._pagesize[1]
    for i,ch in enumerate(reversed(digits)):c.drawCentredString(last-14.3*i,h-top,ch)
    for i,ch in enumerate(f'{cents:02}'):c.drawCentredString(cent+14.3*i,h-top,ch)

def _identity(c,who,form,page=0):
    if form=='0619E':groups=(224.8,282.6,340.6);top=178.5;name,address=(23,205),(23,234);b_first,b_step=399.5,14.3;r_first,r_step=543.5,14.3
    elif form=='1601EQ':groups=(240.5,297.7,354.9);top=157.0;name,address=(23,183.5),(23,212);b_first,b_step=412.5,14.3;r_first,r_step=557.0,14.3
    else:groups=(242.5,299.7,356.9);top=170.5;name,address=(28,201),(28,234);b_first,b_step=414.5,13.6;r_first,r_step=555.5,14.2
    tin=re.sub(r'\D','',who.get('tin') or '')
    if tin and len(tin)!=9:raise ValueError('TIN requires nine main digits and a separate five-digit branch.')
    _boxes(c,tin,[g+i*14.3 for g in groups for i in range(3)],top)
    branch=str(who.get('branchCode') or '')
    if branch and not re.fullmatch(r'\d{5}',branch):raise ValueError('Branch requires five digits.')
    _boxes(c,branch,[b_first+i*b_step for i in range(5)],top)
    rdo=re.sub(r'^0(\d{2}[0-9A-Z])$',r'\1',str(who.get('rdoCode') or '').strip().upper())
    _boxes(c,rdo,[r_first+i*r_step for i in range(3)],top)
    _fit(c,who.get('registeredName'),*name,565)
    _fit(c,who.get('address'),*address,550,8)

def _eq_continuation(d):
    from html import escape
    styles=getSampleStyleSheet();style=styles['BodyText'];style.fontSize=8;style.leading=10
    who=d['taxpayer'];tin=re.sub(r'\D','',who.get('tin') or '')
    tin_label=f"{tin[:3]}-{tin[3:6]}-{tin[6:9]}-{who.get('branchCode') or '00000'}" if len(tin)==9 else 'TIN missing'
    story=[Paragraph('1601EQ - ATC continuation schedule (draft)',styles['Title']),
           Paragraph(f"{escape(str(who.get('registeredName') or ''))} · TIN {escape(tin_label)} · {escape(str(d['period'].get('label') or ''))}",style),
           Paragraph('NOT FOR FILING. Lists all expanded withholding tax ATCs when more than six appear in the quarter. Verify inside eBIRForms before filing.',style),Spacer(1,10)]
    rows=[['ATC','Nature of income payment','Tax base PHP','Rate','Tax withheld PHP']]
    for r in d['rows']:
        rows.append([r['atc'],Paragraph(escape(str(r.get('nature') or '')),style),f"{Decimal(r['baseCentavos'])/100:,.2f}",f"{Decimal(r['rateBp'])/100}%",f"{Decimal(r['taxCentavos'])/100:,.2f}"])
    total_base=sum(_integer(r['baseCentavos']) for r in d['rows'])
    rows.append(['TOTAL','',f"{Decimal(total_base)/100:,.2f}",'',f"{Decimal(d['totalCentavos'])/100:,.2f}"])
    t=Table(rows,colWidths=[55,245,95,50,95],repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#E6EEF3')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8),('ALIGN',(2,1),(-1,-1),'RIGHT'),('LINEBELOW',(0,0),(-1,-1),.3,HexColor('#CAD4DB')),('LINEABOVE',(0,-1),(-1,-1),.8,HexColor('#4A5568')),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(t)
    b=BytesIO();SimpleDocTemplate(b,pagesize=(612,936),leftMargin=36,rightMargin=36).build(story);return PdfReader(BytesIO(b.getvalue()))

def _annual_appendix(d):
    from html import escape
    styles=getSampleStyleSheet();style=styles['BodyText'];style.fontSize=8;style.leading=10
    story=[Paragraph('1604E - calculated annual alphalist review',styles['Title']),
           Paragraph('NOT FOR FILING. Computed withholding is not proof of remittance. Complete-year coverage, actual payments and official electronic validation are not established.',style),Spacer(1,10)]
    rows=[['Payee / TIN','ATC','Income PHP','Rate','Withheld PHP']]
    for r in d['payees']:rows.append([Paragraph(escape(str(r['payee']))+'<br/>'+escape(str(r['tin'] or 'TIN missing')),style),r['atc'],f"{Decimal(r['baseCentavos'])/100:,.2f}",f"{Decimal(r['rateBp'])/100}%",f"{Decimal(r['taxCentavos'])/100:,.2f}"])
    rows.append(['TOTAL','',f"{Decimal(d['totals']['baseCentavos'])/100:,.2f}",'',f"{Decimal(d['totals']['taxCentavos'])/100:,.2f}"])
    t=Table(rows,colWidths=[245,55,90,55,95],repeatRows=1);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#E6EEF3')),('VALIGN',(0,0),(-1,-1),'TOP'),('FONTSIZE',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,HexColor('#CAD4DB')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]));story.append(t)
    b=BytesIO();SimpleDocTemplate(b,pagesize=(612,936),leftMargin=36,rightMargin=36).build(story);return PdfReader(BytesIO(b.getvalue()))

def render(d:dict)->bytes:
    if not d.get('draftOnly') or d.get('readyForFiling'):raise ValueError('Review-only form output.')
    form=d['form'];stem=FILES[form];raw=(TEMPLATES/(stem+'.pdf')).read_bytes()
    provenance=json.loads((TEMPLATES/(stem+'.source.json')).read_text())
    if hashlib.sha256(raw).hexdigest()!=provenance['sha256']:raise ValueError('Official template checksum changed.')
    reader=PdfReader(BytesIO(raw));writer=PdfWriter()
    for i,page in enumerate(reader.pages):
        width,height=map(float,(page.mediabox.width,page.mediabox.height))
        if width!=612 or height!=(792 if form=='0619E' else 936):raise ValueError('Unexpected official form page size.')
        if i>0:
            if form=='1604E':
                supplement=BytesIO();sc=canvas.Canvas(supplement,pagesize=(width,height),invariant=1)
                _fit(sc,d['taxpayer'].get('registeredName'),225,130,362)
                tin=re.sub(r'\D','',d['taxpayer'].get('tin') or '')+str(d['taxpayer'].get('branchCode') or '')
                _boxes(sc,tin,[28.5+j*13.75 for j in range(len(tin))],134.0)
                _fit(sc,'SEE ATTACHED REVIEW ALPHALIST - ELECTRONIC ACCEPTANCE NOT VERIFIED',150,229,265,6.5)
                sc.setFont('Helvetica-Bold',8)
                sc.drawRightString(442,height-271,f"{Decimal(d['totals']['baseCentavos'])/100:,.2f}")
                sc.drawRightString(584,height-271,f"{Decimal(d['totals']['taxCentavos'])/100:,.2f}")
                sc.save();page.merge_page(PdfReader(BytesIO(supplement.getvalue())).pages[0])
            writer.add_page(page);continue
        b=BytesIO();c=canvas.Canvas(b,pagesize=(width,height),invariant=1)
        _identity(c,d['taxpayer'],form)
        if form=='0619E':
            start=date.fromisoformat(d['period']['start'])
            _boxes(c,start.strftime('%m%Y'),[53.5+i*14.3 for i in range(6)],142.7)
            c.setFont('Helvetica-Bold',10);c.drawCentredString(383.5 if d['anyTaxesWithheld'] else 427.3,height-144,'X')
            _money(c,d['totalCentavos'],336.5,monthly=True)
            # Item 14 is calculated tax to remit, not an assertion that it was paid.
        elif form=='1601EQ':
            _boxes(c,str(d['year']),[39.1+i*14.3 for i in range(4)],122.2)
            c.setFont('Helvetica-Bold',10);c.drawCentredString((124.3,168.3,211.3,255.3)[d['quarter']-1],height-123.3,'X')
            c.drawCentredString(413.3 if d['anyTaxesWithheld'] else 456.3,height-123.3,'X')
            for index,r in enumerate(d['rows'][:6]):
                top=310.0+17.44*index
                _boxes(c,r['atc'],[39.1+i*14.3 for i in range(5)],top)
                _money(c,r['baseCentavos'],top,base=True)
                _fit(c,f"{Decimal(r['rateBp'])/100}%",335,top,45,8)
                _money(c,r['taxCentavos'],top)
            _money(c,d['totalCentavos'],414.7)
            if len(d['rows'])>6:
                _fit(c,f"INCLUDES {len(d['rows'])} ATCS - SEE ATTACHED CONTINUATION SCHEDULE",23,20,560,7.5)
            # Remittance deductions and remaining payable remain blank: the report
            # cannot turn calculated monthly tax into evidence of actual payment.
        else:
            year=str(d['year'])
            if not year.startswith('20'):raise ValueError('Official annual template preprints year 20; unsupported century.')
            _boxes(c,year[-2:],[179.0,197.5],131.5)
            # Both actual remittance schedules intentionally remain blank. The
            # existing annual report supplies a computed alphalist, not payments.
        c.setFillColor(HexColor('#9B2525'));c.setFont('Helvetica-Bold',8)
        c.drawCentredString(306,height-8,'DRAFT / REVIEW ONLY - NOT FOR FILING - ACTUAL PAYMENTS NOT VERIFIED')
        c.save();page.merge_page(PdfReader(BytesIO(b.getvalue())).pages[0]);writer.add_page(page)
    if form=='1604E':
        for p in _annual_appendix(d).pages:writer.add_page(p)
    elif form=='1601EQ' and len(d['rows'])>6:
        for p in _eq_continuation(d).pages:writer.add_page(p)
    writer.add_metadata({'/Title':form+' review draft - not for filing'})
    out=BytesIO();writer.write(out);return out.getvalue()
