import json
import logging
import time
import uuid

import jwt
import pytest
from fastapi.testclient import TestClient

from hikesense.agent.graph import DoneEvent, TokenEvent, UnderstoodEvent
from hikesense.agent.prompts import ERROR_UNAVAILABLE
from hikesense.agent.request import HikeRequest
from hikesense.api import auth as auth_api
from hikesense.api import chat as chat_api
from hikesense.api.app import create_app as _create_app
from hikesense.config import Settings
from hikesense.guard import RATE_LIMIT_REPLY
from hikesense.guest_quota import GuestDecision
from hikesense.llm.usage import LLMUsage

ORIGIN = "http://localhost:3000"
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


class FakeQuota:
    """Guest quota without a database: `allow` decides, `keys` records the ip keys asked for."""

    def __init__(self, allow=True, reason="ip"):
        self.allow, self.reason, self.keys = allow, reason, []

    def acquire(self, key):
        self.keys.append(key)
        if self.allow:
            return GuestDecision(True, "ok", 0)
        return GuestDecision(False, self.reason, 3600)


def create_app(settings=None, quota=None, status="aktiv", **kw):
    """The app with fakes for the database lookups (guest quota, account status)."""
    return _create_app(
        settings, guest_quota=quota or FakeQuota(), status_lookup=lambda uid: status, **kw
    )


users: list = []  # user_id keyword the fake run_chat got
langs: list = []  # lang keyword the fake run_chat got


@pytest.fixture
def seen(monkeypatch):
    calls = []
    users.clear()
    langs.clear()

    def fake_run_chat(deps, thread_id, message, user_hash=None, user_id=None, lang="de"):
        calls.append((deps, thread_id, message))
        users.append(user_id)
        langs.append(lang)
        yield UnderstoodEvent(text="Tagestour", request=HikeRequest(intent="day_hike"))
        yield TokenEvent(text="Hallo ")
        yield DoneEvent(usage=LLMUsage(), unsupported=0)

    monkeypatch.setattr(chat_api, "run_chat", fake_run_chat)
    return calls


@pytest.fixture
def client(settings, seen):
    return TestClient(create_app(settings, deps_factory=lambda: "deps"))


def post(client, message="Wanderung", thread_id=None, headers=None, **kw):
    kw["headers"] = bearer() if headers is None else headers
    body = {"thread_id": thread_id or str(uuid.uuid4()), "message": message}
    return client.post("/chat", json=body, **kw)


def parse_sse(text):
    events = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_chat_streams_events_in_order(client, seen):
    r = post(client, "  Wanderung  ")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [name for name, _ in events] == ["understood", "token", "done"]
    assert events[1][1] == {"type": "token", "text": "Hallo "}
    assert seen[0][0] == "deps"
    assert seen[0][2] == "Wanderung"


def test_long_message_is_truncated(client, seen):
    post(client, "a" * 1500)
    assert len(seen[0][2]) == 1000


def test_rate_limit_returns_429(client, seen):
    for _ in range(10):
        assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    ((name, data),) = parse_sse(r.text)
    assert name == "error"
    assert data["message"] == RATE_LIMIT_REPLY.format(s=int(r.headers["retry-after"]))
    assert len(seen) == 10


def test_rate_limit_text_follows_the_request_language(client, seen):
    from hikesense.agent.texts import texts

    for _ in range(10):
        assert post(client).status_code == 200
    body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "en"}
    r = client.post("/chat", json=body, headers=bearer())
    assert r.status_code == 429
    ((_, data),) = parse_sse(r.text)
    assert data["message"] == texts("en").rate_limit_reply.format(s=int(r.headers["retry-after"]))
    assert "requests" in data["message"]
    # an unreadable body or an unknown language still gets the German text
    r = client.post("/chat", content=b"not json", headers=bearer())
    assert r.status_code == 429
    assert "Zu viele Anfragen" in parse_sse(r.text)[0][1]["message"]


def test_rate_limited_deeply_nested_body_is_still_429(client, seen):
    for _ in range(10):
        assert post(client).status_code == 200
    r = client.post("/chat", content=b"[" * 60000, headers=bearer())
    assert r.status_code == 429
    assert "Zu viele Anfragen" in parse_sse(r.text)[0][1]["message"]


def test_stream_failure_text_follows_the_request_language(settings, monkeypatch):
    def boom(deps, thread_id, message, user_hash=None, user_id=None, lang="de"):
        raise RuntimeError("x")
        yield

    monkeypatch.setattr(chat_api, "run_chat", boom)
    client = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "en"}
    r = client.post("/chat", json=body, headers=bearer())
    ((_, data),) = parse_sse(r.text)
    assert (
        data["message"]
        == "The planning assistant is not available right now. Please try again later."
    )


def test_rate_limit_per_user_not_ip(client, seen):
    for _ in range(10):
        assert post(client, headers=bearer("u1")).status_code == 200
    assert post(client, headers=bearer("u1")).status_code == 429
    assert post(client, headers=bearer("u2")).status_code == 200  # same IP, other user


def test_guest_without_token_can_chat(settings, seen):
    quota = FakeQuota()
    client = TestClient(create_app(settings, quota=quota, deps_factory=lambda: "deps"))
    r = client.post("/chat", json={"thread_id": str(uuid.uuid4()), "message": "x"})
    assert r.status_code == 200
    assert [name for name, _ in parse_sse(r.text)] == ["understood", "token", "done"]
    assert len(quota.keys) == 1 and users == [None]


def test_guest_limit_returns_429_with_guest_text(settings, seen):
    from hikesense.agent.texts import texts

    for reason in ("ip", "total"):
        client = TestClient(create_app(settings, quota=FakeQuota(False, reason), deps_factory=lambda: "deps"))
        body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "en"}
        r = client.post("/chat", json=body)
        assert r.status_code == 429 and int(r.headers["retry-after"]) == 3600
        ((name, data),) = parse_sse(r.text)
        assert name == "error"
        assert data["message"] == texts("en").guest_limit_reply
        assert data["code"] == "guest_limit"
    assert seen == []


def test_spoofed_forwarded_header_does_not_change_key(settings, seen):
    quota = FakeQuota()
    client = TestClient(create_app(settings, quota=quota, deps_factory=lambda: "deps"))
    for fake in ("1.1.1.1", "2.2.2.2"):
        body = {"thread_id": str(uuid.uuid4()), "message": "x"}
        client.post("/chat", json=body, headers={"X-Forwarded-For": f"{fake}, 198.51.100.4"})
    assert quota.keys[0] == quota.keys[1]  # without trusted proxies the header is ignored
    assert quota.keys[0] not in ("1.1.1.1", "2.2.2.2")


def test_trusted_proxy_entry_is_the_guest_key(settings, seen):
    quota = FakeQuota()
    trusted = settings.model_copy(update={"hikesense_trusted_proxy_hops": 1})
    client = TestClient(create_app(trusted, quota=quota, deps_factory=lambda: "deps"))
    body = {"thread_id": str(uuid.uuid4()), "message": "x"}
    client.post("/chat", json=body, headers={"X-Forwarded-For": "1.1.1.1, 198.51.100.4"})
    assert quota.keys == ["198.51.100.4"]


def test_signed_in_user_does_not_use_guest_quota(settings, seen):
    quota = FakeQuota(False)
    client = TestClient(create_app(settings, quota=quota, deps_factory=lambda: "deps"))
    assert post(client).status_code == 200
    assert quota.keys == []


def test_blocked_user_gets_403(settings, seen):
    client = TestClient(create_app(settings, status="gesperrt", deps_factory=lambda: "deps"))
    r = post(client)
    assert r.status_code == 403
    assert r.json() == {"detail": "account_blocked"}
    assert seen == []


def test_account_endpoint_reports_status(settings):
    ok = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    assert ok.get("/account", headers=bearer()).json() == {"status": "aktiv"}
    assert ok.get("/account").status_code == 401
    blocked = TestClient(create_app(settings, status="gesperrt", deps_factory=lambda: "deps"))
    r = blocked.get("/account", headers=bearer())
    assert r.status_code == 403 and r.json() == {"detail": "account_blocked"}


def test_invalid_token_401(client, seen):
    r = post(client, headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401 and r.json()["detail"] == "Bitte anmelden."
    assert post(client, headers={"Authorization": "Basic xyz"}).status_code == 401


def test_expired_token_401(client, seen):
    r = post(client, headers=bearer(exp_in=-10))
    assert r.status_code == 401 and "erneut anmelden" in r.json()["detail"]
    assert seen == []


def test_rejected_tokens_do_not_use_rate_limit(client, seen):
    for _ in range(12):
        assert post(client, headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    assert post(client).status_code == 200


def test_cors_allows_authorization_header(client):
    r = client.options(
        "/chat",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_failure_log_has_user_hash_and_id(settings, monkeypatch):
    def boom(deps, thread_id, message, user_hash=None, user_id=None, lang="de"):
        raise RuntimeError("x")
        yield

    monkeypatch.setattr(chat_api, "run_chat", boom)
    client = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    post(client, headers=bearer("user-secret-id"))
    raw = settings.chat_log_path.read_text()
    line = json.loads(raw)
    assert line["user_id"] == "user-secret-id"
    assert len(line["user_hash"]) == 12


def test_chat_passes_user_id_and_logs_no_token(settings, seen):
    settings = settings.model_copy(update={"openrouter_api_key": "sk-or-test-secret-key"})
    headers = bearer("user-42")
    r = post(TestClient(create_app(settings, deps_factory=lambda: "deps")), headers=headers)
    assert r.status_code == 200 and users == ["user-42"]

    def factory():
        raise ValueError("no key")

    client = TestClient(create_app(settings, deps_factory=factory))
    post(client, headers=headers)
    raw = settings.chat_log_path.read_text()
    assert json.loads(raw)["user_id"] == "user-42"
    token = headers["Authorization"].split(" ", 1)[1]
    assert token not in raw and settings.openrouter_api_key not in raw


def test_empty_message_422(client, seen):
    assert post(client, "   ").status_code == 422
    assert post(client, "").status_code == 422
    assert seen == []


def test_bad_thread_id_422(client):
    assert post(client, thread_id="nicht-uuid").status_code == 422


def test_health_reports_llm_and_knowledge(settings):
    body = TestClient(create_app(settings)).get("/health").json()
    assert body == {"status": "ok", "db": False, "llm": True, "knowledge": False, "auth": True}
    settings.chroma_dir.mkdir()
    (settings.chroma_dir / "chroma.sqlite3").write_bytes(b"x")
    body = TestClient(create_app(settings)).get("/health").json()
    assert body["knowledge"] is True
    no_key = settings.model_copy(update={"openrouter_api_key": None})
    assert TestClient(create_app(no_key)).get("/health").json()["llm"] is False


def test_cors_rejects_other_origin(client):
    ok = client.get("/health", headers={"Origin": ORIGIN})
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    bad = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_unexpected_error_becomes_error_event_and_log(settings, monkeypatch, caplog):
    def boom(deps, thread_id, message, user_hash=None, user_id=None, lang="de"):
        yield TokenEvent(text="x")
        raise RuntimeError("secret db password")

    monkeypatch.setattr(chat_api, "run_chat", boom)
    client = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    with caplog.at_level(logging.ERROR):
        r = post(client)
    events = parse_sse(r.text)
    assert events[-1] == ("error", {"type": "error", "message": ERROR_UNAVAILABLE, "code": None})
    assert "secret" not in r.text
    line = json.loads(settings.chat_log_path.read_text().splitlines()[-1])
    assert line["error"] == "RuntimeError"
    assert "secret" not in json.dumps(line)
    assert "secret db password" in caplog.text  # traceback stays server-side


def test_deps_factory_failure_becomes_error_event(settings, seen):
    def factory():
        raise ValueError("no key")

    client = TestClient(create_app(settings, deps_factory=factory))
    events = parse_sse(post(client).text)
    assert events == [("error", {"type": "error", "message": ERROR_UNAVAILABLE, "code": None})]
    line = json.loads(settings.chat_log_path.read_text())
    assert line["error"] == "ValueError"
    assert line["message"] and "llm_calls" in line  # a new line, not mistaken for an old one
    assert "no key" not in json.dumps(line)


def test_oversized_body_is_rejected_before_parsing(client, seen):
    big = {"thread_id": str(uuid.uuid4()), "message": "a" * (70 * 1024)}
    r = client.post("/chat", json=big, headers=bearer())
    assert r.status_code == 413
    assert seen == []


def test_jwks_outage_is_503_not_401(settings, monkeypatch):
    from hikesense.auth import AuthError

    def down(token, settings):
        raise AuthError("unavailable")

    monkeypatch.setattr(auth_api, "verify_token", down)
    client = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    r = post(client)
    assert r.status_code == 503
    assert "gleich noch einmal" in r.json()["detail"]


def test_stream_is_not_buffered_by_proxies(client, seen):
    # the web app proxies /api/chat (Next rewrite): no compression, no proxy buffering
    r = post(client)
    assert r.status_code == 200
    assert "no-transform" in r.headers["cache-control"]
    assert "no-cache" in r.headers["cache-control"]
    assert r.headers["x-accel-buffering"] == "no"


def test_lang_is_accepted_and_defaults_to_de(client, seen):
    body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "en"}
    assert client.post("/chat", json=body, headers=bearer()).status_code == 200
    assert post(client).status_code == 200
    assert chat_api.ChatRequest(thread_id=uuid.uuid4(), message="x").lang == "de"


def test_unknown_lang_422(client, seen):
    body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "fr"}
    assert client.post("/chat", json=body, headers=bearer()).status_code == 422
    assert seen == []


def test_lang_is_passed_on_to_run_chat(client, seen):
    body = {"thread_id": str(uuid.uuid4()), "message": "Hi", "lang": "en"}
    assert client.post("/chat", json=body, headers=bearer()).status_code == 200
    assert post(client).status_code == 200
    assert langs == ["en", "de"]
