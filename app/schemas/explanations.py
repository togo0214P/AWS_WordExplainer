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


class GeneratedContent(BaseModel):
    """Untrusted content returned by a mock or external generator."""

    category: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @field_validator("category", "explanation", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GenerateExplanationResponse(BaseModel):
    word: str
    category_id: int
    category: str
    explanation: str
