"""Bounded background deliveries. Never run this from a bill/payment HTTP request."""
import argparse,time,json
from app.config import Settings
from app.db import make_engine,make_sessions
from app.tools.sync_zoho_orders import sync_lock
from app.zoho_delivery import ZohoSender,process
from app.zoho_outbox import claim,SetupNeeded
from fastapi import HTTPException


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true');parser.add_argument('--batch',type=int,default=3)
    parser.add_argument('--reconcile',help='Check one uncertain job using GET only; never creates a record.')
    args=parser.parse_args()
    if not 1<=args.batch<=10:raise SystemExit('Use batch size 1–10.')
    settings=Settings()
    if settings.data_environment!='official' or settings.database_url.startswith('sqlite:') or (not settings.zoho_outbound_enabled and not args.reconcile):
        raise SystemExit('Live sending is disabled or this is local testing. No Zoho records were changed.')
    sessions=make_sessions(make_engine(settings.database_url,settings.postgres_driver))
    while True:
        count=0
        try:
            with sync_lock(settings):
                sender=ZohoSender(settings)
                if args.reconcile:
                    from app.models import ZohoDelivery
                    with sessions() as db:
                        job=db.get(ZohoDelivery,args.reconcile)
                        if not job or job.environment!='official' or job.status not in ('uncertain','needs_attention'):
                            raise SystemExit('Choose an official job that needs reconciliation.')
                    process(sessions,settings,args.reconcile,sender,reconcile_only=True)
                    return
                for _ in range(args.batch):
                    with sessions() as db:job=claim(db,'official')
                    if not job:break
                    process(sessions,settings,job.id,sender);count+=1
        except (SetupNeeded,HTTPException):
            print('Delivery updater paused by setup, ownership or quota. Local records remain saved.',flush=True)
        print(json.dumps({'jobsChecked':count}),flush=True)
        if not args.watch:return
        time.sleep(60)


if __name__=='__main__':main()
