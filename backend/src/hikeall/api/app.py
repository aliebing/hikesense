"""Minimal FastAPI app: health check."""

from __future__ import annotations

import psycopg
from fastapi import FastAPI

from hikeall.config import Settings


def _db_ok(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("select 1")
        return True
    except psycopg.Error:
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Hike all about")

    @app.get("/health")
    def health() -> dict:
        s = settings or Settings()
        return {"status": "ok", "db": _db_ok(s.supabase_db_url)}

    return app


app = create_app()
