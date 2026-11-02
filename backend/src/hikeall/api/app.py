"""Minimal FastAPI app: health check."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from hikeall.adapters.open_meteo import weather_source
from hikeall.admin_log import LogReader
from hikeall.api.admin import make_admin_router
from hikeall.api.chat import default_deps_factory, make_router
from hikeall.config import Settings
from hikeall.db import upsert_source
from hikeall.rate_limit import RateLimiter
from hikeall.roles import Profile, Role, list_profiles, role_of

log = logging.getLogger(__name__)

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


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


def _default_role_lookup(settings: Settings) -> Callable[[str], Role]:
    def lookup(user_id: str) -> Role:
        with psycopg.connect(settings.supabase_db_url, connect_timeout=5) as conn:
            return role_of(conn, user_id)

    return lookup


def _default_profiles_lookup(settings: Settings) -> Callable[[], list[Profile]]:
    def lookup() -> list[Profile]:
        with psycopg.connect(settings.supabase_db_url, connect_timeout=5) as conn:
            return list_profiles(conn)

    return lookup


def create_app(
    settings: Settings | None = None,
    deps_factory: Callable[[], Any] | None = None,
    role_lookup: Callable[[str], Role] | None = None,
    profiles_lookup: Callable[[], list[Profile]] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if cfg is not None:
            await run_in_threadpool(_register_sources, cfg)
        yield

    app = FastAPI(title="Hike all about", lifespan=lifespan)
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
        factory = deps_factory or default_deps_factory(cfg)
        app.include_router(make_router(cfg, factory, RateLimiter()))
        app.include_router(
            make_admin_router(
                cfg,
                role_lookup or _default_role_lookup(cfg),
                profiles_lookup or _default_profiles_lookup(cfg),
                LogReader(cfg.chat_log_path),
            )
        )

    return app


app = create_app()
