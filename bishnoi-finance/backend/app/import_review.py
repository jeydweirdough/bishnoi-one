"""Transient, source-faithful Q1 review. Never posts or calls another application."""
from collections import Counter,defaultdict
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import csv,hashlib,io,json,re

START='2026-01-01';END='2026-03-31';OPEN='2025-12-31'
MAX_BYTES=8*1024*1024;MAX_ROWS=100_000
KINDS={'invoice':('Invoice ID','Invoice Date','Invoice Number','Customer Name','Invoice Status'),
       'bill':('Bill ID','Bill Date','Bill Number','Vendor Name','Bill Status'),
       'salesorder':('SalesOrder ID','Order Date','SalesOrder Number','Customer Name','Status'),
       'customer_payment':('CustomerPayment ID','Date','Payment Number','Customer Name','Payment Status'),
       'vendor_payment':('VendorPayment ID','Date','Payment Number','Vendor Name','Payment Status'),
       'expense':('Expense Reference ID','Expense Date','Entry Number','Vendor','')}
MONEY_FIELDS={'SubTotal','Total','Balance','Adjustment','Entity Discount Amount','Shipping Charge','Shipping Charge Tax Amount','Round Off',
              'Item Total','Item Tax Amount','Tax Amount','TDS Amount','Amount','Unused Amount','Bank Charges',
              'Amount Applied to Invoice','Withholding Tax Amount','Bill Amount','Expense Amount'}
TEXT_FIELDS={'Invoice ID','Bill ID','SalesOrder ID','CustomerPayment ID','VendorPayment ID','Expense Reference ID',
 'Invoice Date','Bill Date','Order Date','Expense Date','Date','Due Date','Invoice Number','Bill Number','SalesOrder Number','Payment Number','Entry Number',
 'Customer Name','Vendor Name','Vendor','Customer ID','CustomerID','Company ID','CF.TIN Number','Invoice Status','Bill Status','Status','Payment Status',
 'Currency Code','Exchange Rate','Is Inclusive Tax','CF.Invoicing From','CF.Company','CF.Cost Centre','Sales Order Number',
 'Item Name','Item Desc','Description','Item Tax','Tax Name','Item Tax %','Tax Percentage','TDS Name','TDS Percentage','TDS Type',
 'Account','Account Code','Expense Account','Expense Account Code','Accounts Receivable','Accounts Payable','Deposit To','Deposit To Account Code',
 'Paid Through','Paid Through Account Code','InvoicePayment ID','PIPayment ID','Invoice Payment Applied Date','Bill Payment Applied Date',
 'Reference Number','Reference#','Expense Description','Is Reimbursable','Quantity','QuantityOrdered','Item Price','Rate','Tax Type','Item Tax Type',
 'Tax ID','Shipping Charge Tax ID','Discount','Discount Amount','Item.CF.SC/PWD-Discount','Item.CF.SC/PWD-Tax','Mode'}
PRESERVE=MONEY_FIELDS|TEXT_FIELDS
ISSUES={'header_conflict':'Repeated document headers disagree.','line_totals':'Line amounts do not match the subtotal.',
 'components':'Subtotal, tax, charges and adjustments do not explain the total.','duplicate_rows':'Identical rows need review; none were removed.',
 'outside_period':'Transaction date is outside Q1.','currency':'This review supports PHP only; no conversion was assumed.',
 'company':'Company is not confirmed.','source_only':'Draft, void or cancelled source record; not eligible for posting.',
 'account':'A posting account needs matching.','allocation':'Payment allocations do not explain the cash amount and unused amount.',
 'allocation_identity':'Payment allocations have missing or repeated allocation IDs.','unallocated':'Payment contains unallocated money.',
 'missing_target':'An allocation refers to a document outside this pack.','ambiguous_target':'An allocation matches more than one document.',
 'application_date':'Payment or application date is missing, later than Q1, or before the document.',
 'mixed_payment':'This payment has mixed or unconfirmed company allocations.','tax_details':'Tax/customer classification needs review before BIR use.',
 'unsupported_components':'Nonzero discount, shipping, adjustment or withholding needs a supported posting treatment.',
 'expense_identity':'Expense reference has conflicting document headers.','control_duplicate':'Control has repeated party/reference rows; not merged.',
 'missing_reference':'A document reference is missing.','nonpositive':'Zero or negative source amounts require a separate treatment.'}
ISSUES['unsupported_financial']='A populated financial field has no supported treatment yet; review its column coverage.'
ISSUES['field_length']='A source identity, name or number is too long for the accounting model; it was not truncated.'
ISSUES['payment_method']='The exported payment method needs an explicit supported classification.'
ISSUES['withholding_evidence']='Withholding amount is retained; its ATC/certificate treatment is not confirmed for rehearsal.'
ISSUES['expense_rehearsal']='Expense posting and its tax-report treatment need a supported expense workflow; it was not turned into a bill.'
ISSUES['withholding_basis']='Withholding differs between rows. Its header or line basis must be confirmed; no amount was assumed.'
ISSUES['document_identity']='More than one source document uses the same company, party and document number; resolve the identity before posting.'

class ReviewError(ValueError):pass

def cents(value,*,required=False):
    if value is None or not str(value).strip():
        if required:raise ReviewError('A required amount is missing.')
        return 0
    s=str(value).strip().replace(',','').replace('₱','').replace('PHP','').strip()
    if s.startswith('(') and s.endswith(')'):s='-'+s[1:-1]
    try:
        d=Decimal(s)
        if not d.is_finite() or abs(d)>Decimal('90000000000') or d*100!=(d*100).to_integral_value():raise ValueError()
        return int(d*100)
    except (InvalidOperation,ValueError):raise ReviewError('An amount is not valid at two-decimal currency precision.') from None

def iso(value):
    s=str(value or '').strip()
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%m/%d/%y','%b %d, %Y','%B %d, %Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except ValueError:pass
    raise ReviewError('A date is missing or uses an unsupported format.')

def key(*parts):return hashlib.sha256(json.dumps(parts,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:28]
def norm(value):return ' '.join(str(value or '').strip().casefold().split())
def company(value):
    return {'2mg incorporated':'2mg','getmeds philippines inc.':'gpi'}.get(norm(value),'unconfirmed')
def problem(doc,code):
    if code not in doc['issues']:doc['issues'].append(code)

def read_csv(content):
    if '\x00' in content:raise ReviewError('CSV contains a null character.')
    try:
        reader=csv.reader(io.StringIO(content.lstrip('\ufeff')),strict=True);rows=[]
        for row in reader:
            if len(rows)>MAX_ROWS:raise ReviewError('The file exceeds 100,000 rows.')
            rows.append(row)
        return rows
    except csv.Error:raise ReviewError('CSV quoting or field size is invalid.') from None

def control(rows,filename,index):
    header=next((i for i,r in enumerate(rows[:25]) if {'Reference','Transaction Date','Due Date','Balance'}<=set(r)),None)
    if header is None:raise ReviewError('This file is not a supported Zoho export or Oojeema aging report.')
    fields=[h.strip() for h in rows[header]];kind='ar' if 'Customer' in fields else 'ap' if 'Vendor Name' in fields else None
    if not kind:raise ReviewError('The aging report does not identify customers or vendors.')
    meta=' '.join(' '.join(r) for r in rows[:header]);match=re.search(r'(?:As\s+of\s+|Date\s*:\s*)([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})',meta,re.I)
    if not match:
        # Oojeema Date row contains the report's as-of date, not the generation footer.
        date_row=next((r for r in rows[:header] if r and norm(r[0]).rstrip(':')=='date'),None)
        if date_row:
            text=' '.join(date_row[1:]).strip();match=re.search(r'([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})',text)
    if not match:raise ReviewError('The aging report as-of date cannot be verified from its metadata.')
    asof=iso(match.group(1).replace(',  ', ', '));items=[];seen=set();issues=[]
    if asof not in (OPEN,'2026-01-31','2026-02-28',END):raise ReviewError('Use the December 31 opening or January/February/March month-end report.')
    for n,row in enumerate(rows[header+1:],header+2):
        if not any(row):continue
        if len(row)!=len(fields):raise ReviewError(f'Aging row {n} has a different column count.')
        r=dict(zip(fields,row));ref=r.get('Reference','').strip()
        if not r.get('Transaction Date','').strip():
            if ref:raise ReviewError(f'Aging row {n} has a reference but no transaction date.')
            continue  # footer totals are not invoices
        on=iso(r['Transaction Date']);due=iso(r['Due Date']);amount=cents(r['Balance'],required=True)
        buckets=[cents(r.get(h),required=True) for h in ('Current','1 to 30 Days','31 to 60 Days','Over 60 Days')]
        if on>asof or abs(sum(buckets)-amount)>1 or amount<0:raise ReviewError(f'Aging row {n} has inconsistent dates, buckets or balance.')
        party=r.get('Customer' if kind=='ar' else 'Vendor Name','').strip();identity=(norm(party),ref)
        if identity in seen:issues.append('control_duplicate')
        seen.add(identity)
        items.append({'row':n,'party':party,'reference':ref,'date':on,'dueDate':due,'balance':amount,'buckets':buckets})
    return {'id':key('control',kind,asof,index),'kind':kind,'asOf':asof,'file':filename,'items':items,'total':sum(r['balance'] for r in items),
            'issues':sorted(set(issues)),'company':'unconfirmed','currency':'unconfirmed','agingBasis':'not confirmed'}

def parse(files):
    if not files or len(files)>20:raise ReviewError('Choose 1–20 CSV files.')
    if sum(len(f['content'].encode()) for f in files)>MAX_BYTES:raise ReviewError('Choose no more than 8 MB of CSV contents per review.')
    docs=[];controls=[];manifests=[];identities=set();total_rows=0
    for index,f in enumerate(files):
        rows=read_csv(f['content']);total_rows+=len(rows)
        if total_rows>MAX_ROWS:raise ReviewError('The pack exceeds 100,000 rows.')
        if not rows:raise ReviewError(f'File {index+1} is empty.')
        headers=[h.strip() for h in rows[0]]
        kind=next((k for k in ('customer_payment','vendor_payment','invoice','salesorder','bill','expense') if KINDS[k][0] in headers),None)
        if kind is None:
            c=control(rows,f['name'],index)
            if (c['kind'],c['asOf']) in identities:raise ReviewError('The same aging type and as-of date were selected twice.')
            identities.add((c['kind'],c['asOf']));controls.append(c);manifests.append({'name':f['name'],'kind':c['kind'],'rows':len(c['items']),'documents':len(c['items']),'asOf':c['asOf'],'coverage':[]});continue
        if len(set(headers))!=len(headers):raise ReviewError(f'File {index+1} has repeated column headings; export unique headings first.')
        spec=KINDS[kind]
        if not {spec[0],spec[1],spec[3],'Currency Code','Total' if kind in ('invoice','bill','salesorder','expense') else 'Amount'}<=set(headers):
            raise ReviewError(f'File {index+1} is missing required {kind.replace("_"," ")} columns.')
        groups=defaultdict(list);populated=Counter()
        for n,row in enumerate(rows[1:],2):
            if not any(row):continue
            if len(row)!=len(headers):raise ReviewError(f'File {index+1}, row {n} has a different column count.')
            r=dict(zip(headers,row));populated.update(h for h,v in r.items() if v.strip())
            source=r[spec[0]].strip()
            if not source:raise ReviewError(f'File {index+1}, row {n} has no source identity.')
            safe={h:v.strip() for h,v in r.items() if h in PRESERVE}
            safe['__rowHash']=key(json.dumps(r,sort_keys=True))
            unknown=[]
            for h,v in r.items():
                if h in PRESERVE or re.search(r'(?: ID| Code| %| Percentage)$',h,re.I) or not re.search(r'tax|withhold|vat|amount|total|discount|balance|credit|retention|fee',h,re.I) or not v.strip():continue
                try:
                    if Decimal(v.replace(',',''))!=0:unknown.append(h)
                except InvalidOperation:continue
            safe['__unsupportedFinancial']=' | '.join(unknown)
            groups[source].append((n,safe))
        for source,group in groups.items():
            identity=(kind,source)
            if identity in identities:raise ReviewError('A source record appears in more than one selected file; choose one export per type.')
            identities.add(identity)
            try:docs.append(document(kind,source,group,index))
            except ReviewError as error:raise ReviewError(f'File {index+1}, row {group[0][0]}: {error}') from None
        coverage=[{'column':h,'nonblank':populated[h],'treatment':'read for review' if h in PRESERVE else 'not used: check financial coverage' if re.search(r'tax|withhold|vat|amount|total|discount|balance|credit|retention|fee',h,re.I) else 'not retained for this review'} for h in headers if populated[h]]
        manifests.append({'name':f['name'],'kind':kind,'rows':sum(len(g) for g in groups.values()),'documents':len(groups),'coverage':coverage})
    # Allocation IDs identify provider applications, not just rows within one payment.
    applications=defaultdict(list)
    for d in docs:
        for a in d['allocations']:
            if a['sourceId']:applications[(d['kind'],a['sourceId'])].append(d)
    for matches in applications.values():
        if len(matches)>1:
            for d in matches:problem(d,'allocation_identity')
    if sum(abs(d['total']) for d in docs)+sum(c['total'] for c in controls)>9_007_199_254_740_991:raise ReviewError('Aggregate amounts exceed the exact display range.')
    return docs,controls,manifests

def document(kind,source,group,file_index):
    spec=KINDS[kind];r=group[0][1];payment=kind.endswith('_payment')
    number=r.get(spec[2],'') or source
    d={'id':key(kind,source),'sourceId':source,'kind':kind,'fileIndex':file_index,'number':number,'party':r.get(spec[3],''),
       'partyId':r.get('Customer ID') or r.get('CustomerID') or '', 'date':iso(r[spec[1]]),'dueDate':iso(r['Due Date']) if r.get('Due Date') else None,
       'currency':r['Currency Code'],'status':r.get(spec[4],'') if spec[4] else 'paid expense','total':cents(r['Amount' if payment else 'Total'],required=True),
       'company':company(r.get('CF.Invoicing From')) if kind in ('invoice','salesorder') else 'unconfirmed',
       'companySource':r.get('CF.Invoicing From') or r.get('CF.Company') or r.get('CF.Cost Centre') or '',
       'issues':[],'links':[],'allocations':[],'lines':[],'rows':[n for n,_ in group],'sourceSaved':False,
       'tin':r.get('CF.TIN Number') or r.get('Company ID') or '', 'original':{},'accountGroups':[]}
    d['unhandledFields']=sorted({h for _,row in group for h in row.get('__unsupportedFinancial','').split(' | ') if h})
    if kind in ('invoice','bill','salesorder') and not r.get(spec[2]):problem(d,'missing_reference')
    if len(source)>120 or len(d['party'])>200 or len(number)>(30 if kind=='invoice' else 60):problem(d,'field_length')
    if any(row.get('__unsupportedFinancial') for _,row in group):problem(d,'unsupported_financial')
    headers=[spec[1],spec[2],spec[3],'Currency Code','Amount' if payment else 'Total','SubTotal','Balance','Unused Amount','Bank Charges','CF.Company','CF.Invoicing From','CF.Cost Centre','Due Date','Customer ID','CustomerID']
    if any(any(row.get(h,'')!=r.get(h,'') for h in headers) for _,row in group):problem(d,'expense_identity' if kind=='expense' else 'header_conflict')
    if len({row['__rowHash'] for _,row in group})<len(group):problem(d,'duplicate_rows')
    if not START<=d['date']<=END:problem(d,'outside_period')
    if d['currency']!='PHP':problem(d,'currency')
    if norm(d['status']) in ('draft','void','cancelled','canceled'):problem(d,'source_only')
    if d['total']<=0:problem(d,'nonpositive')
    if payment:
        d['unused']=cents(r.get('Unused Amount'));d['bankCharges']=cents(r.get('Bank Charges'))
        if d['bankCharges']:problem(d,'unsupported_components')
        allocation_ids=set()
        for n,row in group:
            received=kind=='customer_payment';aid=row.get('InvoicePayment ID' if received else 'PIPayment ID','')
            ref=row.get('Invoice Number' if received else 'Bill ID','')
            applied=row.get('Invoice Payment Applied Date' if received else 'Bill Payment Applied Date')
            a={'sourceId':aid,'reference':ref,'number':row.get('Invoice Number' if received else 'Bill Number',''),
               'cash':cents(row.get('Amount Applied to Invoice' if received else 'Bill Amount')),'withheld':cents(row.get('Withholding Tax Amount')),
               'date':iso(applied) if applied else None,'documentDate':iso(row.get('Invoice Date' if received else 'Bill Date')) if row.get('Invoice Date' if received else 'Bill Date') else None,
               'targetId':None,'company':'unconfirmed','row':n}
            if aid in allocation_ids or (ref and not aid):problem(d,'allocation_identity')
            if aid:allocation_ids.add(aid)
            d['allocations'].append(a)
        if sum(a['cash'] for a in d['allocations'])+d['unused']!=d['total']:problem(d,'allocation')
        if d['unused'] or any(not a['reference'] for a in d['allocations']):problem(d,'unallocated')
        d['original']={'moneyAccount':r.get('Deposit To' if kind=='customer_payment' else 'Paid Through',''),
                       'moneyCode':r.get('Deposit To Account Code' if kind=='customer_payment' else 'Paid Through Account Code',''),
                       'method':{'cash':'cash','bank transfer':'bank','bank remittance':'bank','bank':'bank','check':'check','cheque':'check','ewallet':'ewallet','gcash':'ewallet'}.get(norm(r.get('Mode')))}
        if not d['original']['method']:problem(d,'payment_method')
        if any(a['withheld'] for a in d['allocations']):problem(d,'withholding_evidence')
    else:
        d['subtotal']=cents(r.get('SubTotal') if kind!='expense' else r.get('Expense Amount'),required=True)
        d['discount']=cents(r.get('Entity Discount Amount'));d['shipping']=cents(r.get('Shipping Charge'));d['shippingTax']=cents(r.get('Shipping Charge Tax Amount'));d['adjustment']=cents(r.get('Adjustment'));d['roundOff']=cents(r.get('Round Off'))
        for n,row in group:
            tax_field='Item Tax Amount' if kind in ('invoice','salesorder') else 'Tax Amount'
            ln={'row':n,'description':row.get('Item Name') or row.get('Description') or row.get('Expense Description') or '',
                'amount':cents(row.get('Item Total') if kind!='expense' else row.get('Expense Amount'),required=True),
                'tax':cents(row.get(tax_field)), 'taxName':row.get('Item Tax') or row.get('Tax Name') or '',
                'taxRate':row.get('Item Tax %') or row.get('Tax Percentage') or '',
                'account':row.get('Account') or row.get('Expense Account') or '',
                'accountCode':row.get('Account Code') or row.get('Expense Account Code') or '',
                'quantity':row.get('Quantity') or row.get('QuantityOrdered') or '', 'unitPrice':row.get('Item Price') or row.get('Rate') or '',
                'discount':row.get('Discount Amount') or '', 'taxHints':{'scPwdDiscount':row.get('Item.CF.SC/PWD-Discount',''),'scPwdTax':row.get('Item.CF.SC/PWD-Tax','')},
                'orderNumber':row.get('Sales Order Number','')}
            d['lines'].append(ln)
        d['tax']=sum(ln['tax'] for ln in d['lines'])
        if kind=='expense':
            gross=sum(ln['amount'] for ln in d['lines'])
            if gross==d['total'] and 0<=d['tax']<=gross:
                for ln in d['lines']:
                    ln['sourceGross']=ln['amount'];ln['amount']-=ln['tax']
                d['subtotal']=gross-d['tax'];d['expenseAmountBasis']='Exported amounts include the exported tax; checked against total.'
            elif gross+d['tax']==d['total']:
                d['subtotal']=gross;d['expenseAmountBasis']='Exported amounts plus exported tax equal total.'
            else:d['expenseAmountBasis']='Amounts do not explain the exported total.'
        if sum(ln['amount'] for ln in d['lines'])!=d['subtotal']:problem(d,'line_totals')
        if d['subtotal']+d['tax']+d['shipping']+d['shippingTax']+d['adjustment']-d['discount']+d['roundOff']!=d['total']:problem(d,'components')
        withholding_rows=[{'row':n,'amount':cents(row.get('TDS Amount'))} for n,row in group]
        d['withholdingRows']=withholding_rows
        amounts={row['amount'] for row in withholding_rows}
        d['withheld']=next(iter(amounts)) if len(amounts)==1 else None
        if len(amounts)>1:problem(d,'withholding_basis')
        if any(amounts):problem(d,'unsupported_components')
        if any(d[k] for k in ('shipping','shippingTax','adjustment','discount','roundOff','withheld')):problem(d,'unsupported_components')
        d['original']={'arAccount':r.get('Accounts Receivable',''),'apAccount':r.get('Accounts Payable',''),
                       'moneyAccount':r.get('Paid Through',''),'moneyCode':r.get('Paid Through Account Code','')}
        if kind=='expense' and r.get('Is Reimbursable')!='false':problem(d,'unsupported_components')
        if kind=='invoice' and (not d['tin'] or any(not ln['taxName'] for ln in d['lines'])):problem(d,'tax_details')
    return d

def connect(docs):
    invoices=defaultdict(list);bills={};orders=defaultdict(list);by_id={d['id']:d for d in docs}
    for d in docs:
        if d['kind']=='invoice':invoices[(d['number'],d['partyId'])].append(d)
        elif d['kind']=='bill':bills[d['sourceId']]=d
        elif d['kind']=='salesorder':orders[d['number']].append(d)
    for d in docs:
        if d['kind']=='invoice':
            for number in sorted({ln['orderNumber'] for ln in d['lines'] if ln['orderNumber']}):
                found=[o for o in orders.get(number,[]) if o['partyId']==d['partyId']]
                if len(found)==1:
                    o=found[0];d['links'].append(o['id']);o['links'].append(d['id'])
        if not d['kind'].endswith('_payment'):continue
        for a in d['allocations']:
            found=invoices.get((a['reference'],d['partyId']),[]) if d['kind']=='customer_payment' else ([bills[a['reference']]] if a['reference'] in bills else [])
            found=[b for b in found if norm(b['party'])==norm(d['party'])]
            if len(found)!=1:
                problem(d,'ambiguous_target' if len(found)>1 else 'missing_target');continue
            target=found[0];a['targetId']=target['id'];a['company']=target['company'];d['links'].append(target['id']);target['links'].append(d['id'])
            if not a['date'] or a['date']<target['date'] or a['date']<d['date'] or a['date']>END:problem(d,'application_date')
        companies={a['company'] for a in d['allocations']}
        d['company']=next(iter(companies)) if len(companies)==1 else 'mixed'
        if len(companies)!=1 or 'unconfirmed' in companies:problem(d,'mixed_payment')
    for d in docs:
        if d['kind']=='salesorder':
            companies={by_id[i]['company'] for i in d['links']}
            if len(companies)>1:d['company']='mixed'
            elif companies:d['company']=next(iter(companies))

def build(files,choices,accounts,source_identities=()):
    docs,controls,manifests=parse(files);groups={};account_map={a['id']:a for a in accounts};codes=defaultdict(list)
    for a in accounts:codes[a['code']].append(a['id'])
    for d in docs:
        if d['kind'] in ('bill','expense'):
            rules=choices.get('billCompanies' if d['kind']=='bill' else 'expenseCompanies',{})
            assigned=rules.get(d['companySource'],'unconfirmed')
            if assigned not in ('2mg','gpi','unconfirmed'):raise ReviewError('Choose a supported company attribution.')
            d['company']=assigned
        d['sourceSaved']=(d['kind'],d['sourceId']) in source_identities
    business_ids=defaultdict(list)
    for d in docs:
        if d['kind'] in ('invoice','bill'):
            business_ids[(d['kind'],d['company'],norm(d['party']),d['number'])].append(d)
    for matches in business_ids.values():
        if len(matches)>1:
            for d in matches:problem(d,'document_identity')
    connect(docs)
    def need(d,role,label,code='',target_type=None):
        identity=key('account',role,code,label);g=groups.setdefault(identity,{'id':identity,'role':role,'label':label or 'No source account supplied','code':code,
            'documents':set(),'suggestion':codes[code][0] if code and len(codes[code])==1 else None,'accountId':None})
        g['documents'].add(d['id']);chosen=choices.get('accounts',{}).get(identity)
        if chosen:
            a=account_map.get(chosen)
            if not a or not a['active'] or not a.get('posting',True):raise ReviewError('A selected account is unavailable or cannot receive postings.')
            required={'income':{'income'},'receivable':{'asset'},'payable':{'liability'},'money':{'asset'},'input_tax':{'asset'},'output_tax':{'liability'},'cwt':{'asset'},'withholding':{'liability'}}.get(role)
            if required and a['type'] not in required:raise ReviewError('A selected account has the wrong accounting type for its use.')
            if role=='money' and not a.get('money'):raise ReviewError('Select a money account under CASH for receipts/payments.')
            g['accountId']=chosen
        d['accountGroups'].append(identity)
        if not g['accountId']:problem(d,'account')
        return identity
    for d in docs:
        if d['company']=='unconfirmed':problem(d,'company')
        if d['kind']=='salesorder' or d['company']!='2mg':continue
        if d['kind'] in ('invoice','bill','expense'):
            for ln in d['lines']:ln['accountGroup']=need(d,'income' if d['kind']=='invoice' else 'cost',ln['account'],ln['accountCode'])
            if d['kind']=='invoice':d['controlGroup']=need(d,'receivable',d['original']['arAccount'])
            elif d['kind']=='bill':d['controlGroup']=need(d,'payable',d['original']['apAccount'])
            else:d['moneyGroup']=need(d,'money',d['original']['moneyAccount'],d['original']['moneyCode'])
            if d.get('tax'):d['taxGroup']=need(d,'output_tax' if d['kind']=='invoice' else 'input_tax','Output VAT' if d['kind']=='invoice' else 'Input VAT')
        else:
            d['moneyGroup']=need(d,'money',d['original']['moneyAccount'],d['original']['moneyCode'])
            if any(a['withheld'] for a in d['allocations']):d['withholdingGroup']=need(d,'cwt' if d['kind']=='customer_payment' else 'withholding','Customer withholding receivable' if d['kind']=='customer_payment' else 'Supplier withholding payable')
        d['accountGroups']=sorted(set(d['accountGroups']))
    hard=set(ISSUES)-{'tax_details'}
    for d in docs:
        if d['kind']=='expense':problem(d,'expense_rehearsal')
        d['financialReady']=d['kind']!='salesorder' and d['company']=='2mg' and not hard.intersection(d['issues'])
        # The rehearsal deliberately does not construct the statutory VAT summary yet.
        d['taxReady']=False
        d['issueMessages']=[ISSUES[c] for c in d['issues']]
    company_groups=[]
    for kind in ('bill','expense'):
        for value,count in Counter(d['companySource'] for d in docs if d['kind']==kind).items():company_groups.append({'kind':kind,'value':value,'count':count})
    return {'documents':docs,'controls':controls,'files':manifests,'accountGroups':[{**g,'documents':len(g['documents'])} for g in groups.values()],
        'companyGroups':company_groups,'accounts':accounts,'choices':choices,'period':{'start':START,'end':END,'opening':OPEN},
        'counts':{'documents':len(docs),'twoMg':sum(d['company']=='2mg' for d in docs),'ready':sum(d['financialReady'] for d in docs),
                  'needsReview':sum(bool(d['issues']) and d['company']!='gpi' for d in docs),'linkedAllocations':sum(bool(a['targetId']) for d in docs for a in d['allocations'])},
        'comparisons':compare(docs,controls,choices),'bookEntriesCreated':0,'providerRequests':0}

def compare(docs,controls,choices):
    output=[];by_id={d['id']:d for d in docs}
    for c in controls:
        row={'id':c['id'],'kind':c['kind'],'asOf':c['asOf'],'sourceTotal':c['total'],'reconstructedTotal':None,'difference':None,
             'status':'Not compared','reason':'Confirm the report covers 2MG in PHP; cross-system references are candidates until verified.',
             'candidateMatches':0,'unmatchedReferences':len(c['items']),'duplicateReferences':bool(c['issues'])}
        # Never imply cross-system identity from names alone, or use current balances as historic balances.
        candidates=[]
        kind='invoice' if c['kind']=='ar' else 'bill'
        for item in c['items']:
            found=[d for d in docs if d['kind']==kind and d['company']=='2mg' and d['number']==item['reference'] and norm(d['party'])==norm(item['party'])]
            if len(found)==1:candidates.append((item,found[0]))
        row['candidateMatches']=len(candidates);row['unmatchedReferences']-=len(candidates)
        row['referenceCandidates']=[{'controlRow':item['row'],'documentId':d['id']} for item,d in candidates]
        if choices.get('controlsCompany')=='2mg' and choices.get('controlsCurrency')=='PHP':
            opening=[x for x in controls if x['kind']==c['kind'] and x['asOf']==OPEN]
            if len(opening)!=1:row['reason']='December 31 opening report is missing.'
            elif c['issues'] or opening[0]['issues']:row['reason']='Repeated control references need resolving before totals can be compared.'
            elif not choices.get('confirmControlReferences'):row['reason']='Confirm that exact party + document references identify the same records across systems.'
            else:
                balances={};ambiguous=False
                for item in opening[0]['items']:
                    identity=(norm(item['party']),item['reference']);balances[identity]=item['balance']
                for d in docs:
                    if d['kind']!=kind or d['company']!='2mg' or d['date']>c['asOf'] or 'source_only' in d['issues']:continue
                    identity=(norm(d['party']),d['number'])
                    if identity in balances:
                        ambiguous=True;continue
                    balances[identity]=d['total']
                payment_kind='customer_payment' if c['kind']=='ar' else 'vendor_payment';unmatched=0;date_gaps=0
                for payment in docs:
                    if payment['kind']!=payment_kind or payment['date']>c['asOf'] or 'source_only' in payment['issues']:continue
                    if any(code in payment['issues'] for code in ('allocation','allocation_identity','header_conflict','duplicate_rows','currency')):
                        unmatched+=len(payment['allocations']);continue
                    for a in payment['allocations']:
                        if not a['date']:
                            date_gaps+=1;continue
                        if a['date']>c['asOf']:continue
                        target=by_id.get(a['targetId']);identity=(norm(target['party']),target['number']) if target else (norm(payment['party']),a['number'])
                        if identity in balances:
                            balances[identity]-=a['cash']+a['withheld']
                        elif a['company']!='gpi':unmatched+=1
                row['reconstructedTotal']=sum(balances.values());row['difference']=row['reconstructedTotal']-c['total']
                row['status']='Provisional comparison';row['reason']='Opening + available invoices/bills − dated cash and withholding. Credits, write-offs and cross-system renumbering are not yet proven complete.'
                row['unmatchedAllocations']=unmatched;row['missingApplicationDates']=date_gaps
                row['identityConflict']=ambiguous
                row['negativeBalances']=sum(x<0 for x in balances.values())
                expected={(norm(item['party']),item['reference']):item['balance'] for item in c['items']}
                row['differentReferences']=sum(balances.get(k,0)!=expected.get(k,0) for k in set(balances)|set(expected))
                disputed=[d for d in docs if d['kind']==kind and d['company']=='2mg' and d['date']<=c['asOf'] and set(d['issues']) & {'withholding_basis','header_conflict','document_identity','unsupported_financial','unsupported_components','components','line_totals','duplicate_rows','currency','outside_period','nonpositive'}]
                if disputed:
                    row['reconstructedTotal']=None;row['difference']=None
                    row['status']='Blocked: source amounts need review'
                    row['reason']='Source document amounts or identities have unresolved conflicts. Resolve their checks before comparing balances.'
                if ambiguous:
                    row['reconstructedTotal']=None;row['difference']=None
                    row['status']='Blocked: conflicting references'
                    row['reason']='More than one opening item or source document uses the same party and reference. Resolve the identity before comparing balances; no amounts were combined or replaced.'
                if c['asOf']==OPEN:
                    row['reconstructedTotal']=None;row['difference']=None;row['status']='Opening evidence';row['reason']='This report supplies the starting balances; comparing it to itself would not prove reconciliation.'
        output.append(row)
    return output
