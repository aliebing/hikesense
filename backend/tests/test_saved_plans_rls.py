import json
import uuid

import psycopg
import pytest

pytestmark = pytest.mark.db


def _as(conn, role, uid=None):
    """Act as `role` for the rest of the (rolled back) transaction, like PostgREST does."""
    claims = {"sub": str(uid), "role": role} if uid else {"role": role}
    conn.execute("select set_config('request.jwt.claims', %s, true)", (json.dumps(claims),))
    conn.execute(f"set local role {role}")


def _reset(conn):
    conn.execute("reset role")


def _user(conn):
    uid = uuid.uuid4()
    conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"{uid}@test.invalid"))
    return uid


def _save(conn, uid, title="Plan"):
    _as(conn, "authenticated", uid)
    row = conn.execute(
        "insert into saved_plans (kind, title, payload) values ('day_hike', %s, %s::jsonb) returning id, user_id",
        (title, json.dumps({"trail_id": "t1"})),
    ).fetchone()
    return row


def test_owner_sees_and_deletes_own_plan(conn):
    a = _user(conn)
    pid, owner = _save(conn, a)
    assert owner == a  # user_id defaults to auth.uid()
    assert conn.execute("select count(*) from saved_plans").fetchone()[0] == 1
    conn.execute("delete from saved_plans where id = %s", (pid,))
    assert conn.execute("select count(*) from saved_plans").fetchone()[0] == 0


def test_other_user_cannot_read_or_delete_plan(conn):
    a, b = _user(conn), _user(conn)
    pid, _ = _save(conn, a)
    _as(conn, "authenticated", b)
    assert conn.execute("select count(*) from saved_plans").fetchone()[0] == 0
    assert conn.execute("delete from saved_plans where id = %s", (pid,)).rowcount == 0
    _reset(conn)
    assert conn.execute("select count(*) from saved_plans where id = %s", (pid,)).fetchone()[0] == 1


def test_cannot_insert_for_another_user(conn):
    a, b = _user(conn), _user(conn)
    _as(conn, "authenticated", b)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            "insert into saved_plans (user_id, kind, title, payload) values (%s, 'multiday', 'x', '{}'::jsonb)", (a,)
        )


def test_kind_is_checked(conn):
    a = _user(conn)
    _as(conn, "authenticated", a)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("insert into saved_plans (kind, title, payload) values ('other', 'x', '{}'::jsonb)")


def test_anon_cannot_read_plans(conn):
    a = _user(conn)
    _save(conn, a)
    _as(conn, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("select count(*) from saved_plans")


def test_authenticated_has_only_select_insert_delete(conn):
    # Supabase default privileges grant everything; a plan is saved or deleted, never edited
    rows = conn.execute(
        "select grantee, privilege_type from information_schema.role_table_grants "
        "where table_name = 'saved_plans' and grantee in ('anon', 'authenticated')"
    ).fetchall()
    assert {r[1] for r in rows if r[0] == "authenticated"} == {"SELECT", "INSERT", "DELETE"}
    assert not [r for r in rows if r[0] == "anon"]
    for priv in ("UPDATE", "TRUNCATE", "REFERENCES", "TRIGGER"):
        sql = "select has_table_privilege('authenticated', 'saved_plans', %s)"
        assert conn.execute(sql, (priv,)).fetchone()[0] is False, priv
