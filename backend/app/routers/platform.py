"""Platform's endpoints. Add them here, under /platform."""

from fastapi import APIRouter

router = APIRouter(prefix="/platform", tags=["platform"])
