import json

from hikesense import chatlog
from hikesense.chatlog import ChatLogEntry


def test_log_has_user_hash_not_id(tmp_path):
    path = tmp_path / "chat.jsonl"
    h = chatlog.hash_user("u1")
    chatlog.write(path, ChatLogEntry(request_id="r", user_hash=h))
    raw = path.read_text()
    assert len(json.loads(raw)["user_hash"]) == 12
    assert '"u1"' not in raw
    assert h == chatlog.hash_user("u1") != chatlog.hash_user("u2")


OLD_LINE = (
    '{"ts":"2026-10-29T17:25:17+00:00","request_id":"728525451cc74439bb38baf51e19a71e",'
    '"intent":"day_hike","activity":"hike","tool_calls":1,"input_tokens":1513,'
    '"output_tokens":327,"cost_usd":0.00042314999999999996,"calls_without_cost":0,'
    '"grounding_unsupported":0,"guard":null,"error":null}'
)


def test_old_line_still_parses():
    entry = ChatLogEntry.model_validate_json(OLD_LINE)
    assert entry.message is None and entry.candidates == []
    assert entry.user_id is None and entry.llm_calls == [] and entry.tools == []


def test_prune_drops_entries_older_than_the_retention(tmp_path):
    import json
    from datetime import UTC, datetime

    from hikesense.chatlog import prune

    p = tmp_path / "chat.jsonl"
    now = datetime(2026, 12, 10, 12, 0, tzinfo=UTC)
    rows = [
        {"request_id": "old", "ts": "2026-11-01T10:00:00+00:00"},
        {"request_id": "naive-old", "ts": "2026-11-09T10:00:00"},  # older lines have no zone
        {"request_id": "edge", "ts": "2026-11-10T12:00:01+00:00"},
        {"request_id": "new", "ts": "2026-12-09T08:00:00+00:00"},
    ]
    p.write_text("".join(json.dumps(r) + "\n" for r in rows) + "kaputt\n")
    assert prune(p, days=30, now=now) == 3  # two too old, one unreadable line
    kept = [json.loads(line)["request_id"] for line in p.read_text().splitlines()]
    assert kept == ["edge", "new"]


def test_prune_without_file_does_nothing(tmp_path):
    from hikesense.chatlog import prune

    assert prune(tmp_path / "missing.jsonl", days=30) == 0


def test_app_prunes_the_chat_log_at_startup(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from hikesense.api.app import create_app
    from hikesense.config import Settings

    log = tmp_path / "chat.jsonl"
    log.write_text(json.dumps({"request_id": "alt", "ts": "2020-01-01T00:00:00+00:00"}) + "\n")
    s = Settings(
        supabase_db_url="postgresql://x:x@127.0.0.1:1/none",
        chat_log_path=log,
        chroma_dir=tmp_path / "chroma",
    )
    with TestClient(
        create_app(
            s, deps_factory=lambda: "deps", guest_quota=object(), status_lookup=lambda u: "aktiv"
        )
    ):
        pass
    assert log.read_text() == ""
