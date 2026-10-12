"""Schemas for explanation APIs."""

from pydantic import BaseModel


class GenerateExplanationRequest(BaseModel):
    word: str
