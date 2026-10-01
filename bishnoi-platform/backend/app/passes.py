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
             "email", "name", "company", "companyName", "role", "appAdmin",
             "companyAdmin", "iat", "exp", "jti"}
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


def issue(settings: Settings, identity: Identity, company: Company, app: Application, grant: IdentityApp) -> str:
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": key_id(settings)}
    claims = {
        "iss": ISSUER,
        "aud": app.key,
        "sub": identity.id,
        "email": identity.email,
        "name": identity.full_name,
        "company": company.id,
        "companyName": company.name,
        "role": grant.role,
        "appAdmin": grant.is_app_admin,
        "companyAdmin": identity.is_company_admin,
        "iat": now,
        "exp": now + LIFETIME,
        "jti": secrets.token_urlsafe(18),
    }
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    signature = signing_key(settings).sign(signing_input.encode())
    return f"{signing_input}.{b64url(signature)}"


if __name__ == "__main__":
    key = new_signing_key()
    pub = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key)).public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    print("PASS_SIGNING_KEY (the platform's API only; keep it secret):")
    print(f"  {key}")
    print("PLATFORM_PUBLIC_KEY (each application; not secret):")
    print(f"  {base64.b64encode(pub).decode()}")
