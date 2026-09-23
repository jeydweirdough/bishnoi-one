"""Inventory's endpoints. Add them here, under /inventory."""

from fastapi import APIRouter

router = APIRouter(prefix="/inventory", tags=["inventory"])
