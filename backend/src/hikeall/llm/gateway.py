"""LLM gateway: OpenRouter via ChatOpenAI, plus a scripted fake for tests."""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Sequence
from typing import Any, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from hikeall import trace
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

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_BASE_URL = "https://openrouter.ai/api/v1"
_TIMEOUT_S = 30
_WEB_MAX_TOKENS = 300  # the text is not used, only the url_citation annotations


def _structured_step(schema: type) -> str:
    # Compared by name: importing RawRequest here would be circular (agent -> llm).
    return "understand" if schema.__name__ == "RawRequest" else f"structured:{schema.__name__}"


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _record(step, model, messages, output, reply, duration_ms) -> None:
    """Trace one call; recording must never break the request."""
    try:
        trace.record_llm(step, model, messages, output, reply, duration_ms)
    except Exception:
        log.exception("Trace: LLM-Aufruf konnte nicht aufgezeichnet werden")


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

        def make(default: float) -> ChatOpenAI:
            override = settings.hikeall_temperature
            temperature = default if override is None else override
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
        started = time.monotonic()
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
        _record(
            _structured_step(schema),
            self._structured_model.model_name,
            trace.message_dicts(messages),
            parsed.model_dump(mode="json"),
            result.get("raw"),
            _ms(started),
        )
        return parsed

    def answer(self, system: str, user: str) -> str:
        messages = [SystemMessage(system), HumanMessage(user)]
        started = time.monotonic()
        message = self._invoke(self._answer_model, messages)
        text = message.content
        if not isinstance(text, str) or not text.strip():
            raise LLMBadOutput("Leere Antwort")
        _record(
            "answer",
            self._answer_model.model_name,
            trace.message_dicts(messages),
            text,
            message,
            _ms(started),
        )
        return text

    def tool_round(self, messages: Sequence[BaseMessage], tools: Sequence[Any]) -> AIMessage:
        # Uses the structured model (temperature 0), so a knowledge answer the model writes in a
        # tool round is generated at 0, not at the 0.3 of answer(). Deliberate: same facts, less
        # variation (final review Minor 11).
        model = self._structured_model.bind_tools(list(tools))
        started = time.monotonic()
        message = self._invoke(model, list(messages))
        _record(
            "react",
            self._structured_model.model_name,
            trace.message_dicts(messages),
            trace.ai_output(message),
            message,
            _ms(started),
        )
        return message

    def web_completion(self, user: str, plugin: dict) -> dict:
        """One completion with an OpenRouter plugin (the web search). LangChain drops the
        message annotations that carry the search hits, so this goes through the OpenAI client
        of the same model; the reported cost (search included) is metered like every call."""
        model = self._structured_model
        started = time.monotonic()
        try:
            response = model.root_client.chat.completions.create(
                model=model.model_name,
                messages=[{"role": "user", "content": user}],
                temperature=0,
                max_tokens=_WEB_MAX_TOKENS,
                extra_body={"plugins": [plugin], "usage": {"include": True}},
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMUnavailable(f"{type(exc).__name__}") from exc
        data = response.model_dump()
        usage = data.get("usage") or {}
        reply = AIMessage(
            content="",
            response_metadata={"token_usage": usage},
            usage_metadata={
                "input_tokens": usage.get("prompt_tokens") or 0,
                "output_tokens": usage.get("completion_tokens") or 0,
                "total_tokens": usage.get("total_tokens") or 0,
            },
        )
        record_usage(reply)
        try:
            output = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            output = None
        _record(
            "web_search",
            model.model_name,
            [{"role": "user", "content": user}],
            output,
            reply,
            _ms(started),
        )
        return data

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
        _record(
            _structured_step(schema),
            "fake",
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            item.model_dump(mode="json") if isinstance(item, BaseModel) else None,
            None,
            0,
        )
        return item

    def answer(self, system: str, user: str) -> str:
        self.calls["answer"] += 1
        if not self._answers:
            raise LLMBadOutput("FakeGateway: keine Antwort")
        item = self._answers.pop(0)
        if isinstance(item, Exception):
            raise item
        _record(
            "answer",
            "fake",
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            item,
            None,
            0,
        )
        return item

    def tool_round(self, messages: Sequence[BaseMessage], tools: Sequence[Any]) -> AIMessage:
        self.calls["tool_round"] += 1
        if not self._tool_rounds:
            raise LLMBadOutput("FakeGateway: keine Tool-Runde")
        item = self._tool_rounds.pop(0)
        if isinstance(item, Exception):
            raise item
        _record("react", "fake", trace.message_dicts(messages), trace.ai_output(item), None, 0)
        return item
