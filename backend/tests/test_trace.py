import json
from datetime import date

import pytest
from langchain_core.messages import AIMessage

from hikeall import trace
from hikeall.agent.request import RawRequest
from hikeall.llm.gateway import FakeGateway


def test_record_llm_without_trace_is_noop():
    trace.record_llm("answer", "m", [], "x", None, 1)  # no error, nothing to see


def test_traced_collects_llm_call_with_usage():
    reply = AIMessage(content="Hallo", usage_metadata={"input_tokens": 10, "output_tokens": 3, "total_tokens": 13},
                      response_metadata={"token_usage": {"cost": 0.0012}})
    with trace.traced() as t:
        trace.record_llm("answer", "gpt-x", [{"role": "user", "content": "hi"}], "Hallo", reply, 42)
    assert t.llm_calls == [{"step": "answer", "model": "gpt-x", "messages": [{"role": "user", "content": "hi"}],
                            "output": "Hallo", "output_truncated": False, "input_tokens": 10, "output_tokens": 3, "cost_usd": 0.0012, "duration_ms": 42}]


def test_cost_missing_stays_none():
    reply = AIMessage(content="x", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})
    with trace.traced() as t:
        trace.record_llm("answer", None, [], "x", reply, 0)
    assert t.llm_calls[0]["cost_usd"] is None


def test_traced_tools_records_call_and_result():
    class T:
        def add(self, a, b=0): return {"sum": a + b}
    with trace.traced() as t:
        assert trace.TracedTools(T()).add(1, b=2) == {"sum": 3}
    call = t.tool_calls[0]
    assert call["name"] == "add" and call["args"] == {"arg0": 1, "b": 2}
    assert json.loads(call["result"]) == {"sum": 3} and call["truncated"] is False and call["error"] is None


def test_traced_tools_truncates_large_result():
    class T:
        def big(self): return "x" * 50_000
    with trace.traced() as t:
        trace.TracedTools(T()).big()
    assert len(t.tool_calls[0]["result"]) == trace.TOOL_RESULT_MAX_CHARS and t.tool_calls[0]["truncated"] is True


def test_traced_tools_records_error_class_and_reraises():
    class T:
        def bad(self): raise ValueError("geheim")
    with trace.traced() as t, pytest.raises(ValueError):
        trace.TracedTools(T()).bad()
    assert t.tool_calls[0]["error"] == "ValueError" and "geheim" not in json.dumps(t.tool_calls)


def test_to_jsonable_handles_sets_dates_dataclasses():
    assert trace.to_jsonable({"t": {"b", "a"}, "d": date(2026, 11, 2)}) == {"t": ["a", "b"], "d": "2026-11-02"}


def test_fake_gateway_records_steps():
    gw = FakeGateway(structured={RawRequest: [RawRequest(intent="other")]}, answers=["A"])
    with trace.traced() as t:
        gw.structured(RawRequest, "SYS", "USER")
        gw.answer("SYS2", "USER2")
    assert [c["step"] for c in t.llm_calls] == ["understand", "answer"]
    assert t.llm_calls[0]["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert t.llm_calls[1]["output"] == "A"


def test_llm_prompts_and_text_output_are_cut_and_flagged():
    big = "x" * (trace.TOOL_RESULT_MAX_CHARS + 5)
    with trace.traced() as t:
        trace.record_llm("answer", "m", [{"role": "user", "content": big}, {"role": "system", "content": "kurz"}],
                         big, None, 1)
    call = t.llm_calls[0]
    assert len(call["messages"][0]["content"]) == trace.TOOL_RESULT_MAX_CHARS
    assert call["messages"][0]["truncated"] is True
    assert "truncated" not in call["messages"][1]
    assert len(call["output"]) == trace.TOOL_RESULT_MAX_CHARS and call["output_truncated"] is True


def test_short_llm_call_is_not_flagged_and_react_content_is_cut():
    with trace.traced() as t:
        trace.record_llm("answer", "m", [], "ok", None, 1)
        trace.record_llm("react", "m", [], {"content": "y" * 30_000, "tool_calls": []}, None, 1)
    assert t.llm_calls[0]["output_truncated"] is False
    assert len(t.llm_calls[1]["output"]["content"]) == trace.TOOL_RESULT_MAX_CHARS
    assert t.llm_calls[1]["output_truncated"] is True


def test_traced_tools_no_pydantic_serializer_warning():
    import warnings

    from pydantic import BaseModel

    class Res(BaseModel):
        actual: float | bool | None = None

    class T:
        def go(self):
            return Res.model_construct(actual=3)  # int in a float | bool field

    with trace.traced() as t, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        trace.TracedTools(T()).go()
    assert caught == []
    assert json.loads(t.tool_calls[0]["result"]) == {"actual": 3}
