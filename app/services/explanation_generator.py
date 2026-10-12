"""Explanation generation providers."""

from typing import Protocol

from app.schemas.categories import CategoryResponse
from app.schemas.explanations import GeneratedContent


class ExplanationGenerator(Protocol):
    """Interface implemented by mock and external explanation providers."""

    def generate(
        self,
        word: str,
        categories: list[CategoryResponse],
    ) -> GeneratedContent:
        """Generate a category name and explanation for a word."""


class MockExplanationGenerator:
    """Return a deterministic candidate without external API access."""

    def generate(
        self,
        word: str,
        categories: list[CategoryResponse],
    ) -> GeneratedContent:
        category = min(categories, key=lambda candidate: candidate.id)
        return GeneratedContent(
            category=category.name,
            explanation=f"「{word}」の説明生成APIを確認するためのモック解説です。",
        )


def get_explanation_generator() -> ExplanationGenerator:
    """Provide the current generator; replace with Gemini after mock validation."""
    return MockExplanationGenerator()
