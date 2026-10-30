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


def _upload(conn, uid):
    """Store an object under the user's folder and its photos row, as the browser does."""
    _as(conn, "authenticated", uid)
    path = f"{uid}/trail-x/{uuid.uuid4()}.jpg"
    conn.execute("insert into storage.objects (bucket_id, name, owner_id) values ('uploads', %s, %s)", (path, str(uid)))
    pid, owner = conn.execute(
        "insert into photos (source, url, author, license) values ('upload', %s, 'Eigenes Foto', 'privat') returning id, owner",
        (path,),
    ).fetchone()
    return path, pid, owner


def test_bucket_is_private(conn):
    assert conn.execute("select public from storage.buckets where id = 'uploads'").fetchone() == (False,)


def test_owner_sees_own_upload_and_owner_defaults(conn):
    a = _user(conn)
    path, pid, owner = _upload(conn, a)
    assert owner == a
    assert conn.execute("select count(*) from photos where id = %s", (pid,)).fetchone()[0] == 1
    assert conn.execute("select count(*) from storage.objects where name = %s", (path,)).fetchone()[0] == 1
    assert conn.execute("delete from photos where id = %s", (pid,)).rowcount == 1


def test_other_user_cannot_see_upload(conn):
    a, b = _user(conn), _user(conn)
    path, pid, _ = _upload(conn, a)
    _as(conn, "authenticated", b)
    assert conn.execute("select count(*) from photos where id = %s", (pid,)).fetchone()[0] == 0
    assert conn.execute("select count(*) from storage.objects where name = %s", (path,)).fetchone()[0] == 0
    assert conn.execute("delete from photos where id = %s", (pid,)).rowcount == 0
    conn.execute("reset role")
    assert conn.execute("select count(*) from photos where id = %s", (pid,)).fetchone()[0] == 1


def test_anon_cannot_see_upload_but_still_sees_commons(conn):
    a = _user(conn)
    _, pid, _ = _upload(conn, a)
    conn.execute("reset role")
    conn.execute("insert into photos (source, url, author, license) values ('commons', 'https://c.example/x.jpg', 'X', 'CC0')")
    _as(conn, "anon")
    assert conn.execute("select count(*) from photos where id = %s", (pid,)).fetchone()[0] == 0
    assert conn.execute("select count(*) from photos where source = 'commons' and url = 'https://c.example/x.jpg'").fetchone()[0] == 1


def test_cannot_write_into_another_users_folder(conn):
    a, b = _user(conn), _user(conn)
    _as(conn, "authenticated", b)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("insert into storage.objects (bucket_id, name) values ('uploads', %s)", (f"{a}/t/x.jpg",))


def test_cannot_insert_photo_for_another_user_or_as_commons(conn):
    a, b = _user(conn), _user(conn)
    _as(conn, "authenticated", b)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("insert into photos (source, url, author, license, owner) values ('upload', 'p', 'x', 'privat', %s)", (a,))
    conn.rollback()
    b2 = _user(conn)
    _as(conn, "authenticated", b2)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("insert into photos (source, url, author, license) values ('commons', 'p', 'x', 'CC0')")


def test_anon_cannot_insert_or_delete_photos(conn):
    _as(conn, "anon")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("insert into photos (source, url, author, license) values ('upload', 'p', 'x', 'privat')")
