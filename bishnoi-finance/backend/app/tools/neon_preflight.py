"""Read-only official-target inventory. Never imports the app or runs migrations."""
import json
from dotenv import dotenv_values
from sqlalchemy import inspect, text
from app.config import API_DIR
from app.db import make_engine


def main():
    address=dotenv_values(API_DIR/'.env').get('FINANCE_NEON_REVIEW_URL')
    if not address:
        print(json.dumps({'connected':False,'message':'Save the private review setting first.'}));return 2
    engine=None
    try:
        engine=make_engine(address,postgres_driver='pg8000')
        with engine.connect() as db:
            db.exec_driver_sql('SET TRANSACTION READ ONLY')
            db.exec_driver_sql("SET LOCAL statement_timeout = '8000ms'")
            if db.scalar(text("SELECT current_setting('transaction_read_only')"))!='on':
                raise RuntimeError('Read-only transaction not confirmed')
            tables=inspect(db).get_table_names()
            version=db.scalar(text('SELECT version_num FROM nbfi_alembic_version')) if 'nbfi_alembic_version' in tables else None
            report={'connected':True,'readOnly':True,'financeRevision':version,
                'financeTables':sum(t.startswith('nbfi_') for t in tables),
                'sourceStoragePresent':'nbfi_zoho_source_documents' in tables,
                'protectedStoragePresent':'nbfi_zoho_connections' in tables}
            db.rollback()
        print(json.dumps(report));return 0
    except Exception as error:
        # Driver exceptions can contain connection details. Never echo them.
        print(json.dumps({'connected':False,'errorClass':type(error).__name__,
            'message':'Read-only preflight could not finish. Check driver, TLS and access settings privately.'}));return 2
    finally:
        if engine is not None:engine.dispose()


if __name__=='__main__':raise SystemExit(main())
