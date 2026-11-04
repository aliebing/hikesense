import json
import time
from datetime import UTC, datetime

import bcrypt
import jwt
import psycopg
import pytest
from fastapi.testclient import TestClient

from hikesense.api.app import create_app
from hikesense.config import Settings
from hikesense.guest_quota import guest_owner
from hikesense.supabase_admin import SupabaseAdminError
from hikesense.users import AppUser

JWT_SECRET = "test-secret-with-at-least-32-characters!!"
HASH = bcrypt.hashpw(b"richtig", bcrypt.gensalt(rounds=4)).decode()
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
USERS = [AppUser("u-1", "a@x.de", "aktiv", T0, None), AppUser("u-2", "b@x.de", "gesperrt", T0, T0)]
LOG_ROWS = [
    {"request_id": "r1", "ts": "2026-11-01T10:00:00", "user_id": "u-1", "message": "Feldberg"},
    {
        "request_id": "r2",
        "ts": "2026-11-01T11:00:00",
        "user_hash": guest_owner("1.2.3.4"),
        "message": "Brocken",
    },
]


@pytest.fixture
def settings(tmp_path):
    return Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        chat_log_path=tmp_path / "chat.jsonl",
        chroma_dir=tmp_path / "chroma",
        openrouter_api_key="k",
        supabase_jwt_secret=JWT_SECRET,
        hikesense_admin_password_hash=HASH,
        hikesense_admin_session_secret="z" * 40,
    )


class FakeBlocker:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, user_id, blocked):
        if self.fail:
            raise SupabaseAdminError(500)
        if user_id not in {u.user_id for u in USERS}:
            return False
        self.calls.append((user_id, blocked))
        return True


def backend(settings, users=lambda: USERS, blocker=None, rows=LOG_ROWS):
    if rows is not None:
        settings.chat_log_path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    app = create_app(
        settings,
        deps_factory=lambda: "deps",
        users_lookup=users,
        set_blocked=blocker or FakeBlocker(),
        guest_quota=None,
        status_lookup=lambda uid: "aktiv",
    )
    return TestClient(app)


def login(c, password="richtig", name="admin"):
    return c.post("/backend/login", json={"name": name, "password": password})


def test_login_sets_httponly_strict_cookie(settings):
    r = login(backend(settings))
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("hs_admin=")
    low = cookie.lower()
    assert "httponly" in low and "samesite=strict" in low and "path=/" in low
    assert "secure" not in low  # plain http in the test client


def test_login_secure_behind_https_proxy(settings):
    r = backend(settings).post(
        "/backend/login",
        json={"name": "admin", "password": "richtig"},
        headers={"X-Forwarded-Proto": "https"},
    )
    assert "secure" in r.headers["set-cookie"].lower()


def test_login_wrong_password_401(settings):
    c = backend(settings)
    for bad in (("falsch", "admin"), ("richtig", "root")):
        r = login(c, *bad)
        assert r.status_code == 401
        assert r.json() == {"detail": "Anmeldung fehlgeschlagen"}
        assert "set-cookie" not in r.headers


def test_login_sixth_failure_429(settings):
    c = backend(settings)
    for _ in range(5):
        assert login(c, "falsch").status_code == 401
    r = login(c, "richtig")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


@pytest.mark.parametrize(
    "missing", ["hikesense_admin_password_hash", "hikesense_admin_session_secret"]
)
def test_login_without_setup_503(settings, missing):
    s = settings.model_copy(update={missing: None})
    r = login(backend(s))
    assert r.status_code == 503 and r.json() == {"detail": "Backend nicht eingerichtet"}


@pytest.mark.parametrize(
    "path", ["/backend/me", "/backend/users", "/backend/searches", "/backend/searches/r1"]
)
def test_every_endpoint_requires_cookie(settings, path):
    r = backend(settings).get(path)
    assert r.status_code == 401 and r.json() == {"detail": "Bitte anmelden"}
    assert "Feldberg" not in r.text


def test_supabase_bearer_token_is_ignored(settings):
    token = jwt.encode(
        {"sub": "u-1", "aud": "authenticated", "exp": int(time.time()) + 3600}, JWT_SECRET, "HS256"
    )
    r = backend(settings).get("/backend/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_forged_cookie_rejected(settings):
    c = backend(settings)
    c.cookies.set("hs_admin", f"{int(time.time()) + 3600}.{'0' * 64}")
    assert c.get("/backend/me").status_code == 401


def test_users_lists_status_and_guest_row(settings):
    c = backend(settings)
    login(c)
    body = c.get("/backend/users").json()
    by_id = {u["user_id"]: (u["status"], u["searches"]) for u in body["users"]}
    assert by_id == {"u-1": ("aktiv", 1), "u-2": ("gesperrt", 0), "guest": ("gast", 1)}
    assert c.get("/backend/me").json() == {"name": "admin"}


def test_searches_and_detail(settings):
    c = backend(settings)
    login(c)
    assert [i["request_id"] for i in c.get("/backend/searches?user=guest").json()["items"]] == [
        "r2"
    ]
    assert c.get("/backend/searches/r1").json()["email"] == "a@x.de"
    assert c.get("/backend/searches/nope").status_code == 404
    assert c.get("/backend/searches?limit=201").status_code == 422


def test_block_and_unblock(settings):
    blocker = FakeBlocker()
    c = backend(settings, blocker=blocker)
    login(c)
    assert c.post("/backend/users/u-1/block").json() == {"status": "gesperrt"}
    assert c.post("/backend/users/u-1/unblock").json() == {"status": "aktiv"}
    assert blocker.calls == [("u-1", True), ("u-1", False)]


def test_block_requires_cookie(settings):
    blocker = FakeBlocker()
    r = backend(settings, blocker=blocker).post("/backend/users/u-1/block")
    assert r.status_code == 401 and blocker.calls == []


def test_block_unknown_user_404(settings):
    c = backend(settings)
    login(c)
    assert c.post("/backend/users/nope/block").status_code == 404


def test_block_admin_api_failure_502(settings):
    c = backend(settings, blocker=FakeBlocker(fail=True))
    login(c)
    r = c.post("/backend/users/u-1/block")
    assert r.status_code == 502 and r.json() == {"detail": "Supabase-Admin-API nicht erreichbar"}


def test_users_db_error_503(settings):
    def down():
        raise psycopg.OperationalError("down")

    c = backend(settings, users=down)
    login(c)
    assert c.get("/backend/users").status_code == 503


def test_logout_clears_cookie(settings):
    c = backend(settings)
    login(c)
    r = c.post("/backend/logout")
    assert r.status_code == 200
    assert (
        'hs_admin=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
    )
    assert c.get("/backend/me").status_code == 401


def test_old_admin_paths_are_gone(settings):
    c = backend(settings)
    login(c)
    assert c.get("/admin/me").status_code == 404
    assert c.get("/admin/users").status_code == 404
