from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.access import Access, active_member, load_access, owns_company
from app.config import Settings
from app.models import LocalCredential, Organization, PlatformSession, Profile, SessionRecord
from app.platform import is_developer_admin
from app.security import TokenClaims, read_token
from app.store.files import FileStore
from app.store.records import Records
from app.tenancy import company_of, set_company

_bearer = HTTPBearer(auto_error=False)

SIGN_IN_AGAIN = "Your session has ended. Please sign in again."


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as session:
        yield session


def current_claims(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenClaims:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in.")
    claims = read_token(settings, credentials.credentials)
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    return claims


def as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment  # SQLite hands back naive UTC


def session_is_open(record: SessionRecord | None, user_id: str) -> bool:
    return (
        record is not None
        and record.user_id == user_id
        and record.revoked_at is None
        and as_utc(record.expires_at) > datetime.now(UTC)
    )


def platform_session_is_open(record: PlatformSession | None, user_id: str) -> bool:
    return (
        record is not None
        and record.user_id == user_id
        and record.revoked_at is None
        and as_utc(record.expires_at) > datetime.now(UTC)
    )


# Reading is looking; everything else is doing.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Except getting out. Ending a borrowed session is not a change to the company,
# and a door that only opens inwards is not a door.
WAY_OUT = frozenset({"/auth/leave", "/auth/logout"})


def current_user(
    request: Request,
    claims: Annotated[TokenClaims, Depends(current_claims)],
    db: Annotated[Session, Depends(get_db)],
) -> Profile:
    """The signed-in person, with this request's database session walled to their company.

    A token with no company is a platform session: a Developer Admin who has not
    opened one. Nothing company-shaped is reachable from it (see `current_org`),
    so there is no wall to put up and none to get around."""
    if claims.org_id is None:
        user = db.get(Profile, claims.user_id)
        if (
            user is None
            or not user.is_active
            or not is_developer_admin(db, user.id)
            or not platform_session_is_open(db.get(PlatformSession, claims.session_id), user.id)
            or issued_before_password_change(db, user.id, claims.issued_at)
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
        refuse_changes_while_viewing(request, claims)
        return user

    set_company(db, claims.org_id)
    user = db.get(Profile, claims.user_id)
    org = db.get(Organization, claims.org_id)
    # Checked on every request, so signing out (in any app the session was
    # handed to), switching someone off (everywhere, or in this company) or
    # suspending the company takes effect at once, and a password reset ends
    # every session that started before it.
    # A Developer Admin reaches a company they are not in -- that is the job --
    # so for them the membership check is skipped and nothing else is.
    if (
        user is None
        or not user.is_active
        or org is None
        or org.status != "active"
        or (active_member(db, user.id) is None and not is_developer_admin(db, user.id))
        or not session_is_open(db.get(SessionRecord, claims.session_id), user.id)
        or issued_before_password_change(db, user.id, claims.issued_at)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, SIGN_IN_AGAIN)
    refuse_changes_while_viewing(request, claims)
    return user


def refuse_changes_while_viewing(request: Request, claims: TokenClaims) -> None:
    """Looking through somebody's eyes is looking, and nothing else.

    A Developer Admin viewing as a rep sees exactly what the rep sees, which is
    the only honest way to check it. What they must not do is act as them: a
    change made this way would be signed with the rep's name, and a system where
    that is possible is a system whose audit log cannot be trusted. Anything
    that needs changing, they change as themselves."""
    if claims.viewed_by is not None and request.method not in SAFE_METHODS and request.url.path not in WAY_OUT:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "You're seeing Orbit as someone else, so nothing can be changed. Leave first, then do it as yourself.",
        )


def issued_before_password_change(db: Session, user_id: str, issued_at: int) -> bool:
    credential = db.get(LocalCredential, user_id)
    if credential is None:
        return False
    return issued_at < int(as_utc(credential.updated_at).timestamp())


def current_org(
    claims: Annotated[TokenClaims, Depends(current_claims)],
    _user: Annotated[Profile, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    """The company this request is in. A platform session is in none, so anything
    that needs one says so plainly rather than failing somewhere deeper."""
    if claims.org_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Open a company first: this belongs to one.")
    return db.get(Organization, company_of(db))


def get_records(request: Request, org: Annotated[Organization, Depends(current_org)]) -> Records:
    """The records store, holding only the signed-in person's company."""
    return request.app.state.records.for_org(org.id)


def get_files(request: Request, org: Annotated[Organization, Depends(current_org)]) -> FileStore:
    return request.app.state.files.for_org(org.id)


def current_access(
    claims: Annotated[TokenClaims, Depends(current_claims)],
    user: Annotated[Profile, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Access:
    """In a platform session there is no company to resolve access in. What the
    person holds there is the recovery key and nothing else -- which is what
    lets them open a company, and nothing more until they do."""
    if claims.org_id is None:
        return Access(recover_settings=True)
    return load_access(db, user.id)


def require_settings(access: Annotated[Access, Depends(current_access)]) -> None:
    access.require_settings()


def require_recovery(access: Annotated[Access, Depends(current_access)]) -> None:
    """The screens somebody needs when the company is broken: its accounts, the
    applications it reaches, and the log. A Developer Admin holds these and
    nothing else; an Admin holds them because they hold everything."""
    access.require_recovery()


def require_owner(
    user: Annotated[Profile, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """The company's own decisions: what it is, how its money reads, its data in
    and out. An Admin runs the company; an owner decides what it is."""
    if not owns_company(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the company's owner can change this.")


def require_owner_or_recovery(
    access: Annotated[Access, Depends(current_access)],
    user: Annotated[Profile, Depends(current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """The company record: the owner, or whoever was trusted with recovery.

    A company whose name, currency or timezone is wrong is a company that does
    not work, and putting that right is the recovery job. Note this asks for the
    recovery key itself, not `can_recover`: an Admin runs the company but
    still does not decide what it is, exactly as before. The riskier half of an
    owner's decisions -- the company's data in and out -- stays owner-only."""
    if not (access.recover_settings or owns_company(db, user.id)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the company's owner can change this.")


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DB = Annotated[Session, Depends(get_db)]
RecordsDep = Annotated[Records, Depends(get_records)]
FilesDep = Annotated[FileStore, Depends(get_files)]
CurrentClaims = Annotated[TokenClaims, Depends(current_claims)]
CurrentUser = Annotated[Profile, Depends(current_user)]
CurrentOrg = Annotated[Organization, Depends(current_org)]
CurrentAccess = Annotated[Access, Depends(current_access)]
