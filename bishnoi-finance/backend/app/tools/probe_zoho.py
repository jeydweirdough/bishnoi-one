"""Run a bounded read-only investigation using Finance's selected Zoho organisation."""
import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import json
import sys
from fastapi import HTTPException
from app.config import Settings
from app.zoho_probe import Limits, ProbeStopped, ZohoReader, run_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    today = datetime.now(ZoneInfo('Asia/Manila')).date()
    parser.add_argument('--start', default=(today-timedelta(days=7)).isoformat(), help='Invoice date lower bound, YYYY-MM-DD')
    parser.add_argument('--end', default=today.isoformat(), help='Invoice date upper bound, YYYY-MM-DD')
    parser.add_argument('--pages', type=int, default=2)
    parser.add_argument('--details', type=int, default=30)
    parser.add_argument('--orders', type=int, default=8)
    parser.add_argument('--related', type=int, default=12)
    parser.add_argument('--requests', type=int, default=60)
    args = parser.parse_args()
    limits = Limits(pages=args.pages, invoice_details=args.details, order_details=args.orders,
                    related_invoice_details=args.related, requests=args.requests)
    try:
        limits.validate()
        # Validate dates before opening a connection or contacting a provider.
        first, last = date.fromisoformat(args.start), date.fromisoformat(args.end)
        if first > last or (last-first).days > 93:
            raise ValueError('Use an ordered window of at most 94 days.')
        reader = ZohoReader(Settings(), maximum=limits.requests,
                            progress=lambda n: print(f'Read-only probe: {n} GET requests used.', file=sys.stderr, flush=True) if n % 10 == 0 else None)
        report = run_probe(reader, args.start, args.end, limits)
        print(json.dumps(report, indent=2))
        return 2 if report['stopReason'] else 0
    except ProbeStopped as error:
        print(json.dumps({'probeStopped': str(error), 'sourceRecordsPersisted': False}))
        return 2
    except HTTPException as error:
        print(json.dumps({'connectionUnavailable': error.status_code, 'sourceRecordsPersisted': False}))
        return 2
    except ValueError:
        print('Invalid probe limits or dates; no source records requested.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
