"""Passes: how a Bishnoi One account gets into an application.

Someone signs in once, here, with their Bishnoi One account. To open an application
the platform gives them a pass: a short note, signed with the platform's
private key, saying who they are, which company, which application and their
role there. The application checks the signature with the platform's public
key (it holds nothing else), takes the pass once, and opens its own session.

A pass is only given for an application the person has been granted, at a
company that has the application and isn't suspended. It lasts two minutes and
works once: it is for the trip from here to the application, nothing more.

The format is a compact JWS (a JWT) signed with Ed25519 ("EdDSA"):
    header  {"alg": "EdDSA", "typ": "JWT", "kid": <key id>}
    claims  {"iss": "bishnoi-platform", "aud": <app key>, "sub": <identity id>,
             "email", "name", "company", "companySlug", "companyName", "role", "appAdmin",
             "companyAdmin", "iat", "exp", "jti", and "roleDef" when they have a role here}
"""

import base64
import hashlib
import json
import secrets
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import DATA_DIR, Settings
from app.models import Application, Company, Identity, IdentityApp

ISSUER = "bishnoi-platform"
LIFETIME = 120  # seconds
KEY_FILE = DATA_DIR / "pass-signing.key"


class PassUnavailable(Exception):
    """The platform can't sign passes (no key set in production)."""


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _raw_private(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())


def new_signing_key() -> str:
    """A new private key, as PASS_SIGNING_KEY takes it (base64 of 32 bytes)."""
    return base64.b64encode(_raw_private(Ed25519PrivateKey.generate())).decode()


KEPT_AS = "signing_key"  # its row in nbpl_settings: never one of Settings' sections, so never shown


def keep_in_database(sessions, settings: Settings) -> None:
    """Production without PASS_SIGNING_KEY (decided 2026-10-27): the key is made
    on the first start and kept in this database, so there's no key to make by
    hand. Whoever has a copy of this database can sign passes, so its backups
    are kept as safely as the server's settings. PASS_SIGNING_KEY still wins."""
    from pydantic import SecretStr
    from sqlalchemy.exc import IntegrityError

    from app.models import PlatformSetting

    if settings.pass_signing_key is not None or not settings.is_production:
        return
    with sessions() as db:
        row = db.get(PlatformSetting, KEPT_AS)
        if row is None:
            db.add(PlatformSetting(key=KEPT_AS, value={"key": new_signing_key()}, updated_by="first start"))
            try:
                db.commit()
            except IntegrityError:  # another server made it at the same moment: theirs stands
                db.rollback()
            row = db.get(PlatformSetting, KEPT_AS)
        settings.pass_signing_key = SecretStr(row.value["key"])


def signing_key(settings: Settings) -> Ed25519PrivateKey:
    if settings.pass_signing_key is not None:
        raw = base64.b64decode(settings.pass_signing_key.get_secret_value().strip())
        return Ed25519PrivateKey.from_private_bytes(raw)
    if settings.environment == "production":
        raise PassUnavailable("PASS_SIGNING_KEY isn't set. Make one with: python -m app.passes")
    # Development: one key, kept beside the local database.
    if KEY_FILE.exists():
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(KEY_FILE.read_text().strip()))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    text = new_signing_key()
    KEY_FILE.write_text(text)
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(text))


def public_key(settings: Settings) -> str:
    """The public half, as each application's PLATFORM_PUBLIC_KEY takes it (base64 of 32 bytes)."""
    raw = signing_key(settings).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def key_id(settings: Settings) -> str:
    return hashlib.sha256(base64.b64decode(public_key(settings))).hexdigest()[:12]


def sign(settings: Settings, claims: dict) -> str:
    """Claims, signed with the platform's key, as a compact JWS."""
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id(settings)}
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    return f"{signing_input}.{b64url(signing_key(settings).sign(signing_input.encode()))}"


def issue(settings: Settings, identity: Identity, company: Company, app: Application, grant: IdentityApp, role: dict | None = None, org: dict | None = None,
          company_admin: bool | None = None) -> str:
    """`role`: their one role at the company, as this application keeps it
    (app/access_roles.py spec); without one, the role on their grant. `org`: where they
    sit on the company's org chart (app/org_push.py placement), when they're placed."""
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id(settings)}
    claims = {
        "iss": ISSUER,
        "aud": app.key,
        "sub": identity.id,
        "email": identity.email,
        "name": identity.full_name,
        "company": company.id,
        "companySlug": company.slug,
        "companyName": company.name,
        "role": role["name"] if role else grant.role,
        "appAdmin": grant.is_app_admin or bool(role and role.get("admin")),
        "companyAdmin": identity.is_company_admin if company_admin is None else company_admin,
        "iat": now,
        "exp": now + LIFETIME,
        "jti": secrets.token_urlsafe(18),
    }
    if org:
        claims["org"] = org
    if role:
        # The role itself, so the application keeps it as the platform has it before matching it by name.
        claims["roleDef"] = role
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    signature = signing_key(settings).sign(signing_input.encode())
    return f"{signing_input}.{b64url(signature)}"


# A company pass: how an application knows its company is registered here.
# Kept by the application for its whole life, renewed by it every hour, and
# sent to it fresh the moment the company changes (app/company_push.py).
COMPANY_LIFETIME = 30 * 24 * 3600  # seconds


def company_pass(settings: Settings, company: Company | None, app: Application, granted: bool, gone: dict | None = None, features: dict | None = None) -> str:
    """Signed: this company, its status, and whether it may use this application.
    The application checks it with the platform's public key, as a sign-in pass.
    `gone` ({"id", "slug", "name"}): the company has been deleted."""
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id(settings)}
    who = {"company": gone["id"], "slug": gone["slug"], "companyName": gone["name"], "status": "deleted"} if gone else {
        "company": company.id, "slug": company.slug, "companyName": company.name, "status": company.status}
    claims = {
        "iss": ISSUER,
        "aud": app.key,
        "kind": "company",
        **who,
        "granted": granted and not gone,
        # Its catalogue apps and features, on or off (step 6): the application hides what's off.
        **({"features": features} if features is not None else {}),
        "iat": now,
        "exp": now + COMPANY_LIFETIME,
        "jti": secrets.token_urlsafe(12),
    }
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    return f"{signing_input}.{b64url(signing_key(settings).sign(signing_input.encode()))}"


def claims_of(token: str) -> dict:
    """What a pass made here says (to record it; not a check)."""
    body = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


# A connect pass: an application's connect key, delivered to the address
# registered for it (app/links.py deliver), so nobody copies it onto a server.
CONNECT_LIFETIME = 120  # seconds


def connect_pass(settings: Settings, app: Application, key: str) -> str:
    """Signed: this application's connect key. The application checks it with
    the platform's public key, as a sign-in pass, then keeps the key."""
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id(settings)}
    claims = {"iss": ISSUER, "aud": app.key, "kind": "connect", "key": key, "iat": now, "exp": now + CONNECT_LIFETIME, "jti": secrets.token_urlsafe(18)}
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    return f"{signing_input}.{b64url(signing_key(settings).sign(signing_input.encode()))}"


if __name__ == "__main__":
    key = new_signing_key()
    pub = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key)).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    print("PASS_SIGNING_KEY (the platform's API only; keep it secret):")
    print(f"  {key}")
    print("PLATFORM_PUBLIC_KEY (each application; not secret):")
    print(f"  {base64.b64encode(pub).decode()}")
