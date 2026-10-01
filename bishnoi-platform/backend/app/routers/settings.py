"""Platform settings: four sections (app/platform_settings.py). Anyone
signed in reads them; a Platform Admin changes them."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import ValidationError

from app import platform_settings
from app.api import camel, not_found
from app.audit import audit
from app.deps import DB, AdminUser, CurrentUser, SettingsDep
from app.models import PlatformSetting

router = APIRouter(prefix="/platform/settings", tags=["settings"])


def _all(db, settings) -> dict:
    return {key: platform_settings.read(db, key, settings).model_dump(by_alias=True) for key in platform_settings.SECTIONS}


@router.get("")
def read_settings(db: DB, settings: SettingsDep, _: CurrentUser) -> dict:
    return {"settings": _all(db, settings)}


@router.put("/{section}")
def save_section(section: str, body: dict, db: DB, settings: SettingsDep, me: AdminUser) -> dict:
    model = platform_settings.SECTIONS.get(section)
    if model is None:
        raise not_found("settings section")
    before = platform_settings.read(db, section, settings).model_dump()
    try:
        value = model.model_validate(body).model_dump()
    except ValidationError as error:
        from fastapi.exceptions import RequestValidationError

        raise RequestValidationError([{**e, "loc": ("body", *e["loc"])} for e in error.errors(include_url=False)]) from None
    row = db.get(PlatformSetting, section)
    if row is None:
        row = PlatformSetting(key=section)
        db.add(row)
    row.value = value
    row.updated_at = datetime.now(UTC)
    row.updated_by = me.email
    fields = [k for k in value if value[k] != before.get(k)]
    audit(db, me, f"settings.{section}", category="security" if section == "security" else "admin", target=section.capitalize(),
          target_type="settings", fields=camel(fields))
    db.commit()
    return {"settings": _all(db, settings)}
