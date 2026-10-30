import json

from hikeall import chatlog
from hikeall.chatlog import ChatLogEntry


def test_log_has_user_hash_not_id(tmp_path):
    path = tmp_path / "chat.jsonl"
    h = chatlog.hash_user("u1")
    chatlog.write(path, ChatLogEntry(request_id="r", user_hash=h))
    raw = path.read_text()
    assert len(json.loads(raw)["user_hash"]) == 12
    assert '"u1"' not in raw
    assert h == chatlog.hash_user("u1") != chatlog.hash_user("u2")
