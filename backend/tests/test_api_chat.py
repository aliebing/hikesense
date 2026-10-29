import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from hikeall.agent.graph import DoneEvent, TokenEvent, UnderstoodEvent
from hikeall.agent.prompts import ERROR_UNAVAILABLE
from hikeall.agent.request import HikeRequest
from hikeall.api import chat as chat_api
from hikeall.api.app import create_app
from hikeall.config import Settings
from hikeall.guard import RATE_LIMIT_REPLY
from hikeall.llm.usage import LLMUsage

ORIGIN = "http://localhost:3000"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        chat_log_path=tmp_path / "chat.jsonl",
        chroma_dir=tmp_path / "chroma",
        openrouter_api_key="k",
    )


@pytest.fixture
def seen(monkeypatch):
    calls = []

    def fake_run_chat(deps, thread_id, message):
        calls.append((deps, thread_id, message))
        yield UnderstoodEvent(text="Tagestour", request=HikeRequest(intent="day_hike"))
        yield TokenEvent(text="Hallo ")
        yield DoneEvent(usage=LLMUsage(), unsupported=0)

    monkeypatch.setattr(chat_api, "run_chat", fake_run_chat)
    return calls


@pytest.fixture
def client(settings, seen):
    return TestClient(create_app(settings, deps_factory=lambda: "deps"))


def post(client, message="Wanderung", thread_id=None, **kw):
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


def test_empty_message_422(client, seen):
    assert post(client, "   ").status_code == 422
    assert post(client, "").status_code == 422
    assert seen == []


def test_bad_thread_id_422(client):
    assert post(client, thread_id="nicht-uuid").status_code == 422


def test_health_reports_llm_and_knowledge(settings):
    body = TestClient(create_app(settings)).get("/health").json()
    assert body == {"status": "ok", "db": False, "llm": True, "knowledge": False}
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
    def boom(deps, thread_id, message):
        yield TokenEvent(text="x")
        raise RuntimeError("secret db password")

    monkeypatch.setattr(chat_api, "run_chat", boom)
    client = TestClient(create_app(settings, deps_factory=lambda: "deps"))
    with caplog.at_level(logging.ERROR):
        r = post(client)
    events = parse_sse(r.text)
    assert events[-1] == ("error", {"type": "error", "message": ERROR_UNAVAILABLE})
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
    assert events == [("error", {"type": "error", "message": ERROR_UNAVAILABLE})]
    assert json.loads(settings.chat_log_path.read_text())["error"] == "ValueError"


def test_oversized_body_is_rejected_before_parsing(client, seen):
    big = {"thread_id": str(uuid.uuid4()), "message": "a" * (70 * 1024)}
    r = client.post("/chat", json=big)
    assert r.status_code == 413
    assert seen == []
