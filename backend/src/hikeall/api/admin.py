"""Admin endpoints: the server checks the Bearer token and the role (`profiles.role`)."""

from __future__ import annotations

import logging
from collections.abc import Callable

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from hikeall.api.chat import AUTH_MESSAGES, authenticate
from hikeall.auth import AuthUser
from hikeall.config import Settings
from hikeall.roles import Role

log = logging.getLogger(__name__)


def make_admin_router(settings: Settings, role_lookup: Callable[[str], Role]) -> APIRouter:
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

    return router
