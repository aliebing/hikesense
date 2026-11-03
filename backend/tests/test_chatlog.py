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
