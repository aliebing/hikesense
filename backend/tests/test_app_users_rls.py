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


def test_signup_creates_active_app_user(conn):
    a = _user(conn)
    rows = conn.execute("select status, email from app_users where user_id = %s", (a,)).fetchall()
    assert rows == [("aktiv", f"{a}@test.invalid")]


def test_user_reads_only_own_app_user(conn):
    a, _b = _user(conn), _user(conn)
    _as(conn, "authenticated", a)
    assert conn.execute("select count(*) from app_users").fetchone()[0] == 1


def test_user_cannot_unblock_self(conn):
    a = _user(conn)
    conn.execute("update app_users set status = 'gesperrt', blocked_at = now() where user_id = %s", (a,))
    _as(conn, "authenticated", a)
    try:
        with conn.transaction():  # savepoint: a privilege error must not abort the outer transaction
            changed = conn.execute("update app_users set status = 'aktiv' where user_id = %s", (a,)).rowcount
        assert changed == 0
    except psycopg.errors.InsufficientPrivilege:
        pass
    conn.execute("reset role")
    assert conn.execute("select status from app_users where user_id = %s", (a,)).fetchone()[0] == "gesperrt"


def test_anon_sees_no_app_users(conn):
    _user(conn)
    _as(conn, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select count(*) from app_users")


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_guest_requests_not_reachable_from_clients(conn, role):
    a = _user(conn)
    _as(conn, role, a if role == "authenticated" else None)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select count(*) from guest_requests")


def test_backfill_existing_users(conn):
    missing = conn.execute(
        "select count(*) from auth.users u left join app_users a on a.user_id = u.id where a.user_id is null"
    ).fetchone()[0]
    assert missing == 0


def test_status_check_rejects_unknown_value(conn):
    a = _user(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("update app_users set status = 'admin' where user_id = %s", (a,))
