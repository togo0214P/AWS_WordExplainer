"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers.categories import router as categories_router
from app.routers.entries import router as entries_router
from app.routers.explanations import router as explanations_router
from app.responses import api_error


app = FastAPI(
    title="AWS Word Explainer API",
    description="単語解説APIの開発用スケルトンです。",
    version="0.1.0",
)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return api_error(
        code="INVALID_REQUEST",
        message="リクエストの値が不正です。",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(explanations_router)
app.include_router(entries_router)
app.include_router(categories_router)
