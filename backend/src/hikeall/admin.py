"""Local admin account `admin@hikeall.local` (sign-in name `admin`).

`.env` holds only a bcrypt hash (HIKEALL_ADMIN_PASSWORD_HASH), never the password. The row goes
straight into Supabase's auth schema, because the sign-up API would need the plain password and
enforces its minimum length. Local development only.
"""

from __future__ import annotations

import re

import psycopg

from hikeall.roles import set_role

ADMIN_EMAIL = "admin@hikeall.local"
_BCRYPT = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def is_bcrypt(value: str) -> bool:
    return bool(_BCRYPT.match(value))


def ensure_admin(conn: psycopg.Connection, password_hash: str) -> str:
    """Creates the admin ("angelegt") or sets its password hash ("aktualisiert"); role is admin."""
    if not is_bcrypt(password_hash):
        raise ValueError("HIKEALL_ADMIN_PASSWORD_HASH ist kein bcrypt-Hash")
    row = conn.execute("select id from auth.users where email = %s", (ADMIN_EMAIL,)).fetchone()
    if row:
        conn.execute(
            "update auth.users set encrypted_password = %s, updated_at = now() where id = %s",
            (password_hash, row[0]),
        )
        set_role(conn, str(row[0]), "admin")
        conn.commit()
        return "aktualisiert"
    uid = conn.execute(
        """
        insert into auth.users (
          instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
          raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
          confirmation_token, recovery_token, email_change_token_new, email_change
        ) values (
          '00000000-0000-0000-0000-000000000000', gen_random_uuid(), 'authenticated',
          'authenticated', %s, %s, now(),
          '{"provider":"email","providers":["email"]}', '{}', now(), now(), '', '', '', ''
        ) returning id
        """,
        (ADMIN_EMAIL, password_hash),
    ).fetchone()[0]
    conn.execute(
        """
        insert into auth.identities (
          provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at
        ) values (
          %s::text, %s, jsonb_build_object('sub', %s::text, 'email', %s::text), 'email', now(), now(),
          now()
        )
        """,
        (uid, uid, uid, ADMIN_EMAIL),
    )
    set_role(conn, str(uid), "admin")
    conn.commit()
    return "angelegt"
