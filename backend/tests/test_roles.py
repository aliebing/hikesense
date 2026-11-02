import uuid

import pytest

from hikeall.roles import role_of, set_role

pytestmark = pytest.mark.db


def _user(conn):
    uid = uuid.uuid4()
    conn.execute("insert into auth.users (id, email) values (%s, %s)", (uid, f"{uid}@test.invalid"))
    return str(uid)


def test_role_defaults_to_user(conn):
    assert role_of(conn, _user(conn)) == "user"


def test_role_defaults_to_user_without_profile(conn):
    uid = _user(conn)
    conn.execute("delete from profiles where user_id = %s", (uid,))
    assert role_of(conn, uid) == "user"
    assert role_of(conn, "not-a-uuid") == "user"
    assert conn.execute("select 1").fetchone() == (1,)  # connection still usable


def test_set_role_admin(conn):
    uid = _user(conn)
    set_role(conn, uid, "admin")
    assert role_of(conn, uid) == "admin"
    set_role(conn, uid, "user")
    assert role_of(conn, uid) == "user"


def test_set_role_creates_missing_profile(conn):
    uid = _user(conn)
    conn.execute("delete from profiles where user_id = %s", (uid,))
    set_role(conn, uid, "admin")
    assert role_of(conn, uid) == "admin"


def test_default_role_lookup_reads_the_real_database(conn):
    """The production lookup (own connection) sees committed rows; cleanup leaves nothing behind."""
    import os

    from hikeall.api.app import _default_role_lookup
    from types import SimpleNamespace

    url = os.environ.get("SUPABASE_DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    lookup = _default_role_lookup(SimpleNamespace(supabase_db_url=url))  # type: ignore[arg-type]
    admin, plain = _user(conn), _user(conn)
    set_role(conn, admin, "admin")
    conn.commit()
    try:
        assert lookup(admin) == "admin"
        assert lookup(plain) == "user"
    finally:
        conn.rollback()
        conn.execute("delete from auth.users where id in (%s::uuid, %s::uuid)", (admin, plain))
        conn.commit()
    left = conn.execute(
        "select count(*) from profiles where user_id in (%s::uuid, %s::uuid)", (admin, plain)
    ).fetchone()[0]
    assert left == 0


def test_backfill_migration_promotes_admin_email(conn):
    import pathlib

    sql = (pathlib.Path(__file__).parents[2] / "supabase/migrations/20261102000002_admin_role_backfill.sql").read_text()
    conn.execute("delete from auth.users where email = 'admin@hikeall.local'")
    uid = uuid.uuid4()
    conn.execute("insert into auth.users (id, email) values (%s, 'admin@hikeall.local')", (uid,))
    assert role_of(conn, str(uid)) == "user"
    conn.execute(sql)
    conn.execute(sql)  # idempotent
    assert role_of(conn, str(uid)) == "admin"


def test_list_profiles_uses_current_auth_email(conn):
    from hikeall.roles import list_profiles

    uid = _user(conn)
    try:
        conn.execute("update auth.users set email = %s where id = %s::uuid", (f"new-{uid}@test.invalid", uid))
        by_id = {p.user_id: p for p in list_profiles(conn)}
        assert by_id[uid].email == f"new-{uid}@test.invalid"
        assert by_id[uid].role == "user"
    finally:
        conn.rollback()
        conn.execute("delete from auth.users where id = %s::uuid", (uid,))
