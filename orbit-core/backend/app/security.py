"""Password hashing and sign-in tokens.

bcrypt because Supabase Auth stores bcrypt too, so existing passwords can be
imported if sign-in moves there.

A token says who (sub), in which company (org), under which sign-in session
(sid) and for which app (azp: "web" is Orbit's own). It's signed with Orbit's
private key (app/keys.py). The session is checked on every request, so signing
out anywhere ends it everywhere it was handed on to (the Orders app).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import Settings
from app.keys import ALGORITHM
from app.models import Profile

MIN_PASSWORD = 8
MAX_PASSWORD_BYTES = 72  # bcrypt's limit
BCRYPT_ROUNDS = 12  # tests lower this; each +1 doubles the time
WEB = "web"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# Checked against when the email is unknown, so a wrong email takes as long as a wrong password.
DUMMY_HASH = hash_password("not-a-real-password")


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    issued_at: int  # epoch seconds
    # The company this session works in. None for a Developer Admin, who is in
    # no company until they open one (app/platform.py).
    org_id: str | None
    session_id: str
    client: str  # which app the token was handed to
    # The Developer Admin looking through this person's eyes, when somebody
    # is. The session still resolves as the person; this says who is driving.
    viewed_by: str | None = None


def issue_token(
    settings: Settings,
    user: Profile,
    org_id: str | None,
    session_id: str,
    *,
    client: str = WEB,
    expires_at: datetime | None = None,
    viewed_by: str | None = None,
) -> tuple[str, int]:
    now = datetime.now(UTC)
    until = expires_at or now + timedelta(hours=settings.session_hours)
    keys = settings.signing_keys
    claims = {
        "sub": user.id,
        "org": org_id,
        "sid": session_id,
        "azp": client,
        # Who is really at the keyboard, when it is not the person named in `sub`.
        "act": viewed_by,
        "email": user.email,
        "aud": settings.jwt_audience,
        "iss": settings.jwt_issuer,
        "role": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int(until.timestamp()),
    }
    token = jwt.encode(claims, keys.private, algorithm=ALGORITHM, headers={"kid": keys.kid})
    return token, max(0, int((until - now).total_seconds()))


def read_token(settings: Settings, token: str) -> TokenClaims | None:
    """Who, since when, in which company and session, for a valid token; None otherwise.

    `org` is null for a platform session -- a Developer Admin, in no company
    until they open one. Tokens from before there were companies and sessions
    (no `org` or `sid` at all), or signed by any key Orbit doesn't publish, are
    refused: sign in again."""
    keys = settings.signing_keys
    try:
        key = keys.public.get(jwt.get_unverified_header(token).get("kid"))
        if key is None:
            return None
        claims = jwt.decode(
            token,
            key,
            algorithms=[ALGORITHM],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            # "org" is checked below, not here: PyJWT counts a null claim as
            # missing, and null is exactly what a platform session carries.
            options={"require": ["exp", "iat", "sub", "aud", "iss", "sid"]},
        )
    except jwt.PyJWTError:
        return None
    fields = (claims["sub"], claims["sid"], claims.get("azp", WEB))
    if not all(isinstance(f, str) and f for f in fields):
        return None
    # Present but allowed to be null. A token from before there were companies
    # has no `org` key at all and is refused.
    if "org" not in claims:
        return None
    org = claims["org"]
    if org is not None and not (isinstance(org, str) and org):
        return None
    acting = claims.get("act")
    if acting is not None and not (isinstance(acting, str) and acting):
        return None
    return TokenClaims(claims["sub"], int(claims["iat"]), org, claims["sid"], fields[2], acting)
