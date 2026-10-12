"""Schemas for entry APIs."""

from pydantic import BaseModel, Field, field_validator


class CreateEntryRequest(BaseModel):
    word: str = Field(min_length=1)
    category_id: int = Field(gt=0)
    explanation: str = Field(min_length=1)

    @field_validator("word", "explanation")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("空白だけの値は指定できません。")
        return value


class CreateEntryResponse(BaseModel):
    id: int
    word: str
    category_id: int
    explanation: str
