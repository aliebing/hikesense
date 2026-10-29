"""Backend -> web event contract: real graph events, serialised by the real SSE API, are the
fixture the web tests parse and render (web/src/lib/__fixtures__/chat-streams.json).

Regenerate after an intended protocol change: HIKEALL_UPDATE_FIXTURES=1 uv run pytest tests/test_contract.py
"""

import json
import os
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from test_agent_graph import (  # noqa: F401 (vocab is a fixture)
    FELDBERG_MSG,
    HIT,
    SourcedTools,
    feldberg_raw,
    knowledge_raw,
    make,
    raw,
    vocab,
)

from hikeall.agent.request import RawRequest
from hikeall.api.app import create_app
from hikeall.config import Settings
from hikeall.llm.gateway import LLMUnavailable

FIXTURE = Path(__file__).resolve().parents[2] / "web/src/lib/__fixtures__/chat-streams.json"


def _stream(settings, deps, *messages) -> str:
    client = TestClient(create_app(settings, deps_factory=lambda: deps))
    thread = str(uuid.uuid4())
    text = ""
    for m in messages:
        r = client.post("/chat", json={"thread_id": thread, "message": m})
        assert r.status_code == 200
        text = r.text  # the last message's stream
    return text


def _streams(vocab, tmp_path) -> dict[str, str]:  # noqa: F811
    settings = Settings(
        supabase_db_url="postgresql://unused",
        chat_log_path=tmp_path / "chat.jsonl",
        chroma_dir=tmp_path / "chroma",
        openrouter_api_key="k",
    )

    def deps(**kw):
        return make(vocab, settings, tools=SourcedTools(hits=[HIT]), **kw)

    fallback = deps(
        structured={RawRequest: [feldberg_raw()]},
        answers=["Der Seebuck-Weg hat 9 km, die Feldberg-Runde 16,2 km."],
    )
    area = deps(structured={RawRequest: [raw(start_text="Nordschwarzwald")]}, answers=["Gut."])
    clarify = deps(structured={RawRequest: [raw(start_text="Feldberg", roundtrip=True)]})
    knowledge = deps(
        structured={RawRequest: [knowledge_raw()]},
        tool_rounds=[AIMessage(content="Im Naturschutzgebiet gilt ein Wegegebot.")],
    )
    error = deps(structured={RawRequest: [LLMUnavailable("x")]})
    return {
        "fallback": _stream(settings, fallback, FELDBERG_MSG),
        "area": _stream(settings, area, "Tour im Nordschwarzwald"),
        "clarify": _stream(settings, clarify, "Rundweg am Feldberg"),
        "knowledge": _stream(settings, knowledge, "Darf man am Feldberg querfeldein gehen?"),
        "error": _stream(settings, error, FELDBERG_MSG),
    }


def test_web_fixture_matches_the_backend_stream(vocab, tmp_path):  # noqa: F811
    streams = _streams(vocab, tmp_path)
    for name, text in streams.items():  # every stream ends with done or error
        assert '"type":"done"' in text or '"type":"error"' in text, name
    rendered = json.dumps(streams, ensure_ascii=False, indent=2) + "\n"
    if os.environ.get("HIKEALL_UPDATE_FIXTURES"):
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(rendered, encoding="utf-8")
    assert FIXTURE.exists(), "Fixture fehlt: HIKEALL_UPDATE_FIXTURES=1 setzen"
    assert FIXTURE.read_text(encoding="utf-8") == rendered, (
        "Backend-Ereignisse weichen vom Web-Fixture ab: HIKEALL_UPDATE_FIXTURES=1 setzen und "
        "die Web-Tests laufen lassen"
    )
