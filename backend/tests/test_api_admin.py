import time

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from hikeall.api.app import create_app
from hikeall.config import Settings

SECRET = "test-secret-with-at-least-32-characters!!"


def bearer(sub="u1", exp_in=3600, aud="authenticated"):
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_in}
    return {"Authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")}


@pytest.fixture
def settings(tmp_path):
    return Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        chat_log_path=tmp_path / "chat.jsonl",
        chroma_dir=tmp_path / "chroma",
        openrouter_api_key="k",
        supabase_jwt_secret=SECRET,
    )


def client_with(settings, lookup):
    return TestClient(create_app(settings, deps_factory=lambda: "deps", role_lookup=lookup))


def test_admin_me_requires_token(settings):
    r = client_with(settings, lambda uid: "admin").get("/admin/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_admin_me_forbidden_for_user(settings):
    r = client_with(settings, lambda uid: "user").get("/admin/me", headers=bearer())
    assert r.status_code == 403
    assert r.json() == {"detail": "Kein Zugriff"}


def test_admin_me_ok_for_admin(settings):
    r = client_with(settings, lambda uid: "admin").get("/admin/me", headers=bearer(sub="a1"))
    assert r.status_code == 200
    assert r.json() == {"user_id": "a1", "role": "admin"}


def test_admin_me_db_down(settings):
    def down(uid):
        raise psycopg.OperationalError("down")

    r = client_with(settings, down).get("/admin/me", headers=bearer())
    assert r.status_code == 503
    assert "Anmeldung" in r.json()["detail"]
