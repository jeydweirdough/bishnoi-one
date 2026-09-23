"""The keys sign-in tokens are signed with (Ed25519).

Orbit signs with its private key and publishes the public half at
/.well-known/jwks.json, so the Orders app (or any other) can check a token
without holding a secret that could also make one. Each key has an id (`kid`,
its RFC 7638 thumbprint) that goes in the token's header.

To change keys: make a new one (`uv run python -m app.tools.keys`), set it as
JWT_PRIVATE_KEY, and move the old key's public half into
JWT_PREVIOUS_PUBLIC_KEYS until the tokens it signed have expired.
"""

import base64
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALGORITHM = "EdDSA"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _pem(text: str) -> bytes:
    # .env files often hold a PEM on one line with its line breaks written as \n.
    return text.strip().replace("\\n", "\n").encode()


def raw_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(key: Ed25519PublicKey) -> str:
    """RFC 7638 thumbprint: the same key always gets the same id, anywhere."""
    canonical = json.dumps({"crv": "Ed25519", "kty": "OKP", "x": _b64(raw_public(key))}, separators=(",", ":"), sort_keys=True)
    return _b64(hashlib.sha256(canonical.encode()).digest())


def new_private_pem() -> str:
    key = Ed25519PrivateKey.generate()
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()


def public_pem(private_pem: str) -> str:
    key = serialization.load_pem_private_key(_pem(private_pem), password=None)
    return key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


@dataclass
class SigningKeys:
    private: Ed25519PrivateKey
    kid: str
    public: dict[str, Ed25519PublicKey] = field(default_factory=dict)

    @classmethod
    def load(cls, private_pem: str, previous_public_pems: list[str] = ()) -> "SigningKeys":
        private = serialization.load_pem_private_key(_pem(private_pem), password=None)
        if not isinstance(private, Ed25519PrivateKey):
            raise ValueError("JWT_PRIVATE_KEY must be an Ed25519 private key (make one: uv run python -m app.tools.keys).")
        public = {key_id(private.public_key()): private.public_key()}
        for text in previous_public_pems:
            key = serialization.load_pem_public_key(_pem(text))
            if not isinstance(key, Ed25519PublicKey):
                raise ValueError("JWT_PREVIOUS_PUBLIC_KEYS must hold Ed25519 public keys.")
            public.setdefault(key_id(key), key)
        return cls(private, key_id(private.public_key()), public)

    @classmethod
    def for_development(cls, path: Path) -> "SigningKeys":
        """A key kept on this machine, made the first time it's needed."""
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(new_private_pem(), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, path)
        return cls.load(path.read_text(encoding="utf-8"))

    def jwks(self) -> dict:
        return {
            "keys": [
                {"kty": "OKP", "crv": "Ed25519", "x": _b64(raw_public(key)), "kid": kid, "alg": ALGORITHM, "use": "sig"}
                for kid, key in self.public.items()
            ]
        }
