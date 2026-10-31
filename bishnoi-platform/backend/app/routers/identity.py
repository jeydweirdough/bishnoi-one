"""Bishnoi One accounts: the companies' people signing in once, here, for every
application they have been given.

- /identity/login, /identity/logout: their sign-in (not the console's staff).
- /identity/me: who they are, and the applications they may open.
- /identity/switch: to another company they work for (same email, one password).
- /identity/pass: a pass into one application (app/passes.py), sent back to
  that application's own address (or to Bishnoi One.exe on the same PC) only;
  for the company they're in, or another of theirs when it names one.
- /identity/password: changing their password (at every company of theirs).
- Sign-in security (2026-10-30, app/sign_in.py): /identity/login/code (the two-step code), forgot
  password (/identity/password/forgot → an emailed link), /identity/password/link and /set (a reset or
  an invitation's link sets the password), /identity/two-step (an authenticator app: start, confirm, off).

A person has one account (models.Account: email, the one password; step 4,
2026-10-28) and a membership at each company they work for (models.Identity);
a sign-in is at one of their memberships at a time. Suspending the account
stops them everywhere; suspending a membership, at that company.
- /pass/key: the platform's public key, for the applications to check passes.

A pass is refused, in words a person can act on, when the account or its
company is suspended, when the company doesn't have the application, or when
the person hasn't been given it.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import Api
from app.access_roles import role_for_pass
from app.org_push import placement
from app.audit import audit
from app import catalogue, document_chain, email_rules, platform_admins, sign_in, signatures
from app.accounts import account_by_email, account_of, memberships, runs_company
from app.deps import DB, Address, SettingsDep, as_utc, get_db
from app.models import AccessRole, Account, Application, Company, User, CompanyApp, Identity, IdentityApp, IdentitySession
from app.passes import ISSUER, PassUnavailable, issue, key_id, public_key
from app import passwords
from app.security import DUMMY_HASH, MAX_PASSWORD, check_password_rules, hash_password, new_token, token_hash, verify_password

router = APIRouter(tags=["bishnoi accounts"])

WRONG = "That email and password don't match a Bishnoi One account."
_bearer = HTTPBearer(auto_error=False)

# Bishnoi One.exe runs the applications on the PC itself, on these ports.
DESKTOP_PORTS = range(47300, 47400)
RETURN_PATH = "/auth/platform"


def current_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[IdentitySession, Identity]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in with your Bishnoi One account.")
    record = db.scalar(select(IdentitySession).where(IdentitySession.token_hash == token_hash(credentials.credentials)))
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Bishnoi One sign-in has ended. Please sign in again.")
    person = db.get(Identity, record.identity_id)
    account = account_of(db, person) if person else None
    changed = account and account.password_changed_at and as_utc(record.created_at) < as_utc(account.password_changed_at)
    if person is None or person.status != "active" or account is None or account.status != "active" or changed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your Bishnoi One sign-in has ended. Please sign in again.")
    if email_rules.off_domain(db, person):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, not_at_domain(db, person))
    return record, person


def not_at_domain(db: Session, person: Identity) -> str:
    """Why someone whose email isn't at their company's domain can't sign in (decided 2026-10-29)."""
    company = db.get(Company, person.company_id)
    return (f"{company.name} signs in with @{company.email_domain} emails, and yours is {person.email}. "
            "Ask your company's administrator to change it, then sign in with the new one.")


Signed = Annotated[tuple[IdentitySession, Identity], Depends(current_identity)]


class LoginIn(Api):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


def same_person(db: Session, email: str) -> list[Identity]:
    """Every company's membership of this person's account: the most recently used first."""
    account = account_by_email(db, email)
    return memberships(db, account) if account else []


def usable(db: Session, rows: list[Identity]) -> list[tuple[Identity, Company]]:
    """The rows they can work in now: active, at an active company."""
    out = []
    for row in rows:
        company = db.get(Company, row.company_id)
        if row.status == "active" and company is not None and company.status == "active":
            out.append((row, company))
    return out


def open_session(db: Session, settings, person: Identity, address, action: str) -> dict:
    token = new_token()
    now = datetime.now(UTC)
    expires_in = settings.identity_session_hours * 3600
    db.add(IdentitySession(token_hash=token_hash(token), identity_id=person.id, created_at=now, expires_at=now + timedelta(seconds=expires_in)))
    person.last_active_at = now
    audit(db, person.email, action, category="security", target=person.email, target_type="identity", target_id=person.id, company_id=person.company_id, address=address)
    db.commit()
    return {"accessToken": token, "tokenType": "bearer", "expiresIn": expires_in}


@router.post("/identity/login")
def login(body: LoginIn, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    email = body.email.strip().lower()
    wait = sign_in.wait_seconds(db, settings, email)
    if wait:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many wrong passwords. Try again in {max(1, wait // 60)} minute(s).",
            headers={"Retry-After": str(wait)},
        )
    account = account_by_email(db, email)
    ok = verify_password(body.password, account.password_hash if account and account.password_hash else DUMMY_HASH)
    if account is None or not account.password_hash or not ok:
        sign_in.failed(db, settings, email, address)
        audit(db, email, "identity.sign_in_failed", category="security", target=email, target_type="identity", target_id=None, address=address)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, WRONG)
    if account.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This Bishnoi One account is suspended. Ask your company's administrator.")
    # An operator needn't be added to a company: they have a membership at every one (app/platform_admins.py).
    if account.is_operator:
        platform_admins.everywhere(db, account)
        db.flush()
    rows = memberships(db, account)
    # At the company they last worked in, of those they can work in now.
    open_rows = usable(db, rows)
    if not rows:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your Bishnoi One account isn't at any company yet. Ask your company's administrator to add you.")
    if not open_rows:
        if all(r.status != "active" for r in rows):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This Bishnoi One account is suspended. Ask your company's administrator.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Bishnoi One access is suspended. Ask your company's administrator.")
    # Someone whose email isn't at their company's domain waits for their administrator to change it.
    at_domain = [(row, c) for row, c in open_rows if not email_rules.off_domain(db, row)]
    if not at_domain:
        raise HTTPException(status.HTTP_403_FORBIDDEN, not_at_domain(db, open_rows[0][0]))
    open_rows = at_domain
    sign_in.cleared(db, email)
    response.headers["Cache-Control"] = "no-store"
    # Two-step sign-in: the password was right; the session opens once the code is (POST /identity/login/code).
    if sign_in.two_step_on(account):
        ticket = sign_in.make_link(db, account, "two_step", 5 / 60, identity_id=open_rows[0][0].id)
        db.commit()
        return {"twoStep": True, "ticket": ticket}
    account.last_sign_in_at = datetime.now(UTC)
    return {**open_session(db, settings, open_rows[0][0], address, "identity.signed_in"), **after_sign_in(db, settings, account, open_rows[0][0])}


def after_sign_in(db: Session, settings, account: Account, person: Identity) -> dict:
    """What the one app does next: change a handed-over password, or set up two-step sign-in where it's required."""
    return {"mustChangePassword": account.must_change_password, "needsTwoStep": sign_in.needs_two_step(settings, account, runs_company(db, person))}


class CodeIn(Api):
    ticket: str = Field(min_length=10, max_length=200)
    code: str = Field(min_length=6, max_length=20)


@router.post("/identity/login/code")
def login_code(body: CodeIn, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    """The second step: the code from their authenticator app, or one of their recovery codes."""
    link = sign_in.find_link(db, body.ticket, ("two_step",))
    account = db.get(Account, link.account_id) if link else None
    if link is None or account is None or account.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This sign-in took too long. Enter your email and password again.")
    wait = sign_in.wait_seconds(db, settings, account.email)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many wrong codes. Try again in {max(1, wait // 60)} minute(s).", headers={"Retry-After": str(wait)})
    secret = sign_in.unsealed(settings, account.two_step_secret)
    recovered = False
    if not (secret and sign_in.code_ok(secret, body.code)):
        recovered = sign_in.use_recovery_code(account, body.code)
        if not recovered:
            sign_in.failed(db, settings, account.email, address)
            audit(db, account.email, "identity.two_step_failed", category="security", target=account.email, target_type="account", target_id=account.id, address=address)
            db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That code isn't right. Use the newest one in your authenticator app.")
    link.used_at = datetime.now(UTC)
    person = db.get(Identity, link.identity_id) if link.identity_id else None
    if person is None or person.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your Bishnoi One access is suspended. Ask your company's administrator.")
    sign_in.cleared(db, account.email)
    account.last_sign_in_at = datetime.now(UTC)
    if recovered:
        audit(db, account.email, "identity.recovery_code_used", category="security", target=account.email, target_type="account", target_id=account.id, address=address)
    response.headers["Cache-Control"] = "no-store"
    out = {**open_session(db, settings, person, address, "identity.signed_in"), **after_sign_in(db, settings, account, person)}
    return {**out, "recoveryCodesLeft": len(account.recovery_codes or []) if recovered else None}


@router.post("/identity/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(signed: Signed, db: DB) -> Response:
    record, person = signed
    record.revoked_at = datetime.now(UTC)
    audit(db, person.email, "identity.signed_out", category="security", target=person.email, target_type="identity", target_id=person.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def admin_grant(person: Identity, app: Application) -> IdentityApp:
    """A company administrator's standing grant to an application their company has: Administrator
    there, given or not (decided 2026-10-25). Never saved; made fresh each time it's asked for."""
    return IdentityApp(identity_id=person.id, application_id=app.id, role="Administrator", is_app_admin=True, granted_at=None)


def grant_of(db: Session, person: Identity, app: Application) -> IdentityApp | None:
    """What this person holds on an application: their grant, or a company administrator's standing one."""
    grant = db.get(IdentityApp, (person.id, app.id))
    if runs_company(db, person) and (grant is None or not grant.is_app_admin):
        return admin_grant(person, app) if grant is None else IdentityApp(
            identity_id=person.id, application_id=app.id, role=grant.role or "Administrator", is_app_admin=True, granted_at=grant.granted_at)
    return grant


def granted(db: Session, person: Identity) -> list[tuple[Application, IdentityApp]]:
    """The applications this person may open: given to them, and their company has it. A company's
    administrator opens every application the company has."""
    rows = db.execute(
        select(Application, IdentityApp)
        .join(CompanyApp, (CompanyApp.application_id == Application.id) & (CompanyApp.company_id == person.company_id))
        .outerjoin(IdentityApp, (IdentityApp.application_id == Application.id) & (IdentityApp.identity_id == person.id))
        .where(Application.is_active)
        .order_by(Application.sort_order, Application.name)
    ).all()
    # A service whose catalogue apps the company switched off isn't opened (step 6).
    rows = [(a, g) for a, g in rows if catalogue.service_on(db, person.company_id, a.key)]
    if runs_company(db, person):
        return [(a, grant_of(db, person, a)) for a, _ in rows]
    return [(a, g) for a, g in rows if g is not None]


@router.get("/identity/me")
def me(signed: Signed, db: DB, settings: SettingsDep) -> dict:
    _, person = signed
    company = db.get(Company, person.company_id)
    role = db.get(AccessRole, person.access_role_id) if person.access_role_id else None
    return {
        "id": person.id,
        "email": person.email,
        "fullName": person.full_name,
        "title": person.title,
        # Administers this company: the company's own choice, or the operator switch (accounts.runs_company).
        "isCompanyAdmin": runs_company(db, person),
        "company": {"id": company.id, "name": company.name, "slug": company.slug} if company else None,
        # Every company they work for, to switch to (this one too).
        "companies": sorted(
            ({"id": c.id, "name": c.name, "slug": c.slug, "current": c.id == person.company_id} for _, c in usable(db, same_person(db, person.email))),
            key=lambda c: c["name"].lower(),
        ),
        # Their one role at the company (app/access_roles.py), when they have one.
        "role": role.name if role else None,
        # Also Bishnoi One staff here (same email): "admin" (Platform Admin) or "member" (Support), else None.
        # The one app's Admin Console shows companies, APIs and accounts to them (app/deps.py staff_by_account).
        # An operator (step 5: the switch on their account) sees the Operations area: "admin", else None.
        "staff": "admin" if (account := account_of(db, person)) and account.is_operator else None,
        # Where they sit on the company's org chart (step 4).
        "org": placement(db, person),
        # Sign-in security (2026-10-30): a handed-over password to change; two-step sign-in, and whether it's owed.
        "mustChangePassword": bool(account and account.must_change_password),
        "twoStep": {"on": bool(account and sign_in.two_step_on(account)), "needed": sign_in.needs_two_step(settings, account, runs_company(db, person)),
                    "suggested": sign_in.suggests_two_step(account, runs_company(db, person))},
        # The company's app catalogue: each catalogue app ("app:purchasing") and feature, on or off (step 6).
        "features": catalogue.switches(db, person.company_id),
        "apps": [
            {"key": a.key, "name": a.name, "appUrl": a.app_url, "role": role.name if role else g.role, "isAppAdmin": g.is_app_admin or bool(role and role.is_admin),
             # When it was given to them: the first one given is where they start (the one app opens it after sign-in).
             "grantedAt": as_utc(g.granted_at).isoformat() if g.granted_at else None}
            for a, g in granted(db, person)
        ],
    }


class SwitchIn(Api):
    company: str = Field(min_length=1, max_length=60)


def at_company(db: Session, person: Identity, slug: str) -> Identity:
    """Their row at another company of theirs (by its short name), or 403."""
    for row, company in usable(db, same_person(db, person.email)):
        if company.slug == slug.strip().lower():
            return row
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't work for that company on Bishnoi One, or its access is suspended. Ask its administrator.")


@router.post("/identity/switch")
def switch(body: SwitchIn, signed: Signed, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    """To another company they work for: a new sign-in there, in place of this one."""
    record, person = signed
    there = at_company(db, person, body.company)
    record.revoked_at = datetime.now(UTC)
    response.headers["Cache-Control"] = "no-store"
    return open_session(db, settings, there, address, "identity.switched_company")


class PassIn(Api):
    app: str = Field(min_length=1, max_length=40)
    return_to: str = Field(min_length=1, max_length=500)
    # Another company of theirs (its short name); the one they're in when not given.
    company: str | None = Field(default=None, max_length=60)


def check_return(app: Application, return_to: str, settings) -> str:
    """The pass goes back only to the application's own address, or to Bishnoi One.exe on this PC."""
    try:
        target = urlsplit(return_to)
    except ValueError:
        target = None
    if target is None or target.path != RETURN_PATH or target.query or target.fragment or target.username or target.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")
    registered = urlsplit(app.app_url) if app.app_url else None
    # The application's own host and port. The scheme may differ from what's
    # registered — an office .local address is served over http while it was
    # stored as https — so the host has to match, not the scheme.
    if registered and target.netloc and target.netloc == registered.netloc:
        return return_to
    # The one app (ONE_APP_URL): every module's screens on one site, so it is a return for each.
    one = urlsplit(settings.one_app_url) if settings.one_app_url else None
    if one and target.netloc and target.netloc == one.netloc:
        return return_to
    if target.scheme == "http" and target.hostname in ("127.0.0.1", "localhost") and target.port:
        if target.port in DESKTOP_PORTS or settings.environment != "production":
            return return_to
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "That return address isn't one this application uses.")


@router.post("/identity/pass")
def make_pass(body: PassIn, signed: Signed, db: DB, settings: SettingsDep, address: Address, response: Response) -> dict:
    _, person = signed
    if body.company:
        person = at_company(db, person, body.company)
    app = db.scalar(select(Application).where(Application.key == body.app, Application.is_active))
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such application.")
    return_to = check_return(app, body.return_to, settings)
    company = db.get(Company, person.company_id)
    if company is None or company.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your company's Bishnoi One access is suspended. Ask your company's administrator.")
    if db.get(CompanyApp, (company.id, app.id)) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{company.name} doesn't have {app.name}. Ask your company's administrator.")
    if not catalogue.service_on(db, company.id, app.key):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{company.name} has switched {app.name} off. Ask your company's administrator.")
    grant = grant_of(db, person, app)
    if grant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your Bishnoi One account doesn't include {app.name}. Ask your company's administrator for access.")
    holder = account_of(db, person)
    if holder is not None and holder.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Change the password you were given first: open Bishnoi One and choose your own.")
    if sign_in.needs_two_step(settings, holder, runs_company(db, person)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Set up two-step sign-in first: open Bishnoi One, Your profile.")
    try:
        token = issue(settings, person, company, app, grant, role_for_pass(db, person, app), placement(db, person), company_admin=runs_company(db, person))
    except PassUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    person.last_active_at = datetime.now(UTC)
    audit(db, person.email, "identity.opened_app", category="security", target=app.name, target_type="application", target_id=app.id, company_id=person.company_id, application_id=app.id, address=address)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"pass": token, "returnTo": return_to}


class PasswordIn(Api):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD)


@router.post("/identity/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: PasswordIn, signed: Signed, db: DB) -> Response:
    record, person = signed
    account = account_of(db, person)
    if not verify_password(body.current_password, (account.password_hash if account else None) or DUMMY_HASH):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Your current password isn't right.")
    problem = sign_in.password_problem(body.new_password, person.email, person.full_name)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    if verify_password(body.new_password, account.password_hash or DUMMY_HASH):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a password different from the one you have.")
    now = datetime.now(UTC)
    password = hash_password(body.new_password)
    # One password at every company of theirs, and in the Admin Console (app/passwords.py).
    passwords.set_for(db, person.email, password, now)
    account.must_change_password = False
    # this sign-in carries on; every other one ends
    record.created_at = now
    audit(db, person.email, "identity.password_changed", category="security", target=person.email, target_type="identity", target_id=person.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- One e-signature per person (step 10, app/signatures.py) -------------------------------------


class SignatureIn(Api):
    image: str = Field(min_length=20, max_length=500_000)
    method: str = Field(pattern="^(drawn|uploaded)$")
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class PasswordOnly(Api):
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


def _signature_out(s) -> dict:
    return {"has": s is not None, "image": signatures.data_url(s.image) if s else None, "method": s.method if s else None,
            "setAt": as_utc(s.created_at).isoformat() if s else None}


def _check_password(db: Session, person: Identity, password: str) -> Account:
    account = account_of(db, person)
    if account is None or not verify_password(password, account.password_hash or DUMMY_HASH):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "password"], "msg": "That password isn't right."}])
    return account


@router.get("/identity/signature")
def my_signature(signed: Signed, db: DB) -> dict:
    _, person = signed
    account = account_of(db, person)
    return _signature_out(signatures.current(db, account.id) if account else None)


@router.put("/identity/signature")
def set_signature(body: SignatureIn, signed: Signed, db: DB) -> dict:
    """Your signature, drawn or uploaded (cleaned in the browser). Every app uses it when you sign a step."""
    _, person = signed
    account = _check_password(db, person, body.password)
    try:
        image = signatures.checked_png(body.image)
    except signatures.BadImage as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "image"], "msg": str(e)}]) from None
    s = signatures.keep(db, account.id, image, body.method)
    audit(db, person.email, "identity.signature_set", category="security", target=person.email, target_type="account", target_id=account.id)
    db.commit()
    return _signature_out(s)


@router.post("/identity/signature/remove")
def remove_signature(body: PasswordOnly, signed: Signed, db: DB) -> dict:
    """Your signature stops being used; documents you signed with it keep it."""
    _, person = signed
    account = _check_password(db, person, body.password)
    if signatures.retire(db, account.id):
        audit(db, person.email, "identity.signature_removed", category="security", target=person.email, target_type="account", target_id=account.id)
        db.commit()
    return _signature_out(None)


@router.get("/connect/signature")
def signature_for_app(db: DB, identity: str = Query(max_length=36), key: Annotated[str | None, Header(alias="X-Bishnoi-App-Key")] = None) -> dict:
    """A person's current signature, for an app placing their signed step (its connect key; only for a
    company that has the app). The app keeps its own copy with what was signed."""
    from app import links

    app = links.app_of_key(db, key)
    if app is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That connect key isn't one the platform made, or it was replaced.")
    person = db.get(Identity, identity)
    if person is None or db.get(CompanyApp, (person.company_id, app.id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "There's no such person at a company with this app.")
    account = account_of(db, person)
    s = signatures.current(db, account.id) if account else None
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This person hasn't set a signature.")
    return {"id": s.id, "image": signatures.data_url(s.image), "method": s.method, "sha256": s.sha256, "setAt": as_utc(s.created_at).isoformat()}


@router.get("/identity/documents/trail")
def document_trail(signed: Signed, db: DB, app: str = Query(max_length=40), kind: str = Query(max_length=40), id: str = Query(max_length=36)) -> dict:
    """The documents before and after one, across the company's apps (step 9). References only: each app
    still decides who may open each document."""
    _, person = signed
    return document_chain.trail(db, person.company_id, app, kind, id)


@router.get("/pass/key")
def pass_key(settings: SettingsDep) -> dict:
    """What the applications check passes with. Not a secret."""
    try:
        return {"issuer": ISSUER, "alg": "EdDSA", "kid": key_id(settings), "publicKey": public_key(settings)}
    except PassUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e


# ---- Forgot password, invitations and two-step sign-in (2026-10-30, app/sign_in.py) -----------------


class ForgotIn(Api):
    email: str = Field(min_length=3, max_length=254)


@router.post("/identity/password/forgot", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(body: ForgotIn, db: DB, settings: SettingsDep, address: Address) -> Response:
    """Emails a link to choose a new password, when the email is an active account's and its company
    sends email. Always answers the same, so nobody learns which emails have accounts."""
    email = body.email.strip().lower()
    account = account_by_email(db, email)
    rows = usable(db, memberships(db, account)) if account and account.status == "active" else []
    rows = [(r, c) for r, c in rows if not r.via_operator] or rows
    if account is not None and rows and sign_in.count_unused(db, account.id, "reset") < 3:
        token = sign_in.make_link(db, account, "reset", settings.reset_link_hours)
        url = sign_in.site(db, settings) + sign_in.link_path("reset", token)
        sent = sign_in.send(db, settings, rows[0][1].id, account.email, "Choose a new Bishnoi One password",
                            f"Hello {account.full_name},\n\nSomeone asked to reset the password of your Bishnoi One account ({account.email}). "
                            f"To choose a new one, open this link within {settings.reset_link_hours} hour(s):\n\n{url}\n\n"
                            "If it wasn't you, ignore this email: your password stays as it is.\n\nBishnoi One")
        audit(db, email, "identity.reset_requested" if sent else "identity.reset_not_sent", category="security", target=email, target_type="account",
              target_id=account.id, company_id=rows[0][1].id, address=address)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/identity/password/link")
def password_link(token: Annotated[str, Query(min_length=10, max_length=200)], db: DB) -> dict:
    """What a reset or invitation link is for, so its page can greet the person."""
    link = sign_in.find_link(db, token, ("reset", "invite"))
    account = db.get(Account, link.account_id) if link else None
    if link is None or account is None or account.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link has expired or was already used. Ask for a new one.")
    rows = usable(db, memberships(db, account))
    return {"kind": link.kind, "email": account.email, "fullName": account.full_name, "company": rows[0][1].name if rows else None}


class SetPasswordIn(Api):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


@router.post("/identity/password/set", status_code=status.HTTP_204_NO_CONTENT)
def set_password_by_link(body: SetPasswordIn, db: DB, address: Address) -> Response:
    """A reset or invitation link's password: theirs at every company; every other sign-in ends."""
    link = sign_in.find_link(db, body.token, ("reset", "invite"))
    account = db.get(Account, link.account_id) if link else None
    if link is None or account is None or account.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link has expired or was already used. Ask for a new one.")
    problem = sign_in.password_problem(body.password, account.email, account.full_name)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "password"], "msg": problem}])
    now = datetime.now(UTC)
    passwords.set_for(db, account.email, hash_password(body.password), now)
    account.must_change_password = False
    link.used_at = now
    sign_in.cleared(db, account.email)
    audit(db, account.email, "identity.password_set_by_link" if link.kind == "reset" else "identity.invitation_accepted", category="security",
          target=account.email, target_type="account", target_id=account.id, address=address)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _two_step_out(settings, db: Session, account: Account, person: Identity) -> dict:
    return {"on": sign_in.two_step_on(account), "required": bool(settings.two_step_required and (runs_company(db, person) or account.is_operator)),
            "recoveryCodesLeft": len(account.recovery_codes or []) if sign_in.two_step_on(account) else 0}


@router.get("/identity/two-step")
def two_step(signed: Signed, db: DB, settings: SettingsDep) -> dict:
    _, person = signed
    return _two_step_out(settings, db, account_of(db, person), person)


@router.post("/identity/two-step/start")
def two_step_start(body: PasswordOnly, signed: Signed, db: DB, settings: SettingsDep) -> dict:
    """A new secret for their authenticator app (shown as a QR code and as text); on once a code from it is confirmed."""
    _, person = signed
    account = _check_password(db, person, body.password)
    if sign_in.two_step_on(account):
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-step sign-in is already on. Turn it off first to move it to another phone.")
    secret = sign_in.new_secret()
    account.two_step_secret = sign_in.sealed(settings, secret)
    db.commit()
    uri = sign_in.setup_uri(account, secret, settings.org_name)
    return {"secret": secret, "uri": uri, "qr": sign_in.qr_svg(uri)}


class TwoStepCodeIn(Api):
    code: str = Field(min_length=6, max_length=20)


@router.post("/identity/two-step/confirm")
def two_step_confirm(body: TwoStepCodeIn, signed: Signed, db: DB, settings: SettingsDep, address: Address) -> dict:
    """The first code from the app: two-step sign-in is on, and ten recovery codes are shown once."""
    _, person = signed
    account = account_of(db, person)
    secret = sign_in.unsealed(settings, account.two_step_secret) if account else None
    if account is None or not secret or sign_in.two_step_on(account):
        raise HTTPException(status.HTTP_409_CONFLICT, "Start again: scan the code, then enter the number it shows.")
    if not sign_in.code_ok(secret, body.code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "code"], "msg": "That code isn't right. Enter the newest one the app shows."}])
    codes, hashes = sign_in.new_recovery_codes()
    account.two_step_on_at, account.recovery_codes = datetime.now(UTC), hashes
    audit(db, account.email, "identity.two_step_on", category="security", target=account.email, target_type="account", target_id=account.id, address=address)
    db.commit()
    return {**_two_step_out(settings, db, account, person), "recoveryCodes": codes}


class TwoStepOffIn(Api):
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    code: str = Field(min_length=6, max_length=20)


@router.post("/identity/two-step/off")
def two_step_off(body: TwoStepOffIn, signed: Signed, db: DB, settings: SettingsDep, address: Address) -> dict:
    _, person = signed
    account = _check_password(db, person, body.password)
    if settings.two_step_required and (runs_company(db, person) or account.is_operator):
        raise HTTPException(status.HTTP_409_CONFLICT, "Administrators must keep two-step sign-in on. To move it to a new phone, ask another administrator to reset it.")
    secret = sign_in.unsealed(settings, account.two_step_secret)
    if not (secret and sign_in.code_ok(secret, body.code)) and not sign_in.use_recovery_code(account, body.code):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, [{"type": "value_error", "loc": ["body", "code"], "msg": "That code isn't right."}])
    account.two_step_secret, account.two_step_on_at, account.recovery_codes = None, None, None
    audit(db, account.email, "identity.two_step_off", category="security", target=account.email, target_type="account", target_id=account.id, address=address)
    db.commit()
    return _two_step_out(settings, db, account, person)
