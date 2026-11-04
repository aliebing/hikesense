"""Supabase Auth Admin API (GoTrue) with the service-role key: ban, confirm, create, delete users.

Server-side only: the service-role key bypasses every RLS policy and must never reach the browser.
Uses the HTTP API rather than writing into the `auth` schema, because Supabase Cloud restricts that.
"""

from __future__ import annotations

import httpx

from hikesense.config import Settings

TIMEOUT_S = 10.0
PER_PAGE = 50
BAN_FOREVER = "876000h"  # ~100 years; GoTrue has no "permanent" value


class SupabaseAdminError(Exception):
    """`status` is the HTTP status, 0 when Supabase was unreachable or not configured."""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(message or f"Supabase-Admin-API: HTTP {status}")
        self.status = status


class SupabaseAdmin:
    def __init__(self, settings: Settings, http: httpx.Client | None = None) -> None:
        key = settings.supabase_service_role_key
        if key is None or not key.get_secret_value() or not settings.supabase_url:
            raise SupabaseAdminError(
                0, "SUPABASE_URL und SUPABASE_SERVICE_ROLE_KEY in .env eintragen"
            )
        self._base = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin"
        secret = key.get_secret_value()
        self._headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}
        self._http = http or httpx.Client(timeout=TIMEOUT_S)

    def _call(self, method: str, path: str, **kw: object) -> httpx.Response:
        try:
            r = self._http.request(
                method, self._base + path, headers=self._headers, timeout=TIMEOUT_S, **kw
            )  # type: ignore[arg-type]
        except httpx.HTTPError as exc:
            raise SupabaseAdminError(
                0, f"Supabase-Admin-API nicht erreichbar ({type(exc).__name__})"
            ) from exc
        if r.status_code >= 400:
            raise SupabaseAdminError(
                r.status_code, f"Supabase-Admin-API: HTTP {r.status_code} {r.text[:200]}"
            )
        return r

    def ban(self, user_id: str) -> None:
        """Blocks sign-in and token refresh; an already issued access token stays valid until it
        expires, so RLS and /chat check app_users.status as well."""
        self._call("PUT", f"/users/{user_id}", json={"ban_duration": BAN_FOREVER})

    def unban(self, user_id: str) -> None:
        self._call("PUT", f"/users/{user_id}", json={"ban_duration": "none"})

    def confirm_user(self, user_id: str) -> None:
        self._call("PUT", f"/users/{user_id}", json={"email_confirm": True})

    def create_confirmed_user(self, email: str, password: str) -> str:
        r = self._call(
            "POST", "/users", json={"email": email, "password": password, "email_confirm": True}
        )
        return str(r.json()["id"])

    def delete_user(self, user_id: str) -> None:
        self._call("DELETE", f"/users/{user_id}")

    def list_users(self) -> list[dict]:
        users: list[dict] = []
        page = 1
        while True:
            batch = (
                self._call("GET", "/users", params={"page": page, "per_page": PER_PAGE})
                .json()
                .get("users", [])
            )
            users.extend(batch)
            if len(batch) < PER_PAGE:
                return users
            page += 1

    def find_user_id(self, email: str) -> str | None:
        want = email.strip().lower()
        for u in self.list_users():
            if (u.get("email") or "").lower() == want:
                return str(u["id"])
        return None
