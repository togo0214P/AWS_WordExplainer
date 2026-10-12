"""HTTP-level tests for explanation generation using a mock provider."""

import unittest
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import entries
from app.routers import explanations
from app.schemas.categories import CategoryResponse
from app.schemas.explanations import GeneratedContent
from app.services.explanation_generator import get_explanation_generator


CATEGORIES = [
    CategoryResponse(id=1, name="コンピューティング"),
    CategoryResponse(id=2, name="ストレージ"),
]


class StubGenerator:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result or GeneratedContent(
            category="コンピューティング",
            explanation="CPUなどの計算処理を提供する分野です。",
        )
        self.error = error
        self.called_with: tuple[str, list[CategoryResponse]] | None = None

    def generate(
        self,
        word: str,
        categories: list[CategoryResponse],
    ) -> object:
        self.called_with = (word, categories)
        if self.error is not None:
            raise self.error
        return self.result


class GenerateExplanationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = StubGenerator()
        app.dependency_overrides[get_explanation_generator] = lambda: self.generator
        self.categories_patcher = patch.object(
            explanations,
            "fetch_categories",
            return_value=CATEGORIES,
        )
        self.categories_patcher.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.categories_patcher.stop()

    def test_returns_candidate_using_registered_category(self) -> None:
        with patch.object(entries, "get_connection") as get_connection:
            response = self.client.post(
                "/api/explanations/generate",
                json={"word": "  EC2  "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "word": "EC2",
                "category_id": 1,
                "category": "コンピューティング",
                "explanation": "CPUなどの計算処理を提供する分野です。",
            },
        )
        self.assertEqual(self.generator.called_with, ("EC2", CATEGORIES))
        get_connection.assert_not_called()

    def test_rejects_blank_or_overlong_word_before_generation(self) -> None:
        for word in ("   ", "あ" * 101):
            with self.subTest(word_length=len(word)):
                response = self.client.post(
                    "/api/explanations/generate",
                    json={"word": word},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")

        self.assertIsNone(self.generator.called_with)

        response = self.client.post(
            "/api/explanations/generate",
            json={"word": "あ" * 100},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["word"], "あ" * 100)

    def test_returns_service_unavailable_when_no_categories_exist(self) -> None:
        with patch.object(explanations, "fetch_categories", return_value=[]):
            response = self.client.post(
                "/api/explanations/generate",
                json={"word": "EC2"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "CATEGORIES_NOT_CONFIGURED",
        )
        self.assertIsNone(self.generator.called_with)

    def test_returns_database_unavailable_if_categories_cannot_be_loaded(self) -> None:
        with patch.object(
            explanations,
            "fetch_categories",
            side_effect=psycopg.OperationalError("database unavailable"),
        ):
            response = self.client.post(
                "/api/explanations/generate",
                json={"word": "EC2"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "DATABASE_UNAVAILABLE")
        self.assertIsNone(self.generator.called_with)

    def test_rejects_unregistered_category_and_malformed_content(self) -> None:
        for result in (
            GeneratedContent(category="未登録", explanation="説明"),
            {"category": "コンピューティング", "explanation": "   "},
        ):
            with self.subTest(result=result):
                self.generator = StubGenerator(result=result)
                response = self.client.post(
                    "/api/explanations/generate",
                    json={"word": "EC2"},
                )
                self.assertEqual(response.status_code, 502)
                self.assertEqual(
                    response.json()["error"]["code"],
                    "GENERATION_FAILED",
                )

    def test_returns_bad_gateway_when_generator_fails(self) -> None:
        self.generator = StubGenerator(error=RuntimeError("provider failure"))

        response = self.client.post(
            "/api/explanations/generate",
            json={"word": "EC2"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "GENERATION_FAILED")


if __name__ == "__main__":
    unittest.main()
