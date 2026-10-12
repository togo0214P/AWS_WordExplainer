"""Routes for saved word entries."""

import logging
from typing import Annotated

import psycopg
from fastapi import APIRouter, Path, status
from fastapi.responses import JSONResponse, Response

from app.repositories.entries import (
    CategoryNotFoundError,
    EntryNotFoundError,
    create_entry as save_entry,
    search_entries as find_entries,
    soft_delete_entry as mark_entry_deleted,
)
from app.responses import api_error
from app.schemas.entries import (
    CreateEntryRequest,
    CreateEntryResponse,
    EntrySearchResponse,
)


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


@router.get(
    "/api/entries",
    status_code=status.HTTP_200_OK,
    response_model=EntrySearchResponse,
)
def search_entries(
    word: str | None = None,
    category_id: int | None = None,
) -> EntrySearchResponse | JSONResponse:
    """Search active entries by an optional partial word and category ID."""
    try:
        return EntrySearchResponse(
            entries=find_entries(word=word, category_id=category_id)
        )
    except psycopg.OperationalError:
        logger.exception("PostgreSQL connection failed while searching entries")
        return api_error(
            code="DATABASE_UNAVAILABLE",
            message="データベースに接続できません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except psycopg.Error:
        logger.exception("PostgreSQL error while searching entries")
        return api_error(
            code="DATABASE_ERROR",
            message="データベースの処理に失敗しました。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.delete(
    "/api/entries/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_entry(id: Annotated[int, Path(gt=0)]) -> Response:
    """Soft-delete an active entry and return no content."""
    try:
        mark_entry_deleted(id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EntryNotFoundError:
        return api_error(
            code="ENTRY_NOT_FOUND",
            message="指定されたエントリーが見つかりません。",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except psycopg.OperationalError:
        logger.exception("PostgreSQL connection failed while deleting an entry")
        return api_error(
            code="DATABASE_UNAVAILABLE",
            message="データベースに接続できません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except psycopg.Error:
        logger.exception("PostgreSQL error while deleting an entry")
        return api_error(
            code="DATABASE_ERROR",
            message="データベースの処理に失敗しました。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
