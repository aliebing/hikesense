"""Admin backend API under /backend: its own sign-in (name `admin` + bcrypt hash from .env) and a
signed HttpOnly cookie. Only that cookie counts here; Supabase tokens are ignored."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import psycopg
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from hikesense import admin_log, admin_session
from hikesense.api.auth import AUTH_MESSAGES
from hikesense.config import Settings
from hikesense.guest_quota import client_ip
from hikesense.supabase_admin import SupabaseAdminError
from hikesense.users import AppUser

log = logging.getLogger(__name__)

SIGN_IN = {"detail": "Bitte anmelden"}
NOT_SET_UP = {"detail": "Backend nicht eingerichtet"}


class LoginBody(BaseModel):
    name: str
    password: str


def make_backend_router(
    settings: Settings,
    users_lookup: Callable[[], list[AppUser]],
    set_blocked: Callable[[str, bool], bool],
    reader: admin_log.LogReader,
    throttle: admin_session.LoginThrottle,
    sessions: admin_session.Sessions | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/backend")
    store = sessions or admin_session.Sessions()

    def secrets() -> tuple[str, str] | None:
        h, s = settings.hikesense_admin_password_hash, settings.hikesense_admin_session_secret
        if h is None or s is None or not h.get_secret_value() or not s.get_secret_value():
            return None
        return h.get_secret_value(), s.get_secret_value()

    def signed_in(request: Request) -> bool:
        sec = secrets()
        return bool(sec) and store.valid(
            request.cookies.get(admin_session.COOKIE), sec[1], time.time()
        )

    def secure(request: Request) -> bool:
        proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        return request.url.scheme == "https" or proto == "https"

    @router.post("/login")
    async def login(request: Request, body: LoginBody) -> JSONResponse:
        sec = secrets()
        if sec is None:
            log.error("backend login: HIKESENSE_ADMIN_PASSWORD_HASH or _SESSION_SECRET missing")
            return JSONResponse(NOT_SET_UP, status_code=503)
        ip = client_ip(request, settings.hikesense_trusted_proxy_hops)
        wait = throttle.try_acquire(ip)  # counted before bcrypt: parallel tries cannot pass the cap
        if wait:
            return JSONResponse(
                {"detail": "Zu viele Versuche"}, status_code=429, headers={"Retry-After": str(wait)}
            )
        ok = body.name.strip() == admin_session.ADMIN_NAME and await run_in_threadpool(
            admin_session.check_password, body.password, sec[0]
        )
        if not ok:
            return JSONResponse({"detail": "Anmeldung fehlgeschlagen"}, status_code=401)
        throttle.succeeded(ip)
        r = JSONResponse({"name": admin_session.ADMIN_NAME})
        r.set_cookie(
            admin_session.COOKIE,
            store.issue(sec[1], time.time()),
            max_age=admin_session.SESSION_S,
            httponly=True,
            samesite="strict",
            secure=secure(request),
            path="/",
        )
        return r

    @router.post("/logout")
    async def logout(request: Request) -> JSONResponse:
        store.revoke(request.cookies.get(admin_session.COOKIE))  # a copy stops working too
        r = JSONResponse({"ok": True})
        r.delete_cookie(
            admin_session.COOKIE, path="/", httponly=True, samesite="strict", secure=secure(request)
        )
        return r

    @router.get("/me")
    async def me(request: Request) -> JSONResponse:
        if not signed_in(request):
            return JSONResponse(SIGN_IN, status_code=401)
        return JSONResponse({"name": admin_session.ADMIN_NAME})

    async def load() -> tuple[list[dict], list[AppUser]] | JSONResponse:
        try:
            users = await run_in_threadpool(users_lookup)
        except psycopg.Error:
            log.exception("app users lookup failed")
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        entries = await run_in_threadpool(reader.entries)
        return entries, users

    @router.get("/users")
    async def list_users(request: Request) -> JSONResponse:
        if not signed_in(request):
            return JSONResponse(SIGN_IN, status_code=401)
        loaded = await load()
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, users = loaded
        return JSONResponse({"users": admin_log.users(entries, users), "total": len(entries)})

    @router.get("/searches")
    async def list_searches(
        request: Request,
        user: str | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
    ) -> JSONResponse:
        if not signed_in(request):
            return JSONResponse(SIGN_IN, status_code=401)
        loaded = await load()
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, users = loaded
        return JSONResponse(admin_log.searches(entries, users, user, offset, limit))

    @router.get("/searches/{request_id}")
    async def search_detail(request: Request, request_id: str) -> JSONResponse:
        if not signed_in(request):
            return JSONResponse(SIGN_IN, status_code=401)
        loaded = await load()
        if isinstance(loaded, JSONResponse):
            return loaded
        entries, users = loaded
        found = admin_log.detail(entries, users, request_id)
        if found is None:
            return JSONResponse({"detail": "Suche nicht gefunden"}, status_code=404)
        return JSONResponse(found)

    async def change(request: Request, user_id: str, block: bool) -> JSONResponse:
        if not signed_in(request):
            return JSONResponse(SIGN_IN, status_code=401)
        try:
            found = await run_in_threadpool(set_blocked, user_id, block)
        except SupabaseAdminError as exc:
            if exc.status == 404:  # gone in Supabase Auth: same answer as an unknown app user
                return JSONResponse({"detail": "Benutzer nicht gefunden"}, status_code=404)
            log.exception("supabase admin api failed")
            return JSONResponse({"detail": "Supabase-Admin-API nicht erreichbar"}, status_code=502)
        except psycopg.Error:
            log.exception("status update failed")
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        if not found:
            return JSONResponse({"detail": "Benutzer nicht gefunden"}, status_code=404)
        return JSONResponse({"status": "gesperrt" if block else "aktiv"})

    @router.post("/users/{user_id}/block")
    async def block(request: Request, user_id: str) -> JSONResponse:
        return await change(request, user_id, True)

    @router.post("/users/{user_id}/unblock")
    async def unblock(request: Request, user_id: str) -> JSONResponse:
        return await change(request, user_id, False)

    return router
