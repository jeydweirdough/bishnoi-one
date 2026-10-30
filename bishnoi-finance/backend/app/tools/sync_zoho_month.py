"""Local background month sync. No business writes; pages read the database independently."""
import argparse,json,time
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.config import Settings
from app.db import make_engine,make_sessions
from app.migrate import upgrade
from app.zoho_probe import ZohoReader,ProbeStopped
from app.zoho_month_sync import sync_month,month_window,WORK_HOURS
from app.tools.sync_zoho_orders import sync_lock


def cycle(settings,sessions,args)->bool:
    """One sync cycle. False when it paused; the worker then tries again after its wait.
    A database or network failure (Neon dropping the connection, a timeout) ends only this
    cycle: saved records stay, the checkpoint advances only after committed pages
    (app/zoho_month_sync.py), and the error's kind is printed (never its text, which can
    carry connection details)."""
    try:
        with sync_lock(settings):
            reader=ZohoReader(settings,maximum=args.requests,progress=lambda n:print(f'Background source sync: {n} GET reads.',flush=True) if n%10==0 else None)
            reader.daily_limit=args.daily_limit
            start,end=month_window()
            result=sync_month(sessions,reader,start,end,args.details,args.daily_limit,interval=args.interval,work_hours=(args.work_start,args.work_end))
            print(json.dumps(result),flush=True)
            return True
    except (ProbeStopped,HTTPException,ValueError):
        print('Source sync paused; saved data remains available. Check the connection, quota or sync lock.',flush=True)
    except (SQLAlchemyError,OSError) as error:
        print(f'Source sync paused: database or network unavailable ({type(error).__name__}); saved data remains available. Trying again after the wait.',flush=True)
    return False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--interval',type=int,default=300)
    parser.add_argument('--requests',type=int,default=100)
    parser.add_argument('--details',type=int,default=30)
    parser.add_argument('--daily-limit',type=int,default=500)
    # Older details are filled in only between these hours, Monday to Friday (Manila); changes are read at any hour.
    parser.add_argument('--work-start',type=int,default=WORK_HOURS[0])
    parser.add_argument('--work-end',type=int,default=WORK_HOURS[1])
    args=parser.parse_args()
    if args.interval<300 or not 1<=args.requests<=100 or not 0<=args.details<=60 or not 1<=args.daily_limit<=1000 or not 0<=args.work_start<args.work_end<=24:
        raise SystemExit('Use interval>=300seconds,1–100requests,0–60details,dailycap1–1000 and work hours 0–24 (start before end).')
    settings=Settings();engine=make_engine(settings.database_url, postgres_driver=settings.postgres_driver);upgrade(engine);sessions=make_sessions(engine)
    # A local stop marker ends this agent-started worker without touching other apps.
    local=settings.database_url.startswith('sqlite:///')
    stop=Path(settings.database_url.removeprefix('sqlite:///')).resolve().parent/'zoho-month-worker.stop' if local else None
    while True:
        if stop and stop.exists():print('Local Zoho worker stopped by marker.',flush=True);return 0
        if not cycle(settings,sessions,args) and not args.watch:return 2
        if not args.watch:return 0
        for _ in range(args.interval):
            if stop and stop.exists():print('Local Zoho worker stopped by marker.',flush=True);return 0
            time.sleep(1)


if __name__=='__main__':raise SystemExit(main())
