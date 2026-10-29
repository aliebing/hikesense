"""POST /chat: one chat message as a Server-Sent-Events stream of agent events."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from hikeall import chatlog
from hikeall.agent.graph import AgentDeps, ErrorEvent, run_chat
from hikeall.agent.prompts import ERROR_UNAVAILABLE
from hikeall.agent.tools import DbTools
from hikeall.chatlog import ChatLogEntry
from hikeall.config import Settings
from hikeall.db import connect
from hikeall.guard import RATE_LIMIT_REPLY, sanitize_text
from hikeall.knowledge.search import try_open
from hikeall.llm.gateway import OpenRouterGateway
from hikeall.rate_limit import RateLimiter
from hikeall.tags.vocabulary import FEATURES_YAML, TagVocabulary

log = logging.getLogger(__name__)

MAX_CHARS = 1000
MAX_BODY_BYTES = 64 * 1024
TRAIL_NAMES_SQL = "select distinct name from trails where name is not null"


class ChatRequest(BaseModel):
    thread_id: uuid.UUID
    message: str


def default_deps_factory(settings: Settings) -> Callable[[], AgentDeps]:
    """Builds the real deps on first use and keeps them (the conversation memory lives in them).
    Raises (e.g. LLMUnavailable without OPENROUTER_API_KEY) until it can build them."""
    lock = threading.Lock()
    cache: list[AgentDeps] = []

    def factory() -> AgentDeps:
        with lock:
            if not cache:
                gateway = OpenRouterGateway.from_settings(settings)
                with connect(settings.supabase_db_url) as conn:
                    vocab = TagVocabulary.load(conn, FEATURES_YAML)
                    names = [r[0] for r in conn.execute(TRAIL_NAMES_SQL)]
                tools = DbTools(
                    lambda: connect(settings.supabase_db_url),
                    try_open(settings.chroma_dir),
                    knowledge_opener=lambda: try_open(settings.chroma_dir),
                )
                cache.append(
                    AgentDeps(
                        tools=tools,
                        gateway=gateway,
                        vocab=vocab,
                        settings=settings,
                        trail_names=names,
                    )
                )
            return cache[0]

    return factory


def _event(event: Any) -> dict[str, str]:
    return {"event": event.type, "data": event.model_dump_json()}


def _failure_log(settings: Settings, exc: Exception) -> None:
    try:
        entry = ChatLogEntry(request_id=uuid.uuid4().hex, error=type(exc).__name__)
        chatlog.write(settings.chat_log_path, entry)
    except Exception:
        log.exception("chat log write failed")


def make_router(
    settings: Settings, deps_factory: Callable[[], Any], limiter: RateLimiter
) -> APIRouter:
    router = APIRouter()

    async def stream(thread_id: str, message: str) -> AsyncIterator[dict[str, str]]:
        try:
            deps = await run_in_threadpool(deps_factory)
            async for event in iterate_in_threadpool(run_chat(deps, thread_id, message)):
                yield _event(event)
        except Exception as exc:
            log.exception("chat failed")
            _failure_log(settings, exc)
            yield _event(ErrorEvent(message=ERROR_UNAVAILABLE))

    @router.post("/chat")
    async def chat(request: Request) -> EventSourceResponse:
        ip = request.client.host if request.client else "unknown"
        decision = limiter.acquire(ip)  # before anything else
        if not decision.allowed:
            message = RATE_LIMIT_REPLY.format(s=decision.retry_after_s)

            async def limited() -> AsyncIterator[dict[str, str]]:
                yield _event(ErrorEvent(message=message))

            return EventSourceResponse(
                limited(),
                status_code=429,
                headers={"Retry-After": str(decision.retry_after_s)},
            )
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Nachricht zu groß")
        data = await request.body()
        if len(data) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Nachricht zu groß")
        try:
            body = ChatRequest.model_validate(json.loads(data))
        except json.JSONDecodeError as exc:
            raise RequestValidationError(
                [{"type": "json_invalid", "loc": ("body",), "msg": str(exc)}]
            )
        except ValidationError as exc:
            raise RequestValidationError(
                exc.errors(include_url=False, include_context=False)
            ) from exc
        message = sanitize_text(body.message, MAX_CHARS)
        if not message:
            raise RequestValidationError(
                [{"type": "value_error", "loc": ("body", "message"), "msg": "empty message"}]
            )
        return EventSourceResponse(stream(str(body.thread_id), message))

    return router
