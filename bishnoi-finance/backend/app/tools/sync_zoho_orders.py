"""Save a bounded source-only Q1 demo batch. No Zoho business writes or accounting posting."""
import argparse
from contextlib import contextmanager
from pathlib import Path
import json
import os
from app.config import Settings
from app.db import make_engine, make_sessions
from app.migrate import upgrade
from app.models import utcnow
from app.zoho_probe import ZohoReader, ProbeStopped
from app.zoho_source import capture, persist
from app import zoho_connection as oauth


@contextmanager
def sync_lock(settings):
    _,_,token_path=oauth.configuration(settings)
    if token_path is None:
        from app.zoho_runtime import worker
        selected=(oauth.saved_record(settings).get('connection') or {}).get('organization')
        if not selected:
            raise ProbeStopped('Connect to Zoho and confirm the organisation first.')
        with worker(settings,selected['id']):
            yield
        return
    with open(token_path.parent/'zoho-source-sync.lock','a+b') as stream:
        if stream.tell()==0: stream.write(b'0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ProbeStopped('Another source sync is running; no second run started.') from None
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream,fcntl.LOCK_UN)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',default='2026-01-01');p.add_argument('--end',default='2026-03-31')
    p.add_argument('--invoices',type=int,default=30);p.add_argument('--orders',type=int,default=30)
    p.add_argument('--pages',type=int,default=2);p.add_argument('--requests',type=int,default=100)
    args=p.parse_args();settings=Settings()
    try:
        with sync_lock(settings):
            engine=make_engine(settings.database_url, postgres_driver=settings.postgres_driver);upgrade(engine)
            reader=ZohoReader(settings,maximum=args.requests,progress=lambda n:print(f'Reading Zoho source data: {n} GET requests.',flush=True) if n%10==0 else None)
            started=utcnow()
            staged,coverage=capture(reader,args.start,args.end,args.invoices,args.orders,args.pages)
            with oauth.locked(settings) as record:
                if (record.get('connection') or {}).get('organization',{}).get('id')!=reader.organization:
                    raise ProbeStopped('Selected organisation changed; nothing was saved.')
            with reader.save_guard():
                with make_sessions(engine)() as db:persist(db,reader.organization,staged,coverage,started)
            print(json.dumps({'savedSourceDocuments':len(staged),'coverage':coverage,'financialPostings':0}))
            return 2 if coverage['error'] else 0
    except (ProbeStopped,ValueError) as e:
        print('Source sync did not complete; no provider business writes or financial postings were made.')
        return 2


if __name__=='__main__':raise SystemExit(main())
