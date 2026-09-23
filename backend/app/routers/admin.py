"""Executive Admin's endpoints. Add them here, under /admin."""

from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])
