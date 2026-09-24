"""Inventory's endpoints. Add them here, under /inventory.

Anything that needs a signed-in person takes `user: CurrentUser` (or
`AdminUser` for this app's admins) from app.deps.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/inventory", tags=["inventory"])
