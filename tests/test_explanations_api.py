"""HTTP-level tests for explanation generation using a mock provider."""

import json
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
import httpx
import openai
from google.genai.errors import APIError
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import entries
from app.routers import explanations
from app.schemas.categories import CategoryResponse
from app.schemas.explanations import GeneratedCategory, GeneratedContent
from app.services.explanation_generator import (
    GeminiExplanationGenerator,
    OpenAIExplanationGenerator,
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

    def test_does_not_create_gemini_client_without_api_key(self) -> None:
        generator = GeminiExplanationGenerator("", "test-model")

        with patch("app.services.explanation_generator.genai.Client") as client_factory:
            with self.assertRaises(GenerationUnavailableError):
                generator.generate("EC2", CATEGORIES)

        client_factory.assert_not_called()


class OpenAIGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = OpenAIExplanationGenerator("test-key", "test-model")

    def test_unset_provider_defaults_to_openai(self) -> None:
        env = os.environ.copy()
        env.pop("EXPLANATION_PROVIDER", None)
        result = subprocess.run(
            [sys.executable, "-c", "from unittest.mock import patch; "
             "patch('dotenv.load_dotenv').start(); "
             "from app.config import settings; print(settings.explanation_provider)"],
            env=env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "openai")

    def test_structured_response_and_api_contract(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 1,
                "model": "test-model", "status": "completed",
                "output": [{"type": "message", "id": "msg_test", "role": "assistant",
                            "status": "completed", "content": [{"type": "output_text",
                                "text": json.dumps({"category": {"id": 1, "name": "コンピューティング"},
                                                    "explanation": "計算資源を提供します。"}),
                                "annotations": []}]}],
            })

        real_client = openai.OpenAI(api_key="test-key", max_retries=0,
                                    http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        with patch("app.services.explanation_generator.OpenAI", return_value=real_client):
            result = self.generator.generate("EC2", CATEGORIES)
        self.assertEqual(result.category.id, 1)
        self.assertEqual(result.explanation, "計算資源を提供します。")
        self.assertEqual(requests[0]["text"]["format"]["type"], "json_schema")
        self.assertFalse(requests[0]["store"])
        self.assertIn("EC2", requests[0]["input"])

    def test_incomplete_or_refused_response_is_rejected(self) -> None:
        for response in (SimpleNamespace(status="incomplete", output_parsed=None),
                         SimpleNamespace(status="completed", output_parsed=None)):
            client = unittest.mock.MagicMock()
            client.__enter__.return_value.responses.parse.return_value = response
            with self.subTest(status=response.status), patch(
                "app.services.explanation_generator.OpenAI", return_value=client
            ):
                with self.assertRaises(ValueError):
                    self.generator.generate("EC2", CATEGORIES)

    def test_missing_configuration_does_not_call_openai(self) -> None:
        for key, model in (("", "model"), ("key", "")):
            with self.subTest(key=bool(key), model=bool(model)), patch(
                "app.services.explanation_generator.OpenAI"
            ) as client:
                with self.assertRaises(GenerationUnavailableError):
                    OpenAIExplanationGenerator(key, model).generate("EC2", CATEGORIES)
                client.assert_not_called()

    def test_api_with_openai_result_checks_category_and_does_not_save(self) -> None:
        client = unittest.mock.MagicMock()
        parsed = GeneratedContent(
            category=GeneratedCategory(id=1, name="コンピューティング"),
            explanation="計算資源を提供します。",
        )
        client.__enter__.return_value.responses.parse.return_value = SimpleNamespace(
            status="completed", output_parsed=parsed
        )
        app.dependency_overrides[get_explanation_generator] = lambda: self.generator
        try:
            with patch("app.services.explanation_generator.OpenAI", return_value=client), patch.object(
                explanations, "fetch_categories", return_value=CATEGORIES
            ), patch.object(entries, "get_connection") as connection:
                test_client = TestClient(app)
                result = test_client.post("/api/explanations/generate", json={"word": "EC2"})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["category_id"], 1)
                connection.assert_not_called()
                parsed.category.name = "不一致"
                result = test_client.post("/api/explanations/generate", json={"word": "EC2"})
                self.assertEqual(result.status_code, 502)
        finally:
            app.dependency_overrides.clear()

    def test_factory_selects_provider_and_rejects_unknown(self) -> None:
        from dataclasses import replace
        from app.services import explanation_generator as module
        for provider, expected in (("gemini", GeminiExplanationGenerator),
                                   ("openai", OpenAIExplanationGenerator),
                                   ("invalid", module.UnavailableExplanationGenerator)):
            with self.subTest(provider=provider), patch.object(
                module, "settings", replace(module.settings, explanation_provider=provider)
            ):
                self.assertIsInstance(module.get_explanation_generator(), expected)

    def test_openai_errors_are_safe_and_return_502(self) -> None:
        request = httpx.Request("POST", "https://example.test")
        for code, error_class in ((401, openai.AuthenticationError), (429, openai.RateLimitError),
                                  (503, openai.InternalServerError)):
            response = httpx.Response(code, request=request)
            error = error_class("secret-value", response=response, body=None)
            with self.subTest(code=code):
                app.dependency_overrides[get_explanation_generator] = lambda: StubGenerator(error=error)
                with patch.object(explanations, "fetch_categories", return_value=CATEGORIES), self.assertLogs(
                    explanations.logger, level="ERROR"
                ) as logs:
                    result = TestClient(app).post("/api/explanations/generate", json={"word": "EC2"})
                app.dependency_overrides.clear()
                self.assertEqual(result.status_code, 502)
                self.assertIn(f"http_status={code}", logs.output[0])
                self.assertNotIn("secret-value", str(logs.output))

        error = openai.APITimeoutError(request=request)
        app.dependency_overrides[get_explanation_generator] = lambda: StubGenerator(error=error)
        try:
            with patch.object(explanations, "fetch_categories", return_value=CATEGORIES):
                result = TestClient(app).post("/api/explanations/generate", json={"word": "EC2"})
            self.assertEqual(result.status_code, 502)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
