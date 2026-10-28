"""Who is asking: the bearer token, checked against this app's sessions.

Two kinds of staff sign in here. Anyone signed in sees everything and works
Support and Incidents; changing the platform itself (companies, applications,
people's access, announcements, settings) takes a Platform Admin (`AdminUser`).

Since 2026-10-24 staff also come in with their Bishnoi One account (the one
app's Admin Console, one sign-in): a Bishnoi One session whose email is an
active staff member's counts as that staff member (current_session, below).
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Account, Identity, IdentitySession, SignInSession, User
from app.security import token_hash

_bearer = HTTPBearer(auto_error=False)

SIGN_IN_AGAIN = "Your session has ended. Please sign in again."


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    with request.app.state.sessions() as db:
        yield db


def client_address(request: Request) -> str | None:
    """Who is asking, as the screens' server reports it (it sits in front)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    return request.client.host if request.client else None


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment  # SQLite hands back naive UTC


def current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> SignInSession:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    record = db.scalar(select(SignInSession).where(SignInSession.token_hash == token_hash(credentials.credentials)))
    if record is None:
        record = staff_by_account(db, credentials.credentials)
    if record is None or record.revoked_at is not None or as_utc(record.expires_at) <= datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return record


def staff_by_account(db: Session, token: str) -> SignInSession | None:
    """A Bishnoi One sign-in (the one app's Admin Console) by someone who is also
    staff here, by email: their staff standing, for as long as that sign-in
    lasts. Not stored: nothing about it is a console session of its own."""
    found = db.scalar(select(IdentitySession).where(IdentitySession.token_hash == token_hash(token)))
    if found is None or found.revoked_at is not None or as_utc(found.expires_at) <= datetime.now(UTC):
        return None
    person = db.get(Identity, found.identity_id)
    if person is None or person.status != "active":
        return None
    account = db.get(Account, person.account_id) if person.account_id else None
    if account is None or account.status != "active":
        return None
    if account.password_changed_at and as_utc(found.created_at) < as_utc(account.password_changed_at):
        return None
    # Operators only (step 5): the switch on their account; their staff record is kept for the history.
    if not account.is_operator:
        return None
    staff = db.scalar(select(User).where(func.lower(User.email) == account.email.lower(), User.is_active))
    if staff is None:
        staff = User(email=account.email, full_name=account.full_name, password_hash=account.password_hash or "!", role="admin")
        db.add(staff)
        db.commit()
    record = SignInSession(id=f"account:{found.id}", token_hash=found.token_hash, user_id=staff.id, created_at=found.created_at, expires_at=found.expires_at)
    record.by_account = True
    return record


def current_user(
    record: Annotated[SignInSession, Depends(current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Checked on every request, so switching someone off or changing their
    password ends their sessions at once."""
    user = db.get(User, record.user_id)
    # Through a Bishnoi One sign-in, that account's password is what counts (checked above), not the console's.
    by_account = getattr(record, "by_account", False)
    if user is None or not user.is_active or (not by_account and as_utc(record.created_at) < as_utc(user.password_changed_at)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return user


def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a Platform Admin can change that. Support can see it, not change it.")
    return user


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DB = Annotated[Session, Depends(get_db)]
Address = Annotated[str | None, Depends(client_address)]
CurrentSession = Annotated[SignInSession, Depends(current_session)]
CurrentUser = Annotated[User, Depends(current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
