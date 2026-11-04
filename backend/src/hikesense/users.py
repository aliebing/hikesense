"""App users (`app_users` joined with Supabase `auth.users`): list, read and set the status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

import psycopg

Status = Literal["unbestätigt", "aktiv", "gesperrt"]
DbStatus = Literal["aktiv", "gesperrt"]


@dataclass
class AppUser:
    user_id: str
    email: str | None
    status: Status
    created_at: datetime
    last_sign_in_at: datetime | None


def list_app_users(conn: psycopg.Connection) -> list[AppUser]:
    """All app users, newest first. The e-mail is the current one from auth.users; unconfirmed
    (no email_confirmed_at) shows only while the account is not blocked."""
    rows = conn.execute(
        """
        select a.user_id::text, coalesce(u.email, a.email), a.status, u.email_confirmed_at is not null,
               a.created_at, u.last_sign_in_at
        from app_users a join auth.users u on u.id = a.user_id
        order by a.created_at desc
        """
    ).fetchall()
    out = []
    for uid, email, status, confirmed, created, last in rows:
        shown: Status = "gesperrt" if status == "gesperrt" else ("aktiv" if confirmed else "unbestätigt")
        out.append(AppUser(uid, email, shown, created, last))
    return out


def status_of(conn: psycopg.Connection, user_id: str) -> DbStatus:
    """`gesperrt` only with an explicit row; unknown users and non-UUID ids count as `aktiv`."""
    try:
        with conn.transaction():  # savepoint: an invalid UUID must not poison the transaction
            row = conn.execute(
                "select status from app_users where user_id = %s::uuid", (user_id,)
            ).fetchone()
    except psycopg.errors.InvalidTextRepresentation:
        return "aktiv"
    return "gesperrt" if row and row[0] == "gesperrt" else "aktiv"


def set_status(conn: psycopg.Connection, user_id: str, status: DbStatus) -> bool:
    """Sets the status (and blocked_at); False when the user has no row. Does not commit."""
    try:
        with conn.transaction():
            n = conn.execute(
                """
                update app_users
                set status = %s, blocked_at = case when %s = 'gesperrt' then now() end
                where user_id = %s::uuid
                """,
                (status, status, user_id),
            ).rowcount
    except psycopg.errors.InvalidTextRepresentation:
        return False
    return n == 1


OLD_ADMIN_EMAIL = "admin@hikesense.local"


class _AccountAdmin(Protocol):
    def confirm_user(self, user_id: str) -> None: ...
    def find_user_id(self, email: str) -> str | None: ...
    def delete_user(self, user_id: str) -> None: ...


def migrate_accounts(conn: psycopg.Connection, admin: _AccountAdmin) -> list[str]:
    """One-time switch to confirmed sign-up (idempotent): existing accounts count as confirmed,
    the old admin account (admins are no app users any more) is deleted. Returns one line per
    action. Goes through the Auth Admin API, which also works on Supabase Cloud."""
    lines = []
    pending = conn.execute(
        "select id::text, email from auth.users where email_confirmed_at is null order by created_at"
    ).fetchall()
    for uid, email in pending:
        admin.confirm_user(uid)
        lines.append(f"bestätigt: {email or uid}")
    old = admin.find_user_id(OLD_ADMIN_EMAIL)
    if old:
        admin.delete_user(old)
        lines.append(f"gelöscht: {OLD_ADMIN_EMAIL}")
    return lines
