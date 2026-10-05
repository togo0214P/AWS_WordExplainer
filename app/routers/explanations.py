"""Routes for generating word explanations."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.responses import not_implemented
from app.schemas.explanations import GenerateExplanationRequest


router = APIRouter(tags=["explanations"])


@router.post(
    "/api/explanations/generate",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def generate_explanation(request: GenerateExplanationRequest) -> JSONResponse:
    """Generate an explanation (implementation pending)."""
    return not_implemented()
