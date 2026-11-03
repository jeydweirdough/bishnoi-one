"""Read-only review files. Operational rows retain status; BIR sources use report readers.

Record totals and line amounts are separate downloads so summing a file never
multiplies a document total by its number of lines. Text cannot execute formulas.
"""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, or_
from app.access import access_of
from app.deps import DB, SettingsDep, CurrentUser
from app.models import Bill, PaymentVoucher, Invoice, InvoicePayment, PettyCashVoucher, ImportedExpense
from app.routers.exports import csv_file, text, money
from app.routers import payables, vouchers, invoices, petty_cash, imported_expenses
from app import bir_reports as bir

router = APIRouter()
KINDS = {
    "bills": "bills.view", "bill-lines": "bills.view",
    "invoices": "invoices.view", "customer-payments": "invoices.view",
    "supplier-payments": "vouchers.view", "payment-allocations": "vouchers.view",
    "petty-cash": "petty_cash.view", "petty-cash-lines": "petty_cash.view",
    "imported-expenses": "petty_cash.view", "imported-expense-lines": "petty_cash.view",
}

def val(d, path):
    for key in path.split('.'):
        d = d.get(key) if isinstance(d, dict) else None
    return d

def columns(spec):
    return [tuple(s.split('=', 1)) for s in spec.split('|')]

IDENTITY = "Record ID=id|Status=status|Entry ID=entryId"
BILL = columns("Internal bill=no|Supplier invoice=billNumber|Bill date=billDate|Due date=dueDate|Supplier=supplier.name|Supplier TIN=supplier.tin|Currency=currency|Exchange rate=rate|Net PHP=netCentavos|VAT PHP=vatCentavos|Withheld PHP=withheldCentavos|Gross PHP=totalCentavos|Payable PHP=payableCentavos|Paid PHP=paidCentavos|Remaining PHP=leftCentavos|Approval stage=state|Approved by=approvedBy|Checked by=checkedBy|Recorded by=recordedBy|Voided at=voidedAt|Void reason=voidReason|Source Zoho reference=zohoRef|Source Oojeema reference=oojeemaRef")
LINE = columns("Account code=account.code|Account=account.name|Description=description|Purchase type=purchaseTypeLabel|VAT treatment=vatLabel|ATC=withholding|Withholding rate percent=withholdingRateBp|Net=netCentavos|VAT=vatCentavos|Withheld=withheldCentavos")
INV = columns("Invoice=number|Invoice date=date|Due date=dueDate|Customer=customer.name|Customer TIN=customer.tin|Reference=reference|Gross PHP=totalCentavos|VAT PHP=taxCentavos|Settled PHP=paidCentavos|Remaining PHP=balanceCentavos|Created by=createdBy|Issued by=issuedBy|Voided at=voidedAt|Void reason=voidReason")
PAY = columns("Payment ID=id|Paid on=paidOn|Cash PHP=amountCentavos|Customer withholding PHP=cwtCentavos|ATC=cwtAtc|2307 reference=cwtCertificate|Method=methodLabel|Payment reference=reference|Check number=checkNumber|Check date=checkDate|Recorded by=recordedBy|Removed at=removedAt|Removed by=removedBy")
VOUCHER = columns("Voucher=number|Supplier=supplier.name|Supplier TIN=supplier.tin|Paid on=paidOn|Method=methodLabel|Paid from code=paidFrom.code|Paid from=paidFrom.name|Cash PHP=totalCentavos|Prepared by=preparedBy|Released by=releasedBy|Payment reference=bankReference|Check number=checkNumber|Source Zoho reference=zohoRef|Source Oojeema reference=oojeemaRef")
PC = columns("Voucher=number|Voucher date=voucherDate|Fund code=fund.code|Fund=fund.name|Person in charge=personInCharge|Department=department|Net PHP=netCentavos|VAT PHP=vatCentavos|Withheld PHP=withheldCentavos|Gross PHP=totalCentavos|Cash paid PHP=paidOutCentavos|Created by=createdBy|Checked by=checkedBy|Voided at=voidedAt|Void reason=voidReason")
EXP = columns("Expense=number|Date=date|Vendor=vendor|Vendor TIN=vendorTin|Reference=reference|Paid from=paidFrom|Net PHP=netCentavos|VAT PHP=vatCentavos|Withheld PHP=withheldCentavos|Gross PHP=totalCentavos|Cash paid PHP=paidOutCentavos|Source file=source.file|Source ID=source.zohoId|Imported by=source.by|Voided at=voidedAt|Void reason=voidReason")

def cells(settings, obj, cols):
    out = []
    for label, key in cols:
        v = val(obj, key)
        if key.endswith('Centavos'):
            out.append(money(settings, v))
        elif key.endswith('RateBp'):
            out.append(str(Decimal(v) / 100) if v is not None else '')
        elif isinstance(v, (int, float)):
            out.append(str(v))
        else:
            out.append(text(v))
    return out

def within(value, start, end):
    return value is not None and (start is None or str(value)[:10] >= start.isoformat()) and (end is None or str(value)[:10] <= end.isoformat())

@router.get('/review/{kind}.csv')
def records(kind: str, user: CurrentUser, db: DB, settings: SettingsDep,
            start: date | None = None, end: date | None = None,
            show: str | None = None, q: str | None = Query(None, max_length=100),
            queue: str | None = None, supplier_id: str | None = Query(None, alias='supplierId'),
            bucket: str | None = None, missing: bool = False,
            status_: str | None = Query(None, alias='status'), attention: bool = False,
            customer: str | None = None):
    if kind not in KINDS:
        raise HTTPException(404, 'No such review export.')
    if not access_of(user).can(KINDS[kind]):
        raise HTTPException(403, 'You do not have access to these records.')
    if start and end and start > end:
        raise HTTPException(422, 'The start date is after the end date.')
    rows = []
    base = columns(IDENTITY)
    detail_cols = []
    if kind in ('bills', 'bill-lines'):
        found = payables.list_bills(user, db, settings, show, q, missing, queue, supplier_id, bucket)['items']
        docs = [payables.bill_out(db, db.get(Bill, x['id']), user) for x in found]
        docs = [x for x in docs if within(x['billDate'], start, end)]
        if kind == 'bills':
            base += BILL
        else:
            # Foreign bill lines stay in source currency. Do not label them PHP.
            base += columns('Internal bill=no|Supplier invoice=billNumber|Bill date=billDate|Supplier=supplier.name|Currency=currency|Exchange rate=rate')
            detail_cols = [('Line', '_line')] + [(label + ' (bill currency)' if key.endswith('Centavos') else label, key) for label, key in LINE]
            for d in docs:
                bill = db.get(Bill, d['id'])
                worked = payables.work_out(db, bill.lines or [], bill.bill_date, bill.amounts_include_vat)
                posted = payables.pesos(worked, bill.rate_e4) if bill.currency and bill.currency != 'PHP' and bill.rate_e4 else worked
                if bill.status != 'draft' and (posted.net,posted.vat,posted.withheld,posted.total,posted.payable) != (bill.net_centavos,bill.vat_centavos,bill.withheld_centavos,bill.total_centavos,bill.payable_centavos):
                    raise HTTPException(409, 'Saved bill totals differ from its calculated lines. Review the bill before downloading line detail.')
                d['lines'] = [shown | calculated for shown, calculated in zip(d['lines'], worked.lines)]
    elif kind in ('supplier-payments', 'payment-allocations'):
        found = vouchers.list_vouchers(user, db, show, q, queue)['items']
        docs = [vouchers.voucher_out(db, db.get(PaymentVoucher, x['id']), user) for x in found]
        docs = [x for x in docs if (start is None and end is None) or within(x['paidOn'], start, end)]
        if kind == 'supplier-payments':
            base += VOUCHER
        else:
            base += columns('Voucher=number|Supplier=supplier.name|Paid on=paidOn|Method=methodLabel')
            detail_cols = columns('Bill ID=billId|Internal bill=billNo|Supplier invoice=billNumber|Bill date=billDate|Allocated cash PHP=amountCentavos|Bill payable PHP (not additive)=payableCentavos|Bill withholding PHP (not additive)=withheldCentavos|Bill remaining after PHP (not additive)=leftAfterCentavos')
    elif kind in ('invoices', 'customer-payments'):
        query = select(Invoice).order_by(Invoice.invoice_date, Invoice.id)
        if status_ in ('draft', 'issued', 'void'):
            query = query.where(Invoice.status == status_)
        if attention:
            query = query.where(Invoice.status == 'draft', Invoice.attention.is_not(None))
        if customer:
            query = query.where(Invoice.customer_id == customer)
        if q and q.strip():
            like = f'%{q.strip().lower()}%'
            query = query.where(or_(func.lower(Invoice.customer_name).like(like), func.lower(Invoice.number).like(like), func.lower(Invoice.reference).like(like)))
        entities = list(db.scalars(query))
        if kind == 'invoices':
            docs = [invoices.invoice_out(db, x, settings, full=False, linked={}) | {'entryId': x.entry_id} for x in entities if within(x.invoice_date, start, end)]
            base += INV
        else:
            docs = []
            base = columns('Invoice ID=invoiceId|Invoice=invoiceNumber|Invoice status=invoiceStatus|Customer=customer|Customer TIN=tin|Payment status=paymentStatus') + PAY
            for inv in entities:
                for p in sorted(inv.payments, key=lambda p: (p.paid_on, p.id)):
                    if within(p.paid_on, start, end):
                        docs.append(invoices.payment_out(p) | {'invoiceId': inv.id, 'invoiceNumber': inv.number, 'invoiceStatus': inv.status, 'customer': inv.customer_name, 'tin': inv.customer_tin, 'paymentStatus': 'removed' if p.removed_at else 'recorded'})
    else:
        pc = kind.startswith('petty-cash')
        model = PettyCashVoucher if pc else ImportedExpense
        query = select(model)
        valid = ('draft','to_check','returned','posted','void','all') if pc else ('posted','void','all')
        if show and show not in valid:
            raise HTTPException(422, 'Pick a listed status.')
        if show and show != 'all':
            query = query.where(model.status == show)
        if q and q.strip():
            like = f'%{q.strip().lower()}%'
            fields = [model.number, model.person_in_charge, model.department] if pc else [model.number, model.vendor, model.reference]
            query = query.where(or_(*(func.lower(f).like(like) for f in fields)))
        docs = [petty_cash.voucher_out(db, x, user) if pc else imported_expenses.detail(x, user) for x in db.scalars(query.order_by(model.id))]
        docs = [x for x in docs if within(x['voucherDate' if pc else 'date'], start, end)]
        if kind.endswith('-lines'):
            base += columns('Voucher=number|Date=' + ('voucherDate' if pc else 'date') + ('|Fund code=fund.code' if pc else '|Vendor=vendor|Vendor TIN=vendorTin'))
            detail_cols = [('Line', '_line')] + (columns('Receipt date=spentOn|Store=store|Store TIN=storeTin|Receipt=receiptNumber') if pc else columns('Source account=sourceAccount|Source tax=sourceTax')) + LINE
        else:
            base += PC if pc else EXP
    header = ['Export from','Export to'] + [x[0] for x in base + detail_cols]
    for d in docs:
        prefix = [start.isoformat() if start else '', end.isoformat() if end else ''] + cells(settings, d, base)
        if detail_cols:
            for index, line in enumerate(d.get('items' if kind == 'imported-expense-lines' else 'lines', []), 1):
                rows.append(prefix + cells(settings, line | {'_line': index}, detail_cols))
        else:
            rows.append(prefix)
    return csv_file(f'{kind}-{start or "all"}-to-{end or "all"}.csv', header, rows)


@router.get('/bir-review/{kind}.csv')
def tax_review(kind: str, user: CurrentUser, db: DB, settings: SettingsDep,
               year: int | None = Query(None, ge=1900, le=9998), quarter: int | None = Query(None, ge=1, le=4),
               month: int | None = Query(None, ge=1, le=12), supplier_id: str | None = Query(None, alias='supplierId')):
    if not access_of(user).can('bir.view'):
        raise HTTPException(403, 'You do not have access to BIR reports.')
    from app.routers.bir import default_quarter, the_quarter
    y,q = default_quarter(settings)
    p = the_quarter(db, year or y, quarter or q)
    if kind == '0619e' or (kind == 'withholding-sources' and month is not None):
        from app.routers.funds import today
        now = today(settings)
        y, m = year or now.year, month or now.month
        p = bir.Period(date(y, m, 1), bir.month_end(y, m), f'{y}-{m:02}')
    rows = []
    if kind == 'vat':
        d = bir.vat_return(db, p)
        header = ['Period from','Period to','Section','Item','Amount PHP','Rate percent','Review note']
        for ln in d['lines']:
            rows.append([str(p.start),str(p.end),'Summary',text(ln['label']),money(settings, ln.get('amountCentavos')),str(Decimal(ln['rateBp'])/100) if 'rateBp' in ln else '', 'Review only; credits and adjustments not verified'])
        for m in d['months']:
            for k,v in m.items():
                if k.endswith('Centavos'):
                    rows.append([m['start'],m['end'],'Monthly',text(m['label'] + ': ' + k),money(settings,v),'',''])
    elif kind == 'vat-sources':
        header = ['Period from','Period to','Source','Date','Record reference','External reference','Party','TIN','Net PHP','VAT PHP','Withheld PHP','VATable net PHP','Zero-rated net PHP','Exempt net PHP','Non-VAT net PHP']
        for inv in bir.issued_between(db,p.start,p.end):
            a = bir.amounts_of(inv)
            amounts = [sum(a[k] for k in ('taxable_sales','zero_rated_sales','exempt_sales','non_taxable_sales')),a['tax'],0,a['taxable_sales'],a['zero_rated_sales'],a['exempt_sales'],a['non_taxable_sales']]
            rows.append([str(p.start),str(p.end),'invoice',str(inv.invoice_date),text(inv.number),text(inv.reference),text(inv.customer_name),text(inv.customer_tin)] + [money(settings,x) for x in amounts])
        for b in bir.bills_between(db,p.start,p.end):
            rows.append([str(p.start),str(p.end),b.source,str(b.on),text(b.no),text(b.reference),text(b.name),text(b.tin)] + [money(settings,x) for x in [b.net,b.vat,b.withheld,*[b.by_kind[k] for k in ('vatable','zero_rated','exempt','non_vat')]]])
    elif kind == 'withholding-sources':
        header = ['Period from','Period to','Source','Date','Record reference','External reference','Payee ID','Payee','TIN','ATC','Nature','Rate percent','Income base PHP','Withheld PHP']
        for b in bir.withheld_bills(db,p.start,p.end,supplier_id):
            for atc, rate, base, tax in b.held:
                rows.append([str(p.start),str(p.end),b.source,str(b.on),text(b.no),text(b.reference),text(b.payee_id),text(b.name),text(b.tin),text(atc),text(bir.nature(atc)),str(Decimal(rate)/100),money(settings,base),money(settings,tax)])
    elif kind in ('0619e','1601eq'):
        if kind == '0619e':
            m = month or p.start.month
            y = year or p.start.year
            p = bir.Period(date(y,m,1),bir.month_end(y,m),f'{y}-{m:02}')
        d = bir.form_0619e(db,p) if kind == '0619e' else bir.form_1601eq(db,p)
        header = ['Period from','Period to','Section','ATC / label','Nature','Rate percent','Income base PHP','Withheld PHP','Remitted PHP','Remaining payable PHP','Review note']
        for r in d['rows']:
            rows.append([str(p.start),str(p.end),'Withholding',text(r['atc']),text(r['nature']),str(Decimal(r['rateBp'])/100),money(settings,r['baseCentavos']),money(settings,r['taxCentavos']),'','',''])
        rows.append([str(p.start),str(p.end),'Total','','','','',money(settings,d['totalCentavos']),'','','Actual remittances and final payable are not verified'])
        if kind == '1601eq':
            for r in d['remitted']:
                rows.append([str(p.start),str(p.end),'Monthly calculation',text(r['label']),'','','',money(settings,r['calculatedWithholdingCentavos']),'','','Calculated withholding is not proof of remittance'])
    elif kind == '2307':
        header = ['Period from','Period to','Payee ID','Payee','TIN','ATC','Nature','Rate percent','Month 1 base PHP','Month 2 base PHP','Month 3 base PHP','Total base PHP','Withheld PHP']
        payees = bir.withheld_suppliers(db,p)
        if supplier_id:
            payees = [x for x in payees if x['id'] == supplier_id]
        for payee in payees:
            c = bir.form_2307(db,p,payee['id'])
            for r in c['rows']:
                rows.append([str(p.start),str(p.end),text(payee['id']),text(payee['name']),text(payee['tin']),text(r['atc']),text(r['nature']),str(Decimal(r['rateBp'])/100),*[money(settings,x) for x in r['months']],money(settings,r['baseCentavos']),money(settings,r['taxCentavos'])])
    else:
        raise HTTPException(404,'No such BIR review export.')
    return csv_file(f'{kind}-{p.start}-to-{p.end}.csv',header,rows)
