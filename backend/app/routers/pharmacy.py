"""Pharmacy's endpoints. Add them here, under /pharmacy."""

from fastapi import APIRouter

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])
