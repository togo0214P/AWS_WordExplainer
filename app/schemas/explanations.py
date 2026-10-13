"""Schemas for explanation APIs and generated content."""

from pydantic import BaseModel, Field, field_validator


class GenerateExplanationRequest(BaseModel):
    word: str = Field(min_length=1, max_length=100)

    @field_validator("word", mode="before")
    @classmethod
    def strip_word(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GeneratedCategory(BaseModel):
    """Category selected by a mock or external generator."""

    id: int
    name: str

    @field_validator("id")
    @classmethod
    def require_positive_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("カテゴリIDは正の整数である必要があります。")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        if not value:
            raise ValueError("カテゴリ名は空にできません。")
        return value


class GeneratedContent(BaseModel):
    """Untrusted content returned by a mock or external generator."""

    category: GeneratedCategory
    explanation: str

    @field_validator("explanation", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("explanation")
    @classmethod
    def require_explanation(cls, value: str) -> str:
        if not value:
            raise ValueError("説明は空にできません。")
        return value


class GenerateExplanationResponse(BaseModel):
    word: str
    category_id: int
    category: str
    explanation: str
