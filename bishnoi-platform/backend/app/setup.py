"""First run (decided 2026-10-27): a new Bishnoi One is set up on a screen, not in
the server's settings. While nobody has an account, the one app shows "Set up
Bishnoi One" (its /setup page): the company, and the first administrator, who
is both the company's administrator and a Platform Admin.

The screen asks for a setup code that is only written to this server's log, so
only whoever runs the server can use it. Once anyone has an account it's gone
for good. FIRST_ADMIN_EMAIL/_PASSWORD (app/first_admin.py) still work instead.

    GET  /setup   {"needed": true|false}
    POST /setup   {code, companyName, name, email, password}
"""

import hmac
import logging
import secrets

from fastapi import APIRouter, HTTPException, status
from pydantic import Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api import Api, check_email, field_error
from app.audit import audit
from app.config import Settings
from app.deps import DB
from app.models import Application, Company, CompanyApp, Identity, PlatformSetting, User, utcnow
from app.routers.companies import as_slug
from app.security import check_password_rules, hash_password

log = logging.getLogger("platform.setup")
router = APIRouter(prefix="/setup", tags=["setup"])

KEPT_AS = "setup_code"  # its row in nbpl_settings while setup is waiting
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread


def needed(db) -> bool:
    return not db.scalar(select(func.count()).select_from(User)) and not db.scalar(select(func.count()).select_from(Identity))


def _code(db) -> str:
    row = db.get(PlatformSetting, KEPT_AS)
    if row is None:
        code = "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3))
        db.add(PlatformSetting(key=KEPT_AS, value={"code": code}, updated_by="first start"))
        try:
            db.commit()
        except IntegrityError:  # another server made one at the same moment: theirs stands
            db.rollback()
        row = db.get(PlatformSetting, KEPT_AS)
    return row.value["code"]


def announce(sessions, settings: Settings) -> None:
    """On every start while nobody has an account: the code, in the log."""
    with sessions() as db:
        if needed(db):
            log.warning("Bishnoi One isn't set up yet. Open the one app's /setup page and enter this setup code: %s", _code(db))


class SetupIn(Api):
    code: str = Field(min_length=1, max_length=40)
    company_name: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return check_email(v.strip())


@router.get("")
def setup_state(db: DB) -> dict:
    return {"needed": needed(db)}


@router.post("", status_code=status.HTTP_201_CREATED)
def set_up(body: SetupIn, db: DB) -> dict:
    if not needed(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bishnoi One is already set up. Sign in instead.")
    given = body.code.strip().upper().replace(" ", "")
    if not hmac.compare_digest(given.encode(), _code(db).encode()):
        raise field_error("code", "That isn't the setup code. It's in the Platform server's log.")
    problem = check_password_rules(body.password)
    if problem:
        raise field_error("password", problem)
    slug = as_slug(body.company_name)
    if not slug:
        raise field_error("companyName", "The name needs a letter or a number in it.")

    company = Company(name=body.company_name.strip(), slug=slug)
    db.add(company)
    db.flush()
    # The company has every application there is; its administrator can take some away later.
    for a in db.scalars(select(Application).where(Application.is_active)):
        db.add(CompanyApp(company_id=company.id, application_id=a.id))
    password_hash, now = hash_password(body.password), utcnow()
    person = Identity(company_id=company.id, full_name=body.name.strip(), email=body.email, is_company_admin=True, password_hash=password_hash, password_changed_at=now)
    staff = User(email=body.email, full_name=body.name.strip(), password_hash=password_hash, role="admin")
    db.add_all([person, staff])
    db.flush()
    audit(db, "setup", "company.created", category="system", target=company.name, target_type="company", target_id=company.id, company_id=company.id)
    audit(db, "setup", "staff.created", category="system", target=staff.email, target_type="staff", target_id=staff.id)
    row = db.get(PlatformSetting, KEPT_AS)
    if row is not None:
        db.delete(row)
    db.commit()
    log.warning("Bishnoi One is set up: %s, administrator %s.", company.name, staff.email)
    return {"email": staff.email, "company": company.slug}
