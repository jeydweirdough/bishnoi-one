"""Signing in with a Bishnoi One account: checking the pass the platform gives.

The platform (bishnoi-platform, app/passes.py) signs a two-minute pass saying who
the person is, their company, this application, and their role here. This
application holds only the platform's public key (PLATFORM_PUBLIC_KEY), so it
can check a pass but never make one. A pass is taken once: its id is kept until
it would have expired anyway.

This file is the same in every Bishnoi One application; only the app's key differs.
"""

import base64
import json
import time
from datetime import UTC, datetime, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ISSUER = "bishnoi-platform"
LEEWAY = 30  # seconds of clock difference allowed between the platform and this PC


class PassRefused(Exception):
    """Why a pass can't be taken, in words for the person."""


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def check(token: str, public_key: str | None, app_key: str, now: float | None = None) -> dict:
    """The pass's claims, once its signature, issuer, application and time are right."""
    if not public_key:
        raise PassRefused("Signing in with a Bishnoi One account isn't set up for this application.")
    now = time.time() if now is None else now
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        head = json.loads(_b64(head_b64))
        body = json.loads(_b64(body_b64))
        if head.get("alg") != "EdDSA":
            raise ValueError("alg")
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key)).verify(_b64(sig_b64), f"{head_b64}.{body_b64}".encode())
    except (ValueError, InvalidSignature, json.JSONDecodeError, TypeError):
        raise PassRefused("This sign-in link isn't valid. Sign in again from the start.") from None
    if body.get("iss") != ISSUER or body.get("aud") != app_key:
        raise PassRefused("This sign-in link is for another application. Sign in again from the start.")
    if not isinstance(body.get("exp"), int) or body["exp"] + LEEWAY < now:
        raise PassRefused("This sign-in link has expired. Sign in again from the start.")
    if not body.get("sub") or not body.get("email") or not body.get("jti"):
        raise PassRefused("This sign-in link isn't valid. Sign in again from the start.")
    return body


def expires(claims: dict) -> datetime:
    return datetime.fromtimestamp(claims["exp"], UTC) + timedelta(seconds=LEEWAY)
