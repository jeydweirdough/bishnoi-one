"""Finance's endpoints. Add them here, under /finance.

Anything that needs a signed-in person takes `user: CurrentUser` from
app.deps, or `user: permitted("<area>.<action>")` from app.access when it
needs a permission (app/permissions.py).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/finance", tags=["finance"])
