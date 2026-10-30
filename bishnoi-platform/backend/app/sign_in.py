"""Signing in safely on one's own (2026-10-30).

- Password rules: long enough, not the email or name, not one of the passwords everyone tries.
- Wrong passwords are counted in the database (nbpl_sign_in_failures), so a restart or a second copy
  of the API doesn't forget them; a sign-in waits once there are too many.
- One-time links (nbpl_sign_in_links): "reset" (forgot password, emailed, an hour), "invite" (a new
  person sets their own password, a week), "two_step" (a sign-in waiting for its code, five minutes).
  Only the token's hash is kept; a link works once.
- Email goes through the company's own Email sending service (Admin Console → Integrations), the one
  the CRM and Inventory use. Without it nothing is sent, and an administrator copies the link instead.
- Two-step sign-in: a time-based code from an authenticator app (RFC 6238: 6 digits, 30 seconds, SHA-1,
  as Google Authenticator, Microsoft Authenticator and 1Password read them). The secret is sealed like
  services' secrets; ten recovery codes, hashed, each usable once.
"""

import base64
import hashlib
import hmac
import io
import logging
import secrets
import smtplib
import struct
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from urllib.parse import quote, urlsplit

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import services as svc
from app.config import Settings
from app.models import Account, Application, ServiceConnection, SignInFailure, SignInLink
from app.security import check_password_rules, new_token, token_hash

log = logging.getLogger("platform.sign_in")

# ---- Password rules ----------------------------------------------------------------------------

# The passwords tried first by anyone guessing (lower case; a password is refused when it is one of
# these, whatever its case, or one of them with digits or ! at the end).
COMMON = {
    "password", "passw0rd", "password1", "qwerty", "qwertyuiop", "abc123", "abcdef", "letmein", "welcome", "admin", "administrator",
    "iloveyou", "monkey", "dragon", "sunshine", "princess", "football", "baseball", "master", "superman", "trustno1", "changeme",
    "secret", "default", "login", "bishnoi", "bishnoione", "getmeds", "manila", "philippines", "pilipinas", "mahalkita", "iloveu",
}


def password_problem(password: str, email: str | None = None, name: str | None = None) -> str | None:
    """Why this password won't do, or None."""
    basic = check_password_rules(password)
    if basic:
        return basic
    low = password.lower()
    if len(set(low)) <= 2:
        return "Use a password with more different characters."
    if low.rstrip("0123456789!") in COMMON or low in COMMON or low.isdigit() and len(set(low)) < 5:
        return "That password is one of the first anyone would try. Choose another."
    local = (email or "").lower().partition("@")[0]
    if len(local) >= 4 and local in low:
        return "Don't use your email in your password."
    for part in (name or "").lower().split():
        if len(part) >= 4 and part in low:
            return "Don't use your name in your password."
    return None


# ---- Wrong passwords, counted in the database ---------------------------------------------------


def wait_seconds(db: Session, settings: Settings, email: str) -> int:
    """How long this email waits before another try, or 0."""
    window = timedelta(minutes=settings.login_lockout_minutes)
    since = datetime.now(UTC) - window
    rows = db.scalars(select(SignInFailure.at).where(SignInFailure.email == email, SignInFailure.at > since).order_by(SignInFailure.at)).all()
    if len(rows) < settings.login_attempts:
        return 0
    first = rows[-settings.login_attempts]
    first = first if first.tzinfo else first.replace(tzinfo=UTC)
    return max(1, int((first + window - datetime.now(UTC)).total_seconds()) + 1)


def failed(db: Session, settings: Settings, email: str, address: str | None) -> None:
    db.add(SignInFailure(email=email, address=(address or "")[:64] or None))
    # Old ones are of no use: kept a day at most.
    db.execute(delete(SignInFailure).where(SignInFailure.at < datetime.now(UTC) - timedelta(days=1)))


def cleared(db: Session, email: str) -> None:
    db.execute(delete(SignInFailure).where(SignInFailure.email == email))


# ---- One-time links ------------------------------------------------------------------------------


def make_link(db: Session, account: Account, kind: str, hours: float, made_by: str | None = None, identity_id: str | None = None) -> str:
    """A new link of this kind (older unused ones of the same kind stop working); the token, once."""
    now = datetime.now(UTC)
    if kind != "two_step":
        for old in db.scalars(select(SignInLink).where(SignInLink.account_id == account.id, SignInLink.kind == kind, SignInLink.used_at.is_(None))):
            old.used_at = now
    token = new_token()
    db.add(SignInLink(account_id=account.id, kind=kind, token_hash=token_hash(token), created_at=now, expires_at=now + timedelta(hours=hours),
                      made_by=made_by, identity_id=identity_id))
    db.flush()
    return token


def find_link(db: Session, token: str, kinds: tuple[str, ...]) -> SignInLink | None:
    """A link that still works: one of these kinds, not used, not expired."""
    link = db.scalar(select(SignInLink).where(SignInLink.token_hash == token_hash(token or "")))
    if link is None or link.kind not in kinds or link.used_at is not None:
        return None
    expires = link.expires_at if link.expires_at.tzinfo else link.expires_at.replace(tzinfo=UTC)
    return link if expires > datetime.now(UTC) else None


def site(db: Session, settings: Settings) -> str:
    """The one app's address, for links in emails: ONE_APP_URL, else the Admin Console's registered address."""
    if settings.one_app_url:
        return settings.one_app_url.rstrip("/")
    console = db.scalar(select(Application.app_url).where(Application.key == "platform"))
    parts = urlsplit(console or "")
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else "http://localhost:4301"


def link_path(kind: str, token: str) -> str:
    """Where the link opens in the one app (app/login/password: public, like the sign-in)."""
    return f"/login/password?{'invite' if kind == 'invite' else 'reset'}={quote(token)}"


# ---- Email through the company's own sending service ----------------------------------------------


def relay(db: Session, settings: Settings, company_id: str | None) -> dict | None:
    """The company's Email sending details, when it's switched on and filled in."""
    if not company_id:
        return None
    row = db.scalar(select(ServiceConnection).where(ServiceConnection.company_id == company_id, ServiceConnection.service == "smtp", ServiceConnection.is_enabled))
    if row is None:
        return None
    secret = svc.unseal(settings, row.secrets)
    values = {**(row.values or {}), **(secret or {})}
    return values if secret is not None and values.get("host") and values.get("password") else None


def send(db: Session, settings: Settings, company_id: str | None, to: str, subject: str, text: str) -> bool:
    """One email; False when the company has no email sending, or sending failed (logged, never raised)."""
    via = relay(db, settings, company_id)
    if via is None:
        return False
    sender = via.get("from_email") or via.get("username") or ""
    try:
        with smtplib.SMTP(via["host"], int(via.get("port") or 587), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(via.get("username", ""), via["password"])
            message = EmailMessage()
            message["From"] = formataddr((settings.org_name, sender))
            message["To"] = to
            message["Subject"] = subject
            message["Message-ID"] = make_msgid(domain=sender.rpartition("@")[2] or None)
            message.set_content(text)
            smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError, ValueError) as e:
        log.error("Sign-in email to the company's relay failed (%s).", e.__class__.__name__)
        return False


# ---- Two-step sign-in (authenticator app) ---------------------------------------------------------

STEP = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def code_now(secret: str, at: float | None = None) -> str:
    return _code(secret, int((at if at is not None else time.time()) // STEP))


def code_ok(secret: str, code: str) -> bool:
    """The code for now, or the step before or after (a phone's clock a little off)."""
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != DIGITS:
        return False
    now = int(time.time() // STEP)
    return any(hmac.compare_digest(_code(secret, now + d), code) for d in (-1, 0, 1))


def sealed(settings: Settings, secret: str) -> str:
    return svc.seal(settings, {"totp": secret}) or ""


def unsealed(settings: Settings, value: str | None) -> str | None:
    found = svc.unseal(settings, value)
    return (found or {}).get("totp")


def setup_uri(account: Account, secret: str, issuer: str = "Bishnoi One") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account.email)}?secret={secret}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"


def qr_svg(uri: str) -> str:
    """The setup link as a QR code, an SVG data URL for an <img>."""
    import segno

    out = io.BytesIO()
    segno.make(uri, error="m").save(out, kind="svg", scale=5, border=2, dark="#1c2420")
    return "data:image/svg+xml;base64," + base64.b64encode(out.getvalue()).decode()


def new_recovery_codes() -> tuple[list[str], list[str]]:
    """Ten codes to show once, and their hashes to keep."""
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}".upper() for _ in range(10)]
    return codes, [token_hash(c) for c in codes]


def use_recovery_code(account: Account, code: str) -> bool:
    """A recovery code that hasn't been used yet: crossed off."""
    wanted = token_hash((code or "").strip().upper())
    left = list(account.recovery_codes or [])
    if wanted not in left:
        return False
    left.remove(wanted)
    account.recovery_codes = left
    return True


def two_step_on(account: Account) -> bool:
    return bool(account.two_step_on_at and account.two_step_secret)


def needs_two_step(settings: Settings, account: Account | None, runs: bool) -> bool:
    """Someone who must have two-step sign-in (a company administrator or an operator, where it's required) but hasn't."""
    return bool(settings.two_step_required and account is not None and (runs or account.is_operator) and not two_step_on(account))


def count_unused(db: Session, account_id: str, kind: str) -> int:
    return db.scalar(select(func.count()).select_from(SignInLink).where(SignInLink.account_id == account_id, SignInLink.kind == kind,
                                                                         SignInLink.used_at.is_(None), SignInLink.expires_at > datetime.now(UTC))) or 0
