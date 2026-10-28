"""Resumable month summaries and bounded detail enrichment, independent of page requests."""
from datetime import datetime,timedelta,timezone
from contextlib import nullcontext
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models import ZohoSourceDocument,ZohoSourceRun,utcnow
from app.zoho_source import normalize
from app.zoho_probe import ProbeStopped


def month_window():
    import calendar
    today=datetime.now(ZoneInfo('Asia/Manila')).date()
    return today.replace(day=1).isoformat(),today.replace(day=calendar.monthrange(today.year,today.month)[1]).isoformat()


def latest_month_run(db,org,start,end):
    return next((r for r in db.scalars(select(ZohoSourceRun).where(ZohoSourceRun.organization_id==org).order_by(ZohoSourceRun.started_at.desc()))
                 if r.coverage.get('mode')=='month-sync' and r.window_start.isoformat()==start
                 and r.window_end.isoformat()==end),None)


def usage_today(db,org):
    day=datetime.now(ZoneInfo('Asia/Manila')).date().isoformat()
    return sum(r.coverage.get('getRequests',0)+r.coverage.get('oauthRefreshes',0)
               for r in db.scalars(select(ZohoSourceRun).where(ZohoSourceRun.organization_id==org))
               if r.coverage.get('mode')=='month-sync' and r.coverage.get('usageDay')==day)


def save_document(db,org,kind,raw,full):
    data=normalize(kind,raw)
    old=db.get(ZohoSourceDocument,(org,kind,data['id']))
    now=utcnow()
    if not full:
        unchanged=bool(old and old.data.get('sourceUpdatedAt') and
                       old.data.get('sourceUpdatedAt')==data['sourceUpdatedAt'])
        previous=old.data if old else {}
        # Summaries do not contain authoritative links or line detail.
        for key in ('lines','orderIds','invoiceIds'):
            if previous.get(key):data[key]=previous[key]
        if unchanged:
            for key in ('subtotalCentavos','taxCentavos','shippingCentavos','discountCentavos','withheldCentavos'):
                if data.get(key) is None and key in previous:data[key]=previous[key]
        data['detailLoaded']=bool(unchanged and previous.get('detailLoaded'))
        data['relationshipsFresh']=bool(unchanged and previous.get('relationshipsFresh',True))
        if unchanged and previous.get('detailFetchedAt'):data['detailFetchedAt']=previous['detailFetchedAt']
    else:
        data['detailFetchedAt']=now.isoformat()
    if old:old.data,old.fetched_at=data,now
    else:db.add(ZohoSourceDocument(organization_id=org,kind=kind,source_id=data['id'],data=data,fetched_at=now))
    return data


def sync_month(sessions,reader,start,end,detail_limit=30,daily_limit=500):
    from datetime import date
    if date.fromisoformat(start)>date.fromisoformat(end) or (date.fromisoformat(end)-date.fromisoformat(start)).days>31:
        raise ValueError('Use a current-month window of at most32days.')
    if not 0<=detail_limit<=60 or not 1<=daily_limit<=1000:raise ValueError('Invalid sync budget.')
    started=utcnow();checkpoint=started.astimezone(ZoneInfo('Asia/Manila')).strftime('%Y-%m-%dT%H:%M:%S%z')
    with sessions() as db:
        previous=latest_month_run(db,reader.organization,start,end)
        previous_data=previous.coverage if previous else {}
        if usage_today(db,reader.organization)>=daily_limit:raise ProbeStopped('Local daily request cap reached; saved records remain available.')
        # Resume exact page positions after a bounded/failed scan. Otherwise use an overlap change feed.
        resume=bool(previous and not previous_data.get('summaryComplete'))
        if resume:
            checkpoint=previous_data.get('targetCheckpoint',checkpoint)
        cursors=dict(previous_data.get('cursors',{})) if resume else {'invoice':1,'salesorder':1}
        since=previous_data.get('since') if resume else previous_data.get('checkpoint')
        if since and not resume:
            since=(datetime.strptime(since,'%Y-%m-%dT%H:%M:%S%z')-timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S%z')
        coverage={'mode':'month-sync','windowStart':start,'windowEnd':end,'usageDay':datetime.now(ZoneInfo('Asia/Manila')).date().isoformat(),
                  'cursors':cursors,'since':since,'checkpoint':previous_data.get('checkpoint'),'targetCheckpoint':checkpoint,
                  'summaryComplete':False,'partial':True,'error':None,'getRequests':0,'oauthRefreshes':0,
                  'invoiceSummaries':0,'orderSummaries':0,'detailReads':0,'intervalSeconds':300,
                  'dailyLimit':daily_limit,'scope':'This month plus updates to previously saved documents',
                  'fullSummaryScanAt':previous_data.get('fullSummaryScanAt')}
        run=ZohoSourceRun(organization_id=reader.organization,started_at=started,finished_at=started,
                          window_start=date.fromisoformat(start),window_end=date.fromisoformat(end),coverage=coverage)
        db.add(run);db.commit();run_id=run.id
    def update(db):
        coverage['getRequests']=reader.calls
        coverage['oauthRefreshes']=reader.refreshes
        with reader.save_guard() if hasattr(reader,'save_guard') else nullcontext():
            row=db.get(ZohoSourceRun,run_id);row.coverage=dict(coverage);row.finished_at=utcnow();db.commit()
    def request(path,params=None):
        with sessions() as db:
            if usage_today(db,reader.organization)>=daily_limit:raise ProbeStopped('Local daily request cap reached.')
        return reader.get(path,params)
    try:
        for kind,path,key in (('invoice','/invoices','invoices'),('salesorder','/salesorders','salesorders')):
            page=cursors.get(kind,1)
            while page is not None:
                params={'page':page,'per_page':200,'sort_column':'date'}
                if since:params['last_modified_time']=since
                else:params.update(date_start=start,date_end=end)
                payload=request(path,params)
                values=payload.get(key)
                if not isinstance(values,list):raise ProbeStopped('Source list response was not recognised.')
                with sessions() as db:
                    for raw in values:
                        identifier=str(raw.get('invoice_id' if kind=='invoice' else 'salesorder_id',''))
                        on=str(raw.get('date',''))
                        if not start<=on<=end and not db.get(ZohoSourceDocument,(reader.organization,kind,identifier)):continue
                        save_document(db,reader.organization,kind,raw,False)
                    more=(payload.get('page_context')or{}).get('has_more_page')
                    page=page+1 if more is True or (more is None and len(values)==200) else None
                    cursors[kind]=page;coverage['cursors']=dict(cursors)
                    coverage['invoiceSummaries' if kind=='invoice' else 'orderSummaries']+=len(values)
                    update(db)
        coverage['summaryComplete']=True;coverage['checkpoint']=checkpoint
        if not since:coverage['fullSummaryScanAt']=checkpoint
        with sessions() as db:update(db)
        # Fill missing/currently-stale details outside frontend requests. Alternate kinds for fair progress.
        with sessions() as db:
            candidates={kind:[] for kind in ('invoice','salesorder')}
            for row in db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==reader.organization)):
                if row.kind in candidates and start<=row.data.get('date','')<=end and not row.data.get('detailLoaded',False):
                    candidates[row.kind].append((row.data.get('date',''),row.source_id))
            for values in candidates.values():values.sort(reverse=True)
        for index in range(detail_limit):
            kind='invoice' if index%2==0 else 'salesorder'
            if not candidates[kind]:kind='salesorder' if kind=='invoice' else 'invoice'
            if not candidates[kind]:break
            _,identifier=candidates[kind].pop(0)
            path='/invoices/' if kind=='invoice' else '/salesorders/'
            raw=request(path+identifier).get(kind)
            if not isinstance(raw,dict) or str(raw.get('invoice_id' if kind=='invoice' else 'salesorder_id'))!=identifier:
                raise ProbeStopped('Source detail identity mismatch.')
            with sessions() as db:
                save_document(db,reader.organization,kind,raw,True);coverage['detailReads']+=1;update(db)
    except (ProbeStopped,ValueError):
        coverage['error']='Sync paused by a request limit or read failure. Saved records remain available; the next run resumes safely.'
    with sessions() as db:
        rows=list(db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==reader.organization)))
        current=[r for r in rows if start<=r.data.get('date','')<=end]
        coverage['savedMonthInvoices']=sum(r.kind=='invoice' for r in current)
        coverage['savedMonthOrders']=sum(r.kind=='salesorder' for r in current)
        coverage['pendingDetails']=sum(not r.data.get('detailLoaded',False) for r in current)
        coverage['partial']=not coverage['summaryComplete'] or bool(coverage['pendingDetails'])
        update(db)
    return coverage
