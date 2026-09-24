"""Pharmacy's endpoints. Add them here, under /pharmacy.

Anything that needs a signed-in person takes `user: CurrentUser` (or
`AdminUser` for this app's admins) from app.deps.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])
