"""Licensing's endpoints. Add them here, under /licensing.

Anything that needs a signed-in person takes `user: CurrentUser` (or
`AdminUser` for this app's admins) from app.deps.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/licensing", tags=["licensing"])
