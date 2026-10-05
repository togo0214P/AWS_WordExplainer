"""Routes for category options."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.responses import not_implemented


router = APIRouter(tags=["categories"])


@router.get("/api/categories", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def list_categories() -> JSONResponse:
    """List categories (implementation pending)."""
    return not_implemented()
