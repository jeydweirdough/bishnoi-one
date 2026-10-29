"""Operators (feature plan step 5, 2026-10-28): the people at Bishnoi One who run the service for
every company. A switch on their Bishnoi One account (step 4), not a separate staff login; the
Operations area's Operators screen uses these. Only an operator may change them.

- GET /platform/operators: every operator, and the accounts that could be made one.
- PUT /platform/operators/{account_id}: {"isOperator": true | false}.
- POST /platform/operators: a new operator with an email of their own (one email, one account: an
  operator has no company and goes into any; decided 2026-10-29). Only operators add operators.
- GET /platform/people?q=: Find a person, any email at any company, with where they belong.

An operator's staff record (nbpl_users) is kept in step for the history and audit log that point
at it; switching the account off ends their sessions there too.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Query, status
from pydantic import Field, field_validator
from sqlalchemy import func, or_, select

from app import email_rules
from app.accounts import account_by_email, memberships
from app.api import Api, check_email, conflict, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser
from app.models import Account, Company, User
from app.security import MAX_PASSWORD, check_password_rules, hash_password

router = APIRouter(prefix="/platform/operators", tags=["operators"])
people = APIRouter(prefix="/platform/people", tags=["operators"])


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
    else:
        home = email_rules.home(db, a)
        if home is not None:
            company = db.get(Company, home.company_id)
            raise conflict(f"{a.email} is a person at {company.name}. An operator signs in with an email of their own: add them as a new operator.")
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


class NewOperatorIn(Api):
    email: str = Field(max_length=254)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return check_email(value)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_operator(body: NewOperatorIn, db: DB, me: AdminUser) -> dict:
    """A new operator: their own email (never one a company's person has), and a first password to pass on."""
    if account_by_email(db, body.email) or db.scalar(select(User.id).where(func.lower(User.email) == body.email)):
        raise field_error("email", email_rules.UNAVAILABLE)
    if (why := check_password_rules(body.password)) is not None:
        raise field_error("password", why)
    now = datetime.now(UTC)
    hashed = hash_password(body.password)
    a = Account(email=body.email, full_name=body.full_name.strip(), password_hash=hashed, password_changed_at=now, is_operator=True)
    db.add(a)
    db.flush()
    db.add(User(email=body.email, full_name=a.full_name, password_hash=hashed, password_changed_at=now, role="admin"))
    audit(db, me, "operator.added", category="security", target=a.email, target_type="account", target_id=a.id)
    db.commit()
    return {"operator": operator_out(a)}


@people.get("")
def find_people(db: DB, _: CurrentUser, q: str = Query(min_length=2, max_length=100)) -> dict:
    """Any account by email or name: the company it belongs to (or that it's an operator's), and its status."""
    like = f"%{q.strip().lower()}%"
    found = db.scalars(select(Account).where(or_(func.lower(Account.email).like(like), func.lower(Account.full_name).like(like)))
                       .order_by(func.lower(Account.full_name)).limit(25)).all()
    out = []
    for a in found:
        rows = [m for m in memberships(db, a) if not m.via_operator]
        companies = {c.id: c for c in db.scalars(select(Company).where(Company.id.in_([m.company_id for m in rows])))} if rows else {}
        out.append({**operator_out(a), "memberships": [
            {"id": m.id, "companyId": m.company_id, "company": companies[m.company_id].name, "companySlug": companies[m.company_id].slug,
             "status": m.status, "isCompanyAdmin": m.is_company_admin, "offDomain": bool(email_rules.off_domain(db, m))}
            for m in rows if m.company_id in companies]})
    return {"people": out}
