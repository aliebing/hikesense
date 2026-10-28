"""Minimal FastAPI app: health check."""

from __future__ import annotations

import psycopg
from fastapi import FastAPI

from hikeall.config import Settings


def _db_ok(settings: Settings | None) -> bool:
    try:
        url = (settings or Settings()).supabase_db_url
        with psycopg.connect(url, connect_timeout=2) as conn:
            conn.execute("select 1")
        return True
    except Exception:  # noqa: BLE001 - any settings/db failure means db=false
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Hike all about")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "db": _db_ok(settings)}

    return app


app = create_app()
