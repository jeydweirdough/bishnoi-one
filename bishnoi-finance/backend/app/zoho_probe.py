"""Bounded GET-only Zoho probe. Source payloads stay in memory; reports contain no raw records."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
import hashlib
import re
import time
from contextlib import contextmanager, nullcontext

from fastapi import HTTPException
import httpx
from app import zoho_connection as oauth


class ProbeStopped(Exception):
    """A safe reason, never a provider payload or credential."""


@dataclass(frozen=True)
class Limits:
    pages: int = 2
    page_size: int = 100
    invoice_details: int = 30
    order_details: int = 8
    related_invoice_details: int = 12
    requests: int = 60

    def validate(self):
        values = (self.pages, self.page_size, self.invoice_details, self.order_details,
                  self.related_invoice_details, self.requests)
        if any(not isinstance(v, int) or v < 1 for v in values) or self.pages > 5 or self.page_size > 100 or self.requests > 100:
            raise ValueError('Probe limits exceed the supported bounded sample.')
        if self.invoice_details > 60 or self.order_details > 20 or self.related_invoice_details > 30:
            raise ValueError('Detail limits exceed the supported bounded sample.')


class ZohoReader:
    """Only fixed invoice/SO read paths; selected org cannot be overridden by callers."""
    def __init__(self, settings, maximum=60, interval=1.1, progress=None):
        if not 1 <= maximum <= 100 or interval < 1:
            raise ValueError('Use 1–100 requests and at least one second between calls.')
        self.settings, self.maximum, self.interval = settings, maximum, interval
        self.calls, self.refreshes, self._last = 0, 0, 0
        self.progress = progress or (lambda count: None)
        with oauth.locked(settings) as record:
            organization = record.get('connection', {}).get('organization')
            if not organization:
                raise ProbeStopped('Connect and confirm the Zoho organisation in Finance first.')
            self.organization = organization['id']
            self.connected_at = record['connection'].get('connectedAt')
        self.daily_limit = settings.zoho_daily_limit

    @contextmanager
    def save_guard(self):
        """Do not publish a response after a disconnect, org change or lost lease."""
        from app.zoho_storage import database_mode
        from app.zoho_runtime import fence
        try:
            with oauth.locked(self.settings) as record:
                connection=record.get('connection') or {}
                if (connection.get('organization') or {}).get('id') != self.organization or connection.get('connectedAt') != self.connected_at:
                    raise ProbeStopped('Connection changed; old results were not saved.')
                with fence(self.settings,self.organization) if database_mode(self.settings) else nullcontext():
                    yield
        except HTTPException:
            raise ProbeStopped('The connection or updater changed; old results were not saved.') from None

    def get(self, path, params=None):
        if not re.fullmatch(r'/(?:invoices(?:/[A-Za-z0-9_-]{1,80})?|salesorders(?:/[A-Za-z0-9_-]{1,80})?)', path):
            raise ProbeStopped('This probe only permits invoice and sales-order reads.')
        params = dict(params or {})
        if set(params) - {'date_start', 'date_end', 'page', 'per_page', 'sort_column', 'last_modified_time'}:
            raise ProbeStopped('Unsupported probe query; organisation is chosen by the saved connection.')
        oauth.require_network(self.settings)
        try:
            with oauth.locked(self.settings) as record:
                connection = record.get('connection') or {}
                if connection.get('organization', {}).get('id') != self.organization or connection.get('connectedAt') != self.connected_at:
                    raise ProbeStopped('Connection or selected organisation changed. Start a fresh probe.')
                if connection.get('expires', 0) <= time.time() + 60:
                    oauth.refresh(self.settings, connection)
                    self.refreshes += 1
                with httpx.Client(timeout=15, follow_redirects=False) as client:
                    def read():
                        if self.calls >= self.maximum:
                            raise ProbeStopped('Request budget reached; findings are a partial sample.')
                        time.sleep(max(0, self.interval - (time.monotonic() - self._last)))
                        from app.zoho_storage import database_mode
                        if database_mode(self.settings):
                            from app.zoho_runtime import reserve
                            reserve(self.settings,self.organization,self.daily_limit)
                        self.calls += 1
                        self._last = time.monotonic()
                        self.progress(self.calls)
                        return client.get(oauth.REGIONS[self.settings.zoho_region][1] + '/books/v3' + path,
                                          params={**params, 'organization_id': self.organization},
                                          headers={'Authorization': 'Zoho-oauthtoken ' + connection['access']})
                    response = read()
                    if response.status_code == 401:
                        oauth.refresh(self.settings, connection)
                        self.refreshes += 1
                        response = read()
                if response.status_code == 429:
                    raise ProbeStopped('Zoho rate limit reached; stopped without further retries.')
                if response.status_code >= 400:
                    raise ProbeStopped(f'Zoho refused a read (HTTP {response.status_code}); no records changed.')
                data = response.json()
                if not isinstance(data, dict) or data.get('code') != 0:
                    raise ProbeStopped('Zoho did not return a successful read; no provider payload was recorded.')
                return data
        except (httpx.HTTPError, ValueError):
            raise ProbeStopped('Read failed or returned invalid JSON; stopped without recording source payloads.') from None
        except HTTPException as error:
            raise ProbeStopped(f'Connection unavailable (HTTP {error.status_code}); check Finance connection status.') from None


def source_id(value):
    return str(value) if isinstance(value, (str, int)) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', str(value)) else None


def order_ids(invoice):
    result = set()
    for row in [invoice, *(invoice.get('salesorders') or []), *(invoice.get('line_items') or [])]:
        if isinstance(row, dict):
            value = source_id(row.get('salesorder_id'))
            if value:
                result.add(value)
    return result


def linked_invoices(order):
    return {value for row in (order.get('invoices') or []) if isinstance(row, dict)
            if (value := source_id(row.get('invoice_id')))}


def prefix_hint(number):
    value = str(number or '').upper().strip()
    if re.match(r'^2MG(?:[-\s]|$)', value): return '2MG-prefix'
    if re.match(r'^GPI(?:[-\s]|$)', value): return 'GPI-prefix'
    if re.match(r'^INV(?:[-\s]|$)', value): return 'INV-prefix'
    return 'other-or-missing'


def marker_summary(entity):
    """Field presence and known company words only; never print arbitrary source text."""
    result = Counter()
    for key in ('location_id', 'location_name', 'branch_id', 'branch_name', 'template_id', 'template_name'):
        if entity.get(key):
            result[key + ':present'] += 1
            for company in ('2MG', 'GPI'):
                if re.search(r'(?<![A-Z0-9])' + company + r'(?![A-Z0-9])', str(entity[key]).upper()):
                    result[key + ':' + company + '-word'] += 1
    for area in ('custom_fields', 'tags'):
        for row in entity.get(area) or []:
            if not isinstance(row, dict): continue
            result[area + ':entries'] += 1
            label = str(row.get('label', row.get('tag_name', '')))
            company_label = bool(re.search(r'company|entity|business.?unit|branch|source', label, re.I))
            if company_label: result[area + ':company-like-label'] += 1
            text = ' '.join(str(row.get(k, '')) for k in ('value', 'tag_option_name', 'label', 'tag_name')).upper()
            for company in ('2MG', 'GPI'):
                if re.search(r'(?<![A-Z0-9])' + company + r'(?![A-Z0-9])', text):
                    result[area + ':' + company + '-word'] += 1
    lines = entity.get('line_items') or []
    result['lines:count'] += len(lines)
    for line in lines:
        if isinstance(line, dict):
            for key in ('salesorder_item_id', 'salesorder_id', 'location_id', 'tags'):
                if line.get(key): result['lines:' + key + ':present'] += 1
    return result


def sample_rows(rows, limit):
    """Prioritise mixed-prefix references as candidates, then balance series."""
    references = defaultdict(list)
    for row in rows:
        if row.get('reference_number'):
            references[str(row['reference_number'])].append(row)
    candidates = [row for group in references.values()
                  if {'2MG-prefix', 'GPI-prefix'}.issubset({prefix_hint(r.get('invoice_number')) for r in group})
                  for row in group]
    result = []
    seen = set()
    for row in candidates:
        if row['invoice_id'] not in seen and len(result) < limit:
            result.append(row)
            seen.add(row['invoice_id'])
    buckets = defaultdict(list)
    for row in rows:
        if row['invoice_id'] not in seen:
            buckets[prefix_hint(row.get('invoice_number'))].append(row)
    while len(result) < limit and any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key] and len(result) < limit: result.append(buckets[key].pop(0))
    return result


def company_field_evidence(invoice):
    """Known words and semantic label classes only; no source labels/values."""
    evidence = []
    for field in invoice.get('custom_fields') or []:
        if not isinstance(field, dict): continue
        label = str(field.get('label', '')).lower()
        kind = next((word for word in ('company', 'source', 'branch', 'entity', 'business') if word in label), None)
        if not kind: continue
        value = str(field.get('value', '')).upper()
        words = [word for word in ('2MG', 'GPI', 'GETMEDS') if word in value]
        evidence.append((kind, '+'.join(words) if words else 'other-or-empty'))
    return evidence


def run_probe(reader, start, end, limits=Limits()):
    limits.validate()
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end or (end - start).days > 93:
        raise ValueError('Choose an ordered date window of at most 94 days.')
    report = {'window': {'start': start.isoformat(), 'end': end.isoformat()},
              'limits': vars(limits), 'invoiceListRows': 0, 'uniqueInvoicesInWindow': 0,
              'listPages': 0, 'listCoverage': 'not-started', 'outsideWindowRowsIgnored': 0,
              'invoiceDetails': 0, 'orderDetails': 0, 'relatedInvoiceDetails': 0,
              'relatedInvoicesOutsideWindow': 0, 'stopReason': None,
              'prefixesAreOwnershipProof': False, 'sourceRecordsPersisted': False}
    rows, details, associations, orders = {}, {}, defaultdict(set), {}
    invoice_fields, invoice_markers, order_markers = Counter(), Counter(), Counter()
    explicit_order_links, reciprocal_links, inconsistent_links = set(), set(), set()
    def consume(invoice, identifier):
        details[identifier] = invoice
        invoice_fields.update(key for key in invoice if key.startswith(('custom_', 'cf_')) or
                              set(key.lower().split('_')) & {'salesorder', 'salesorders', 'order', 'location', 'branch', 'template', 'tags'})
        invoice_markers.update(marker_summary(invoice))
        for order_id in order_ids(invoice):
            associations[order_id].add(identifier)
            explicit_order_links.add((order_id, identifier))
    try:
        for page in range(1, limits.pages + 1):
            payload = reader.get('/invoices', {'date_start': start.isoformat(), 'date_end': end.isoformat(),
                                             'page': page, 'per_page': limits.page_size, 'sort_column': 'date'})
            values = payload.get('invoices')
            if not isinstance(values, list): raise ProbeStopped('Invoice list schema was not recognised.')
            report['listPages'] += 1
            report['invoiceListRows'] += len(values)
            for row in values:
                identifier = source_id(row.get('invoice_id'))
                try: in_window = start <= date.fromisoformat(row.get('date', '')) <= end
                except (ValueError, TypeError): in_window = False
                if not in_window:
                    report['outsideWindowRowsIgnored'] += 1
                    continue
                if identifier: rows[identifier] = row
            more = (payload.get('page_context') or {}).get('has_more_page')
            if more is False or (more is None and len(values) < limits.page_size):
                report['listCoverage'] = 'returned-pages-exhausted'
                break
            report['listCoverage'] = 'page-limit-reached'
        report['uniqueInvoicesInWindow'] = len(rows)
        for row in sample_rows(list(rows.values()), limits.invoice_details):
            identifier = str(row['invoice_id'])
            payload = reader.get('/invoices/' + identifier)
            invoice = payload.get('invoice')
            if not isinstance(invoice, dict) or str(invoice.get('invoice_id')) != identifier:
                raise ProbeStopped('Invoice detail identity/schema mismatch; stopped.')
            report['invoiceDetails'] += 1
            consume(invoice, identifier)
        # Prioritise known mixed-prefix groups, then multi-invoice groups, then others.
        def priority(order_id):
            hints = {prefix_hint(details[i].get('invoice_number')) for i in associations[order_id]}
            return (not {'2MG-prefix', 'GPI-prefix'}.issubset(hints), -len(associations[order_id]), order_id)
        order_queue = sorted(associations, key=priority)[:limits.order_details]
        for order_id in order_queue:
            payload = reader.get('/salesorders/' + order_id)
            order = payload.get('salesorder')
            if not isinstance(order, dict) or str(order.get('salesorder_id')) != order_id:
                raise ProbeStopped('Sales order identity/schema mismatch; stopped.')
            orders[order_id] = order
            report['orderDetails'] += 1
            order_markers.update(marker_summary(order))
            for invoice_id in sorted(linked_invoices(order)):
                if invoice_id not in details and report['relatedInvoiceDetails'] < limits.related_invoice_details:
                    related = reader.get('/invoices/' + invoice_id).get('invoice')
                    if not isinstance(related, dict) or str(related.get('invoice_id')) != invoice_id:
                        raise ProbeStopped('Related invoice identity/schema mismatch; stopped.')
                    report['relatedInvoiceDetails'] += 1
                    try: outside = not start <= date.fromisoformat(related.get('date', '')) <= end
                    except (ValueError, TypeError): outside = True
                    report['relatedInvoicesOutsideWindow'] += int(outside)
                    consume(related, invoice_id)
                if invoice_id in details:
                    associations[order_id].add(invoice_id)
                    if order_id in order_ids(details[invoice_id]): reciprocal_links.add((order_id, invoice_id))
                    elif order_ids(details[invoice_id]): inconsistent_links.add((order_id, invoice_id))
    except ProbeStopped as error:
        report['stopReason'] = str(error)
    # Summarise only; never return raw records, numbers, customer data or source IDs.
    report['uniqueInvoicesInWindow'] = len(rows)
    report['listPrefixHints'] = dict(Counter(prefix_hint(row.get('invoice_number')) for row in rows.values()))
    report['detailPrefixHints'] = dict(Counter(prefix_hint(row.get('invoice_number')) for row in details.values()))
    report['companyFieldHintCorrelation'] = dict(Counter(
        prefix_hint(row.get('invoice_number')) + ' / ' + kind + '-field / ' + hint
        for row in details.values() for kind, hint in company_field_evidence(row)))
    reference_groups = defaultdict(list)
    for row in rows.values():
        if row.get('reference_number'):
            reference_groups[str(row['reference_number'])].append(row)
    mixed_references = [group for group in reference_groups.values()
                        if {'2MG-prefix', 'GPI-prefix'}.issubset({prefix_hint(row.get('invoice_number')) for row in group})]
    report['mixedPrefixReferenceCandidates'] = len(mixed_references)
    report['referenceCandidateDistinctOrderCounts'] = [len(set().union(*(
        order_ids(details.get(str(row['invoice_id']), {})) for row in group))) for group in mixed_references[:5]]
    report['detailStatuses'] = dict(Counter(str(row.get('status', 'unknown')) for row in details.values()))
    report['invoicesWithExplicitOrderIDs'] = sum(bool(order_ids(row)) for row in details.values())
    report['orderGroupsBySourceID'] = len(associations)
    report['multipleInvoiceOrderGroups'] = sum(len(ids) > 1 for ids in associations.values())
    report['reciprocalInvoiceOrderLinks'] = len(reciprocal_links)
    report['inconsistentRelationshipLinks'] = len(inconsistent_links)
    mixed = []
    for order_id, invoice_ids in associations.items():
        labels = Counter(prefix_hint(details[i].get('invoice_number')) for i in invoice_ids)
        if {'2MG-prefix', 'GPI-prefix'}.issubset(labels):
            mixed.append({'handle': hashlib.sha256(order_id.encode()).hexdigest()[:12],
                          'invoicePrefixHints': dict(labels), 'orderFetched': order_id in orders,
                          'reciprocalLinks': sum((order_id, i) in reciprocal_links for i in invoice_ids)})
    report['mixedPrefixOrderCandidates'] = len(mixed)
    report['candidateExamples'] = mixed[:5]
    report['invoiceStructuralFields'] = dict(invoice_fields)
    report['invoiceMarkerPresence'] = dict(invoice_markers)
    report['orderMarkerPresence'] = dict(order_markers)
    report['getRequests'] = reader.calls
    report['oauthRefreshes'] = getattr(reader, 'refreshes', 0)
    report['detailCoverageComplete'] = report['invoiceDetails'] == len(rows) and report['stopReason'] is None
    report['interpretation'] = ('Prefix combinations are investigation candidates, not confirmed legal-company ownership. '
                                'No matches in this bounded sample do not prove mixed orders never occur. '
                                'Reading source records does not post Finance books or establish BIR compliance.')
    return report
