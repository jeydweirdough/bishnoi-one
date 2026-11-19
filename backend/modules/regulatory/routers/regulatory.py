"""Regulatory's endpoints. Add them here, under /regulatory.

Anything that needs a signed-in person takes `user: CurrentUser` (or
`AdminUser` for this app's admins) from modules.regulatory.deps.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/regulatory", tags=["regulatory"])
