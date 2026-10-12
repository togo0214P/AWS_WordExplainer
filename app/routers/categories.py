"""Routes for category options."""

import logging

import psycopg
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.repositories.categories import list_categories as fetch_categories
from app.responses import api_error
from app.schemas.categories import CategoriesResponse


router = APIRouter(tags=["categories"])
logger = logging.getLogger(__name__)


@router.get(
    "/api/categories",
    status_code=status.HTTP_200_OK,
    response_model=CategoriesResponse,
)
def list_categories() -> CategoriesResponse | JSONResponse:
    """Return registered categories, including an empty list when none exist."""
    try:
        return CategoriesResponse(categories=fetch_categories())
    except psycopg.OperationalError:
        logger.exception("PostgreSQL connection failed while listing categories")
        return api_error(
            code="DATABASE_UNAVAILABLE",
            message="データベースに接続できません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except psycopg.Error:
        logger.exception("PostgreSQL error while listing categories")
        return api_error(
            code="DATABASE_ERROR",
            message="データベースの処理に失敗しました。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
