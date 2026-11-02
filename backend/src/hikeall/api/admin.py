"""Admin endpoints: the server checks the Bearer token and the role (`profiles.role`)."""

from __future__ import annotations

import logging
from collections.abc import Callable

import psycopg
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from hikeall import admin_log
from hikeall.api.auth import AUTH_MESSAGES, authenticate
from hikeall.auth import AuthUser
from hikeall.config import Settings
from hikeall.roles import Profile, Role

log = logging.getLogger(__name__)


def make_admin_router(
    settings: Settings,
    role_lookup: Callable[[str], Role],
    profiles_lookup: Callable[[], list[Profile]],
    reader: admin_log.LogReader,
) -> APIRouter:
    router = APIRouter(prefix="/admin")

    async def require_admin(request: Request) -> AuthUser | JSONResponse:
        """The admin user, or the 401/403/503 response to send instead."""
        user = await authenticate(request, settings)
        if isinstance(user, JSONResponse):
            return user
        try:
            role = await run_in_threadpool(role_lookup, user.user_id)
        except psycopg.Error:
            log.exception("role lookup failed")
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        if role != "admin":
            return JSONResponse({"detail": "Kein Zugriff"}, status_code=403)
        return user

    @router.get("/me")
    async def me(request: Request) -> JSONResponse:
        user = await require_admin(request)
        if isinstance(user, JSONResponse):
            return user
        return JSONResponse({"user_id": user.user_id, "role": "admin"})

    async def load(request: Request) -> tuple[list[dict], list[Profile]] | JSONResponse:
        """Log entries and profiles; the role check has already passed."""
        try:
            profiles = await run_in_threadpool(profiles_lookup)
        except psycopg.Error:
            log.exception("profiles lookup failed")
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        entries = await run_in_threadpool(reader.entries)
        return entries, profiles

    @router.get("/users")
    async def list_users(request: Request) -> JSONResponse:
        denied = await require_admin(request)
        if isinstance(denied, JSONResponse):
            return denied
        loaded = await load(request)
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, profiles = loaded
        return JSONResponse({"users": admin_log.users(entries, profiles), "total": len(entries)})

    @router.get("/searches")
    async def list_searches(
        request: Request,
        user: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ) -> JSONResponse:
        denied = await require_admin(request)
        if isinstance(denied, JSONResponse):
            return denied
        loaded = await load(request)
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, profiles = loaded
        return JSONResponse(admin_log.searches(entries, profiles, user, offset, limit))

    @router.get("/searches/{request_id}")
    async def search_detail(request: Request, request_id: str) -> JSONResponse:
        denied = await require_admin(request)
        if isinstance(denied, JSONResponse):
            return denied
        loaded = await load(request)
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, profiles = loaded
        found = admin_log.detail(entries, profiles, request_id)
        if found is None:
            return JSONResponse({"detail": "Suche nicht gefunden"}, status_code=404)
        return JSONResponse(found)

    return router
