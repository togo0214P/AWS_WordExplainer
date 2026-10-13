"""HTTP-level tests for explanation generation using a mock provider."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from google.genai.errors import APIError
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import entries
from app.routers import explanations
from app.schemas.categories import CategoryResponse
from app.schemas.explanations import GeneratedCategory, GeneratedContent
from app.services.explanation_generator import (
    GeminiExplanationGenerator,
    GenerationUnavailableError,
    build_generation_prompt,
    get_explanation_generator,
)


CATEGORIES = [
    CategoryResponse(id=1, name="コンピューティング"),
    CategoryResponse(id=2, name="ストレージ"),
]


class StubGenerator:
    def __init__(self, result: object = None, error: Exception | None = None) -> None:
        self.result = result or GeneratedContent(
            category=GeneratedCategory(id=1, name="コンピューティング"),
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
            GeneratedContent(
                category=GeneratedCategory(id=99, name="未登録"),
                explanation="説明",
            ),
            GeneratedContent(
                category=GeneratedCategory(id=2, name="コンピューティング"),
                explanation="説明",
            ),
            {
                "category": {"id": 1, "name": "コンピューティング"},
                "explanation": "   ",
            },
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

    def test_logs_gemini_api_error_details_without_changing_response(self) -> None:
        error = APIError(
            503,
            {
                "error": {
                    "status": "UNAVAILABLE",
                    "message": "Gemini service is temporarily unavailable",
                }
            },
        )
        self.generator = StubGenerator(error=error)

        with self.assertLogs(explanations.logger, level="ERROR") as captured:
            response = self.client.post(
                "/api/explanations/generate",
                json={"word": "EC2"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "GENERATION_FAILED")
        self.assertIn("http_status=503", captured.output[0])
        self.assertIn("api_status=UNAVAILABLE", captured.output[0])
        self.assertIn("Gemini service is temporarily unavailable", captured.output[0])

    def test_returns_service_unavailable_when_generator_has_no_api_key(self) -> None:
        self.generator = StubGenerator(error=GenerationUnavailableError())

        response = self.client.post(
            "/api/explanations/generate",
            json={"word": "EC2"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "GENERATION_UNAVAILABLE",
        )


class GeminiGeneratorTests(unittest.TestCase):
    def test_builds_prompt_with_registered_category_ids_and_names(self) -> None:
        prompt = build_generation_prompt("EC2", CATEGORIES)

        self.assertIn("EC2", prompt)
        self.assertIn('"id": 1', prompt)
        self.assertIn('"name": "コンピューティング"', prompt)
        self.assertIn("解説対象のデータ", prompt)

    def test_calls_gemini_with_structured_json_schema_and_parses_result(self) -> None:
        returned_json = json.dumps(
            {
                "category": {"id": 1, "name": "コンピューティング"},
                "explanation": "CPUなどの計算処理を提供する分野です。",
            },
            ensure_ascii=False,
        )
        calls: list[dict[str, object]] = []

        def generate_content(**kwargs: object) -> SimpleNamespace:
            calls.append(dict(kwargs))
            return SimpleNamespace(text=returned_json)

        models = SimpleNamespace(generate_content=generate_content)
        client = SimpleNamespace(models=models, close=lambda: None)
        generator = GeminiExplanationGenerator("test-key", "test-model")

        with patch(
            "app.services.explanation_generator.genai.Client",
            return_value=client,
        ) as client_factory:
            result = generator.generate("EC2", CATEGORIES)

        self.assertEqual(result.category.id, 1)
        self.assertEqual(result.category.name, "コンピューティング")
        self.assertEqual(result.explanation, "CPUなどの計算処理を提供する分野です。")
        client_factory.assert_called_once()
        self.assertEqual(client_factory.call_args.kwargs["api_key"], "test-key")
        self.assertEqual(
            client_factory.call_args.kwargs["http_options"].timeout,
            60_000,
        )
        self.assertEqual(calls[0]["model"], "test-model")
        self.assertIn("EC2", calls[0]["contents"])
        self.assertEqual(
            calls[0]["config"].response_mime_type,
            "application/json",
        )
        self.assertIs(calls[0]["config"].response_schema, GeneratedContent)

    def test_factory_returns_gemini_generator(self) -> None:
        self.assertIsInstance(get_explanation_generator(), GeminiExplanationGenerator)

    def test_does_not_create_gemini_client_without_api_key(self) -> None:
        generator = GeminiExplanationGenerator("", "test-model")

        with patch("app.services.explanation_generator.genai.Client") as client_factory:
            with self.assertRaises(GenerationUnavailableError):
                generator.generate("EC2", CATEGORIES)

        client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
