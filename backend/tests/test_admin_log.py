import json

from hikeall.admin_log import UNKNOWN, LogReader, detail, owner_of, searches, summary, users
from hikeall.chatlog import hash_user
from hikeall.roles import Profile

P1 = Profile(user_id="11111111-1111-1111-1111-111111111111", email="a@x.de", role="admin")
P2 = Profile(user_id="22222222-2222-2222-2222-222222222222", email="b@x.de", role="user")

OLD = {
    "ts": "2026-10-29T17:25:17+00:00", "request_id": "old1", "intent": "day_hike",
    "activity": "hike", "tool_calls": 1, "input_tokens": 1513, "output_tokens": 327,
    "cost_usd": 0.00042, "calls_without_cost": 0, "grounding_unsupported": 0,
    "guard": None, "error": None,
}


def _row(i, **kw):
    base = {"ts": f"2026-11-0{i}T10:00:00+00:00", "request_id": f"r{i}", "input_tokens": 1,
            "output_tokens": 2, "cost_usd": 0.5, "calls_without_cost": 0}
    return {**base, **kw}


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_missing_file_gives_no_entries(tmp_path):
    assert LogReader(tmp_path / "none.jsonl").entries() == []


def test_broken_and_partial_lines_are_skipped(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text(json.dumps(OLD) + '\n{"request_id": \n[]\n{"ts": "x"}\n')
    assert len(LogReader(f).entries()) == 1


def test_reader_reloads_after_append(tmp_path):
    f = tmp_path / "c.jsonl"
    _write(f, [_row(1)])
    r = LogReader(f)
    assert len(r.entries()) == 1
    with f.open("a") as h:
        h.write(json.dumps(_row(2)) + "\n")
    got = r.entries()
    assert [e["request_id"] for e in got] == ["r2", "r1"]


def test_owner_by_user_id_then_hash_then_unknown():
    profiles = [P1, P2]
    rows = [
        {"user_id": P1.user_id},
        {"user_hash": hash_user(P2.user_id)},
        {"user_hash": "deadbeef0000"},
    ]
    assert [owner_of(r, profiles) for r in rows] == [P1.user_id, P2.user_id, UNKNOWN]
    assert owner_of({}, profiles) == UNKNOWN


def test_old_line_summary_has_dashes():
    s = summary(OLD, UNKNOWN, None)
    assert s["message"] is None and s["hits"] is None and s["detailed"] is False
    assert s["tokens"] == 1513 + 327
    assert s["fallback"] is False


def test_new_line_summary_hits_and_fallback():
    e = _row(1, message="hi", intent="day_hike", candidates=[
        {"status": "shown"}, {"status": "fallback"}, {"status": "rejected"}], duration_ms=7,
        llm_calls=[], tools=[{"name": "search_day_hikes"}])
    s = summary(e, P1.user_id, P1.email)
    assert s["hits"] == 2 and s["fallback"] is True and s["detailed"] is True
    assert s["duration_ms"] == 7
    assert summary({**e, "intent": "knowledge", "tools": []}, "o", None)["hits"] is None
    assert summary({**e, "candidates": [], "fallback_reason": "x"}, "o", None)["fallback"] is True


def test_cost_unknown_when_not_reported():
    e = _row(1, cost_usd=0.0, calls_without_cost=2)
    assert summary(e, "o", None)["cost_usd"] is None
    res = searches([e, _row(2, cost_usd=0.25)], [], None, 0, 10)
    assert res["sums"]["cost_usd"] == 0.25


def test_searches_filter_paging_and_sums():
    es = [_row(i, user_id=P1.user_id, duration_ms=10 * i) for i in (1, 2, 3)]
    es.append(_row(4, user_id=P2.user_id))
    res = searches(es, [P1, P2], P1.user_id, 1, 1)
    assert len(res["items"]) == 1
    assert res["total"] == 3 and res["sums"]["count"] == 3
    assert res["sums"]["cost_usd"] == 1.5
    assert res["sums"]["avg_duration_ms"] == 20


def test_users_counts_and_unknown_row():
    es = [_row(1, user_id=P2.user_id), _row(2, user_id=P2.user_id), _row(3, user_id=P1.user_id), _row(4)]
    got = users(es, [P1, P2])
    assert [(u["email"], u["searches"]) for u in got] == [("b@x.de", 2), ("a@x.de", 1), (None, 1)]
    assert got[-1]["user_id"] == UNKNOWN and got[-1]["role"] is None
    assert users([], [P1])[-1]["user_id"] == P1.user_id


def test_detail_unknown_id_is_none():
    assert detail([_row(1)], [], "nope") is None
    d = detail([_row(1, user_id=P1.user_id)], [P1], "r1")
    assert d["owner"] == P1.user_id and d["email"] == "a@x.de" and d["request_id"] == "r1"


def test_hits_only_when_a_day_hike_search_ran():
    cands = [{"status": "shown"}, {"status": "fallback"}]
    ran = _row(1, message="m", intent="day_hike", candidates=cands, tools=[{"name": "search_day_hikes"}])
    assert summary(ran, "o", None)["hits"] == 2
    clarify = _row(2, message="m", intent="day_hike", candidates=[], tools=[])
    assert summary(clarify, "o", None)["hits"] is None
    trail = _row(3, message="m", intent="day_hike", candidates=cands, tools=[{"name": "get_trail"}])
    assert summary(trail, "o", None)["hits"] is None
    none_found = _row(4, message="m", intent="day_hike", candidates=[], tools=[{"name": "search_day_hikes"}])
    assert summary(none_found, "o", None)["hits"] == 0


def test_detailed_follows_llm_calls_key():
    error_line = _row(1, message="Hallo", error="ValueError", llm_calls=[], tools=[])
    assert summary(error_line, "o", None)["detailed"] is True
    assert summary(_row(2), "o", None)["detailed"] is False


def test_sum_cost_is_none_when_no_cost_reported():
    es = [_row(1, cost_usd=0.0, calls_without_cost=1), _row(2, cost_usd=None)]
    assert searches(es, [], None, 0, 10)["sums"]["cost_usd"] is None
    assert searches([*es, _row(3, cost_usd=0.0)], [], None, 0, 10)["sums"]["cost_usd"] == 0.0
