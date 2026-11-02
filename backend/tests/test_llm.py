import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from hikeall.chatlog import ChatLogEntry
from hikeall.chatlog import write as write_chatlog
from hikeall.config import Settings
from hikeall.llm.gateway import (
    BudgetExceeded,
    FakeGateway,
    LLMBadOutput,
    LLMError,
    LLMUnavailable,
    OpenRouterGateway,
)
from hikeall.llm.usage import metered, record_usage


def test_usage_sums_openrouter_cost():
    with metered() as u:
        record_usage(
            AIMessage(
                "x",
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"token_usage": {"cost": 0.001}},
            )
        )
        record_usage(
            AIMessage(
                "y", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
            )
        )
    assert u.cost_usd == 0.001 and u.calls_without_cost == 1 and u.calls == 2
    assert u.input_tokens == 11 and u.output_tokens == 6


def test_record_usage_outside_metered_is_noop():
    record_usage(AIMessage("x"))


def test_budget_exceeded_when_cost_over_limit():
    msg = AIMessage("x", response_metadata={"token_usage": {"cost": 0.06}})
    with metered(max_cost_usd=0.05), pytest.raises(BudgetExceeded):
        record_usage(msg)


def test_budget_not_exceeded_at_limit():
    msg = AIMessage("x", response_metadata={"token_usage": {"cost": 0.05}})
    with metered(max_cost_usd=0.05) as u:
        record_usage(msg)
    assert u.cost_usd == 0.05


def test_error_hierarchy():
    for cls in (LLMUnavailable, LLMBadOutput, BudgetExceeded):
        assert issubclass(cls, LLMError)


def test_missing_key_raises_unavailable():
    settings = Settings(supabase_db_url="x", openrouter_api_key=None, _env_file=None)
    with pytest.raises(LLMUnavailable, match="OPENROUTER_API_KEY fehlt"):
        OpenRouterGateway.from_settings(settings)


def test_settings_defaults():
    s = Settings(supabase_db_url="x", _env_file=None)
    assert s.hikeall_model == "openai/gpt-4o-mini"
    assert s.max_tool_calls == 8 and s.max_cost_usd == 0.05
    assert s.chat_log_path.name == "chat.jsonl" and s.chat_log_path.parent.name == "logs"


def test_gateway_from_settings_configures_openrouter():
    s = Settings(supabase_db_url="x", openrouter_api_key="k-test", _env_file=None)
    gw = OpenRouterGateway.from_settings(s)
    assert isinstance(gw, OpenRouterGateway)


def test_temperature_is_sent_when_set():
    base = Settings(supabase_db_url="x", openrouter_api_key="k-test", _env_file=None)
    assert base.hikeall_temperature is None
    default = OpenRouterGateway.from_settings(base)
    assert (default._structured_model.temperature, default._answer_model.temperature) == (0.0, 0.3)
    s = Settings(
        supabase_db_url="x", openrouter_api_key="k-test", hikeall_temperature=0.7, _env_file=None
    )
    gw = OpenRouterGateway.from_settings(s)
    assert gw._structured_model.temperature == 0.7 and gw._answer_model.temperature == 0.7


class Out(BaseModel):
    n: int


def test_fake_gateway_returns_in_order_and_counts():
    tool_msg = AIMessage("t")
    gw = FakeGateway(
        structured={Out: [Out(n=1), Out(n=2)]}, answers=["a", "b"], tool_rounds=[tool_msg]
    )
    assert gw.structured(Out, "s", "u").n == 1
    assert gw.structured(Out, "s", "u").n == 2
    assert gw.answer("s", "u") == "a"
    assert gw.answer("s", "u") == "b"
    assert gw.tool_round([], []) is tool_msg
    assert gw.calls == {"structured": 2, "answer": 2, "tool_round": 1}


def test_fake_gateway_exhausted_raises():
    gw = FakeGateway()
    with pytest.raises(LLMBadOutput):
        gw.answer("s", "u")


def test_chatlog_fields(tmp_path):
    path = tmp_path / "logs" / "chat.jsonl"
    entry = ChatLogEntry(
        request_id="r1",
        intent="search",
        activity="hiking",
        tool_calls=2,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.001,
        calls_without_cost=0,
        grounding_unsupported=0,
        guard=None,
        error=None,
    )
    write_chatlog(path, entry)
    write_chatlog(path, entry)
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert set(row) == {
        "ts", "request_id", "user_hash", "intent", "activity", "tool_calls", "input_tokens",
        "output_tokens", "cost_usd", "calls_without_cost", "grounding_unsupported",
        "grounding_unsupported_names", "unsat_claims_removed",
        "guard", "discarded_model_numbers", "error",
        "user_id", "message", "previous_messages", "request", "answer", "fallback_reason",
        "candidates", "plan", "weather_days", "llm_calls", "tools", "duration_ms",
    }  # fmt: skip
    assert not any(k in row for k in ("password", "token", "jwt", "api_key"))
    assert row["request_id"] == "r1"


class _Stub:
    """Stands in for ChatOpenAI: returns one prepared reply, no network."""

    def __init__(self, reply, name="stub-model"):
        self.model_name = name
        self._reply = reply

    def with_structured_output(self, schema, include_raw=False):
        return self

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self._reply


def _reply(content, cost):
    return AIMessage(
        content=content,
        usage_metadata={"input_tokens": 11, "output_tokens": 4, "total_tokens": 15},
        response_metadata={"token_usage": {"cost": cost}},
    )


def test_openrouter_gateway_traces_every_call_kind():
    from hikeall import trace
    from hikeall.agent.request import RawRequest

    raw = _reply("", 0.001)
    structured = _Stub({"raw": raw, "parsed": RawRequest(intent="knowledge")}, "m-struct")
    structured.root_client = type("RC", (), {})()

    class _Completions:
        @staticmethod
        def create(**kw):
            class R:
                @staticmethod
                def model_dump():
                    return {
                        "choices": [{"message": {"content": "web text"}}],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9, "cost": 0.005},
                    }

            return R()

    structured.root_client.chat = type("C", (), {"completions": _Completions()})()
    # the tool round shares the structured model: give it its own reply via bind_tools
    tool_reply = _reply("denke", 0.002)
    structured.bind_tools = lambda tools: _Stub(tool_reply, "m-struct")
    answer = _Stub(_reply("Antwort", 0.003), "m-answer")
    gw = OpenRouterGateway(structured_model=structured, answer_model=answer)

    with trace.traced() as t:
        gw.structured(RawRequest, "sys", "usr")
        gw.answer("sys", "usr")
        gw.tool_round([HumanMessage("hi")], [])
        gw.web_completion("suche", {"id": "web"})

    got = [(c["step"], c["model"], c["input_tokens"], c["output_tokens"], c["cost_usd"]) for c in t.llm_calls]
    assert got == [
        ("understand", "m-struct", 11, 4, 0.001),
        ("answer", "m-answer", 11, 4, 0.003),
        ("react", "m-struct", 11, 4, 0.002),
        ("web_search", "m-struct", 7, 2, 0.005),
    ]
    assert t.llm_calls[1]["output"] == "Antwort"
    assert t.llm_calls[0]["messages"][1] == {"role": "user", "content": "usr"}
