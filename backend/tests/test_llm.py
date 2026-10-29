import json

import pytest
from langchain_core.messages import AIMessage
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


def test_chatlog_has_no_message_text(tmp_path):
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
        "ts", "request_id", "intent", "activity", "tool_calls", "input_tokens",
        "output_tokens", "cost_usd", "calls_without_cost", "grounding_unsupported",
        "guard", "discarded_model_numbers", "error",
    }  # fmt: skip
    assert not any(k in row for k in ("message", "text", "content", "answer"))
    assert row["request_id"] == "r1"
