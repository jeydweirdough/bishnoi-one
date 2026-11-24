"""Company-use evidence is separate from supplier origin and tax treatment."""
from datetime import UTC, datetime
from fastapi import HTTPException
from sqlalchemy import select
from modules.finance.models import Account, CompanyScopeReview, Supplier
from modules.finance.locks import begin_change


def reviewed_ids(kind, scope):
    return select(CompanyScopeReview.subject_id).where(CompanyScopeReview.subject_kind == kind, CompanyScopeReview.scope == scope)


def configured(db, kind):
    return db.scalar(select(CompanyScopeReview.subject_id).where(CompanyScopeReview.subject_kind == kind).limit(1)) is not None


def usable_clause(kind, id_column):
    # Missing evidence is a hold, including on an unconfigured installation.
    return id_column.in_(reviewed_ids(kind, '2mg'))


def scope_for(db, kind, id):
    review = db.get(CompanyScopeReview, (kind, id))
    return review.scope if review else 'review'


def require_ids(db, kind, ids, *, status_code=409):
    begin_change(db)
    ids = list(ids)
    wanted = {id for id in ids if id}
    approved = set(db.scalars(select(CompanyScopeReview.subject_id).where(
        CompanyScopeReview.subject_kind == kind, CompanyScopeReview.subject_id.in_(wanted),
        CompanyScopeReview.scope == '2mg').order_by(CompanyScopeReview.subject_id).with_for_update(read=True))) if wanted else set()
    if any(not id for id in ids) or wanted - approved:
        raise HTTPException(status_code, f'{"An account" if kind == "account" else "A supplier"} is missing or not verified for 2MG. Review company use and any default account before recording new work. Retained records remain available as history.')


def require_bill(db, bill):
    require_ids(db, 'supplier', [bill.supplier_id])
    require_ids(db, 'account', [line.get('accountId') for line in bill.lines or []])
    from modules.finance.purchase_intake import guard_bill
    guard_bill(db,bill)


def approve_for_2mg(db, kind: str, ids: list[str], *, reviewed_by: str, reason: str | None = None) -> int:
    """Explicitly approve existing accounts or suppliers for 2MG company use."""
    begin_change(db)
    wanted = list(dict.fromkeys(i for i in ids if i))
    if not wanted:
        return 0
    model = Account if kind == 'account' else Supplier
    found = set(db.scalars(select(model.id).where(model.id.in_(wanted))))
    missing = [i for i in wanted if i not in found]
    if missing:
        raise HTTPException(404, f'One or more {"accounts" if kind == "account" else "suppliers"} could not be found.')
    now = datetime.now(UTC)
    evidence = {'source': 'in-app 2MG approval'}
    if reason:
        evidence['reason'] = reason
    changed = 0
    for sid in wanted:
        review = db.get(CompanyScopeReview, (kind, sid))
        if review is None:
            db.add(CompanyScopeReview(subject_kind=kind, subject_id=sid, scope='2mg', evidence=evidence, reviewed_by=reviewed_by, reviewed_at=now))
            changed += 1
        elif review.scope != '2mg':
            review.scope = '2mg'
            review.evidence = evidence
            review.reviewed_by = reviewed_by
            review.reviewed_at = now
            changed += 1
    return changed


def require_posting(db, legs, reverses=None, *, source: str = 'manual'):
    if reverses is not None:
        expected = sorted((line.account_id, line.credit_centavos, line.debit_centavos) for line in reverses.lines if line.debit_centavos or line.credit_centavos)
        actual = sorted((leg.account.id, leg.debit, leg.credit) for leg in legs)
        if reverses.status != 'approved' or expected != actual:
            raise HTTPException(409, 'A historical reversal must exactly reverse the original entry.')
        return  # Preserve an exact correction; this does not open legacy accounts for new work.
    checked = [leg for leg in legs if leg.account.type not in ('income', 'expense')] if source == 'closing' else legs
    if any(not leg.account.is_active for leg in checked):
        raise HTTPException(409, 'A posting account is switched off. Review the account setup before recording new work.')
    if checked:
        require_ids(db, 'account', [leg.account.id for leg in checked])
