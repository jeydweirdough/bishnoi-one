"""Static draft PDF on the official vector template; never submits or persists a return."""
from io import BytesIO
from pathlib import Path
import hashlib,json,re

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

TEMPLATES = Path(__file__).parent / "templates" / "bir"
PAGE_HEIGHT = 1008
# Top coordinates measured on the official April 2024 pages, in points.
PAGE_TWO_TOPS = {"31":136.2,"32":152.1,"33":168.1,"34":184.9,"35":201.7,"36":217.7,"37":233.6,
    "38":259.9,"39":275.8,"40":291.8,"41":307.7,"42":325.0,"43":340.9,
    "44":371.2,"45":387.2,"46":403.1,"47":419.1,"48":435.0,"49":451.0,"50":468.1,"51":485.2,
    "52":511.8,"53":528.6,"54":544.6,"55":560.5,"56":576.5,"57":592.4,"58":608.4,"59":624.3,"60":640.3,"61":656.2}
PAGE_ONE_TOPS = {"15":346.4,"16":377.3,"17":394.8,"18":412.4,"19":430.0,"20":447.6,"21":465.2,
    "22":482.8,"23":500.4,"24":518.0,"25":535.6,"26":553.2}


def _money(c, cents, column, top):
    if type(cents) is not int:
        raise ValueError("PDF amounts must use integer centavos.")
    whole, fractional = divmod(abs(cents),100)
    digits = ("-" if cents < 0 else "") + str(whole)
    if len(digits)>12:
        raise ValueError("Amount exceeds the official form's printed cells.")
    last,first_cent = (325.8,354.7) if column=="A" else (539.5,568.5)
    c.setFillColor(colors.black);c.setFont("Courier-Bold",9)
    baseline=PAGE_HEIGHT-top-7
    for i,digit in enumerate(reversed(digits)):c.drawCentredString(last-14.25*i,baseline,digit)
    for i,digit in enumerate(f"{fractional:02}"):c.drawCentredString(first_cent+14.25*i,baseline,digit)


def _fit(c,text,x,top,width,size=10):
    # Shrink only within a readable range; never silently clip names or addresses.
    from reportlab.pdfbase.pdfmetrics import stringWidth
    text=str(text or "").upper()
    if not text:return
    while size>6 and stringWidth(text,"Helvetica",size)>width:size-=.25
    if stringWidth(text,"Helvetica",size)>width:
        raise ValueError("Text does not fit the official form; review its full value before printing.")
    c.setFillColor(colors.black);c.setFont("Helvetica",size);c.drawString(x,PAGE_HEIGHT-top-size,text)


def _header(c,draft,page):
    who=draft["taxpayer"]
    rdo=str(who.get("rdoCode") or "").upper()
    if rdo and not re.fullmatch(r"\d{2}[0-9A-Z]",rdo):raise ValueError("RDO does not fit its three printed cells.")
    tin_digits=re.sub(r"\D","",who.get("tin") or "")
    if tin_digits and len(tin_digits)!=9:raise ValueError("TIN requires nine main digits and a separate branch code.")
    def boxed(value,first,top):
        c.setFillColor(colors.black);c.setFont("Courier-Bold",9)
        for i,char in enumerate(value):c.drawCentredString(first+14.25*i,PAGE_HEIGHT-top-7,char)
    if page==0:
        boxed(f"{who.get('fiscalMonthEnd',12):02}{draft['year']}",312.5,112)
        boxed(draft["period"]["start"][5:7]+draft["period"]["start"][8:10]+draft["period"]["start"][:4],70.5,141)
        boxed(draft["period"]["end"][5:7]+draft["period"]["end"][8:10]+draft["period"]["end"][:4],211.5,141)
        c.setFont("Helvetica-Bold",10)
        c.drawString(78 if who.get("fiscalMonthEnd",12)==12 else 145,PAGE_HEIGHT-121,"X")
        c.drawString((439,477,520,561)[draft["quarter"]-1],PAGE_HEIGHT-121,"X")
        _fit(c,who.get("registeredName"),25,200,562)
        _fit(c,who.get("address"),25,229,562,9)
        boxed(str(who.get("rdoCode") or "").upper(),554.5,173)
        tin=re.sub(r"\D","",who.get("tin") or "")
        if len(tin)==9:
            for i,ch in enumerate(tin):
                group,offset=divmod(i,3)
                c.setFont("Courier-Bold",9);c.drawCentredString((240.5,297.7,354.9)[group]+offset*14.15,PAGE_HEIGHT-180,ch)
    else:
        _fit(c,who.get("registeredName"),225,91,360)
        tin=re.sub(r"\D","",who.get("tin") or "")
        if len(tin)==9:
            for i,ch in enumerate(tin):
                group,offset=divmod(i,3)
                c.setFont("Courier-Bold",9);c.drawCentredString(29+group*43+offset*14.25,PAGE_HEIGHT-101,ch)
    # The official background preprints branch 00000; never print the wrong branch.
    if who.get("branchCode","00000")!="00000":
        raise ValueError("Non-zero branch needs a reviewed branch-cell layout before printing this draft.")


def _appendix(draft,template_hash):
    styles=getSampleStyleSheet();normal=styles["BodyText"];normal.fontSize=9;normal.leading=12
    buf=BytesIO();doc=SimpleDocTemplate(buf,pagesize=(612,1008),leftMargin=36,rightMargin=36,topMargin=30,bottomMargin=30)
    story=[Paragraph("2550Q - source-to-form review sheet",styles["Title"]),
           Paragraph("DRAFT / TEST DATA - NOT FOR FILING",styles["Heading2"]),
           Paragraph("Period: "+draft["period"]["start"]+" to "+draft["period"]["end"]+" | "+draft["version"],normal),Spacer(1,12)]
    table=[["Form field","Amount and meaning","PHP"]]
    for key,field in draft["fields"].items():
        if field["valueCentavos"] is not None:
            v=field["valueCentavos"]
            table.append([key,Paragraph(field["label"],normal),f"{'-' if v<0 else ''}{abs(v)//100:,}.{abs(v)%100:02}"])
    t=Table(table,colWidths=[62,360,118],repeatRows=1,hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e6eef3")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
      ("FONTSIZE",(0,0),(-1,-1),9),("ALIGN",(-1,1),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"TOP"),
      ("BOTTOMPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("LINEBELOW",(0,0),(-1,-1),.3,colors.lightgrey)]))
    story += [t,Spacer(1,12),Paragraph("Unresolved fields remain blank",styles["Heading2"])]
    pending=[k for k,v in draft["fields"].items() if v["valueCentavos"] is None]
    story.append(Paragraph(", ".join(pending),normal))
    story.append(Paragraph("Confirm prior-quarter credits, 2024 adjustment eligibility, exempt-sales allocation and actual remittances/payments. Background items also need review: amended/short-period declarations, taxpayer classification, tax relief, ZIP, contact and email. An unpaid balance alone does not justify a VAT adjustment. Do not sign this draft.",normal))
    story += [Spacer(1,10),Paragraph("Where the figures came from",styles["Heading2"]),
       Paragraph("Sales are mapped from the existing quarterly VAT report. Purchase fields are filled only for an explicitly confirmed all-domestic scenario; otherwise they remain blank. Each field and its source are also in the companion field map. Existing report reversal/coverage gaps require separate review.",normal),
       Paragraph("The original BIR template and its barcode images are preserved. No new barcode, signature, payment reference or filing receipt is generated.",normal),
       Paragraph("Template source: BIR 2550Q April 2024 ENCS. SHA-256: "+template_hash,normal),
       Spacer(1,12),Paragraph("Sir Mel's check",styles["Heading2"]),
       Paragraph("Compare source documents, account codes, dates, approved status and ledger entries to every filled field. Record a difference; never change expected answers just to match this PDF. Actual/expected values and the reviewer decision must be checked before a later filing workflow.",normal)]
    doc.build(story);return PdfReader(BytesIO(buf.getvalue()))


def render_draft(draft:dict)->bytes:
    if not draft.get("draftOnly") or draft.get("readyForFiling"):
        raise ValueError("This renderer only creates review drafts.")
    raw=(TEMPLATES/"2550q-2024-04.pdf").read_bytes()
    provenance=json.loads((TEMPLATES/"2550q-2024-04.source.json").read_text(encoding="utf-8"))
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=provenance["sha256"]:raise ValueError("Official template checksum changed.")
    reader=PdfReader(BytesIO(raw))
    if len(reader.pages)!=2 or reader.get_fields():raise ValueError("Unexpected official template structure.")
    writer=PdfWriter()
    for index,page in enumerate(reader.pages):
        if list(page.mediabox)!=[0,0,612,1008]:raise ValueError("Unexpected page size.")
        overlay=BytesIO();c=canvas.Canvas(overlay,pagesize=(612,1008),invariant=1)
        _header(c,draft,index)
        for key,field in draft["fields"].items():
            if field["valueCentavos"] is None:continue
            if index==1 and key[-1:] in ("A","B"):
                _money(c,field["valueCentavos"],key[-1],PAGE_TWO_TOPS[key[:-1]])
            elif index==0 and key in PAGE_ONE_TOPS:_money(c,field["valueCentavos"],"B",PAGE_ONE_TOPS[key])
        c.setFillColor(colors.HexColor("#9b2525"));c.setFont("Helvetica-Bold",9)
        c.drawCentredString(306,18,"DRAFT / TEST ONLY - NOT FOR FILING - BLANKS NEED REVIEW")
        c.save();page.merge_page(PdfReader(BytesIO(overlay.getvalue())).pages[0]);writer.add_page(page)
    for page in _appendix(draft,digest).pages:writer.add_page(page)
    writer.add_metadata({"/Title":"2550Q review draft - not for filing","/Subject":"Official April 2024 background with review-only data"})
    result=BytesIO();writer.write(result);return result.getvalue()
