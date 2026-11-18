"""Photos, optional, on a visit (2026-11-18, owner's Step 4B): the clinic, a display, a receipt. Never required.

    GET    /photos?targetType=visit&targetId=   a visit's photos, oldest first
    POST   /photos                              multipart: file, targetType, targetId
    GET    /photos/{id}                         the image
    DELETE /photos/{id}                         the person who took it, or visits.edit

Only for a visit within the person's reach: seeing needs visits.view, adding visits.create or visits.edit. The
screens shrink a photo before sending it (about 1600 px, JPEG), so 3 MB is plenty.
"""

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.crm.access import Access, CurrentAccess
from modules.crm.api import iso, not_found, person_out
from modules.crm.audit import audit
from modules.crm.deps import DB, CurrentUser
from modules.crm.models import Photo, Visit
from modules.crm.scope import reaches

router = APIRouter(tags=["photos"])

Target = Literal["visit"]
TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
MAX_BYTES = 3_000_000
PER_TARGET = 10


def kind_of(data: bytes) -> str | None:
    """PNG, JPEG or WebP, by the file's first bytes (never by what the browser says it is)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return next((k for head, k in TYPES.items() if data.startswith(head)), None)


def forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, "Your role doesn't allow that.")


def visit_of(db: Session, access: Access, visit_id: str) -> Visit:
    if not access.can("visits.view"):
        raise forbidden()
    visit = db.get(Visit, visit_id)
    if visit is None or not reaches(visit, access):
        raise not_found("visit")
    return visit


def may_remove(access: Access, photo: Photo) -> bool:
    return photo.taken_by_id == access.user_id or access.can("visits.edit")


def photo_out(photo: Photo, access: Access) -> dict:
    return {"id": photo.id, "targetType": photo.target_type, "targetId": photo.target_id, "contentType": photo.content_type,
            "size": photo.size, "href": f"/crm/photos/{photo.id}", "takenBy": person_out(photo.taken_by),
            "createdAt": iso(photo.created_at), "canRemove": may_remove(access, photo)}


def photos_of(db: Session, target_ids: list[str], access: Access) -> dict[str, list[dict]]:
    """Each visit's photos, in one read."""
    out: dict[str, list[dict]] = {i: [] for i in target_ids}
    if target_ids:
        for p in db.scalars(select(Photo).where(Photo.target_type == "visit", Photo.target_id.in_(target_ids)).order_by(Photo.created_at)):
            out[p.target_id].append(photo_out(p, access))
    return out


def drop_photos(db: Session, visit_id: str) -> None:
    for p in db.scalars(select(Photo).where(Photo.target_type == "visit", Photo.target_id == visit_id)):
        db.delete(p)


@router.get("/photos")
def list_photos(access: CurrentAccess, db: DB, target_type: Target = Query(alias="targetType"),
                target_id: str = Query(alias="targetId", max_length=36)) -> list[dict]:
    visit_of(db, access, target_id)
    return photos_of(db, [target_id], access)[target_id]


@router.post("/photos", status_code=status.HTTP_201_CREATED)
async def add_photo(access: CurrentAccess, me: CurrentUser, db: DB, file: UploadFile = File(...),
                    target_type: Target = Form(alias="targetType"), target_id: str = Form(alias="targetId", max_length=36)) -> dict:
    if not (access.can("visits.create") or access.can("visits.edit")):
        raise forbidden()
    visit = visit_of(db, access, target_id)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "The photo is too large: keep it under 3 MB.")
    kind = kind_of(data)
    if kind is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "The photo must be a PNG, JPEG or WebP image.")
    if len(photos_of(db, [visit.id], access)[visit.id]) >= PER_TARGET:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{PER_TARGET} photos at most on a visit. Remove one first.")
    photo = Photo(target_type=target_type, target_id=visit.id, content_type=kind, data=data, size=len(data), taken_by_id=me.id)
    db.add(photo)
    db.flush()
    audit(db, me, "visit.photo_added", target=visit.company.name, target_type="visit", target_id=visit.id)
    db.commit()
    db.refresh(photo)
    return photo_out(photo, access)


def _photo(db: Session, access: Access, photo_id: str) -> tuple[Photo, Visit]:
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise not_found("photo")
    return photo, visit_of(db, access, photo.target_id)


@router.get("/photos/{photo_id}")
def get_photo(access: CurrentAccess, db: DB, photo_id: str) -> Response:
    photo, _ = _photo(db, access, photo_id)
    return Response(photo.data, media_type=photo.content_type,
                    headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_photo(access: CurrentAccess, me: CurrentUser, db: DB, photo_id: str) -> Response:
    photo, visit = _photo(db, access, photo_id)
    if not may_remove(access, photo):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the person who added it, or someone who edits visits, removes a photo.")
    audit(db, me, "visit.photo_removed", target=visit.company.name, target_type="visit", target_id=visit.id)
    db.delete(photo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
