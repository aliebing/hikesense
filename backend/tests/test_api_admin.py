import json
import time

import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from hikeall.api.app import create_app
from hikeall.config import Settings
from hikeall.roles import Profile

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


# --- users / searches / detail ---

PROFILES = [Profile("u-1", "a@x.de", "user"), Profile("a-1", "adm@x.de", "admin")]
LOG_ROWS = [
    {"request_id": "r1", "ts": "2026-11-01T10:00:00", "user_id": "u-1", "message": "Feldberg"},
    {"request_id": "r2", "ts": "2026-11-01T11:00:00", "user_id": "ghost", "message": "Brocken"},
]


def admin_client(settings, profiles=lambda: PROFILES, rows=LOG_ROWS):
    if rows is not None:
        settings.chat_log_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    app = create_app(
        settings,
        deps_factory=lambda: "deps",
        role_lookup=lambda uid: "admin" if uid == "a-1" else "user",
        profiles_lookup=profiles,
    )
    return TestClient(app)


ADMIN = {"sub": "a-1"}


@pytest.mark.parametrize("path", ["/admin/users", "/admin/searches", "/admin/searches/r1"])
def test_every_admin_endpoint_rejects_anonymous_and_users(settings, path):
    c = admin_client(settings)
    anon = c.get(path)
    assert anon.status_code == 401
    user = c.get(path, headers=bearer(sub="u-1"))
    assert user.status_code == 403
    assert user.json() == {"detail": "Kein Zugriff"}
    for r in (anon, user):
        assert "Feldberg" not in r.text and "Brocken" not in r.text


def test_users_lists_profiles_with_counts(settings):
    r = admin_client(settings).get("/admin/users", headers=bearer(sub="a-1"))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    by_id = {u["user_id"]: u["searches"] for u in body["users"]}
    assert by_id == {"u-1": 1, "a-1": 0, "unknown": 1}


def test_searches_filters_by_user_and_unknown(settings):
    c = admin_client(settings)
    h = bearer(sub="a-1")
    r = c.get("/admin/searches?user=unknown", headers=h).json()
    assert [i["request_id"] for i in r["items"]] == ["r2"]
    r = c.get("/admin/searches?user=u-1", headers=h).json()
    assert [i["request_id"] for i in r["items"]] == ["r1"]
    assert c.get("/admin/searches", headers=h).json()["total"] == 2


def test_searches_limit_bounds(settings):
    c = admin_client(settings)
    h = bearer(sub="a-1")
    assert c.get("/admin/searches?limit=0", headers=h).status_code == 422
    assert c.get("/admin/searches?limit=201", headers=h).status_code == 422
    assert c.get("/admin/searches?offset=-1", headers=h).status_code == 422


def test_detail_and_404(settings):
    c = admin_client(settings)
    h = bearer(sub="a-1")
    ok = c.get("/admin/searches/r1", headers=h)
    assert ok.status_code == 200 and ok.json()["email"] == "a@x.de"
    nf = c.get("/admin/searches/nope", headers=h)
    assert nf.status_code == 404
    assert nf.json() == {"detail": "Suche nicht gefunden"}


def test_profiles_db_error_is_503(settings):
    def down():
        raise psycopg.OperationalError("down")

    r = admin_client(settings, profiles=down).get("/admin/users", headers=bearer(sub="a-1"))
    assert r.status_code == 503
    assert "Anmeldung" in r.json()["detail"]


def test_missing_log_file_is_empty_not_500(settings):
    c = admin_client(settings, rows=None)
    h = bearer(sub="a-1")
    assert c.get("/admin/searches", headers=h).json()["items"] == []
    assert c.get("/admin/users", headers=h).json()["total"] == 0
