"""Minimal FastAPI app: health check."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hikeall.api.chat import default_deps_factory, make_router
from hikeall.config import Settings
from hikeall.rate_limit import RateLimiter

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


def create_app(
    settings: Settings | None = None, deps_factory: Callable[[], Any] | None = None
) -> FastAPI:
    app = FastAPI(title="Hike all about")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
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
        }

    if cfg is not None:
        factory = deps_factory or default_deps_factory(cfg)
        app.include_router(make_router(cfg, factory, RateLimiter()))

    return app


app = create_app()
