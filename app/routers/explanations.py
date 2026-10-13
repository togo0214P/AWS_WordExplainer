"""Routes for generating word explanations."""

import logging

import psycopg
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from google.genai.errors import APIError
from pydantic import ValidationError

from app.config import settings
from app.repositories.categories import list_categories as fetch_categories
from app.responses import api_error
from app.schemas.explanations import (
    GeneratedContent,
    GenerateExplanationRequest,
    GenerateExplanationResponse,
)
from app.services.explanation_generator import (
    ExplanationGenerator,
    GenerationUnavailableError,
    get_explanation_generator,
)


router = APIRouter(tags=["explanations"])
logger = logging.getLogger(__name__)


@router.post(
    "/api/explanations/generate",
    status_code=status.HTTP_200_OK,
    response_model=GenerateExplanationResponse,
)
def generate_explanation(
    request: GenerateExplanationRequest,
    generator: ExplanationGenerator = Depends(get_explanation_generator),
) -> GenerateExplanationResponse | JSONResponse:
    """Return a validated explanation candidate without saving it."""
    try:
        categories = fetch_categories()
    except psycopg.OperationalError:
        logger.exception(
            "PostgreSQL connection failed while generating an explanation"
        )
        return api_error(
            code="DATABASE_UNAVAILABLE",
            message="データベースに接続できません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except psycopg.Error:
        logger.exception("PostgreSQL error while loading generation categories")
        return api_error(
            code="DATABASE_ERROR",
            message="データベースの処理に失敗しました。",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if not categories:
        return api_error(
            code="CATEGORIES_NOT_CONFIGURED",
            message="説明生成に使うカテゴリが登録されていません。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        generated = generator.generate(request.word, categories)
        content = GeneratedContent.model_validate(generated)
    except GenerationUnavailableError:
        return api_error(
            code="GENERATION_UNAVAILABLE",
            message="説明生成APIを利用できません。設定を確認してください。",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except ValidationError:
        logger.warning("Explanation generator returned an invalid response")
        return _generation_failed()
    except APIError as error:
        message = _safe_upstream_error_message(error.message)
        logger.error(
            "Gemini API request failed "
            "(http_status=%s, api_status=%s, message=%s)",
            error.code,
            error.status,
            message,
        )
        return _generation_failed()
    except Exception as error:
        logger.error("Explanation generation failed (%s)", type(error).__name__)
        return _generation_failed()

    category = next(
        (
            candidate
            for candidate in categories
            if candidate.id == content.category.id
            and candidate.name == content.category.name
        ),
        None,
    )
    if category is None:
        logger.warning("Explanation generator returned an unregistered category")
        return _generation_failed()

    return GenerateExplanationResponse(
        word=request.word,
        category_id=category.id,
        category=category.name,
        explanation=content.explanation,
    )


def _generation_failed() -> JSONResponse:
    return api_error(
        code="GENERATION_FAILED",
        message="説明を生成できませんでした。時間をおいて再度お試しください。",
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def _safe_upstream_error_message(message: object) -> str:
    """Return a one-line, bounded upstream message with secrets redacted."""
    safe_message = str(message or "").replace("\r", " ").replace("\n", " ")
    if settings.gemini_api_key:
        safe_message = safe_message.replace(settings.gemini_api_key, "[REDACTED]")
    return safe_message[:500]
