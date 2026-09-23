"""Finance's endpoints. Add them here, under /finance.

Anything that needs a signed-in person takes `user: CurrentUser` (or
`AdminUser` for this app's admins) from app.deps.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/finance", tags=["finance"])
