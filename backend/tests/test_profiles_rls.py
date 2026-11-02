import json
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db


def _as(conn, role, uid=None):
    claims = {"sub": str(uid), "role": role} if uid else {"role": role}
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
    conn.execute(f"set local role {role}")


def _user(conn):
    uid = uuid.uuid4()
    conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"{uid}@test.invalid"))
    return uid


def test_signup_creates_user_profile(conn):
    a = _user(conn)
    rows = conn.execute("select role, email from profiles where user_id = %s", (a,)).fetchall()
    assert rows == [("user", f"{a}@test.invalid")]


def test_user_reads_only_own_profile(conn):
    a, _b = _user(conn), _user(conn)
    _as(conn, "authenticated", a)
    assert conn.execute("select count(*) from profiles").fetchone()[0] == 1


def test_user_cannot_change_own_role(conn):
    a = _user(conn)
    _as(conn, "authenticated", a)
    try:
        with conn.transaction():  # savepoint: a privilege error must not abort the outer transaction
            changed = conn.execute("update profiles set role = 'admin' where user_id = %s", (a,)).rowcount
        assert changed == 0
    except psycopg.errors.InsufficientPrivilege:
        pass
    conn.execute("reset role")
    assert conn.execute("select role from profiles where user_id = %s", (a,)).fetchone()[0] == "user"


def test_anon_sees_no_profiles(conn):
    _user(conn)
    _as(conn, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select count(*) from profiles")


def test_backfill_creates_missing_profiles(conn):
    a = _user(conn)
    conn.execute("delete from profiles where user_id = %s", (a,))
    conn.execute("insert into profiles (user_id, email) select id, email from auth.users on conflict do nothing")
    assert conn.execute("select count(*) from profiles where user_id = %s", (a,)).fetchone()[0] == 1
