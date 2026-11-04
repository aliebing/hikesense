"""Bearer-token authentication shared by the chat and admin routers."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from hikesense.auth import AuthError, AuthUser, verify_token
from hikesense.config import Settings

AUTH_MESSAGES = {
    "missing": "Bitte anmelden.",
    "invalid": "Bitte anmelden.",
    "expired": "Sitzung abgelaufen – bitte erneut anmelden.",
    "unavailable": "Anmeldung kann gerade nicht geprüft werden – bitte gleich noch einmal versuchen.",
}


async def authenticate_optional(
    request: Request, settings: Settings
) -> AuthUser | None | JSONResponse:
    """None for a guest (no Authorization header at all). A header that is present but invalid
    or expired still gets the 401, so a client with a stale session signs in again instead of
    silently becoming a guest."""
    if not request.headers.get("authorization", "").strip():
        return None
    return await authenticate(request, settings)


async def authenticate(request: Request, settings: Settings) -> AuthUser | JSONResponse:
    """The signed-in user from the Bearer token, or the 401/503 response to send instead."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    try:
        return await run_in_threadpool(
            verify_token, token.strip() if scheme.lower() == "bearer" else "", settings
        )
    except AuthError as exc:
        if exc.reason == "unavailable":
            return JSONResponse({"detail": AUTH_MESSAGES["unavailable"]}, status_code=503)
        return JSONResponse(
            {"detail": AUTH_MESSAGES.get(exc.reason, AUTH_MESSAGES["invalid"])},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
