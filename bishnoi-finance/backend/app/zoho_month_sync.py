"""Resumable month summaries and bounded detail enrichment, independent of page requests.

How the daily request cap is spent (Plan - Zoho reader budget, approved 2026-10-30):
- Every cycle runs the cheap change scan (200 summaries per request), so new and edited Zoho records show
  within one cycle.
- Details of records that changed come next, at any hour, and may use the reserve.
- Details of older records still missing them ("backfill") use only what is left after the reserve, spread
  evenly over the cycles left in the working day; nights and weekends do no backfill.
- Once a day the scan lists the whole window instead of only changes, and saved records Zoho no longer lists
  are flagged (never deleted).
- Zoho's own "too many requests" answers (HTTP 429, Zoho Books API docs checked 2026-10-30): code 45 = the
  organisation's daily limit is used up, so reading stops until tomorrow; code 44 (over 100 a minute) and
  code 1070 (too many at once) only end this cycle. A 429 without a recognised code is treated as code 45,
  because every app connected to the organisation shares that limit.
"""
from datetime import datetime,timedelta,timezone
from contextlib import nullcontext
from math import ceil
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models import ZohoSourceDocument,ZohoSourceRun,utcnow
from app.zoho_source import normalize
from app.zoho_probe import ProbeStopped,ZohoLimit

MANILA=ZoneInfo('Asia/Manila')
RESERVE_SHARE=0.2  # Part of the daily cap backfill never touches, kept for changed records (plan, 2026-10-30).
WORK_HOURS=(7,16)  # Backfill window, Manila time, Monday to Friday: the user's 7am-4pm shift (vault). Override per worker.
STAMP='%Y-%m-%dT%H:%M:%S%z'


def month_window():
    import calendar
    today=datetime.now(MANILA).date()
    return today.replace(day=1).isoformat(),today.replace(day=calendar.monthrange(today.year,today.month)[1]).isoformat()


def latest_month_run(db,org,start,end):
    return next((r for r in db.scalars(select(ZohoSourceRun).where(ZohoSourceRun.organization_id==org).order_by(ZohoSourceRun.started_at.desc()))
                 if r.coverage.get('mode')=='month-sync' and r.window_start.isoformat()==start
                 and r.window_end.isoformat()==end),None)


def today_runs(db,org):
    day=datetime.now(MANILA).date().isoformat()
    return [r for r in db.scalars(select(ZohoSourceRun).where(ZohoSourceRun.organization_id==org))
            if r.coverage.get('mode')=='month-sync' and r.coverage.get('usageDay')==day]


def usage_today(db,org):
    return sum(r.coverage.get('getRequests',0)+r.coverage.get('oauthRefreshes',0) for r in today_runs(db,org))


def zoho_day_limit_hit(db,org):
    """True once Zoho itself said today's organisation limit is used up (code 45, or an unrecognised 429)."""
    return any(r.coverage.get('zohoDailyLimitHit') for r in today_runs(db,org))


def backfill_allowance(now,used,daily_limit,interval,work_hours=WORK_HOURS):
    """How many older details this cycle may read, and why. `now` is Manila time."""
    reserve=ceil(daily_limit*RESERVE_SHARE)
    if now.weekday()>=5:return 0,reserve,'Weekend: changes only.'
    start,end=(now.replace(hour=h,minute=0,second=0,microsecond=0) for h in work_hours)
    if not start<=now<end:return 0,reserve,'Outside working hours: changes only.'
    spare=daily_limit-used-reserve
    if spare<=0:return 0,reserve,'The rest of today\'s cap is kept for changed records.'
    cycles=max(1,ceil((end-now).total_seconds()/interval))
    return ceil(spare/cycles),reserve,f'Spread over about {cycles} more cycles today.'


def stamp(value):
    try:return datetime.strptime(value,STAMP) if value else None
    except ValueError:return None


def save_document(db,org,kind,raw,full,from_change_feed=False):
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
        # A record Zoho reports as changed (through the change feed, or a saved one whose time moved) gets its
        # details before the older backlog. A record first seen in the daily full list is backlog.
        if not data['detailLoaded']:
            if previous.get('changedAt'):data['changedAt']=previous['changedAt']
            elif (old and not unchanged) or from_change_feed:data['changedAt']=now.isoformat()
    else:
        data['detailFetchedAt']=now.isoformat()
    if old:old.data,old.fetched_at=data,now
    else:db.add(ZohoSourceDocument(organization_id=org,kind=kind,source_id=data['id'],data=data,fetched_at=now))
    return data


def sync_month(sessions,reader,start,end,detail_limit=30,daily_limit=500,interval=300,work_hours=WORK_HOURS,now=None):
    from datetime import date
    if date.fromisoformat(start)>date.fromisoformat(end) or (date.fromisoformat(end)-date.fromisoformat(start)).days>31:
        raise ValueError('Use a current-month window of at most32days.')
    if not 0<=detail_limit<=60 or not 1<=daily_limit<=1000 or interval<60 or not 0<=work_hours[0]<work_hours[1]<=24:
        raise ValueError('Invalid sync budget.')
    clock=now or (lambda:datetime.now(MANILA))  # Only the backfill window reads it; usage days use the real date.
    started=utcnow();checkpoint=started.astimezone(MANILA).strftime(STAMP)
    today=datetime.now(MANILA).date().isoformat()
    with sessions() as db:
        if zoho_day_limit_hit(db,reader.organization):
            raise ProbeStopped('Zoho said the organisation\'s daily limit is used up; reading resumes tomorrow.')
        previous=latest_month_run(db,reader.organization,start,end)
        previous_data=previous.coverage if previous else {}
        if usage_today(db,reader.organization)>=daily_limit:raise ProbeStopped('Local daily request cap reached; saved records remain available.')
        # Resume exact page positions after a bounded/failed scan. Otherwise use an overlap change feed,
        # except for the first scan of each day, which lists the whole window (the daily totals check).
        resume=bool(previous and not previous_data.get('summaryComplete'))
        if resume:
            checkpoint=previous_data.get('targetCheckpoint',checkpoint)
        cursors=dict(previous_data.get('cursors',{})) if resume else {'invoice':1,'salesorder':1}
        since=previous_data.get('since') if resume else previous_data.get('checkpoint')
        if not resume and (previous_data.get('fullSummaryScanAt') or '')[:10]!=today:since=None
        if since and not resume:
            since=(datetime.strptime(since,STAMP)-timedelta(minutes=5)).strftime(STAMP)
        coverage={'mode':'month-sync','windowStart':start,'windowEnd':end,'usageDay':today,
                  'cursors':cursors,'since':since,'checkpoint':previous_data.get('checkpoint'),'targetCheckpoint':checkpoint,
                  'summaryComplete':False,'partial':True,'error':None,'getRequests':0,'oauthRefreshes':0,
                  'invoiceSummaries':0,'orderSummaries':0,'detailReads':0,'changedDetailReads':0,'backfillDetailReads':0,
                  'staleDetails':0,'intervalSeconds':interval,'dailyLimit':daily_limit,
                  'workHours':f'{work_hours[0]:02d}:00-{work_hours[1]:02d}:00 Monday to Friday (Manila)',
                  'scope':'This month plus updates to previously saved documents',
                  'fullSummaryScanAt':previous_data.get('fullSummaryScanAt'),
                  'totalsCheck':previous_data.get('totalsCheck')}
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
    def detail(kind,identifier):
        """Read one record's details. Saved only when Zoho's answer is that record and is not older than the summary."""
        raw=request(('/invoices/' if kind=='invoice' else '/salesorders/')+identifier).get(kind)
        if not isinstance(raw,dict) or str(raw.get('invoice_id' if kind=='invoice' else 'salesorder_id'))!=identifier:
            raise ProbeStopped('Source detail identity mismatch.')
        with sessions() as db:
            saved=db.get(ZohoSourceDocument,(reader.organization,kind,identifier))
            known,given=stamp(saved.data.get('sourceUpdatedAt') if saved else None),stamp(raw.get('last_modified_time'))
            if known and given and given<known:
                coverage['staleDetails']+=1  # Zoho answered with an older copy; it stays pending for the next cycle.
            else:
                save_document(db,reader.organization,kind,raw,True);coverage['detailReads']+=1
            update(db)
    full_list=since is None and not resume
    seen={'invoice':set(),'salesorder':set()}
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
                        if start<=on<=end:seen[kind].add(identifier)
                        if not start<=on<=end and not db.get(ZohoSourceDocument,(reader.organization,kind,identifier)):continue
                        save_document(db,reader.organization,kind,raw,False,from_change_feed=bool(since))
                    more=(payload.get('page_context')or{}).get('has_more_page')
                    page=page+1 if more is True or (more is None and len(values)==200) else None
                    cursors[kind]=page;coverage['cursors']=dict(cursors)
                    coverage['invoiceSummaries' if kind=='invoice' else 'orderSummaries']+=len(values)
                    update(db)
        coverage['summaryComplete']=True;coverage['checkpoint']=checkpoint
        if not since:coverage['fullSummaryScanAt']=checkpoint
        with sessions() as db:
            if full_list:
                # The whole window was listed in this one run: compare with what is saved.
                missing=[]
                for row in db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==reader.organization)):
                    if row.kind in seen and start<=row.data.get('date','')<=end and row.source_id not in seen[row.kind]:
                        missing.append({'kind':row.kind,'id':row.source_id,'number':row.data.get('number')})
                coverage['totalsCheck']={'checkedAt':checkpoint,'listedInvoices':len(seen['invoice']),'listedOrders':len(seen['salesorder']),
                                         'notListedByZoho':len(missing),'examples':missing[:20]}
            update(db)
        # Changed records first (any date, any hour), then the older backlog within this cycle's allowance.
        with sessions() as db:
            changed,backlog=[],{kind:[] for kind in ('invoice','salesorder')}
            for row in db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==reader.organization)):
                if row.kind not in backlog or row.data.get('detailLoaded',False):continue
                if row.data.get('changedAt'):changed.append((row.data['changedAt'],row.kind,row.source_id))
                elif start<=row.data.get('date','')<=end:backlog[row.kind].append((row.data.get('date',''),row.source_id))
            changed.sort()
            for values in backlog.values():values.sort(reverse=True)
        for _,kind,identifier in changed[:detail_limit]:
            detail(kind,identifier);coverage['changedDetailReads']+=1
        with sessions() as db:used=usage_today(db,reader.organization)
        allowed,reserve,reason=backfill_allowance(clock(),used,daily_limit,interval,work_hours)
        allowed=min(allowed,max(0,detail_limit-coverage['changedDetailReads']))
        coverage['budget']={'usedBeforeBackfill':used,'reserve':reserve,'backfillAllowed':allowed,'reason':reason}
        for index in range(allowed):
            kind='invoice' if index%2==0 else 'salesorder'
            if not backlog[kind]:kind='salesorder' if kind=='invoice' else 'invoice'
            if not backlog[kind]:break
            _,identifier=backlog[kind].pop(0)
            detail(kind,identifier);coverage['backfillDetailReads']+=1
    except ZohoLimit as limit:
        coverage['zohoLimit']=limit.kind
        coverage['zohoDailyLimitHit']=limit.kind in ('day','unknown')
        coverage['error']=str(limit)
    except (ProbeStopped,ValueError):
        coverage['error']='Sync paused by a request limit or read failure. Saved records remain available; the next run resumes safely.'
    with sessions() as db:
        rows=list(db.scalars(select(ZohoSourceDocument).where(ZohoSourceDocument.organization_id==reader.organization)))
        current=[r for r in rows if start<=r.data.get('date','')<=end]
        coverage['savedMonthInvoices']=sum(r.kind=='invoice' for r in current)
        coverage['savedMonthOrders']=sum(r.kind=='salesorder' for r in current)
        coverage['pendingDetails']=sum(not r.data.get('detailLoaded',False) for r in current)
        coverage['changedPending']=sum(bool(r.data.get('changedAt')) and not r.data.get('detailLoaded',False) for r in rows)
        coverage['partial']=not coverage['summaryComplete'] or bool(coverage['pendingDetails'])
        update(db)
        coverage['usedToday']=usage_today(db,reader.organization)  # Includes this run, saved just above.
        update(db)
    return coverage
