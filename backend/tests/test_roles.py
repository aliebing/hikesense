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
