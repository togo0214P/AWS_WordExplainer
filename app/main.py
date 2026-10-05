"""FastAPI application entry point."""

from fastapi import FastAPI

from app.routers.categories import router as categories_router
from app.routers.entries import router as entries_router
from app.routers.explanations import router as explanations_router


app = FastAPI(
    title="AWS Word Explainer API",
    description="単語解説APIの開発用スケルトンです。",
    version="0.1.0",
)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(explanations_router)
app.include_router(entries_router)
app.include_router(categories_router)
