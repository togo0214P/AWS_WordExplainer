"""Schemas for entry APIs."""

from pydantic import BaseModel


class CreateEntryRequest(BaseModel):
    word: str
    category_id: int
    explanation: str
