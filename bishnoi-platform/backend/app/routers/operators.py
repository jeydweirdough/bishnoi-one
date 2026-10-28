"""Operators (feature plan step 5, 2026-10-28): the people at Bishnoi One who run the service for
every company. A switch on their Bishnoi One account (step 4), not a separate staff login; the
Operations area's Operators screen uses these. Only an operator may change them.

- GET /platform/operators: every operator, and the accounts that could be made one.
- PUT /platform/operators/{account_id}: {"isOperator": true | false}.

An operator's staff record (nbpl_users) is kept in step for the history and audit log that point
at it; switching the account off ends their sessions there too.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.api import Api, conflict, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser
from app.models import Account, User

router = APIRouter(prefix="/platform/operators", tags=["operators"])


def operator_out(a: Account) -> dict:
    return {"id": a.id, "no": a.no, "email": a.email, "fullName": a.full_name, "isOperator": a.is_operator, "status": a.status,
            "lastSignInAt": iso(a.last_sign_in_at), "createdAt": iso(a.created_at)}


@router.get("")
def operators(db: DB, _: CurrentUser, q: str | None = Query(None, max_length=100)) -> dict:
    found = []
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        found = db.scalars(select(Account).where(Account.is_operator.is_(False), Account.status == "active",
                                                 or_(func.lower(Account.email).like(like), func.lower(Account.full_name).like(like)))
                           .order_by(func.lower(Account.full_name)).limit(10)).all()
    ops = db.scalars(select(Account).where(Account.is_operator).order_by(func.lower(Account.full_name))).all()
    return {"operators": [operator_out(a) for a in ops], "found": [operator_out(a) for a in found]}


class OperatorIn(Api):
    is_operator: bool


@router.put("/{account_id}")
def set_operator(account_id: str, body: OperatorIn, db: DB, me: AdminUser) -> dict:
    a = db.get(Account, account_id)
    if a is None:
        raise not_found("account")
    if a.is_operator == body.is_operator:
        return {"operator": operator_out(a)}
    if not body.is_operator:
        if a.email.lower() == me.email.lower():
            raise conflict("You can't switch yourself off. Ask another operator.")
        if not db.scalar(select(func.count()).select_from(Account).where(Account.is_operator, Account.id != a.id, Account.status == "active")):
            raise conflict("Bishnoi One always needs an operator. Make someone else one first.")
    elif a.status != "active":
        raise conflict(f"{a.email}'s account is suspended. Switch it on first.")
    staff = db.scalar(select(User).where(func.lower(User.email) == a.email.lower()))
    now = datetime.now(UTC)
    if body.is_operator:
        if staff is None:
            staff = User(email=a.email, full_name=a.full_name, password_hash=a.password_hash or "!", role="admin")
            db.add(staff)
        staff.role, staff.is_active = "admin", True
    elif staff is not None:
        staff.is_active = False
        staff.password_changed_at = now  # their console sessions end
    a.is_operator = body.is_operator
    audit(db, me, "operator.switched_on" if body.is_operator else "operator.switched_off", category="security", target=a.email, target_type="account", target_id=a.id)
    db.commit()
    return {"operator": operator_out(a)}
