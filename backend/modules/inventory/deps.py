"""Who is asking, and for which company: the bearer token, checked against
that company's sessions, in that company's own database (app/tenants.py)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.inventory.config import Settings
from modules.inventory.models import SignInSession, User
from modules.inventory.security import token_hash
from modules import one_session
from modules.inventory.tenants import Tenant, clean, company_of

_bearer = HTTPBearer(auto_error=False)

SIGN_IN_AGAIN = "Your session has ended. Please sign in again."


def company_may_use(settings: Settings, slug: str) -> None:
    """Refuses when the company isn't registered, active and given Inventory on the platform."""
    from modules.inventory.company import standing  # here: app.company needs the settings module first

    found = standing(settings, slug)
    if found.outage:
        # The platform couldn't be asked: a wait, not a refusal (the screens show "not available right now").
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, found.message, headers={"Retry-After": "30"})
    if not found.ok:
        raise HTTPException(status.HTTP_403_FORBIDDEN, found.message)


def open_company(request: Request, slug: str) -> Tenant:
    """The company's database, once it's known it may use Inventory."""
    company_may_use(request.app.state.settings, slug)
    request.state.company = slug
    return request.app.state.tenants.get(slug)


APP_KEY = "inventory"  # this module's key on the Platform


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    return auth[7:].strip() or None if auth.lower().startswith("bearer ") else None


def account_answer(request: Request) -> tuple[dict, bool] | None:
    """One sign-in (stage M3, modules/one_session.py): when the bearer token is the Bishnoi One account's
    (never "<company>.<random>" like this module's own) and this module runs in the one backend, what the
    Platform says about it (the person, their company, their role here), else None."""
    token = _bearer_token(request)
    if not token or "." in token:
        return None
    return one_session.answer(request, APP_KEY, token)


def current_tenant(request: Request) -> Tenant:
    """The company this request is for (once per request): the token's prefix, or for an account token
    the company the Platform says the person is signed in at."""
    found = getattr(request.state, "tenant", None)
    if found is None:
        account = account_answer(request)
        if account is None:
            found = open_company(request, company_of(request))
        else:
            from modules.inventory.company import standing  # here: app.company needs the settings module first

            slug = clean(account[0].get("companySlug"))
            if slug is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
            found = open_company(request, slug)
            # The Platform's answer and the company's own standing must be about the same company.
            known = standing(request.app.state.settings, slug)
            if known.company_id and account[0].get("company") != known.company_id:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "This sign-in isn't for this company. Sign in again from Bishnoi One.")
        request.state.tenant = found
    return found


def get_settings_dep(request: Request, tenant: Annotated[Tenant, Depends(current_tenant)]) -> Settings:
    base: Settings = request.app.state.settings
    overrides: dict = {"company": tenant.slug}
    # ORG_NAME in .env is the default company's, on this computer; any other
    # company is shown by its name on the platform.
    if base.is_production or tenant.slug != base.default_company:
        from modules.inventory.company import standing

        overrides["org_name"] = standing(base, tenant.slug).name or tenant.slug
    # What Inventory is linked to, as the platform says (Connections); nothing when not connected.
    from modules.inventory.platform_links import overrides as links

    overrides |= links(base)
    return base.model_copy(update=overrides)


def get_db(tenant: Annotated[Tenant, Depends(current_tenant)]):
    with tenant.sessions() as db:
        yield db


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment  # SQLite hands back naive UTC


def current_session(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> SignInSession:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    account = account_answer(request)
    if account is not None:
        # The Bishnoi One account's own token: the session row kept here for it (one sign-in, M3).
        from modules.inventory.routers.auth import account_session

        request.state.account_session = True
        return account_session(db, credentials.credentials, *account)
    record = db.scalar(select(SignInSession).where(SignInSession.token_hash == token_hash(credentials.credentials)))
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return record


def current_user(
    request: Request,
    record: Annotated[SignInSession, Depends(current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Checked on every request, so switching someone off or changing their
    password ends their sessions at once; and so does the company being
    suspended on the platform, or losing Inventory there (current_tenant)."""
    user = db.get(User, record.user_id)
    if getattr(request.state, "account_session", False):
        # The Platform keeps the password and checked the sign-in itself (modules/one_session.py).
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
        if not user.is_active:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your account in this application is switched off. Ask your administrator.")
    elif user is None or not user.is_active or as_utc(record.created_at) < as_utc(user.password_changed_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    # An administrator viewing as someone: answered as them, read-only (app/platform_roles.py).
    from modules.inventory.platform_roles import viewed_as

    return viewed_as(request, db, user)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DB = Annotated[Session, Depends(get_db)]
CurrentSession = Annotated[SignInSession, Depends(current_session)]
CurrentUser = Annotated[User, Depends(current_user)]
CurrentTenant = Annotated[Tenant, Depends(current_tenant)]
