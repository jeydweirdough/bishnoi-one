"""One sign-in for Orbit and the apps around it (the Orders app).

The handoff is OAuth's authorization-code flow with PKCE, kept to what these
apps need:

1. The Orders app sends the browser to Orbit's web app, /sso/authorize, with
   its client id, where to come back to, a random `state` and a PKCE
   challenge. Someone not signed in to Orbit signs in first.
2. Orbit's web app asks the API for a one-time code (POST /sso/codes, as the
   signed-in person) and sends the browser back with it.
3. The Orders app's server swaps the code (POST /sso/token) with its client
   secret and the PKCE verifier. The token it gets names the same session
   (`sid`), so signing out in either app ends both.

Codes last 60 seconds, work once, and are only ever stored hashed. Tokens are
checked by anyone with Orbit's public keys: GET /.well-known/jwks.json.
"""

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import Field

from app.access import active_member
from app.deps import DB, CurrentClaims, CurrentUser, SettingsDep, as_utc, session_is_open
from app.models import Organization, Profile, SessionRecord, SsoClient, SsoCode, utcnow
from app.schemas import Api
from app.security import issue_token
from app.tenancy import all_companies, set_company

log = logging.getLogger("crm.sso")

router = APIRouter(tags=["single sign-on"])

CODE_SECONDS = 60


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def active_client(db, client_id: str) -> SsoClient | None:
    client = db.get(SsoClient, client_id)
    return client if client is not None and client.revoked_at is None else None


class CodeIn(Api):
    client_id: str = Field(min_length=1, max_length=40)
    redirect_uri: str = Field(min_length=1, max_length=500)
    code_challenge: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    code_challenge_method: str = Field("S256", pattern=r"^S256$")


class TokenIn(Api):
    grant_type: str = Field(pattern=r"^authorization_code$")
    code: str = Field(min_length=1, max_length=200)
    client_id: str = Field(min_length=1, max_length=40)
    client_secret: str = Field(min_length=1, max_length=200)
    redirect_uri: str = Field(min_length=1, max_length=500)
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


@router.get("/.well-known/jwks.json")
def jwks(settings: SettingsDep) -> dict:
    return settings.signing_keys.jwks()


@router.post("/sso/codes", status_code=status.HTTP_201_CREATED)
def make_code(body: CodeIn, claims: CurrentClaims, user: CurrentUser, db: DB) -> dict:
    """A one-time code handing this session to another app. Asked for by Orbit's web app, as the person."""
    client = active_client(db, body.client_id)
    # The address must be registered exactly, or the code could be sent anywhere.
    if client is None or body.redirect_uri not in client.redirect_uris:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That app isn't set up for signing in through Orbit.")
    code = secrets.token_urlsafe(32)
    db.add(
        SsoCode(
            id=digest(code),
            client_id=client.id,
            session_id=claims.session_id,
            redirect_uri=body.redirect_uri,
            code_challenge=body.code_challenge,
            expires_at=utcnow() + timedelta(seconds=CODE_SECONDS),
        )
    )
    db.commit()
    log.info("sign-in code for %s issued to %s", client.id, user.email)
    return {"code": code, "redirectUri": body.redirect_uri}


def refused() -> HTTPException:
    # One answer for every reason, so a guesser learns nothing.
    return HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")


@router.post("/sso/token")
def swap_code(body: TokenIn, request: Request, db: DB, settings: SettingsDep) -> dict:
    """The app's server swaps a code for a token of the same session."""
    client = active_client(db, body.client_id)
    if client is None or not hmac.compare_digest(client.secret_hash, digest(body.client_secret)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")

    with all_companies(db):  # the code says which company; nothing else does yet
        code = db.get(SsoCode, digest(body.code))
        if code is None or code.used_at is not None:
            raise refused()
        # Used or not, it can't be tried again.
        code.used_at = utcnow()
        db.commit()
        org_id = code.org_id
    if (
        code.client_id != client.id
        or code.redirect_uri != body.redirect_uri
        or as_utc(code.expires_at) < datetime.now(UTC)
        or not hmac.compare_digest(code.code_challenge, pkce_challenge(body.code_verifier))
    ):
        raise refused()

    set_company(db, org_id)
    record = db.get(SessionRecord, code.session_id)
    user = db.get(Profile, record.user_id) if record else None
    org = db.get(Organization, org_id)
    if (
        user is None
        or not user.is_active
        or org is None
        or org.status != "active"
        or active_member(db, user.id) is None
        or not session_is_open(record, user.id)
    ):
        raise refused()
    token, expires_in = issue_token(settings, user, org_id, record.id, client=client.id, expires_at=as_utc(record.expires_at))
    log.info("signed in to %s: %s", client.id, user.email)
    return {"accessToken": token, "tokenType": "Bearer", "expiresIn": expires_in}
