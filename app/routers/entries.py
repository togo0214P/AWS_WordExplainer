"""Routes for saved word entries."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.responses import not_implemented
from app.schemas.entries import CreateEntryRequest


router = APIRouter(tags=["entries"])


@router.post("/api/entries", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_entry(request: CreateEntryRequest) -> JSONResponse:
    """Save an accepted entry (implementation pending)."""
    return not_implemented()


@router.get("/api/entries", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def search_entries(
    word: str | None = None,
    category_id: int | None = None,
) -> JSONResponse:
    """Search entries (implementation pending)."""
    return not_implemented()


@router.delete(
    "/api/entries/{entry_id}",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def delete_entry(entry_id: int) -> JSONResponse:
    """Delete an entry (implementation pending)."""
    return not_implemented()
