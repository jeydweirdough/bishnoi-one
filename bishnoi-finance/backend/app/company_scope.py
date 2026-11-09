"""Company-use evidence is separate from supplier origin and tax treatment."""
from sqlalchemy import exists, select
from app.models import CompanyScopeReview


def reviewed_ids(kind, scope):
    return select(CompanyScopeReview.subject_id).where(CompanyScopeReview.subject_kind == kind, CompanyScopeReview.scope == scope)


def configured(db, kind):
    return db.scalar(select(CompanyScopeReview.subject_id).where(CompanyScopeReview.subject_kind == kind).limit(1)) is not None


def usable_clause(kind, id_column):
    # Preserve unconfigured installations; once reviewed, unknown is not normal 2MG setup.
    ready = exists(select(CompanyScopeReview.subject_id).where(CompanyScopeReview.subject_kind == kind))
    return ~ready | id_column.in_(reviewed_ids(kind, '2mg'))


def scope_for(db, kind, id):
    review = db.get(CompanyScopeReview, (kind, id))
    return review.scope if review else 'review'
