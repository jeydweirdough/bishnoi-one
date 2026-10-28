from datetime import date
import json
import pytest
from app.zoho_probe import Limits, ProbeStopped, ZohoReader, marker_summary, order_ids, run_probe


class Reader:
    def __init__(self, data, maximum=100):
        self.data, self.calls, self.paths, self.maximum = data, 0, [], maximum
    def get(self, path, params=None):
        if self.calls >= self.maximum: raise ProbeStopped('Request budget reached.')
        self.calls += 1
        self.paths.append((path, params))
        if path == '/invoices': return self.data[(path, params['page'])]
        return self.data[path]


def invoice(identifier, number, orders, on='2026-10-21'):
    return {'invoice_id': identifier, 'invoice_number': number, 'date': on,
            'status': 'sent', 'customer_name': 'DO NOT EXPOSE THIS CUSTOMER',
            'salesorders': [{'salesorder_id': i} for i in orders],
            'custom_fields': [{'label': 'Private note', 'value': 'DO NOT EXPOSE PRIVATE NOTE'}],
            'line_items': [{'salesorder_item_id': 'line-example'}]}


def test_mixed_groups_multiple_orders_and_outside_window_followup_redacted():
    a=invoice('a','2MG-SI1',['order1','order2'])
    b=invoice('b','GPI-SI1',['order1'],'2026-09-30')
    reader=Reader({('/invoices',1):{'invoices':[a,a], 'page_context':{'has_more_page':False}},
                   '/invoices/a':{'invoice':a}, '/invoices/b':{'invoice':b},
                   '/salesorders/order1':{'salesorder':{'salesorder_id':'order1','invoices':[{'invoice_id':'a'},{'invoice_id':'b'}]}},
                   '/salesorders/order2':{'salesorder':{'salesorder_id':'order2','invoices':[{'invoice_id':'a'}]}}})
    report=run_probe(reader,'2026-10-20','2026-10-27')
    assert report['uniqueInvoicesInWindow']==1 and report['invoiceDetails']==1
    assert report['mixedPrefixOrderCandidates']==1 and report['multipleInvoiceOrderGroups']==1
    assert report['orderGroupsBySourceID']==2 and report['relatedInvoicesOutsideWindow']==1
    assert report['reciprocalInvoiceOrderLinks']==3
    assert report['prefixesAreOwnershipProof'] is False and report['sourceRecordsPersisted'] is False
    text=json.dumps(report)
    assert 'DO NOT EXPOSE' not in text and '2MG-SI1' not in text and 'order1' not in text


def test_prefixes_and_shared_reference_do_not_fabricate_order_links():
    a=invoice('a','2MG-SI1',[]);b=invoice('b','GPI-SI1',[])
    a['reference_number']=b['reference_number']='same-reference'
    reader=Reader({('/invoices',1):{'invoices':[a,b],'page_context':{'has_more_page':False}},
                   '/invoices/a':{'invoice':a},'/invoices/b':{'invoice':b}})
    report=run_probe(reader,'2026-10-20','2026-10-27')
    assert report['mixedPrefixOrderCandidates']==0 and report['orderGroupsBySourceID']==0
    assert report['detailPrefixHints']=={'2MG-prefix':1,'GPI-prefix':1}


def test_page_date_detail_and_request_limits_are_explicit():
    a=invoice('a','2MG-SI1',[]);b=invoice('b','GPI-SI1',[]);outside=invoice('old','INV-1',[],'2025-01-01')
    reader=Reader({('/invoices',1):{'invoices':[a,b,outside],'page_context':{'has_more_page':True}},
                   '/invoices/a':{'invoice':a},'/invoices/b':{'invoice':b}},maximum=2)
    report=run_probe(reader,'2026-10-20','2026-10-27',Limits(pages=1))
    assert report['listCoverage']=='page-limit-reached' and report['outsideWindowRowsIgnored']==1
    assert report['getRequests']==2 and report['stopReason'] and not report['detailCoverageComplete']
    assert reader.paths[0][1]['date_start']=='2026-10-20'


def test_invalid_dates_do_not_request_anything():
    reader=Reader({})
    with pytest.raises(ValueError):run_probe(reader,'2026-10-27','2026-01-01')
    with pytest.raises(ValueError):run_probe(reader,'2026-01-01','2026-10-27')
    assert reader.calls==0


def test_marker_output_contains_only_presence_and_company_words():
    data={'custom_fields':[{'label':'Company','value':'2MG private customer wording'},
                           {'label':'Bank account','value':'999999999999'}],
          'location_name':'PRIVATE CUSTOMER', 'line_items':[{'salesorder_id':'safe-id'}]}
    markers=marker_summary(data)
    assert markers['custom_fields:2MG-word']==1 and markers['custom_fields:company-like-label']==1
    text=json.dumps(markers)
    assert 'PRIVATE' not in text and '999999' not in text and 'safe-id' not in text


def test_paths_and_organization_override_rejected_before_network():
    reader=object.__new__(ZohoReader)
    for path in ('https://evil.example','/invoices/a/email','/salesorders/../x','/contacts','/invoices/../x'):
        with pytest.raises(ProbeStopped):reader.get(path)
    with pytest.raises(ProbeStopped):reader.get('/invoices',{'organization_id':'other-org'})
    with pytest.raises(ValueError):Limits(requests=101).validate()
    assert order_ids({'salesorder_id':'one','salesorders':[{'salesorder_id':'two'}],
                      'line_items':[{'salesorder_id':'three'}]})=={'one','two','three'}

def test_shared_reference_prioritizes_candidates_without_confirming_relationship():
    from app.zoho_probe import sample_rows,company_field_evidence
    a=invoice('a','2MG-ONE',[]); b=invoice('b','GPI-ONE',[]); c=invoice('c','INV-ONE',[])
    a['reference_number']=b['reference_number']='same business reference'
    assert {row['invoice_id'] for row in sample_rows([c,a,b],2)}=={'a','b'}
    assert not order_ids(a) and not order_ids(b)
    evidence=company_field_evidence({'custom_fields':[{'label':'Source','value':'2MG private customer wording'},
                                                     {'label':'Customer name','value':'do not expose'}]})
    assert evidence==[('source','2MG')]
    assert 'private' not in json.dumps(evidence)
