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
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from hikesense import chatlog
from hikesense.adapters.http import make_http_client
from hikesense.adapters.open_meteo import OpenMeteoClient
from hikesense.adapters.page_fetch import safe_client
from hikesense.adapters.web_search import OpenRouterWebSearch
from hikesense.agent.events import EventFinder
from hikesense.agent.graph import AgentDeps, ErrorEvent, run_chat
from hikesense.agent.texts import Lang, texts
from hikesense.agent.tools import DbTools
from hikesense.api.auth import AUTH_MESSAGES, authenticate, authenticate_optional
from hikesense.chatlog import ChatLogEntry
from hikesense.config import Settings
from hikesense.db import connect
from hikesense.guard import sanitize_text
from hikesense.guest_quota import GuestQuota, client_ip, guest_owner, ip_key
from hikesense.knowledge.search import try_open
from hikesense.llm.gateway import OpenRouterGateway
from hikesense.rate_limit import RateLimiter
from hikesense.tags.vocabulary import FEATURES_YAML, TagVocabulary

log = logging.getLogger(__name__)

MAX_CHARS = 1000
MAX_BODY_BYTES = 64 * 1024
WEATHER_TIMEOUT_S = 10.0
TRAIL_NAMES_SQL = "select distinct name from trails where name is not null"
# The web app proxies /api/chat (Next rewrite, one origin for a phone tunnel): the stream must
# neither be compressed (no-transform) nor buffered by a proxy, or events arrive all at once.
STREAM_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


class ChatRequest(BaseModel):
    thread_id: uuid.UUID
    message: str
    # reply language; missing field (old clients, tests, eval) means German
    lang: Lang = "de"


def default_deps_factory(
    settings: Settings, weather_client: Any | None = None
) -> Callable[[], AgentDeps]:
    """Builds the real deps on first use and keeps them (the conversation memory lives in them).
    Raises (e.g. LLMUnavailable without OPENROUTER_API_KEY) until it can build them.
    `weather_client` replaces the live Open-Meteo client (the eval passes stored forecasts)."""
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
                    weather_client=OpenMeteoClient(make_http_client(WEATHER_TIMEOUT_S))
                    if weather_client is None
                    else weather_client,
                    # redirects are followed by the page fetcher itself (each hop checked);
                    # every connection is pinned to a vetted public address
                    event_finder=EventFinder(
                        OpenRouterWebSearch(gateway),
                        safe_client(),
                        gateway,
                        ua=settings.hikesense_user_agent,
                    ),
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


def _failure_log(
    settings: Settings,
    exc: Exception,
    user_hash: str | None = None,
    user_id: str | None = None,
    message: str | None = None,
) -> None:
    try:
        entry = ChatLogEntry(
            request_id=uuid.uuid4().hex,
            user_hash=user_hash,
            user_id=user_id,
            message=message,
            error=type(exc).__name__,
        )
        chatlog.write(settings.chat_log_path, entry)
    except Exception:
        log.exception("chat log write failed")


async def _peek_lang(request: Request) -> Lang:
    """The reply language of a request that is turned away before its body is validated: read
    leniently (small bodies only); anything unclear means German."""
    declared = request.headers.get("content-length", "")
    if not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
        return "de"
    try:
        lang = json.loads(await request.body()).get("lang")
    except Exception:  # noqa: BLE001 - e.g. RecursionError on deeply nested JSON
        return "de"
    return "en" if lang == "en" else "de"


BLOCKED = {"detail": "account_blocked"}


def make_router(
    settings: Settings,
    deps_factory: Callable[[], Any],
    limiter: RateLimiter,
    guest_quota: GuestQuota,
    status_lookup: Callable[[str], str],
) -> APIRouter:
    router = APIRouter()

    async def stream(
        thread_id: str, message: str, user_hash: str, user_id: str | None, lang: Lang
    ) -> AsyncIterator[dict[str, str]]:
        try:
            deps = await run_in_threadpool(deps_factory)
            chat_stream = run_chat(deps, thread_id, message, user_hash, user_id=user_id, lang=lang)
            async for event in iterate_in_threadpool(chat_stream):
                yield _event(event)
        except Exception as exc:
            log.exception("chat failed")
            _failure_log(settings, exc, user_hash, user_id, message)
            yield _event(ErrorEvent(message=texts(lang).error_unavailable))

    async def refused(
        message: str, retry_after_s: int, code: str | None = None
    ) -> EventSourceResponse:
        async def one() -> AsyncIterator[dict[str, str]]:
            yield _event(ErrorEvent(message=message, code=code))

        return EventSourceResponse(
            one(),
            status_code=429,
            headers={**STREAM_HEADERS, "Retry-After": str(retry_after_s)},
        )

    async def blocked(user_id: str) -> JSONResponse | None:
        """403 for a blocked account (its access token may still be valid for up to an hour)."""
        try:
            status = await run_in_threadpool(status_lookup, user_id)
        except Exception:
            log.exception("account status lookup failed")
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        return JSONResponse(BLOCKED, status_code=403) if status == "gesperrt" else None

    @router.get("/account")
    async def account(request: Request) -> JSONResponse:
        user = await authenticate(request, settings)
        if isinstance(user, JSONResponse):
            return user
        denied = await blocked(user.user_id)
        return denied or JSONResponse({"status": "aktiv"})

    @router.post("/chat", response_model=None)
    async def chat(request: Request) -> EventSourceResponse | JSONResponse:
        user = await authenticate_optional(request, settings)
        if isinstance(user, JSONResponse):
            return user
        if user is None:  # guest: counted per IP and for all guests together
            key = ip_key(client_ip(request, settings.hikesense_trusted_proxy_hops))
            try:
                guest = await run_in_threadpool(guest_quota.acquire, key)
            except Exception:
                log.exception("guest quota failed")
                return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
            if not guest.allowed:
                lang = await _peek_lang(request)
                return await refused(
                    texts(lang).guest_limit_reply, guest.retry_after_s, "guest_limit"
                )
            user_hash, user_id = guest_owner(key), None
        else:
            denied = await blocked(user.user_id)
            if denied is not None:
                return denied
            decision = limiter.acquire(user.user_id)  # before the graph, after the token check
            if not decision.allowed:
                lang = await _peek_lang(request)
                message = texts(lang).rate_limit_reply.format(s=decision.retry_after_s)
                return await refused(message, decision.retry_after_s)
            user_hash, user_id = chatlog.hash_user(user.user_id), user.user_id
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
        return EventSourceResponse(
            stream(str(body.thread_id), message, user_hash, user_id, body.lang),
            headers=STREAM_HEADERS,
        )

    return router
