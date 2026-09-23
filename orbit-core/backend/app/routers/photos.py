"""Profile pictures: the person's own, the admin's copy of it, and serving them.

A picture belongs to the person, not to a company, so someone in two companies
looks the same in both. That is also why an admin may only change the picture of
someone who works for their company alone, exactly as with a name or password.
Everyone in a company can see their colleagues' pictures; nobody else can.
"""

import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import works_elsewhere
from app.audit import audit
from app.deps import DB, CurrentUser, as_utc, require_settings
from app.errors import conflict, field_errors
from app.models import Membership, Profile, ProfilePhoto, utcnow
from app.photos import CONTENT_TYPE, MAX_UPLOAD_BYTES, PhotoError, square_photo

router = APIRouter(tags=["people"])

PHOTO_FIELD = ("photo",)


def photo_of(db: Session, user_id: str) -> ProfilePhoto | None:
    return db.get(ProfilePhoto, user_id)


def when(moment) -> str:
    """One shape for every timestamp: SQLite hands back naive datetimes, Postgres aware ones."""
    return as_utc(moment).isoformat()


def photo_times(db: Session, user_ids: list[str]) -> dict[str, str]:
    """When each person's picture last changed, for the screens that show them."""
    if not user_ids:
        return {}
    rows = db.execute(select(ProfilePhoto.user_id, ProfilePhoto.updated_at).where(ProfilePhoto.user_id.in_(user_ids)))
    return {user_id: when(at) for user_id, at in rows}


def save_photo(db: Session, user_id: str, data: bytes) -> ProfilePhoto:
    try:
        picture = square_photo(data)
    except PhotoError as exc:
        raise field_errors([(PHOTO_FIELD, str(exc))]) from exc
    row = photo_of(db, user_id)
    if row is None:
        row = ProfilePhoto(user_id=user_id, content_type=CONTENT_TYPE, data=picture)
        db.add(row)
    else:
        row.content_type, row.data, row.updated_at = CONTENT_TYPE, picture, utcnow()
    db.commit()
    return row


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise field_errors([(PHOTO_FIELD, f"That picture is over {MAX_UPLOAD_BYTES // (1024 * 1024)}MB. Try a smaller one.")])
    return data


def colleague(db: Session, user_id: str) -> Profile:
    """Someone in the caller's company. The company wall keeps everyone else out."""
    person = db.scalar(select(Profile).join(Membership, Membership.user_id == Profile.id).where(Profile.id == user_id))
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such person.")
    return person


def picture_response(request: Request, row: ProfilePhoto | None) -> Response:
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No picture.")
    tag = f'"{hashlib.sha256(row.data).hexdigest()[:32]}"'
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": tag})
    return Response(
        content=row.data,
        media_type=row.content_type,
        headers={
            "ETag": tag,
            # A colleague's picture is theirs, not the internet's.
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- everyone's own picture -------------------------------------------------------------


@router.put("/me/photo")
async def set_my_photo(user: CurrentUser, db: DB, photo: Annotated[UploadFile, File()]) -> dict:
    row = save_photo(db, user.id, await read_upload(photo))
    audit(db, user, "person.photo_changed", user.email)
    return {"photoAt": when(row.updated_at)}


@router.delete("/me/photo", status_code=status.HTTP_204_NO_CONTENT)
def remove_my_photo(user: CurrentUser, db: DB) -> Response:
    row = photo_of(db, user.id)
    if row is not None:
        db.delete(row)
        db.commit()
        audit(db, user, "person.photo_removed", user.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- looking at a colleague's ------------------------------------------------------------


@router.get("/people/{user_id}/photo")
def person_photo(user_id: str, request: Request, _user: CurrentUser, db: DB) -> Response:
    colleague(db, user_id)
    return picture_response(request, photo_of(db, user_id))


# --- an admin, for their company's people -----------------------------------------------


admin = APIRouter(prefix="/admin", tags=["settings"], dependencies=[Depends(require_settings)])


def only_ours(db: Session, user_id: str) -> Profile:
    person = colleague(db, user_id)
    if works_elsewhere(db, person.id):
        raise conflict("This person also works in another company, so only they can change their picture.")
    return person


@admin.put("/users/{user_id}/photo")
async def set_person_photo(user_id: str, me: CurrentUser, db: DB, photo: Annotated[UploadFile, File()]) -> dict:
    person = only_ours(db, user_id)
    row = save_photo(db, person.id, await read_upload(photo))
    audit(db, me, "person.photo_changed", person.email)
    return {"photoAt": when(row.updated_at)}


@admin.delete("/users/{user_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def remove_person_photo(user_id: str, me: CurrentUser, db: DB) -> Response:
    person = only_ours(db, user_id)
    row = photo_of(db, person.id)
    if row is not None:
        db.delete(row)
        db.commit()
        audit(db, me, "person.photo_removed", person.email)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
