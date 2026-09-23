"""Who is asking: the bearer token, checked against this app's sessions."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import SalesSettings, SignInSession, User
from app.security import token_hash

_bearer = HTTPBearer(auto_error=False)

SIGN_IN_AGAIN = "Your session has ended. Please sign in again."


def get_settings_dep(request: Request) -> Settings:
    """The settings from .env, with what an admin changed in Settings over them
    (company name, currency, locale, timezone), read fresh on each request."""
    base: Settings = request.app.state.settings
    with request.app.state.sessions() as db:
        row = db.get(SalesSettings, 1)
    if row is None:
        return base
    overrides = {"org_name": row.org_name, "org_currency": row.currency, "org_locale": row.locale, "org_timezone": row.timezone}
    overrides = {k: v for k, v in overrides.items() if v}
    return base.model_copy(update=overrides) if overrides else base


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment  # SQLite hands back naive UTC


def current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> SignInSession:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    record = db.scalar(select(SignInSession).where(SignInSession.token_hash == token_hash(credentials.credentials)))
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return record


def current_user(
    record: Annotated[SignInSession, Depends(current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Checked on every request, so switching someone off or changing their
    password ends their sessions at once."""
    user = db.get(User, record.user_id)
    if user is None or not user.is_active or as_utc(record.created_at) < as_utc(user.password_changed_at):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return user


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DB = Annotated[Session, Depends(get_db)]
CurrentSession = Annotated[SignInSession, Depends(current_session)]
CurrentUser = Annotated[User, Depends(current_user)]
