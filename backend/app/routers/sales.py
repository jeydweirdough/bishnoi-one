"""Sales's endpoints. Add them here, under /sales.

An endpoint that needs a permission takes
`access: Annotated[Access, Depends(require("customers.view"))]` (app.access);
one that only needs a signed-in person takes `user: CurrentUser` (app.deps).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/sales", tags=["sales"])
