"""Media: approved presentations, PDFs and videos that reps show customers.

Administrators (admin.settings) add them: a file kept here (up to 4 MB, what
the screens can send up), or a link to one kept elsewhere (a shared drive,
for big decks and videos). Each has an approval date and, if it has one, an
expiry: before and after, it isn't shown. It can be for some divisions only.

Everyone else sees what's current for their division, and each opening is
counted, with the customer when opened from their page.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import quote as url_quote

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import Field, field_validator
from sqlalchemy import func, select

from app.access import Access, CurrentAccess, require
from app.api import Api, changed, field_error, iso, not_found
from app.audit import audit
from app.deps import DB, CurrentUser, SettingsDep
from app.models import Company, MediaItem, MediaView, Product, StoredFile, Team, User
from app.pricing import today
from app.scope import reaches

router = APIRouter(tags=["media"])
Manage = Annotated[Access, Depends(require("admin.settings"))]

MAX_BYTES = 4 * 1024 * 1024
KINDS = {
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx (a zip)
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def current(item: MediaItem, on: str) -> bool:
    return item.is_active and item.approved_on <= on and (not item.expires_on or item.expires_on >= on)


def for_them(item: MediaItem, team_id: str | None) -> bool:
    return not item.only_teams or team_id in item.only_teams


def media_out(db, item: MediaItem, on: str, *, admin: bool) -> dict:
    names = dict(db.execute(select(Product.code, Product.name).where(Product.code.in_(item.products or []))).all()) if item.products else {}
    out = {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "kind": "file" if item.file_ref else "link",
        "fileName": item.file_name,
        "products": [{"code": c, "name": names.get(c, c)} for c in item.products or []],
        "onlyTeams": item.only_teams or [],
        "approvedOn": item.approved_on,
        "expiresOn": item.expires_on,
        "isActive": item.is_active,
        "isCurrent": current(item, on),
    }
    if admin:
        since = datetime.now(UTC) - timedelta(days=30)
        out["opened30d"] = db.scalar(select(func.count()).select_from(MediaView).where(MediaView.media_id == item.id, MediaView.at >= since)) or 0
        out["url"] = item.url
    return out


@router.get("/media")
def list_media(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, product: str | None = Query(None, max_length=40), everything: bool = Query(False, alias="all")) -> dict:
    """What's current for this person's division; with `all`, an administrator sees every one."""
    on = today(settings.org_timezone)
    admin = access.can("admin.settings")
    items = db.scalars(select(MediaItem).order_by(MediaItem.title)).all()
    if not (everything and admin):
        items = [m for m in items if current(m, on) and for_them(m, me.team_id)]
    if product:
        items = [m for m in items if product in (m.products or [])]
    return {"items": [media_out(db, m, on, admin=admin) for m in items], "canManage": admin}


def get_media(db, item_id: str) -> MediaItem:
    item = db.get(MediaItem, item_id)
    if item is None:
        raise not_found("material")
    return item


class OpenIn(Api):
    company_id: str | None = Field(None, max_length=36)


@router.post("/media/{item_id}/opened")
def opened(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, item_id: str, body: OpenIn) -> dict:
    """Counts an opening (for a customer, when opened from their page); answers where it is."""
    item = get_media(db, item_id)
    if not access.can("admin.settings") and not (current(item, today(settings.org_timezone)) and for_them(item, me.team_id)):
        raise not_found("material")
    company = db.get(Company, body.company_id) if body.company_id else None
    db.add(MediaView(media_id=item.id, user_id=me.id, company_id=company.id if company and reaches(company, access) else None))
    db.commit()
    return {"url": item.url, "file": bool(item.file_ref)}


@router.get("/media/{item_id}/file")
def read_file(access: CurrentAccess, me: CurrentUser, db: DB, settings: SettingsDep, item_id: str) -> Response:
    item = get_media(db, item_id)
    if not access.can("admin.settings") and not (current(item, today(settings.org_timezone)) and for_them(item, me.team_id)):
        raise not_found("material")
    stored = db.get(StoredFile, item.file_ref) if item.file_ref else None
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This material is a link, not a file.")
    return Response(stored.data, media_type=stored.content_type, headers={"Content-Disposition": f"inline; filename*=utf-8''{url_quote(item.file_name or 'material')}"})


# --- managing them -------------------------------------------------------------------------


class MediaFields(Api):
    title: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = Field(None, max_length=500)
    url: str | None = Field(None, max_length=1000)
    products: list[Annotated[str, Field(max_length=40)]] | None = Field(None, max_length=50)
    only_teams: list[Annotated[str, Field(max_length=36)]] | None = Field(None, max_length=50)
    approved_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    expires_on: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("A link starts with https://.")
        return value or None


class MediaIn(MediaFields):
    title: str = Field(min_length=1, max_length=160)
    approved_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


def check(db, wanted: dict) -> None:
    if wanted.get("products"):
        known = set(db.scalars(select(Product.code).where(Product.code.in_(wanted["products"]))))
        if any(c not in known for c in wanted["products"]):
            raise field_error("products", "Pick products from the catalogue.")
    if wanted.get("only_teams"):
        known = set(db.scalars(select(Team.id)))
        if any(t not in known for t in wanted["only_teams"]):
            raise field_error("onlyTeams", "Pick teams from the list.")


@router.post("/admin/media", status_code=status.HTTP_201_CREATED)
def add_media(_: Manage, me: CurrentUser, db: DB, settings: SettingsDep, body: MediaIn) -> dict:
    values = body.model_dump(exclude_none=True)
    check(db, values)
    if values.get("expires_on") and values["expires_on"] < values["approved_on"]:
        raise field_error("expiresOn", "It expires before it's approved.")
    item = MediaItem(**values, created_by_id=me.id)
    db.add(item)
    db.flush()
    audit(db, me, "media.added", target=item.title, target_type="media", target_id=item.id)
    db.commit()
    return media_out(db, item, today(settings.org_timezone), admin=True)


@router.patch("/admin/media/{item_id}")
def change_media(_: Manage, me: CurrentUser, db: DB, settings: SettingsDep, item_id: str, body: MediaFields) -> dict:
    item = get_media(db, item_id)
    wanted = changed(body)
    if "title" in wanted and not wanted["title"]:
        raise field_error("title", "Give it a title.")
    if "approved_on" in wanted and not wanted["approved_on"]:
        raise field_error("approvedOn", "Say when it was approved.")
    check(db, wanted)
    fields = [k for k, v in wanted.items() if getattr(item, k) != v]
    for k in fields:
        setattr(item, k, wanted[k] if wanted[k] is not None or k in ("description", "url", "expires_on") else getattr(item, k))
    if item.expires_on and item.expires_on < item.approved_on:
        raise field_error("expiresOn", "It expires before it's approved.")
    if fields:
        audit(db, me, "media.changed", target=item.title, target_type="media", target_id=item.id, fields=fields)
        db.commit()
    return media_out(db, item, today(settings.org_timezone), admin=True)


@router.put("/admin/media/{item_id}/file")
async def upload_file(_: Manage, me: CurrentUser, db: DB, settings: SettingsDep, item_id: str, file: Annotated[UploadFile, File()]) -> dict:
    item = get_media(db, item_id)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise field_error("file", "The file is over 4 MB. Put it on the shared drive and add it as a link instead.")
    kind = next((v for magic, v in KINDS.items() if data.startswith(magic)), None)
    if kind is None:
        raise field_error("file", "Add a PDF, a PowerPoint (.pptx) or a picture (PNG or JPG).")
    if item.file_ref:
        old = db.get(StoredFile, item.file_ref)
        if old is not None:
            db.delete(old)
    ref = secrets.token_hex(16)
    db.add(StoredFile(ref=ref, content_type=kind, data=data))
    item.file_ref, item.file_name, item.url = ref, (file.filename or "material")[:200], None
    audit(db, me, "media.changed", target=item.title, target_type="media", target_id=item.id, fields=["file"])
    db.commit()
    return media_out(db, item, today(settings.org_timezone), admin=True)


@router.delete("/admin/media/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(_: Manage, me: CurrentUser, db: DB, item_id: str) -> Response:
    item = get_media(db, item_id)
    if item.file_ref and (stored := db.get(StoredFile, item.file_ref)) is not None:
        db.delete(stored)
    audit(db, me, "media.deleted", target=item.title, target_type="media", target_id=item.id)
    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
