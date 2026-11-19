"""Who is asking: the bearer token, checked against this app's sessions."""

from datetime import UTC, datetime
from typing import Annotated

from modules import one_session
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.pharmacy.config import Settings
from modules.pharmacy.models import SignInSession, User
from modules.pharmacy.security import token_hash

_bearer = HTTPBearer(auto_error=False)

SIGN_IN_AGAIN = "Your session has ended. Please sign in again."


def get_settings_dep(request: Request) -> Settings:
    """The settings from .env, with what the platform says this app is linked to over them (Connections)."""
    from modules.pharmacy.platform_links import effective

    return effective(request.app.state.settings)


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment  # SQLite hands back naive UTC


APP_KEY = "pharmacy"  # this module's key on the Platform


def current_session(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> SignInSession:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    record = db.scalar(select(SignInSession).where(SignInSession.token_hash == token_hash(credentials.credentials)))
    if record is None:
        # Not a session of this module's own: in the one backend, the Bishnoi One account's token (one sign-in, M3).
        account = one_session.answer(request, APP_KEY, credentials.credentials)
        if account is not None:
            from modules.pharmacy.routers.auth import account_session

            request.state.account_session = True
            return account_session(db, credentials.credentials, *account)
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return record


def current_user(
    request: Request,
    record: Annotated[SignInSession, Depends(current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Checked on every request, so switching someone off or changing their
    password ends their sessions at once."""
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
    from modules.pharmacy.platform_roles import viewed_as

    return viewed_as(request, db, user)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DB = Annotated[Session, Depends(get_db)]
CurrentSession = Annotated[SignInSession, Depends(current_session)]
CurrentUser = Annotated[User, Depends(current_user)]
