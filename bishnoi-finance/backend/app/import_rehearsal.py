"""Actual model/ledger rehearsal in a NEW private SQLite DB, never the active books."""
from collections import Counter
from datetime import date,datetime,timezone
from pathlib import Path
import json,uuid
from sqlalchemy import select,func,text
from app.config import Settings,DATA_DIR
from app.db import make_engine,make_sessions
from app.migrate import upgrade
from app.models import Account,Bill,Invoice,InvoicePayment,PaymentVoucher,Supplier,VoucherLine,JournalLine,utcnow
from app.ledger import post,Leg
from app.tax import rates
from app.import_review import ReviewError


def rehearsal(review,source_db,actor):
    if not any(d['financialReady'] for d in review['documents']):
        raise ReviewError('No records are eligible yet. Match the grouped posting accounts and confirm company attribution first; no rehearsal database or entries were created.')
    directory=DATA_DIR/'import-rehearsals';directory.mkdir(exist_ok=True)
    identifier=str(uuid.uuid4());path=directory/(identifier+'.db')
    engine=make_engine('sqlite:///'+path.as_posix());upgrade(engine);sessions=make_sessions(engine)
    rates.seed(sessions)
    result={'id':identifier,'environment':'local_test','officialWrites':0,'providerRequests':0,'completeBaseline':False,
            'posted':{},'held':{},'heldReasons':{},'debitCentavos':0,'creditCentavos':0,'balanced':False,
            'note':'Local rehearsal only. Opening items, unsupported adjustments, tax classification and unmatched records remain separate; this is not BIR sign-off.'}
    held=Counter();posted=Counter();held_ids=[]
    try:
        source_accounts=list(source_db.scalars(select(Account)))
        with sessions() as db:
            existing={a.code:a for a in db.scalars(select(Account))};mapping={}
            for a in source_accounts:
                if a.code in existing:
                    old=existing[a.code]
                    if (old.name,old.type)!=(a.name,a.type):raise ReviewError('A local rehearsal seed account conflicts with the selected chart.')
                    mapping[a.id]=old.id
                else:mapping[a.id]=a.id
            known={a.id for a in existing.values()};pending=[a for a in source_accounts if a.code not in existing]
            while pending:
                ready=[a for a in pending if not a.parent_id or mapping.get(a.parent_id) in known]
                if not ready:raise ReviewError('Account parent links are incomplete.')
                for a in ready:
                    db.add(Account(id=mapping[a.id],code=a.code,name=a.name,type=a.type,parent_id=mapping.get(a.parent_id),is_active=a.is_active))
                    known.add(mapping[a.id]);pending.remove(a)
                db.flush()
            db.commit()
        selected={g['id']:mapping.get(g['accountId']) for g in review['accountGroups']}
        groups={g['id']:g for g in review['accountGroups']};documents={d['id']:d for d in review['documents']}
        entries={};model_rows={};suppliers={}
        with sessions() as db:
            def account(group):
                identifier=selected.get(group)
                found=db.get(Account,identifier) if identifier else None
                if not found:raise ReviewError('A posting account has not been matched.')
                return found
            def supplier(d):
                # A source-labelled local counterpart, not a guessed match to the live directory.
                identity=d['party'].strip().casefold()
                if identity not in suppliers:
                    s=Supplier(name=d['party'][:200],created_by=actor,vat_registered=False,tax_defaults_confirmed=False,
                        import_details={'localRehearsalOnly':True,'directoryIdentityNotVerified':True})
                    db.add(s);db.flush();suppliers[identity]=s
                return suppliers[identity]
            for d in sorted(review['documents'],key=lambda d:(d['date'],d['kind'],d['sourceId'])):
                if d['kind']=='salesorder':continue
                if d['kind'].endswith('_payment'):continue
                if not d['financialReady']:
                    held.update(d['issues'] or ['company']);held_ids.append(d['id']);continue
                if d['kind']=='expense':
                    held['expense_posting_not_supported']+=1;held_ids.append(d['id']);continue
                legs=[]
                if d['kind']=='invoice':
                    if not d['dueDate'] or d['dueDate']<d['date']:
                        held['due_date']+=1;held_ids.append(d['id']);continue
                    control=account(d['controlGroup']);legs.append(Leg(control,debit=d['total']))
                    legs.extend(Leg(account(ln['accountGroup']),credit=ln['amount'],description=ln['description'][:300]) for ln in d['lines'])
                    if d['tax']:legs.append(Leg(account(d['taxGroup']),credit=d['tax']))
                    entry=post(db,date.fromisoformat(d['date']),'Q1 local import rehearsal',legs,actor,reference=d['number'][:80],source='invoice')
                    inv=Invoice(number=d['number'],status='issued',customer_id=d['partyId'] or None,customer_name=d['party'][:200],customer_tin=d['tin'] or None,
                        invoice_date=date.fromisoformat(d['date']),terms_days=(date.fromisoformat(d['dueDate'])-date.fromisoformat(d['date'])).days,
                        created_by=actor,issued_by='Source import rehearsal; not re-issued',issued_at=utcnow(),entry_id=entry.id,
                        total_centavos=d['total'],tax_centavos=d['tax'],paid_centavos=0,reference=d['sourceId'][:80],
                        lines=[{'description':ln['description'],'quantity':1,'unitPriceCentavos':ln['amount']} for ln in d['lines']],
                        computed={'sourceRehearsal':True,'summary':[],'totalDueCentavos':d['total'],'taxClassificationVerified':False})
                    db.add(inv);db.flush();model_rows[d['id']]=inv
                else:
                    if not d['dueDate']:
                        held['due_date']+=1;held_ids.append(d['id']);continue
                    control=account(d['controlGroup']);legs.extend(Leg(account(ln['accountGroup']),debit=ln['amount'],description=ln['description'][:300]) for ln in d['lines'])
                    if d['tax']:legs.append(Leg(account(d['taxGroup']),debit=d['tax']))
                    legs.append(Leg(control,credit=d['total']))
                    entry=post(db,date.fromisoformat(d['date']),'Q1 local import rehearsal',legs,actor,reference=d['number'][:80],source='bill')
                    b=Bill(supplier=supplier(d),bill_number=d['number'],bill_date=date.fromisoformat(d['date']),due_date=date.fromisoformat(d['dueDate']),
                        status='recorded',created_by=actor,recorded_by='Source import rehearsal; approvals not replayed',recorded_at=utcnow(),
                        amounts_include_vat=False,lines=[{'accountId':account(ln['accountGroup']).id,'description':ln['description'],
                            'amountCentavos':ln['amount'],'netCentavos':ln['amount'],'vatCentavos':ln['tax'],'withheldCentavos':0,'vat':'source_unclassified','withholding':None,'purchaseType':'unconfirmed'} for ln in d['lines']],
                        tax_reviewed=False,net_centavos=d['subtotal'],vat_centavos=d['tax'],withheld_centavos=0,
                        total_centavos=d['total'],payable_centavos=d['total'],paid_centavos=0,payables_account_id=control.id,entry_id=entry.id,zoho_ref=d['sourceId'])
                    db.add(b);db.flush();model_rows[d['id']]=b
                entries[d['id']]=entry;posted[d['kind']]+=1
            # Payments follow only successfully rehearsed targets, preserving each source payment once.
            for d in sorted((x for x in review['documents'] if x['kind'].endswith('_payment')),key=lambda d:(d['date'],d['sourceId'])):
                if not d['financialReady']:
                    held.update(d['issues'] or ['company']);held_ids.append(d['id']);continue
                if any(a['targetId'] not in model_rows for a in d['allocations']):
                    held['waiting_for_document_or_opening']+=1;held_ids.append(d['id']);continue
                if any(a['withheld'] for a in d['allocations']):
                    held['withholding_account_and_certificate_review']+=1;held_ids.append(d['id']);continue
                per_target=Counter()
                for a in d['allocations']:per_target[a['targetId']]+=a['cash']
                if any(model_rows[t].paid_centavos+cash>documents[t]['total'] for t,cash in per_target.items()) or any(a['cash']<=0 for a in d['allocations']):
                    held['overpayment']+=1;held_ids.append(d['id']);continue
                money=account(d['moneyGroup']);received=d['kind']=='customer_payment'
                if received:
                    for a in d['allocations']:
                        target=model_rows[a['targetId']];control=account(documents[a['targetId']]['controlGroup'])
                        e=post(db,date.fromisoformat(a['date']),'Q1 local collection rehearsal',[Leg(money,debit=a['cash']),Leg(control,credit=a['cash'])],actor,reference=d['number'][:80],source='invoice')
                        p=InvoicePayment(invoice=target,paid_on=date.fromisoformat(a['date']),amount_centavos=a['cash'],method=d['original']['method'],
                            reference=d['sourceId'][:80],recorded_by=actor,entry_id=e.id,cwt_centavos=0)
                        db.add(p);target.paid_centavos+=a['cash']
                else:
                    # Current model has one paid date per voucher. Do not collapse different application dates.
                    dates={a['date'] for a in d['allocations']}
                    if len(dates)!=1 or next(iter(dates))!=d['date']:
                        held['multiple_payment_dates']+=1;held_ids.append(d['id']);continue
                    targets=[model_rows[a['targetId']] for a in d['allocations']]
                    if len({b.supplier_id for b in targets})!=1:
                        held['supplier_identity']+=1;held_ids.append(d['id']);continue
                    if len(d['number'])>20 or db.scalar(select(PaymentVoucher.id).where(PaymentVoucher.number==d['number'])):
                        held['source_payment_number_conflict']+=1;held_ids.append(d['id']);continue
                    if d['original']['method'] not in ('cash','bank','check'):
                        held['unsupported_voucher_method']+=1;held_ids.append(d['id']);continue
                    legs=[Leg(account(documents[a['targetId']]['controlGroup']),debit=a['cash']) for a in d['allocations']]+[Leg(money,credit=d['total'])]
                    e=post(db,date.fromisoformat(d['date']),'Q1 local supplier-payment rehearsal',legs,actor,reference=d['number'][:80],source='voucher')
                    v=PaymentVoucher(number=d['number'],supplier_id=targets[0].supplier_id,status='released',method=d['original']['method'],paid_from_id=money.id,
                        total_centavos=d['total'],prepared_by=actor,released_by='Source import rehearsal',paid_on=date.fromisoformat(d['date']),entry_id=e.id,zoho_ref=d['sourceId'])
                    for index,a in enumerate(d['allocations']):
                        target=model_rows[a['targetId']];v.lines.append(VoucherLine(bill_id=target.id,position=index,amount_centavos=a['cash']));target.paid_centavos+=a['cash']
                    db.add(v)
                posted[d['kind']]+=1
            db.commit()
            debit,credit=db.execute(select(func.coalesce(func.sum(JournalLine.debit_centavos),0),func.coalesce(func.sum(JournalLine.credit_centavos),0))).one()
            result.update(posted=dict(posted),held=dict(Counter(documents[i]['kind'] for i in held_ids)),heldReasons=dict(held),
                debitCentavos=debit,creditCentavos=credit,balanced=debit==credit,
                receivablesCentavos=sum(i.total_centavos-i.paid_centavos for i in model_rows.values() if isinstance(i,Invoice)),
                payablesCentavos=sum(b.payable_centavos-b.paid_centavos for b in model_rows.values() if isinstance(b,Bill)),
                openingItemsPosted=0,taxReportsCertified=False,heldDocumentCount=len(held_ids))
        (directory/(identifier+'.json')).write_text(json.dumps(result),encoding='utf-8')
        return result
    finally:engine.dispose()
