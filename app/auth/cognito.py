"""Verify Cognito access tokens using the user pool's public keys."""

import json
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings


class AuthenticationError(Exception):
    pass


class AuthenticationUnavailable(Exception):
    pass


class JwksCache:
    def __init__(self) -> None:
        self._keys: dict[str, jwt.PyJWK] = {}
        self._issuer = ""
        self._expires = 0.0
        self._last_refresh = float("-inf")
        self._last_refresh_failed = False
        self._lock = threading.Lock()

    def get_key(self, issuer: str, kid: str) -> jwt.PyJWK:
        with self._lock:
            if issuer != self._issuer or time.monotonic() >= self._expires:
                self._refresh(issuer)
            key = self._keys.get(kid)
            if key is None:
                # Limit refreshes triggered by attacker-controlled key IDs. A new
                # Cognito signing key becomes available after this short interval.
                if time.monotonic() - self._last_refresh >= 30:
                    self._refresh(issuer)
                    key = self._keys.get(kid)
                elif self._last_refresh_failed:
                    raise AuthenticationUnavailable()
            if key is None:
                raise AuthenticationError()
            return key

    def _refresh(self, issuer: str) -> None:
        self._last_refresh = time.monotonic()
        self._last_refresh_failed = True
        try:
            with urlopen(f"{issuer}/.well-known/jwks.json", timeout=5) as response:
                payload = json.load(response)
            keys = {}
            for item in payload["keys"]:
                if item.get("kty") == "RSA" and item.get("kid") and item.get("alg", "RS256") == "RS256":
                    keys[item["kid"]] = jwt.PyJWK.from_dict(item, algorithm="RS256")
            if not keys:
                raise ValueError("No usable signing keys")
        except (URLError, OSError, ValueError, KeyError, TypeError, AttributeError, jwt.PyJWTError) as exc:
            raise AuthenticationUnavailable() from exc
        self._keys = keys
        self._last_refresh_failed = False
        self._issuer = issuer
        self._expires = time.monotonic() + 3600


jwks_cache = JwksCache()
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise AuthenticationError()
    region = settings.cognito_region
    pool_id = settings.cognito_user_pool_id
    client_id = settings.cognito_client_id
    if not region or not pool_id or not client_id:
        raise AuthenticationUnavailable()
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
    try:
        header = jwt.get_unverified_header(credentials.credentials)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
            raise AuthenticationError()
        key = jwks_cache.get_key(issuer, header["kid"])
        claims = jwt.decode(
            credentials.credentials, key.key, algorithms=["RS256"], issuer=issuer,
            options={"require": ["exp", "iss", "sub", "token_use", "client_id"], "verify_aud": False},
        )
        if claims.get("token_use") != "access" or claims.get("client_id") != client_id or not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthenticationError()
        return claims
    except jwt.PyJWTError as exc:
        raise AuthenticationError() from exc
