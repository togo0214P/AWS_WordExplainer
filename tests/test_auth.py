"""Authentication behavior at the HTTP boundary and during key rotation."""
import io
import json
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from urllib.error import URLError

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth import cognito
from app.main import app


class CognitoAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.issuer = "https://cognito-idp.test-region.amazonaws.com/test-pool"

    def setUp(self):
        self.client = TestClient(app)
        self.cache = cognito.JwksCache()
        self.config = patch.object(cognito, "settings", replace(cognito.settings,
            cognito_region="test-region", cognito_user_pool_id="test-pool", cognito_client_id="client"))
        self.config.start()
        self.cache_patch = patch.object(cognito, "jwks_cache", self.cache)
        self.cache_patch.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.cache_patch.stop)

    def jwks(self, key=None, kid="key1"):
        data = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk((key or self.private).public_key()))
        data.update(kid=kid, alg="RS256", use="sig")
        return io.BytesIO(json.dumps({"keys": [data]}).encode())

    def token(self, key=None, kid="key1", **changes):
        claims = {"iss": self.issuer, "sub": "user-1", "exp": int(time.time()) + 300,
                  "token_use": "access", "client_id": "client"}
        claims.update(changes)
        return jwt.encode(claims, key or self.private, algorithm="RS256", headers={"kid": kid})

    def request(self, token):
        return self.client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    def test_health_public_and_all_business_routes_require_authentication(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        for method, path in (("get", "/api/me"), ("get", "/api/categories"),
                             ("post", "/api/explanations/generate"), ("get", "/api/entries"),
                             ("post", "/api/entries"), ("delete", "/api/entries/1")):
            with self.subTest(path=path, method=method):
                result = getattr(self.client, method)(path)
                self.assertEqual(result.status_code, 401)
                self.assertEqual(result.json()["error"]["code"], "UNAUTHORIZED")

    def test_valid_token_and_invalid_claims_or_signature(self):
        with patch.object(cognito, "urlopen", side_effect=lambda *a, **kw: self.jwks()):
            self.assertEqual(self.request(self.token()).json(), {"sub": "user-1"})
            for token in (self.token(exp=int(time.time()) - 1), self.token(iss="wrong"),
                          self.token(client_id="wrong"), self.token(token_use="id"),
                          self.token(key=self.other_private), "malformed"):
                with self.subTest(token=token[:15]):
                    self.assertEqual(self.request(token).status_code, 401)

    def test_unknown_keys_are_rate_limited_and_rotation_is_detected(self):
        with patch.object(cognito.time, "monotonic", return_value=100) as clock, patch.object(
            cognito, "urlopen", side_effect=[self.jwks(), self.jwks(self.other_private, "key2")]
        ) as fetch:
            self.assertEqual(self.request(self.token()).status_code, 200)
            for kid in ("unknown1", "unknown2", "key2"):
                self.assertEqual(self.request(self.token(key=self.other_private, kid=kid)).status_code, 401)
            self.assertEqual(fetch.call_count, 1)
            clock.return_value = 131
            self.assertEqual(self.request(self.token(key=self.other_private, kid="key2")).status_code, 200)
            self.assertEqual(self.request(self.token(kid="unknown3")).status_code, 401)
            self.assertEqual(fetch.call_count, 2)

    def test_failed_unknown_key_refresh_is_rate_limited_and_fails_closed(self):
        with patch.object(cognito.time, "monotonic", return_value=100) as clock, patch.object(
            cognito, "urlopen", side_effect=[self.jwks(), URLError("offline"), self.jwks(self.other_private, "key2")]
        ) as fetch:
            self.assertEqual(self.request(self.token()).status_code, 200)
            clock.return_value = 131
            self.assertEqual(self.request(self.token(kid="key2")).status_code, 503)
            self.assertEqual(self.request(self.token(kid="other")).status_code, 503)
            self.assertEqual(fetch.call_count, 2)
            clock.return_value = 162
            self.assertEqual(self.request(self.token(key=self.other_private, kid="key2")).status_code, 200)
            self.assertEqual(fetch.call_count, 3)

    def test_missing_config_and_jwks_failure_fail_closed(self):
        with patch.object(cognito, "settings", replace(cognito.settings, cognito_client_id="")):
            self.assertEqual(self.request(self.token()).status_code, 503)
        with patch.object(cognito, "urlopen", side_effect=URLError("offline")):
            result = self.request(self.token())
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.json()["error"]["code"], "AUTHENTICATION_UNAVAILABLE")

    def test_cors_preflight_permits_authorization(self):
        # Middleware is configured at startup; inspect its configured header list.
        middleware = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
        self.assertIn("Authorization", middleware.kwargs["allow_headers"])
