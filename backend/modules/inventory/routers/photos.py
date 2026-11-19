"""Photos, optional, on a delivery and on its packages (2026-11-18, owner's Step 4B): the goods, the proof of
delivery, a box. Never required. The courier's proof-of-delivery photo (routers/shipping.py) stays as it was.

    GET    /inventory/photos?targetType=delivery|package&targetId=   the photos of one, oldest first
    POST   /inventory/photos                                         multipart: file, targetType, targetId
    GET    /inventory/photos/{id}                                    the image
    DELETE /inventory/photos/{id}                                    the person who took it, or orders.edit

Seeing them needs orders.view; adding orders.edit or orders.issue. The screens shrink a photo before sending it
(about 1600 px, JPEG), so 3 MB is plenty.
"""

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select

from modules.inventory.access import CurrentAccess, allowed
from modules.inventory.api import conflict, found, iso
from modules.inventory.audit import audit
from modules.inventory.deps import DB, CurrentUser
from modules.inventory.models import Order, Package, Photo
from modules.inventory.out import person

router = APIRouter(prefix="/inventory", tags=["photos"])

Target = Literal["delivery", "package"]
TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MAX_BYTES = 3_000_000
PER_TARGET = 10


def kind_of(data: bytes) -> str | None:
    """PNG, JPEG or WebP, by the file's first bytes (never by what the browser says it is)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return next((k for head, k in TYPES.items() if data.startswith(head)), None)


def target_of(db: DB, target_type: str, target_id: str) -> tuple[Order, str]:
    """The delivery the photo belongs to (a package's own delivery), and a label for the log."""
    if target_type == "package":
        p = found(db, Package, target_id, "package")
        o = found(db, Order, p.order_id, "order")
        return o, f"{o.number} · {p.number}"
    o = found(db, Order, target_id, "order")
    return o, o.number


def may_remove(access, photo: Photo) -> bool:
    return photo.taken_by_id == access.user.id or access.can("orders.edit")


def photo_out(photo: Photo, access) -> dict:
    return {"id": photo.id, "targetType": photo.target_type, "targetId": photo.target_id, "contentType": photo.content_type,
            "size": photo.size, "href": f"/inventory/photos/{photo.id}", "takenBy": person(photo.taken_by),
            "createdAt": iso(photo.created_at), "canRemove": may_remove(access, photo)}


def photos_of(db: DB, target_type: str, target_ids: list[str]) -> dict[str, list[Photo]]:
    out: dict[str, list[Photo]] = {i: [] for i in target_ids}
    if target_ids:
        for p in db.scalars(select(Photo).where(Photo.target_type == target_type, Photo.target_id.in_(target_ids)).order_by(Photo.created_at)):
            out[p.target_id].append(p)
    return out


def drop_photos(db: DB, target_type: str, target_id: str) -> None:
    """A package unpacked: its photos go with it."""
    for p in db.scalars(select(Photo).where(Photo.target_type == target_type, Photo.target_id == target_id)):
        db.delete(p)


@router.get("/photos")
def list_photos(access: allowed("orders.view"), db: DB, target_type: Target = Query(alias="targetType"),
                target_id: str = Query(alias="targetId", max_length=36)) -> list[dict]:
    target_of(db, target_type, target_id)
    return [photo_out(p, access) for p in photos_of(db, target_type, [target_id])[target_id]]


@router.post("/photos", status_code=status.HTTP_201_CREATED)
async def add_photo(access: CurrentAccess, me: CurrentUser, db: DB, file: UploadFile = File(...),
                    target_type: Target = Form(alias="targetType"), target_id: str = Form(alias="targetId", max_length=36)) -> dict:
    if not (access.can("orders.edit") or access.can("orders.issue")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")
    o, label = target_of(db, target_type, target_id)
    if o.status == "cancelled":
        raise conflict("This delivery is cancelled: no photos are added to it.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The photo is too large: keep it under 3 MB.")
    kind = kind_of(data)
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The photo must be a PNG, JPEG or WebP image.")
    if len(photos_of(db, target_type, [target_id])[target_id]) >= PER_TARGET:
        raise conflict(f"{PER_TARGET} photos at most here. Remove one first.")
    photo = Photo(target_type=target_type, target_id=target_id, content_type=kind, data=data, size=len(data), taken_by_id=me.id)
    db.add(photo)
    db.flush()
    audit(db, me, "order.photo_added", target=label, target_type="order", target_id=o.id)
    db.commit()
    db.refresh(photo)
    return photo_out(photo, access)


@router.get("/photos/{photo_id}")
def get_photo(_: allowed("orders.view"), db: DB, photo_id: str) -> Response:
    photo = found(db, Photo, photo_id, "photo")
    return Response(photo.data, media_type=photo.content_type,
                    headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(access: allowed("orders.view"), me: CurrentUser, db: DB, photo_id: str) -> Response:
    photo = found(db, Photo, photo_id, "photo")
    if not may_remove(access, photo):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who added it, or someone who edits deliveries, removes a photo.")
    try:
        o, label = target_of(db, photo.target_type, photo.target_id)
        audit(db, me, "order.photo_removed", target=label, target_type="order", target_id=o.id)
    except HTTPException:  # what it showed is gone already
        audit(db, me, "order.photo_removed", target=photo.target_id, target_type="order", target_id=photo.target_id)
    db.delete(photo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
