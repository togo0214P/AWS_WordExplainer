"""Schemas for category APIs."""

from pydantic import BaseModel


class CategoryResponse(BaseModel):
    id: int
    name: str


class CategoriesResponse(BaseModel):
    categories: list[CategoryResponse]
