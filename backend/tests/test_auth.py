import itertools
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from hikeall.auth import AuthError, verify_token
from hikeall.config import Settings

SECRET = "test-secret-with-at-least-32-characters!!"


@pytest.fixture
def settings():
    return Settings(supabase_db_url="postgresql://x:x@127.0.0.1:1/none", supabase_jwt_secret=SECRET)


def make_token(sub="u1", aud="authenticated", exp_in=3600, secret=SECRET, **extra):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_in, **extra}
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_hs256_token(settings):
    assert verify_token(make_token(sub="u1"), settings).user_id == "u1"


def test_missing_token(settings):
    with pytest.raises(AuthError) as e:
        verify_token("", settings)
    assert e.value.reason == "missing"


def test_expired_token(settings):
    with pytest.raises(AuthError) as e:
        verify_token(make_token(exp_in=-10), settings)
    assert e.value.reason == "expired"


def test_wrong_audience_rejected(settings):
    with pytest.raises(AuthError) as e:
        verify_token(make_token(aud="anon"), settings)
    assert e.value.reason == "invalid"


def test_wrong_signature_and_garbage_rejected(settings):
    for bad in (make_token(secret="x" * 40), "not.a.jwt", "abc"):
        with pytest.raises(AuthError) as e:
            verify_token(bad, settings)
        assert e.value.reason == "invalid"


def test_alg_none_rejected(settings):
    claims = {"sub": "u1", "aud": "authenticated", "exp": int(time.time()) + 3600}
    token = jwt.encode(claims, None, algorithm="none")
    with pytest.raises(AuthError) as e:
        verify_token(token, settings)
    assert e.value.reason == "invalid"


def test_hs256_without_secret_rejected():
    s = Settings(supabase_db_url="postgresql://x:x@127.0.0.1:1/none")
    with pytest.raises(AuthError):
        verify_token(make_token(), s)


_urls = itertools.count()


@pytest.fixture
def jwks(monkeypatch):
    """ES256 key pair behind a stubbed JWKS fetch (no network); counts the fetches."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="k1", use="sig", alg="ES256")
    state = {"fetches": 0, "fail": False}

    def fetch(self):
        state["fetches"] += 1
        if state["fail"]:
            raise PyJWKClientConnectionError("down")
        data = {"keys": [jwk]}
        self.jwk_set_cache.put(data)  # what the real fetch_data does on success
        self._last_successful_fetch = time.monotonic()
        return data

    monkeypatch.setattr(PyJWKClient, "fetch_data", fetch)
    s = Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        supabase_url=f"http://jwks-{next(_urls)}.test",  # fresh client cache entry per test
    )
    return key, s, state


def es_token(key, kid="k1", sub="u1"):
    claims = {"sub": sub, "aud": "authenticated", "exp": int(time.time()) + 3600}
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": kid})


def test_valid_es256_token_via_jwks(jwks):
    key, s, state = jwks
    assert verify_token(es_token(key), s).user_id == "u1"
    assert verify_token(es_token(key), s).user_id == "u1"
    assert state["fetches"] == 1  # cached


def test_unknown_kid_refetches_at_most_once_a_minute(jwks):
    key, s, state = jwks
    verify_token(es_token(key), s)
    for i in range(3):
        with pytest.raises(AuthError) as e:
            verify_token(es_token(key, kid=f"unknown{i}"), s)
        assert e.value.reason == "invalid"
    assert state["fetches"] == 1  # initial fetch only; no refetch inside the cooldown


def test_unreachable_jwks_is_unavailable_not_invalid(jwks):
    key, s, state = jwks
    state["fail"] = True
    with pytest.raises(AuthError) as e:
        verify_token(es_token(key), s)
    assert e.value.reason == "unavailable"
