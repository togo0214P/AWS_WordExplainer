"""Shared API response helpers."""

from fastapi import status
from fastapi.responses import JSONResponse


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
