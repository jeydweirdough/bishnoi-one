"""Saved, read-only Zoho order/invoice views. No ledger or local approval writes."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from sqlalchemy import select
from app.models import ZohoSourceDocument, ZohoSourceRun, utcnow
from app.zoho_probe import ProbeStopped, source_id, order_ids, linked_invoices, sample_rows

COMPANIES = {'2mg incorporated': '2mg', 'getmeds philippines inc.': 'gpi'}


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite(): raise ValueError('Invalid source amount.')
        result = int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if abs(result) > 9_000_000_000_000_000: raise ValueError('Source amount is too large.')
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('A source amount was invalid; no amount was guessed.') from None


def text(value, maximum=300):
    return ('' if value is None else str(value))[:maximum]


def invoicing_from(invoice):
    values = {str(field.get('value') or '').strip() for field in invoice.get('custom_fields') or []
              if isinstance(field, dict) and (field.get('api_name') == 'cf_invoicing_from' or
                  str(field.get('label', '')).strip().casefold() == 'invoicing from')}
    if invoice.get('cf_invoicing_from'):
        values.add(str(invoice['cf_invoicing_from']).strip())
    if len(values) != 1: return 'unknown', ''
    value = values.pop()
    return COMPANIES.get(value.casefold(), 'unknown'), value[:120]


def normalize(kind, raw):
    is_invoice = kind == 'invoice'
    identifier = source_id(raw.get('invoice_id' if is_invoice else 'salesorder_id'))
    if not identifier: raise ValueError('Source document identity is missing.')
    on = date.fromisoformat(str(raw.get('date', '')))
    if 'total' not in raw: raise ValueError('Source total is missing.')
    currency = str(raw.get('currency_code') or '').upper()
    currency = currency if re.fullmatch('[A-Z]{3}', currency) else 'UNKNOWN'
    lines = []
    for line in raw.get('line_items') or []:
        if not isinstance(line, dict): raise ValueError('Source line is invalid.')
        lines.append({'id': source_id(line.get('line_item_id')), 'orderLineId': source_id(line.get('salesorder_item_id')),
                      'name': text(line.get('name') or line.get('description'), 500),
                      'quantity': text(line.get('quantity'), 40),
                      'unitPriceCentavos': money(line['rate']) if line.get('rate') is not None else None,
                      'amountCentavos': money(line['item_total']) if line.get('item_total') is not None else None})
    result = {'id': identifier, 'number': text(raw.get('invoice_number' if is_invoice else 'salesorder_number'), 100),
              'date': on.isoformat(), 'status': text(raw.get('status') or 'unknown', 80),
              'customerId': source_id(raw.get('customer_id')), 'customerName': text(raw.get('customer_name')),
              'reference': text(raw.get('reference_number'), 120), 'currency': currency,
              'totalCentavos': money(raw['total']), 'lines': lines,
              'sourceUpdatedAt': text(raw.get('last_modified_time'), 80),
              'detailLoaded': True, 'relationshipsFresh': True}
    if is_invoice:
        company, value = invoicing_from(raw)
        result.update(company=company, invoicingFrom=value, orderIds=sorted(order_ids(raw)),
                      balanceCentavos=money(raw['balance']) if raw.get('balance') is not None else None)
        for target, source in (('subtotalCentavos','sub_total'),('taxCentavos','tax_total'),
                               ('shippingCentavos','shipping_charge'),('discountCentavos','discount_total'),
                               ('withheldCentavos','tax_amount_withheld')):
            result[target]=money(raw[source]) if raw.get(source) is not None else None
        result['dueDate']=text(raw.get('due_date'),10)
    else:
        declared, value = invoicing_from(raw)
        result.update(invoiceIds=sorted(linked_invoices(raw)), salesperson=text(raw.get('salesperson_name'), 120),
                      declaredCompany=declared, declaredInvoicingFrom=value,
                      invoicedStatus=text(raw.get('invoiced_status'),80))
    return result


def capture(reader, start, end, invoice_limit=30, order_limit=30, pages=2, related_limit=15):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last or (last-first).days > 93 or not 1 <= pages <= 5 or not 1 <= invoice_limit <= 60 or not 1 <= order_limit <= 40 or not 0 <= related_limit <= 30:
        raise ValueError('Choose a bounded source sample.')
    coverage = {'mode':'bounded-demo', 'windowStart':start, 'windowEnd':end, 'listPages':0,
                'summaries':0, 'invoiceDetails':0, 'orderDetails':0, 'relatedInvoiceDetails':0,
                'relatedOutsideWindow':0, 'listComplete':False, 'partial':True, 'error':None}
    staged, summaries = {}, {}
    def remember(kind, raw):
        normalized = normalize(kind, raw)
        staged[(kind, normalized['id'])] = normalized
        return normalized
    try:
        for page in range(1, pages+1):
            payload = reader.get('/invoices', {'date_start':start,'date_end':end,'page':page,'per_page':100,'sort_column':'date'})
            values = payload.get('invoices')
            if not isinstance(values, list): raise ProbeStopped('Invoice list schema was not recognised.')
            coverage['listPages'] += 1
            for row in values:
                identifier = source_id(row.get('invoice_id'))
                try: inside = first <= date.fromisoformat(row.get('date', '')) <= last
                except (ValueError, TypeError): inside = False
                if identifier and inside: summaries[identifier] = row
            more = (payload.get('page_context') or {}).get('has_more_page')
            if more is False or (more is None and len(values)<100):
                coverage['listComplete'] = True
                break
        for row in sample_rows(list(summaries.values()), invoice_limit):
            identifier = str(row['invoice_id'])
            raw = reader.get('/invoices/'+identifier).get('invoice')
            if not isinstance(raw, dict) or str(raw.get('invoice_id')) != identifier: raise ProbeStopped('Invoice identity mismatch.')
            remember('invoice', raw)
            coverage['invoiceDetails'] += 1
        order_queue = sorted({order for (kind, _), inv in staged.items() if kind=='invoice' for order in inv['orderIds']})
        for identifier in order_queue[:order_limit]:
            raw = reader.get('/salesorders/'+identifier).get('salesorder')
            if not isinstance(raw, dict) or str(raw.get('salesorder_id')) != identifier: raise ProbeStopped('Sales order identity mismatch.')
            order = remember('salesorder', raw)
            coverage['orderDetails'] += 1
            for invoice_id in order['invoiceIds']:
                if ('invoice', invoice_id) in staged: continue
                if coverage['relatedInvoiceDetails'] >= related_limit: break
                raw_invoice = reader.get('/invoices/'+invoice_id).get('invoice')
                if not isinstance(raw_invoice, dict) or str(raw_invoice.get('invoice_id')) != invoice_id: raise ProbeStopped('Related invoice identity mismatch.')
                invoice = remember('invoice', raw_invoice)
                coverage['relatedInvoiceDetails'] += 1
                coverage['relatedOutsideWindow'] += int(not first <= date.fromisoformat(invoice['date']) <= last)
        coverage['partial'] = not (coverage['listComplete'] and coverage['invoiceDetails']==len(summaries) and len(order_queue)<=order_limit)
    except (ProbeStopped, ValueError):
        # No raw response/provider details in persisted errors or logs.
        coverage['error'] = 'Read stopped before the requested sample finished; saved records remain a partial sample.'
        coverage['partial'] = True
    coverage['summaries'] = len(summaries)
    coverage['unreadLinkedInvoices'] = len({i for (kind, _), doc in staged.items() if kind=='salesorder'
                                          for i in doc['invoiceIds'] if ('invoice', i) not in staged})
    if coverage['unreadLinkedInvoices']:
        coverage['partial'] = True
    coverage['getRequests'] = reader.calls
    coverage['stagedDocuments'] = len(staged)
    return staged, coverage


def persist(db, organization, staged, coverage, started):
    now = utcnow()
    for (kind, identifier), payload in staged.items():
        record = db.get(ZohoSourceDocument, (organization, kind, identifier))
        if record is None:
            db.add(ZohoSourceDocument(organization_id=organization, kind=kind, source_id=identifier, data=payload, fetched_at=now))
        else:
            record.data, record.fetched_at = payload, now
    db.add(ZohoSourceRun(organization_id=organization, started_at=started, finished_at=now,
                         window_start=date.fromisoformat(coverage['windowStart']), window_end=date.fromisoformat(coverage['windowEnd']), coverage=coverage))
    db.commit()


def saved_orders(db, organization):
    records = list(db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==organization)))
    invoices = {r.source_id:r for r in records if r.kind=='invoice'}
    by_order = defaultdict(set)
    for identifier, invoice in invoices.items():
        for order_id in invoice.data['orderIds']: by_order[order_id].add(identifier)
    result = []
    for record in records:
        if record.kind != 'salesorder': continue
        data = record.data
        ids = set(data['invoiceIds']) | by_order[record.source_id]
        linked = [invoices[i].data for i in sorted(ids) if i in invoices]
        missing = len(ids-set(invoices))
        conflicts = [i for i in linked if i['orderIds'] and record.source_id not in i['orderIds']]
        pending_links = [i for i in linked if i.get('relationshipsFresh') is False]
        valid = [i for i in linked if i not in conflicts and i not in pending_links]
        companies = {i['company'] for i in valid}
        totals = defaultdict(int)
        for invoice in valid:
            if invoice['company']=='2mg': totals[invoice['currency']] += invoice['totalCentavos']
        label = 'Mixed: 2MG and GPI' if {'2mg','gpi'} <= companies else '2MG' if '2mg' in companies else 'GPI' if 'gpi' in companies else 'Not yet attributed'
        declared_2mg = data.get('declaredCompany')=='2mg'
        if not companies and declared_2mg:
            label = '2MG indicated on order · invoices pending'
        elif not companies and data.get('declaredCompany')=='gpi':
            label = 'GPI indicated on order · invoices pending'
        if missing or conflicts or pending_links or 'unknown' in companies: label += ' · attribution incomplete'
        result.append({**data, 'invoices':linked, 'has2mg':'2mg' in companies or declared_2mg, 'companyLabel':label,
                       'missingInvoiceDetails':missing, 'relationshipIssues':len(conflicts), 'pendingInvoiceLinks':len(pending_links), 'twoMgInvoiceTotals':[{'currency':c,'centavos':v} for c,v in sorted(totals.items())],
                       'fetchedAt':record.fetched_at.isoformat()})
    return sorted(result, key=lambda x:(x['date'], x['number'], x['id']), reverse=True)
