"""LLM gateway: OpenRouter via ChatOpenAI, plus a scripted fake for tests."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from hikeall.config import Settings
from hikeall.llm.usage import (
    BudgetExceeded,
    LLMBadOutput,
    LLMError,
    LLMUnavailable,
    record_usage,
)

__all__ = [
    "BudgetExceeded",
    "FakeGateway",
    "LLMBadOutput",
    "LLMError",
    "LLMGateway",
    "LLMUnavailable",
    "OpenRouterGateway",
]

T = TypeVar("T", bound=BaseModel)

_BASE_URL = "https://openrouter.ai/api/v1"
_TIMEOUT_S = 30


class LLMGateway(Protocol):
    def structured(self, schema: type[T], system: str, user: str) -> T: ...

    def answer(self, system: str, user: str) -> str: ...

    def tool_round(self, messages: Sequence[BaseMessage], tools: Sequence[Any]) -> AIMessage: ...


class OpenRouterGateway:
    def __init__(self, structured_model: ChatOpenAI, answer_model: ChatOpenAI) -> None:
        self._structured_model = structured_model
        self._answer_model = answer_model

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenRouterGateway:
        if not settings.openrouter_api_key:
            raise LLMUnavailable("OPENROUTER_API_KEY fehlt")

        def make(temperature: float) -> ChatOpenAI:
            return ChatOpenAI(
                base_url=_BASE_URL,
                api_key=settings.openrouter_api_key,
                model=settings.hikeall_model,
                temperature=temperature,
                timeout=_TIMEOUT_S,
                max_retries=1,
                extra_body={"usage": {"include": True}},
            )

        return cls(structured_model=make(0.0), answer_model=make(0.3))

    def structured(self, schema: type[T], system: str, user: str) -> T:
        messages = [SystemMessage(system), HumanMessage(user)]
        try:
            runnable = self._structured_model.with_structured_output(schema, include_raw=True)
            result = runnable.invoke(messages)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMUnavailable(f"{type(exc).__name__}") from exc
        record_usage(result.get("raw"))
        parsed = result.get("parsed")
        if not isinstance(parsed, schema):
            raise LLMBadOutput("Ungültige strukturierte Ausgabe")
        return parsed

    def answer(self, system: str, user: str) -> str:
        message = self._invoke(self._answer_model, [SystemMessage(system), HumanMessage(user)])
        text = message.content
        if not isinstance(text, str) or not text.strip():
            raise LLMBadOutput("Leere Antwort")
        return text

    def tool_round(self, messages: Sequence[BaseMessage], tools: Sequence[Any]) -> AIMessage:
        model = self._structured_model.bind_tools(list(tools))
        return self._invoke(model, list(messages))

    @staticmethod
    def _invoke(model: Any, messages: list[BaseMessage]) -> AIMessage:
        try:
            message = model.invoke(messages)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMUnavailable(f"{type(exc).__name__}") from exc
        record_usage(message)
        return message


class FakeGateway:
    """Returns prepared replies in order and counts calls. For agent tests (no network)."""

    def __init__(
        self,
        structured: dict[type, list] | None = None,
        answers: list[str] | None = None,
        tool_rounds: list[AIMessage] | None = None,
    ) -> None:
        self._structured = {k: list(v) for k, v in (structured or {}).items()}
        self._answers = list(answers or [])
        self._tool_rounds = list(tool_rounds or [])
        self.calls: Counter[str] = Counter()

    def structured(self, schema: type[T], system: str, user: str) -> T:
        self.calls["structured"] += 1
        queue = self._structured.get(schema)
        if not queue:
            raise LLMBadOutput(f"FakeGateway: keine Antwort für {schema.__name__}")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def answer(self, system: str, user: str) -> str:
        self.calls["answer"] += 1
        if not self._answers:
            raise LLMBadOutput("FakeGateway: keine Antwort")
        item = self._answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def tool_round(self, messages: Sequence[BaseMessage], tools: Sequence[Any]) -> AIMessage:
        self.calls["tool_round"] += 1
        if not self._tool_rounds:
            raise LLMBadOutput("FakeGateway: keine Tool-Runde")
        item = self._tool_rounds.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
