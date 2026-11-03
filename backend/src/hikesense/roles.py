"""User roles (`profiles.role`): `admin` only with an explicit row, everything else is `user`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import psycopg

Role = Literal["user", "admin"]


def role_of(conn: psycopg.Connection, user_id: str) -> Role:
    try:
        with conn.transaction():  # savepoint: an invalid UUID must not poison the transaction
            row = conn.execute(
                "select role from profiles where user_id = %s::uuid", (user_id,)
            ).fetchone()
    except psycopg.errors.InvalidTextRepresentation:
        return "user"
    return "admin" if row and row[0] == "admin" else "user"


def set_role(conn: psycopg.Connection, user_id: str, role: Role) -> None:
    """Upserts the profile (email from auth.users). Does not commit; the caller does."""
    conn.execute(
        """
        insert into profiles (user_id, email, role)
        select id, email, %s from auth.users where id = %s::uuid
        on conflict (user_id) do update set role = excluded.role
        """,
        (role, user_id),
    )


@dataclass
class Profile:
    user_id: str
    email: str | None
    role: Role


def list_profiles(conn: psycopg.Connection) -> list[Profile]:
    """All profiles; the email is the current one from auth.users (profiles.email can be stale)."""
    rows = conn.execute(
        """
        select p.user_id::text, coalesce(u.email, p.email), p.role
        from profiles p left join auth.users u on u.id = p.user_id
        order by 2
        """
    ).fetchall()
    return [Profile(r[0], r[1], "admin" if r[2] == "admin" else "user") for r in rows]
