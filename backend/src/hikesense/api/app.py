"""Minimal FastAPI app: health check."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from hikesense import chatlog
from hikesense.adapters.open_meteo import weather_source
from hikesense.admin_log import LogReader
from hikesense.admin_session import LoginThrottle
from hikesense.api.backend import make_backend_router
from hikesense.api.chat import default_deps_factory, make_router
from hikesense.config import Settings, export_langsmith_env
from hikesense.db import upsert_source
from hikesense.guest_quota import DbGuestQuota, GuestQuota
from hikesense.rate_limit import RateLimiter
from hikesense.supabase_admin import SupabaseAdmin
from hikesense.users import AppUser, apply_block, list_app_users, status_of

log = logging.getLogger(__name__)

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


CHECKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def origin_allowed(request: Request, extra: list[str]) -> bool:
    """A state-changing request from a browser must come from this app: its Origin is one of the
    local or configured origins, or names the host the browser called (Next forwards it as
    X-Forwarded-Host). No Origin header (curl, smoke run) is no cross-site request."""
    origin = request.headers.get("origin")
    if origin is None:
        return True
    if origin in ALLOWED_ORIGINS or origin in extra:
        return True
    host = origin.split("://", 1)[1] if "://" in origin else ""
    called = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    called = called.split(",")[0].strip()
    return bool(host) and host == called


def _db_ok(settings: Settings | None) -> bool:
    try:
        url = (settings or Settings()).supabase_db_url
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("select 1")
        return True
    except Exception:  # noqa: BLE001 - any settings/db failure means db=false
        return False


def _knowledge_ok(settings: Settings) -> bool:
    d = settings.chroma_dir
    return d.is_dir() and any(d.iterdir())


def _register_sources(settings: Settings) -> None:
    """Weather is fetched live, so its source row is written at startup (best effort)."""
    try:
        with psycopg.connect(settings.supabase_db_url, connect_timeout=2) as conn:
            upsert_source(conn, weather_source())
    except Exception:
        log.warning("could not register the open-meteo source", exc_info=True)


PRUNE_EVERY_S = 6 * 3600


def _prune_chat_log(settings: Settings) -> None:
    try:
        gone = chatlog.prune(settings.chat_log_path, settings.hikesense_log_retention_days)
        if gone:
            log.info(
                "chat log: %d entries older than %d days deleted",
                gone,
                settings.hikesense_log_retention_days,
            )
    except Exception:
        log.exception("chat log prune failed")


async def _prune_every(settings: Settings, seconds: float) -> None:
    while True:
        await asyncio.sleep(seconds)
        await run_in_threadpool(_prune_chat_log, settings)


def _default_users_lookup(settings: Settings) -> Callable[[], list[AppUser]]:
    def lookup() -> list[AppUser]:
        with psycopg.connect(settings.supabase_db_url, connect_timeout=5) as conn:
            return list_app_users(conn)

    return lookup


def _default_set_blocked(settings: Settings) -> Callable[[str, bool], bool]:
    def set_blocked(user_id: str, block: bool) -> bool:
        admin = SupabaseAdmin(settings)
        with psycopg.connect(settings.supabase_db_url, connect_timeout=5) as conn:
            return apply_block(conn, admin, user_id, block, commit=conn.commit)

    return set_blocked


def _default_status_lookup(settings: Settings) -> Callable[[str], str]:
    def lookup(user_id: str) -> str:
        with psycopg.connect(settings.supabase_db_url, connect_timeout=5) as conn:
            return status_of(conn, user_id)

    return lookup


def create_app(
    settings: Settings | None = None,
    deps_factory: Callable[[], Any] | None = None,
    users_lookup: Callable[[], list[AppUser]] | None = None,
    set_blocked: Callable[[str, bool], bool] | None = None,
    guest_quota: GuestQuota | None = None,
    status_lookup: Callable[[str], str] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        pruner = None
        if cfg is not None:
            await run_in_threadpool(_register_sources, cfg)
            await run_in_threadpool(_prune_chat_log, cfg)
            pruner = asyncio.create_task(_prune_every(cfg, PRUNE_EVERY_S))
        yield
        if pruner is not None:
            pruner.cancel()

    app = FastAPI(title="HikeSense", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    try:
        cfg = settings or Settings()
    except Exception:  # noqa: BLE001 - unset DB URL etc.: health reports db=false, chat errors
        cfg = None
    extra = [
        o.strip().rstrip("/")
        for o in (cfg.hikesense_allowed_origins if cfg else "").split(",")
        if o.strip()
    ]

    @app.middleware("http")
    async def check_origin(request: Request, call_next):
        if request.method in CHECKED_METHODS and not origin_allowed(request, extra):
            return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)
        return await call_next(request)

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "db": _db_ok(settings),
            "llm": bool(cfg and cfg.openrouter_api_key),
            "knowledge": bool(cfg and _knowledge_ok(cfg)),
            "auth": bool(cfg and (cfg.supabase_jwt_secret or cfg.supabase_url)),
        }

    if cfg is not None:
        export_langsmith_env(cfg)  # optional LangSmith tracing, off unless configured
        factory = deps_factory or default_deps_factory(cfg)
        app.include_router(
            make_router(
                cfg,
                factory,
                RateLimiter(),
                guest_quota or DbGuestQuota(cfg),
                status_lookup or _default_status_lookup(cfg),
            )
        )
        app.include_router(
            make_backend_router(
                cfg,
                users_lookup or _default_users_lookup(cfg),
                set_blocked or _default_set_blocked(cfg),
                LogReader(cfg.chat_log_path),
                LoginThrottle(),
            )
        )

    return app


app = create_app()
