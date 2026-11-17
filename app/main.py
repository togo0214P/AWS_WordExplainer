"""FastAPI application entry point."""

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth.cognito import AuthenticationError, AuthenticationUnavailable, get_current_user
from app.routers.categories import router as categories_router
from app.routers.entries import router as entries_router
from app.routers.explanations import router as explanations_router
from app.responses import api_error


app = FastAPI(
    title="AWS Word Explainer API",
    description="単語解説APIの開発用スケルトンです。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    response = api_error("UNAUTHORIZED", "認証が必要です。", status.HTTP_401_UNAUTHORIZED)
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


@app.exception_handler(AuthenticationUnavailable)
async def authentication_unavailable_handler(request: Request, exc: AuthenticationUnavailable) -> JSONResponse:
    return api_error("AUTHENTICATION_UNAVAILABLE", "認証サービスを利用できません。", status.HTTP_503_SERVICE_UNAVAILABLE)


@app.get("/api/me", tags=["authentication"])
def me(user: dict = Depends(get_current_user)) -> dict[str, str]:
    return {"sub": user["sub"]}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(explanations_router, dependencies=[Depends(get_current_user)])
app.include_router(entries_router, dependencies=[Depends(get_current_user)])
app.include_router(categories_router, dependencies=[Depends(get_current_user)])
