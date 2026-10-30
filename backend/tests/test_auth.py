import time

import jwt
import pytest

from hikeall.auth import AuthError, verify_token
from hikeall.config import Settings

SECRET = "test-secret-with-at-least-32-characters!!"


@pytest.fixture
def settings():
    return Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none", supabase_jwt_secret=SECRET
    )


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
    token = jwt.encode({"sub": "u1", "aud": "authenticated"}, None, algorithm="none")
    with pytest.raises(AuthError):
        verify_token(token, settings)


def test_hs256_without_secret_rejected():
    s = Settings(supabase_db_url="postgresql://x:x@127.0.0.1:1/none")
    with pytest.raises(AuthError):
        verify_token(make_token(), s)
