"""One e-signature per person (feature plan step 10, 2026-10-29), kept on their Bishnoi One account.

- Set on their profile in the Admin Console, drawn or uploaded; the browser cleans it (paper made
  transparent, ink made black, trimmed) and only the cleaned PNG reaches here. Setting or removing
  it takes their password.
- A replaced or removed signature is kept (replaced_at), so documents already signed with it still
  show it.
- Every app asks for the person's current one when they sign a step (GET /connect/signature, with
  its connect key) and keeps its own copy with what was signed, so a later change never changes a
  signed document.
- The same rules as Finance's own signatures (decided 2026-10-22), which they replace over time.
"""

import base64
import hashlib
import struct
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountSignature

PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 300_000
MAX_WIDTH, MAX_HEIGHT = 1200, 600


class BadImage(ValueError):
    """What's wrong with an image sent as a signature, in plain words."""


def checked_png(data_url_or_base64: str) -> bytes:
    raw = data_url_or_base64.split(",", 1)[1] if data_url_or_base64.startswith("data:") else data_url_or_base64
    try:
        image = base64.b64decode(raw, validate=True)
    except ValueError:
        raise BadImage("That isn't an image.") from None
    if len(image) > MAX_BYTES:
        raise BadImage("The signature is too large. Try again with a smaller or cleaner picture.")
    if not image.startswith(PNG) or image[12:16] != b"IHDR":
        raise BadImage("The signature must be a PNG image.")
    width, height = struct.unpack(">II", image[16:24])
    if not (10 <= width <= MAX_WIDTH and 10 <= height <= MAX_HEIGHT):
        raise BadImage("The signature's size doesn't look right. Draw or upload it again.")
    return image


def current(db: Session, account_id: str) -> AccountSignature | None:
    return db.scalar(select(AccountSignature).where(AccountSignature.account_id == account_id, AccountSignature.replaced_at.is_(None))
                     .order_by(AccountSignature.created_at.desc()))


def retire(db: Session, account_id: str) -> bool:
    now, any_ = datetime.now(UTC), False
    for s in db.scalars(select(AccountSignature).where(AccountSignature.account_id == account_id, AccountSignature.replaced_at.is_(None))):
        s.replaced_at, any_ = now, True
    return any_


def keep(db: Session, account_id: str, image: bytes, method: str) -> AccountSignature:
    retire(db, account_id)
    s = AccountSignature(account_id=account_id, image=image, method=method, sha256=hashlib.sha256(image).hexdigest(), created_at=datetime.now(UTC))
    db.add(s)
    return s


def data_url(image: bytes, kind: str = "image/png") -> str:
    return f"data:{kind};base64," + base64.b64encode(image).decode()
