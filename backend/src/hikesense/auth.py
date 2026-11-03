"""Supabase access-token check: HS256 with the project secret, ES256/RS256 through the JWKS."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Literal

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from hikesense.config import Settings

log = logging.getLogger(__name__)

AUDIENCE = "authenticated"
HS_ALGS = ("HS256",)
JWKS_ALGS = ("ES256", "RS256")

_clients: dict[str, PyJWKClient] = {}
_lock = threading.Lock()


@dataclass(frozen=True)
class AuthUser:
    user_id: str


class AuthError(Exception):
    def __init__(self, reason: Literal["missing", "expired", "invalid", "unavailable"]) -> None:
        super().__init__(reason)
        self.reason = reason


def _jwks_client(settings: Settings) -> PyJWKClient:
    url = f"{(settings.supabase_url or '').rstrip('/')}/auth/v1/.well-known/jwks.json"
    with _lock:
        if url not in _clients:
            _clients[url] = PyJWKClient(
                url, cache_keys=True, lifespan=3600, timeout=5, cooldown_duration=60
            )  # unknown kid: refetch at most once a minute
        return _clients[url]


def verify_token(token: str, settings: Settings) -> AuthUser:
    if not token:
        raise AuthError("missing")
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg in HS_ALGS and settings.supabase_jwt_secret:
            key: object = settings.supabase_jwt_secret
        elif alg in JWKS_ALGS and settings.supabase_url:
            key = _jwks_client(settings).get_signing_key_from_jwt(token).key
        else:
            raise AuthError("invalid")
        claims = jwt.decode(
            token,
            key,  # type: ignore[arg-type]
            algorithms=[alg],
            audience=AUDIENCE,
            options={"require": ["exp", "sub"]},
        )
    except AuthError:
        raise
    except PyJWKClientConnectionError as exc:  # JWKS unreachable: not the user's fault
        log.error("JWKS fetch failed: %s", type(exc.__cause__ or exc).__name__)
        raise AuthError("unavailable") from exc
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("expired") from exc
    except Exception as exc:  # bad signature/audience/format, JWKS unreachable: not logged in
        raise AuthError("invalid") from exc
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("invalid")
    return AuthUser(user_id=sub)
