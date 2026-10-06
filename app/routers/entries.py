"""Routes for saved word entries."""

import logging

import psycopg
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.repositories.entries import CategoryNotFoundError, create_entry as save_entry
from app.responses import api_error, not_implemented
from app.schemas.entries import CreateEntryRequest, CreateEntryResponse


router = APIRouter(tags=["entries"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/entries",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateEntryResponse,
)
def create_entry(request: CreateEntryRequest) -> CreateEntryResponse | JSONResponse:
    """Save an entry accepted by the user in the view."""
    try:
        return save_entry(request)
    except CategoryNotFoundError:
        return api_error(
            code="CATEGORY_NOT_FOUND",
            message="指定されたカテゴリは登録されていません。",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except psycopg.OperationalError:
        logger.exception("PostgreSQL connection failed while creating an entry")
        return api_error(
            code="DATABASE_UNAVAILABLE",
            message="データベースに接続できません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except psycopg.Error:
        logger.exception("PostgreSQL error while creating an entry")
        return api_error(
            code="DATABASE_ERROR",
            message="データベースの処理に失敗しました。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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
