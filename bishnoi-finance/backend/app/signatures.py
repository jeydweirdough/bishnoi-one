"""E-signatures (decided 2026-10-22: Plans/Plan - E-signatures).

- Each person sets their own on their account page, drawn or uploaded; the
  browser cleans it (paper made transparent, ink made black, trimmed) and only
  the cleaned PNG reaches here. Setting or removing it needs their password, or,
  for someone who signs in with Bishnoi One (no Finance password they know), a
  sign-in in the last few minutes.
- It's placed by the person's own step, never by anyone else: a journal entry
  prepared (typed by hand) or approved; a liquidation reviewed or settled. Each
  placing records who, which step, when, which signature, and a fingerprint
  (SHA-256) of the document's content then.
- A replaced or removed signature is kept: what it signed still shows it.
"""

import base64
import hashlib
import json
import struct
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FundRequest, JournalEntry, Signature, SignedStep, User

PNG = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 300_000
MAX_WIDTH, MAX_HEIGHT = 1200, 600
STEP_LABELS = {"prepared": "Prepared by", "approved": "Approved by", "reviewed": "Reviewed by", "settled": "Settled by"}


class BadImage(ValueError):
    """What's wrong with an image sent as a signature, in plain words."""


def checked_png(data_url_or_base64: str) -> bytes:
    """The PNG inside a data URL (or plain base64), if it's a sensible signature image."""
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


def current(db: Session, user_id: str) -> Signature | None:
    return db.scalar(
        select(Signature).where(Signature.user_id == user_id, Signature.replaced_at.is_(None)).order_by(Signature.created_at.desc())
    )


def retire(db: Session, user_id: str, removed_by: str | None = None) -> bool:
    """The person's signature stops being theirs (kept for what it signed)."""
    now, any_ = datetime.now(UTC), False
    for s in db.scalars(select(Signature).where(Signature.user_id == user_id, Signature.replaced_at.is_(None))):
        s.replaced_at, s.removed_by, any_ = now, removed_by, True
    return any_


def data_url(image: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(image).decode()


def fingerprint(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def journal_content(e: JournalEntry) -> dict:
    """What a journal entry says: what its signatures vouch for."""
    return {
        "number": e.number, "date": e.entry_date.isoformat(), "memo": e.memo, "reference": e.reference,
        "lines": [[ln.account.code, ln.debit_centavos, ln.credit_centavos, ln.description] for ln in e.lines],
    }


def fund_content(r: FundRequest) -> dict:
    """What a liquidation comes to: what the reviewer's and settler's signatures vouch for."""
    return {
        "number": r.number, "requester": r.requester_name, "released": r.released_centavos,
        "expenses": [[x.spent_on.isoformat(), x.description, x.amount_centavos, x.category.label if x.category else None, x.accepted] for x in r.expenses],
        "covered": r.covered_centavos, "returnDue": r.return_due_centavos, "returned": r.returned_centavos,
        "reimburseDue": r.reimburse_due_centavos, "reimbursed": r.reimbursed_centavos,
    }


def sign(db: Session, user: User, record_type: str, record_id: str, step: str, content: dict) -> SignedStep:
    """This person's step on this document, with their signature as it is now (none if unset)."""
    mine = current(db, user.id)
    signed = SignedStep(
        record_type=record_type, record_id=record_id, step=step, user_id=user.id, signature_id=mine.id if mine else None,
        signer_name=user.full_name[:120], signer_role=user.role.name[:80], fingerprint=fingerprint(content),
    )
    db.add(signed)
    return signed


def steps_out(db: Session, record_type: str, record_id: str) -> list[dict]:
    """A document's signed steps, oldest first, each with the signature it was signed with."""
    rows = db.scalars(
        select(SignedStep).where(SignedStep.record_type == record_type, SignedStep.record_id == record_id).order_by(SignedStep.signed_at, SignedStep.id)
    ).all()
    images = {s.id: s.image for s in db.scalars(select(Signature).where(Signature.id.in_({r.signature_id for r in rows if r.signature_id})))}
    return [
        {
            "step": r.step, "label": STEP_LABELS.get(r.step, r.step), "name": r.signer_name, "role": r.signer_role,
            "at": (r.signed_at if r.signed_at.tzinfo else r.signed_at.replace(tzinfo=UTC)).isoformat(),
            "image": data_url(images[r.signature_id]) if r.signature_id in images else None,
            "ref": r.fingerprint[:12],
        }
        for r in rows
    ]
