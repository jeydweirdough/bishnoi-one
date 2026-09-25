"""What the other Nabhi apps ask Finance: tax. Only for an app holding one of
INTEGRATION_KEYS, sent in the X-Nabhi-Key header (the same way the CRM reads
Inventory), so a quote, a pharmacy sale and an invoice are all taxed by
Finance's one set of rules.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.deps import DB, SettingsDep
from app.routers.tax import SaleBody, setup_out, work_out


def calling_app(settings: SettingsDep, x_nabhi_key: Annotated[str | None, Header()] = None) -> str:
    """The name of the app whose key came with the request."""
    if x_nabhi_key:
        for key in settings.integration_keys:
            name, _, secret = key.get_secret_value().partition(":")
            if hmac.compare_digest(secret.encode(), x_nabhi_key.encode()):
                return name
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This needs a Nabhi app's key (X-Nabhi-Key).")


router = APIRouter(prefix="/integration/tax", tags=["integration"], dependencies=[Depends(calling_app)])


@router.get("/setup")
def setup(db: DB, settings: SettingsDep) -> dict:
    """The categories a product can have and the buyers there are, for the
    caller's own forms. Read-only: the registration and rates are Finance's."""
    return setup_out(db, settings, False)


@router.post("/compute")
def compute(db: DB, settings: SettingsDep, body: SaleBody) -> dict:
    return work_out(db, settings, body)
