"""FastAPI application skeleton for the word explanation API."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI(
    title="AWS Word Explainer API",
    description="単語解説APIの開発用スケルトンです。",
    version="0.1.0",
)


class GenerateExplanationRequest(BaseModel):
    word: str


class CreateEntryRequest(BaseModel):
    word: str
    category_id: int
    explanation: str


def not_implemented() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": "このAPIの処理はまだ実装されていません。",
            }
        },
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/explanations/generate",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    tags=["explanations"],
)
async def generate_explanation(request: GenerateExplanationRequest) -> JSONResponse:
    """Generate an explanation (implementation pending)."""
    return not_implemented()


@app.post(
    "/api/entries",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    tags=["entries"],
)
async def create_entry(request: CreateEntryRequest) -> JSONResponse:
    """Save an accepted entry (implementation pending)."""
    return not_implemented()


@app.get(
    "/api/entries",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    tags=["entries"],
)
async def search_entries(
    word: str | None = None,
    category_id: int | None = None,
) -> JSONResponse:
    """Search entries (implementation pending)."""
    return not_implemented()


@app.get(
    "/api/categories",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    tags=["categories"],
)
async def list_categories() -> JSONResponse:
    """List categories (implementation pending)."""
    return not_implemented()


@app.delete(
    "/api/entries/{entry_id}",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    tags=["entries"],
)
async def delete_entry(entry_id: int) -> JSONResponse:
    """Delete an entry (implementation pending)."""
    return not_implemented()
