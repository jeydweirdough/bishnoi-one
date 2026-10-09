"""Settings → Connections: which outside services the CRM can use for this
company. They're connected on Bishnoi One Platform (Companies → the company →
Connections), not here: this only says which are on, and where to change them."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import connections as svc
from app.access import Access, require
from app.deps import SettingsDep

Manage = Annotated[Access, Depends(require("admin.settings"))]
router = APIRouter(prefix="/admin/connections", tags=["settings"])


@router.get("")
def list_connections(_: Manage, settings: SettingsDep) -> dict:
    on = svc.services(settings)
    return {
        # Without a connect key, the CRM can't ask the platform at all.
        "connected": svc.connected(settings),
        "company": settings.company,
        "services": [{"key": s.key, "name": s.name, "purpose": s.purpose, "on": s.key in on} for s in svc.SERVICES],
    }
